# Remove Pipeline Module Refactoring Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除 `Pipeline` 類別，將組合邏輯移至 `main.py`，讓 data flow 單向通行。

**Architecture:** `ClipRecorder` 直接持有 `RollingBuffer` 與 `EventLogger` 參考，實作 `FallEventObserver` 介面。`main.py` 負責建立所有元件並執行主迴圈。

**Tech Stack:** Python 3.12+, pytest, ruff

---

## Overview

```
Before:
main.py → Pipeline (god object) → all components

After:
main.py (composition root)
    ├── create components
    ├── wire observers: DelayConfirm → [EventLogger, LineNotifier, ClipRecorder]
    └── run loop: Camera → Detector → RuleEngine → DelayConfirm
```

---

## Task 1: Extend ClipRecorder to be a FallEventObserver

**Files:**
- Modify: `src/events/clip_recorder.py`
- Test: `tests/test_clip_recorder.py`

**Step 1: Write the failing test**

在 `tests/test_clip_recorder.py` 新增測試：

```python
def test_clip_recorder_on_fall_confirmed_saves_clip(tmp_path):
    """ClipRecorder should save clip when fall is confirmed."""
    import time
    import numpy as np
    from src.capture.rolling_buffer import RollingBuffer, FrameData
    from src.events.clip_recorder import ClipRecorder
    from src.events.event_logger import EventLogger
    from src.events.observer import FallEvent

    # Setup
    buffer = RollingBuffer(buffer_seconds=10, fps=15)
    event_time = time.time()

    # Push frames to buffer
    for i in range(30):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = FrameData(timestamp=event_time - 1 + i * 0.033, frame=frame, bbox=None)
        buffer.push(frame_data)

    db_path = str(tmp_path / "test.db")
    event_logger = EventLogger(db_path=db_path)
    recorder = ClipRecorder(
        rolling_buffer=buffer,
        event_logger=event_logger,
        clip_before_sec=0.5,
        clip_after_sec=0.5,
        output_dir=str(tmp_path / "clips"),
        fps=15,
    )

    # Create event and trigger observer
    event = FallEvent(
        event_id="evt_123",
        confirmed_at=event_time,
        last_notified_at=event_time,
        notification_count=1,
    )
    event_logger.on_fall_confirmed(event)  # Create DB record first
    recorder.on_fall_confirmed(event)

    # Verify clip was saved
    clips = list((tmp_path / "clips").glob("*.mp4"))
    assert len(clips) == 1

    # Verify event_logger was updated
    events = event_logger.get_recent_events(limit=1)
    assert events[0]["clip_path"] is not None

    event_logger.close()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_clip_recorder.py::test_clip_recorder_on_fall_confirmed_saves_clip -v
```

Expected: FAIL with `TypeError: ClipRecorder.__init__() got an unexpected keyword argument 'rolling_buffer'`

**Step 3: Update ClipRecorder implementation**

修改 `src/events/clip_recorder.py`：

```python
import logging
from datetime import datetime
from pathlib import Path

import cv2

from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.events.observer import FallEvent, FallEventObserver

logger = logging.getLogger(__name__)


class ClipRecorder(FallEventObserver):
    def __init__(
        self,
        rolling_buffer: RollingBuffer | None = None,
        event_logger: "EventLogger | None" = None,
        clip_before_sec: float = 5.0,
        clip_after_sec: float = 5.0,
        output_dir: str = "data/clips",
        fps: int = 15,
        codec: str = "avc1",
    ):
        self.rolling_buffer = rolling_buffer
        self.event_logger = event_logger
        self.clip_before_sec = clip_before_sec
        self.clip_after_sec = clip_after_sec
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.codec = codec

    def _generate_filename(self, event_id: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{event_id}.mp4"

    def save(self, frames: list[FrameData], event_id: str) -> str | None:
        if not frames:
            return None

        filename = self._generate_filename(event_id)
        output_path = self.output_dir / filename

        first_frame = frames[0].frame
        height, width = first_frame.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        writer = cv2.VideoWriter(str(output_path), fourcc, self.fps, (width, height))

        if not writer.isOpened():
            return None

        try:
            for frame_data in frames:
                writer.write(frame_data.frame)
        finally:
            writer.release()

        return str(output_path)

    def on_fall_confirmed(self, event: FallEvent) -> None:
        if self.rolling_buffer is None:
            logger.warning("ClipRecorder: rolling_buffer not set, skipping clip save")
            return

        frames = self.rolling_buffer.get_clip(
            event_time=event.confirmed_at,
            before_sec=self.clip_before_sec,
            after_sec=self.clip_after_sec,
        )
        if frames:
            clip_path = self.save(frames, event.event_id)
            if clip_path:
                logger.info(f"Clip saved: {clip_path}")
                if self.event_logger is not None:
                    self.event_logger.update_clip_path(event.event_id, clip_path)

    def on_fall_recovered(self, event: FallEvent) -> None:
        pass  # No action needed on recovery
```

**Note:** 需要在檔案頂部加入 `TYPE_CHECKING` import 避免循環依賴：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.events.event_logger import EventLogger
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_clip_recorder.py::test_clip_recorder_on_fall_confirmed_saves_clip -v
```

Expected: PASS

**Step 5: Run all ClipRecorder tests**

```bash
uv run pytest tests/test_clip_recorder.py -v
```

確保舊的 `save()` 測試仍然通過。

**Step 6: Commit**

```bash
git add src/events/clip_recorder.py tests/test_clip_recorder.py
git commit -m "feat(clip_recorder): implement FallEventObserver with RollingBuffer"
```

---

## Task 2: Create run_detection_loop function in main.py

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py` (new file)

**Step 1: Write the failing test**

建立 `tests/test_main.py`：

```python
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from src.analysis.delay_confirm import FallState


def test_process_frame_returns_state():
    """process_frame should return FallState from delay_confirm."""
    from main import process_frame
    from src.capture.rolling_buffer import RollingBuffer
    from src.analysis.delay_confirm import DelayConfirm
    from src.analysis.rule_engine import RuleEngine
    from src.detection.bbox import BBox

    # Mock detector
    detector = MagicMock()
    standing_bbox = BBox(x=100, y=50, width=100, height=200)
    detector.detect.return_value = [standing_bbox]

    rule_engine = RuleEngine(fall_threshold=1.3)
    delay_confirm = DelayConfirm(delay_sec=3.0)
    buffer = RollingBuffer(buffer_seconds=10, fps=15)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    state = process_frame(
        frame=frame,
        current_time=0.0,
        detector=detector,
        rule_engine=rule_engine,
        delay_confirm=delay_confirm,
        rolling_buffer=buffer,
        use_pose=False,
    )

    assert state == FallState.NORMAL
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_main.py::test_process_frame_returns_state -v
```

Expected: FAIL with `ImportError: cannot import name 'process_frame' from 'main'`

**Step 3: Implement process_frame function**

在 `main.py` 中新增函數（暫時保留 Pipeline 匯入，後續移除）：

```python
import logging
import signal
import sys
import time

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.analysis.rule_engine import RuleEngine
from src.capture.camera import Camera
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import load_config
from src.detection.bbox import BBox
from src.detection.detector import Detector, PoseDetector
from src.events.clip_recorder import ClipRecorder
from src.events.event_logger import EventLogger
from src.events.notifier import LineNotifier
from src.lifecycle.cleanup_scheduler import CleanupScheduler

logger = logging.getLogger(__name__)


def process_frame(
    frame: np.ndarray,
    current_time: float,
    detector: Detector | PoseDetector,
    rule_engine: RuleEngine | PoseRuleEngine,
    delay_confirm: DelayConfirm,
    rolling_buffer: RollingBuffer,
    use_pose: bool,
) -> FallState:
    """Process a single frame through the detection pipeline."""
    detections = detector.detect(frame)
    detection = detections[0] if detections else None

    if use_pose:
        is_fallen = rule_engine.is_fallen(detection, timestamp=current_time)
        bbox_tuple = None
    else:
        is_fallen = rule_engine.is_fallen(detection)
        bbox_tuple = None
        if detection and isinstance(detection, BBox):
            bbox_tuple = (detection.x, detection.y, detection.width, detection.height)

    frame_data = FrameData(timestamp=current_time, frame=frame.copy(), bbox=bbox_tuple)
    rolling_buffer.push(frame_data)

    return delay_confirm.update(is_fallen=is_fallen, current_time=current_time)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_main.py::test_process_frame_returns_state -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(main): add process_frame function for frame processing"
```

---

## Task 3: Refactor main() to use composition root pattern

**Files:**
- Modify: `main.py`

**Step 1: Rewrite main() function**

替換 `main.py` 的 `main()` 函數：

```python
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()
    use_pose = config.detection.use_pose

    # === Component Creation ===
    camera = Camera(
        source=config.camera.source,
        fps=config.camera.fps,
        resolution=(config.camera.resolution[0], config.camera.resolution[1]),
    )

    if use_pose:
        detector: Detector | PoseDetector = PoseDetector(
            model_path=config.detection.pose_model,
            confidence=config.detection.confidence,
        )
        rule_engine: RuleEngine | PoseRuleEngine = PoseRuleEngine(
            torso_angle_threshold=config.analysis.fall_threshold,
            enable_smoothing=config.detection.enable_smoothing,
            smoothing_min_cutoff=config.detection.smoothing_min_cutoff,
            smoothing_beta=config.detection.smoothing_beta,
        )
    else:
        detector = Detector(
            model_path=config.detection.model,
            confidence=config.detection.confidence,
            classes=config.detection.classes,
        )
        rule_engine = RuleEngine(fall_threshold=config.analysis.fall_threshold)

    rolling_buffer = RollingBuffer(
        buffer_seconds=config.recording.buffer_seconds,
        fps=config.camera.fps,
    )

    event_logger = EventLogger(db_path="data/fds.db")

    clip_recorder = ClipRecorder(
        rolling_buffer=rolling_buffer,
        event_logger=event_logger,
        clip_before_sec=config.recording.clip_before_sec,
        clip_after_sec=config.recording.clip_after_sec,
        fps=config.camera.fps,
    )

    notifier = LineNotifier(
        channel_access_token=config.notification.line_channel_access_token,
        user_id=config.notification.line_user_id,
        enabled=config.notification.enabled,
    )

    delay_confirm = DelayConfirm(
        delay_sec=config.analysis.delay_sec,
        same_event_window=config.analysis.same_event_window,
        re_notify_interval=config.analysis.re_notify_interval,
    )

    # === Wire Observers ===
    delay_confirm.add_observer(event_logger)
    delay_confirm.add_observer(notifier)
    delay_confirm.add_observer(clip_recorder)

    # === Lifecycle ===
    cleanup_scheduler = CleanupScheduler(config)
    cleanup_scheduler.start()

    def signal_handler(_signum: int, _frame: object) -> None:
        logger.info("收到終止訊號，正在關閉...")
        cleanup_scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # === Main Loop ===
    mode = "Pose" if use_pose else "BBox"
    logger.info(f"Starting fall detection (mode: {mode})...")
    if use_pose and config.detection.enable_smoothing:
        logger.info("Keypoint smoothing: enabled")

    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue

            current_time = time.time()
            state = process_frame(
                frame=frame,
                current_time=current_time,
                detector=detector,
                rule_engine=rule_engine,
                delay_confirm=delay_confirm,
                rolling_buffer=rolling_buffer,
                use_pose=use_pose,
            )

            if state == FallState.CONFIRMED:
                logger.warning("Fall confirmed!")

    except KeyboardInterrupt:
        logger.info("Stopping detection...")
    finally:
        camera.release()
        event_logger.close()
        cleanup_scheduler.stop()


if __name__ == "__main__":
    main()
```

**Step 2: Remove old Pipeline import**

確保移除舊的 `from src.core.pipeline import Pipeline`。

**Step 3: Run ruff to check code quality**

```bash
uv run ruff check main.py
uv run ruff format main.py
```

**Step 4: Commit**

```bash
git add main.py
git commit -m "refactor(main): replace Pipeline with composition root pattern"
```

---

## Task 4: Delete Pipeline module and update tests

**Files:**
- Delete: `src/core/pipeline.py`
- Delete: `tests/test_pipeline.py`
- Delete: `tests/test_pipeline_pose.py`
- Modify: `tests/integration/test_full_pipeline.py`
- Modify: `tests/integration/test_pipeline_pose_integration.py`

**Step 1: Delete Pipeline module**

```bash
rm src/core/pipeline.py
```

**Step 2: Delete Pipeline-specific tests**

```bash
rm tests/test_pipeline.py
rm tests/test_pipeline_pose.py
```

**Step 3: Rewrite integration test**

重寫 `tests/integration/test_full_pipeline.py`：

```python
"""Integration tests for full detection flow."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.capture.rolling_buffer import RollingBuffer
from src.detection.bbox import BBox
from main import process_frame


class TestFullDetectionFlow:
    def test_fall_detection_flow(self):
        """Test complete flow: standing -> fall -> confirm -> recover"""
        # Setup
        detector = MagicMock()
        rule_engine = RuleEngine(fall_threshold=1.3)
        delay_confirm = DelayConfirm(delay_sec=0.1, same_event_window=60.0, re_notify_interval=120.0)
        buffer = RollingBuffer(buffer_seconds=2, fps=15)

        standing_bbox = BBox(x=100, y=50, width=100, height=200)
        fallen_bbox = BBox(x=100, y=50, width=200, height=100)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Standing - NORMAL
        detector.detect.return_value = [standing_bbox]
        state = process_frame(frame, 0.0, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.NORMAL

        # Fallen - SUSPECTED
        detector.detect.return_value = [fallen_bbox]
        state = process_frame(frame, 1.0, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.SUSPECTED

        # Still fallen after delay - CONFIRMED
        state = process_frame(frame, 1.2, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.CONFIRMED

        # Standing again - NORMAL
        detector.detect.return_value = [standing_bbox]
        state = process_frame(frame, 2.0, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.NORMAL
```

**Step 4: Rewrite Pose integration test**

重寫 `tests/integration/test_pipeline_pose_integration.py`：

```python
"""Integration tests for Pose mode detection flow."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.capture.rolling_buffer import RollingBuffer
from src.detection.skeleton import Skeleton, Keypoint
from main import process_frame


def create_standing_skeleton() -> Skeleton:
    """Create a standing person skeleton (torso angle ~10 degrees)."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.NOSE] = [320, 50, 0.9]
    keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
    keypoints[Keypoint.LEFT_ANKLE] = [290, 400, 0.9]
    keypoints[Keypoint.RIGHT_ANKLE] = [350, 400, 0.9]
    return Skeleton(keypoints=keypoints)


def create_fallen_skeleton() -> Skeleton:
    """Create a fallen person skeleton (torso angle ~85 degrees)."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.NOSE] = [100, 400, 0.9]
    keypoints[Keypoint.LEFT_SHOULDER] = [170, 390, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [170, 410, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [350, 390, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 410, 0.9]
    keypoints[Keypoint.LEFT_ANKLE] = [500, 390, 0.9]
    keypoints[Keypoint.RIGHT_ANKLE] = [500, 410, 0.9]
    return Skeleton(keypoints=keypoints)


class TestPoseModeDetectionFlow:
    def test_pose_fall_detection(self):
        """Test Pose mode: standing -> fall -> confirm"""
        detector = MagicMock()
        rule_engine = PoseRuleEngine(torso_angle_threshold=60.0, enable_smoothing=False)
        delay_confirm = DelayConfirm(delay_sec=0.1)
        buffer = RollingBuffer(buffer_seconds=2, fps=15)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Standing
        detector.detect.return_value = [create_standing_skeleton()]
        state = process_frame(frame, 0.0, detector, rule_engine, delay_confirm, buffer, True)
        assert state == FallState.NORMAL

        # Fallen
        detector.detect.return_value = [create_fallen_skeleton()]
        state = process_frame(frame, 1.0, detector, rule_engine, delay_confirm, buffer, True)
        assert state == FallState.SUSPECTED

        state = process_frame(frame, 1.2, detector, rule_engine, delay_confirm, buffer, True)
        assert state == FallState.CONFIRMED

    def test_pose_smoothing_reduces_jitter(self):
        """Smoothing should reduce false positives from noisy keypoints."""
        detector = MagicMock()
        rule_engine = PoseRuleEngine(
            torso_angle_threshold=60.0,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        )
        delay_confirm = DelayConfirm(delay_sec=3.0)
        buffer = RollingBuffer(buffer_seconds=2, fps=15)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        np.random.seed(42)
        base_skeleton = create_standing_skeleton()
        states = []

        for i in range(30):
            noisy_keypoints = base_skeleton.keypoints.copy()
            noisy_keypoints[:, 0] += np.random.randn(17) * 5
            noisy_keypoints[:, 1] += np.random.randn(17) * 5
            noisy_skeleton = Skeleton(keypoints=noisy_keypoints)

            detector.detect.return_value = [noisy_skeleton]
            state = process_frame(frame, i * 0.033, detector, rule_engine, delay_confirm, buffer, True)
            states.append(state)

        assert all(s == FallState.NORMAL for s in states)
```

**Step 5: Run all tests**

```bash
uv run pytest -v
```

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove Pipeline module, update integration tests"
```

---

## Task 5: Update CLAUDE.md architecture documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update Pipeline Flow section**

將 CLAUDE.md 中的 Pipeline Flow 區塊改為：

```markdown
### Detection Flow (main.py)

```
Camera → Detector → RuleEngine → DelayConfirm → Observers
           ↓            ↓              ↓              ↓
      YOLO detect   is_fallen?   State Machine    EventLogger (SQLite)
      BBox/Skeleton                               LineNotifier (LINE API)
                                                  ClipRecorder (影片錄製)
```

**關鍵流程:**

1. `Camera.read()` 擷取影像幀
2. `Detector.detect()` 執行 YOLO 推論 → 回傳 `BBox` 或 `Skeleton`
3. `RuleEngine.is_fallen()` / `PoseRuleEngine.is_fallen()` 套用規則
4. `DelayConfirm.update()` 狀態機判斷（3 秒延遲確認）
5. 狀態變化時觸發 Observer Pattern 通知所有訂閱者
6. `ClipRecorder` 從 `RollingBuffer` 取得前後影片並儲存
```

**Step 2: Update Module Dependencies**

```markdown
### Module Dependencies

```
capture ← detection ← analysis ← events ← lifecycle
                                   ↑
                              main.py (composition root)
```

- `main.py` 是 composition root，負責建立與組裝所有元件
- 各模組不互相依賴，由 `main.py` 注入依賴
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for pipeline removal"
```

---

## Task 6: Final cleanup and verification

**Step 1: Remove any remaining Pipeline references**

```bash
uv run ruff check . --fix
uv run ruff format .
```

**Step 2: Search for stale Pipeline references**

```bash
grep -r "Pipeline" --include="*.py" .
grep -r "pipeline" --include="*.py" . | grep -v "test_pipeline_pose_integration"
```

移除任何殘留的 import 或 reference。

**Step 3: Run full test suite**

```bash
uv run pytest -v --cov=src --cov-report=term-missing
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: cleanup stale Pipeline references"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | ClipRecorder implements FallEventObserver | `clip_recorder.py`, `test_clip_recorder.py` |
| 2 | Add process_frame function | `main.py`, `test_main.py` |
| 3 | Refactor main() with composition root | `main.py` |
| 4 | Delete Pipeline, update tests | `pipeline.py` (deleted), integration tests |
| 5 | Update CLAUDE.md | `CLAUDE.md` |
| 6 | Final cleanup | Various |

**Total commits: 6**
