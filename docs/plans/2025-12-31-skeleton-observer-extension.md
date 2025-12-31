# Skeleton Observer Extension Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 擴展 Observer Pattern，在 SUSPECTED 階段記錄事件，於 outcome 確定後（CONFIRMED/CLEARED）提取骨架，收集含標籤的訓練資料。

**Architecture:** 新增 `on_fall_suspected()` 和 `on_suspicion_cleared()` 事件，建立 `SkeletonCollector` Observer 處理非同步骨架提取。使用 `concurrent.futures.ThreadPoolExecutor` 避免阻塞主迴圈。每個事件只提取一次骨架，在 outcome 確定時執行。

**Tech Stack:** Python 3.12+, concurrent.futures, existing SkeletonExtractor

---

## 設計決策

### 1. 提取時機
- **SUSPECTED**: 只記錄事件，不提取（outcome 尚未確定）
- **CONFIRMED/CLEARED**: 提取骨架並標記 outcome

### 2. 時間範圍策略
```
保證 t-n (事件前): buffer 裡一定有 ✅
t+n (事件後): 有多少拿多少 ⚠️

實際取得:
  CLEARED (1秒後): t-5 ~ t+1
  CONFIRMED (3秒後): t-5 ~ t+3
```

### 3. 單一事件 = 單一骨架檔案
```
SUSPECTED → 記錄（不提取）
    │
    ├─→ CONFIRMED → 提取一次 → sus_xxx_confirmed.json
    │
    └─→ CLEARED → 提取一次 → sus_xxx_cleared.json
```

---

## 現有流程檢核

```
現有狀態轉換與通知：
  NORMAL → SUSPECTED        : 無通知 ❌
  SUSPECTED → NORMAL        : 無通知 ❌ (只呼叫 _reset())
  SUSPECTED → CONFIRMED     : on_fall_confirmed() ✅
  CONFIRMED → NORMAL        : on_fall_recovered() ✅
```

```
擴展後：
  NORMAL → SUSPECTED        : on_fall_suspected() ✅ 新增（記錄事件）
  SUSPECTED → NORMAL        : on_suspicion_cleared() ✅ 新增（提取骨架）
  SUSPECTED → CONFIRMED     : on_fall_confirmed() ✅ 保持 + 更新 suspected outcome
  CONFIRMED → NORMAL        : on_fall_recovered() ✅ 保持不變
```

---

## Task 1: 擴展 FallEvent 資料結構

**Files:**
- Modify: `src/events/observer.py`
- Test: `tests/test_observer.py` (新建)

**Step 1: Write the failing test**

```python
# tests/test_observer.py
from src.events.observer import FallEvent, SuspectedEvent


class TestSuspectedEvent:
    def test_suspected_event_creation(self):
        event = SuspectedEvent(
            suspected_id="sus_1234567890",
            suspected_at=1234567890.0,
        )
        assert event.suspected_id == "sus_1234567890"
        assert event.suspected_at == 1234567890.0
        assert event.outcome == "pending"

    def test_suspected_event_with_outcome(self):
        event = SuspectedEvent(
            suspected_id="sus_1234567890",
            suspected_at=1234567890.0,
            outcome="confirmed",
            outcome_at=1234567893.0,
        )
        assert event.outcome == "confirmed"
        assert event.outcome_at == 1234567893.0
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_observer.py -v
```
Expected: FAIL with "cannot import name 'SuspectedEvent'"

**Step 3: Write minimal implementation**

```python
# src/events/observer.py
from dataclasses import dataclass
from typing import Protocol, Literal


@dataclass
class FallEvent:
    event_id: str
    confirmed_at: float
    last_notified_at: float
    notification_count: int


@dataclass
class SuspectedEvent:
    """疑似跌倒事件，用於骨架收集"""
    suspected_id: str
    suspected_at: float
    outcome: Literal["pending", "confirmed", "cleared"] = "pending"
    outcome_at: float | None = None


class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...


class SuspectedEventObserver(Protocol):
    """擴展 Observer，支援 SUSPECTED 階段通知"""
    def on_fall_suspected(self, event: SuspectedEvent) -> None: ...
    def on_suspicion_cleared(self, event: SuspectedEvent) -> None: ...
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_observer.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/events/observer.py tests/test_observer.py
git commit -m "feat(observer): add SuspectedEvent and SuspectedEventObserver protocol"
```

---

## Task 2: 擴展 DelayConfirm 狀態機

**Files:**
- Modify: `src/analysis/delay_confirm.py`
- Modify: `tests/test_delay_confirm.py`

**Step 1: Write the failing test**

```python
# tests/test_delay_confirm.py (新增測試類別)
from src.events.observer import SuspectedEvent


class MockSuspectedObserver:
    def __init__(self):
        self.suspected_events: list[SuspectedEvent] = []
        self.cleared_events: list[SuspectedEvent] = []

    def on_fall_suspected(self, event: SuspectedEvent) -> None:
        self.suspected_events.append(event)

    def on_suspicion_cleared(self, event: SuspectedEvent) -> None:
        self.cleared_events.append(event)


class TestDelayConfirmSuspectedObservers:
    def test_suspected_observer_notified_on_suspected(self):
        observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_suspected_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)

        assert len(observer.suspected_events) == 1
        assert observer.suspected_events[0].suspected_id.startswith("sus_")

    def test_suspected_observer_notified_on_cleared(self):
        observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_suspected_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=False, current_time=1.0)  # 未達 3 秒，疑似取消

        assert len(observer.cleared_events) == 1
        assert observer.cleared_events[0].outcome == "cleared"

    def test_suspected_event_outcome_updated_on_confirmed(self):
        observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_suspected_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)  # 確認跌倒

        # suspected 事件的 outcome 應該被更新為 confirmed
        assert observer.suspected_events[0].outcome == "confirmed"

    def test_existing_observers_still_work(self):
        """確保原有 observer 不受影響"""
        fall_observer = MockObserver()
        suspected_observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_observer(fall_observer)
        dc.add_suspected_observer(suspected_observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)

        assert fall_observer.confirm_count == 1
        assert len(suspected_observer.suspected_events) == 1
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_delay_confirm.py::TestDelayConfirmSuspectedObservers -v
```
Expected: FAIL with "has no attribute 'add_suspected_observer'"

**Step 3: Write minimal implementation**

```python
# src/analysis/delay_confirm.py
from enum import Enum

from src.events.observer import FallEvent, FallEventObserver, SuspectedEvent, SuspectedEventObserver


class FallState(Enum):
    NORMAL = "normal"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class DelayConfirm:
    def __init__(
        self,
        delay_sec: float = 3.0,
        same_event_window: float = 60.0,
        re_notify_interval: float = 120.0,
    ):
        self.state = FallState.NORMAL
        self.delay_sec = delay_sec
        self.same_event_window = same_event_window
        self.re_notify_interval = re_notify_interval

        self.suspected_since: float | None = None
        self.current_event: FallEvent | None = None
        self.current_suspected: SuspectedEvent | None = None  # 新增
        self.observers: list[FallEventObserver] = []
        self.suspected_observers: list[SuspectedEventObserver] = []  # 新增

    def add_observer(self, observer: FallEventObserver) -> None:
        self.observers.append(observer)

    def add_suspected_observer(self, observer: SuspectedEventObserver) -> None:  # 新增
        self.suspected_observers.append(observer)

    def update(self, is_fallen: bool, current_time: float) -> FallState:
        match self.state:
            case FallState.NORMAL:
                if is_fallen:
                    self.state = FallState.SUSPECTED
                    self.suspected_since = current_time
                    self._notify_suspected(current_time)  # 新增

            case FallState.SUSPECTED:
                if not is_fallen:
                    self._clear_suspicion(current_time)  # 修改
                elif current_time - self.suspected_since >= self.delay_sec:
                    self._confirm_fall(current_time)

            case FallState.CONFIRMED:
                if not is_fallen:
                    self._recover(current_time)
                else:
                    self._check_re_notify(current_time)

        return self.state

    def _notify_suspected(self, current_time: float) -> None:  # 新增
        self.current_suspected = SuspectedEvent(
            suspected_id=f"sus_{int(current_time)}",
            suspected_at=current_time,
            outcome="pending",
        )
        for observer in self.suspected_observers:
            observer.on_fall_suspected(self.current_suspected)

    def _clear_suspicion(self, current_time: float) -> None:  # 新增（原 _reset 擴展）
        if self.current_suspected:
            self.current_suspected.outcome = "cleared"
            self.current_suspected.outcome_at = current_time
            for observer in self.suspected_observers:
                observer.on_suspicion_cleared(self.current_suspected)
        self._reset()

    def _confirm_fall(self, current_time: float) -> None:
        # 更新 suspected 事件的 outcome
        if self.current_suspected:
            self.current_suspected.outcome = "confirmed"
            self.current_suspected.outcome_at = current_time

        if (
            self.current_event
            and current_time - self.current_event.confirmed_at < self.same_event_window
        ):
            self.state = FallState.CONFIRMED
            return

        self.state = FallState.CONFIRMED
        self.current_event = FallEvent(
            event_id=f"evt_{int(current_time)}",
            confirmed_at=current_time,
            last_notified_at=current_time,
            notification_count=1,
        )
        for observer in self.observers:
            observer.on_fall_confirmed(self.current_event)

    def _check_re_notify(self, current_time: float) -> None:
        if not self.current_event:
            return
        if current_time - self.current_event.last_notified_at >= self.re_notify_interval:
            self.current_event.last_notified_at = current_time
            self.current_event.notification_count += 1
            for observer in self.observers:
                observer.on_fall_confirmed(self.current_event)

    def _recover(self, current_time: float) -> None:
        self.state = FallState.NORMAL
        if self.current_event:
            for observer in self.observers:
                observer.on_fall_recovered(self.current_event)
        self.suspected_since = None
        self.current_suspected = None  # 新增

    def _reset(self) -> None:
        self.state = FallState.NORMAL
        self.suspected_since = None
        self.current_suspected = None  # 新增
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_delay_confirm.py -v
```
Expected: ALL PASS (包含原有測試)

**Step 5: Commit**

```bash
git add src/analysis/delay_confirm.py tests/test_delay_confirm.py
git commit -m "feat(delay_confirm): add suspected event notifications"
```

---

## Task 3: 新增 SkeletonExtractor.extract_from_frames() 方法

**Files:**
- Modify: `src/lifecycle/skeleton_extractor.py`
- Modify: `tests/lifecycle/test_skeleton_extractor.py`

**Step 1: Write the failing test**

```python
# tests/lifecycle/test_skeleton_extractor.py (新增)
import numpy as np
from src.capture.rolling_buffer import FrameData


class TestExtractFromFrames:
    def test_extract_from_frames_returns_sequence(self, extractor):
        # 建立模擬 FrameData
        frames = [
            FrameData(
                timestamp=i * 0.066,  # 15fps
                frame=np.zeros((480, 640, 3), dtype=np.uint8),
                bbox=None,
            )
            for i in range(10)
        ]

        result = extractor.extract_from_frames(
            frames=frames,
            event_id="test_evt",
            fps=15.0,
        )

        assert result is not None
        assert result.metadata.event_id == "test_evt"
        assert result.keypoint_format == "coco17"

    def test_extract_from_frames_empty_list(self, extractor):
        result = extractor.extract_from_frames(
            frames=[],
            event_id="empty_evt",
            fps=15.0,
        )

        assert result.sequence == []
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/lifecycle/test_skeleton_extractor.py::TestExtractFromFrames -v
```
Expected: FAIL with "has no attribute 'extract_from_frames'"

**Step 3: Write minimal implementation**

在 `src/lifecycle/skeleton_extractor.py` 的 `SkeletonExtractor` class 中新增：

```python
from src.capture.rolling_buffer import FrameData

def extract_from_frames(
    self,
    frames: list[FrameData],
    event_id: str,
    fps: float = 15.0,
) -> SkeletonSequence:
    """從 FrameData 列表提取骨架序列

    Args:
        frames: RollingBuffer.get_clip() 返回的 FrameData 列表
        event_id: 事件 ID
        fps: 影片幀率

    Returns:
        SkeletonSequence 實例
    """
    if not frames:
        return SkeletonSequence(
            metadata=SkeletonMetadata(
                event_id=event_id,
                timestamp=datetime.now().isoformat(),
                source_video="memory",
                duration_sec=0,
                fps=int(fps),
                total_frames=0,
                extractor=ExtractorMetadata(
                    engine="yolov8", model=self.model_path, version="8.0.0"
                ),
            ),
            keypoint_format="coco17",
            sequence=[],
            version="1.0",
        )

    duration_sec = (frames[-1].timestamp - frames[0].timestamp) if len(frames) > 1 else 0
    first_frame = frames[0].frame
    frame_shape = first_frame.shape[:2]  # (height, width)

    metadata = SkeletonMetadata(
        event_id=event_id,
        timestamp=datetime.now().isoformat(),
        source_video="memory",
        duration_sec=duration_sec,
        fps=int(fps),
        total_frames=len(frames),
        extractor=ExtractorMetadata(
            engine="yolov8", model=self.model_path, version="8.0.0"
        ),
    )

    sequence = []
    for idx, frame_data in enumerate(frames):
        skeletons = self.detector.detect(frame_data.frame)
        if skeletons:
            skeleton_frame = self._skeleton_to_frame(
                skeletons[0], idx, frame_data.timestamp, frame_shape
            )
            sequence.append(skeleton_frame)

    return SkeletonSequence(
        metadata=metadata,
        keypoint_format="coco17",
        sequence=sequence,
        version="1.0",
    )
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/lifecycle/test_skeleton_extractor.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/lifecycle/skeleton_extractor.py tests/lifecycle/test_skeleton_extractor.py
git commit -m "feat(skeleton_extractor): add extract_from_frames method"
```

---

## Task 4: 建立 SkeletonCollector Observer

**Files:**
- Create: `src/lifecycle/skeleton_collector.py`
- Create: `tests/lifecycle/test_skeleton_collector.py`

**Step 1: Write the failing test**

```python
# tests/lifecycle/test_skeleton_collector.py
import numpy as np
from unittest.mock import MagicMock, patch

from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.events.observer import SuspectedEvent
from src.lifecycle.skeleton_collector import SkeletonCollector


class TestSkeletonCollector:
    def test_on_fall_suspected_records_event(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=True,
        )

        event = SuspectedEvent(
            suspected_id="sus_123",
            suspected_at=100.0,
        )

        collector.on_fall_suspected(event)

        # 只記錄，不提取
        assert "sus_123" in collector.pending_events
        assert collector.extraction_count == 0

    def test_on_suspicion_cleared_extracts_skeleton(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        # 預先填入一些 frames
        for i in range(30):
            buffer.push(FrameData(
                timestamp=i * 0.066,
                frame=np.zeros((480, 640, 3), dtype=np.uint8),
                bbox=None,
            ))

        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=True,
        )

        event = SuspectedEvent(
            suspected_id="sus_123",
            suspected_at=1.0,
            outcome="cleared",
            outcome_at=2.0,
        )

        collector.on_fall_suspected(event)
        collector.on_suspicion_cleared(event)

        # 事件已處理，從 pending 移除
        assert "sus_123" not in collector.pending_events

    def test_disabled_collector_does_nothing(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=False,  # 停用
        )

        event = SuspectedEvent(
            suspected_id="sus_123",
            suspected_at=100.0,
        )

        collector.on_fall_suspected(event)

        assert "sus_123" not in collector.pending_events
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/lifecycle/test_skeleton_collector.py -v
```
Expected: FAIL with "No module named 'src.lifecycle.skeleton_collector'"

**Step 3: Write minimal implementation**

```python
# src/lifecycle/skeleton_collector.py
"""
骨架收集器

訂閱 SUSPECTED 事件，在 outcome 確定後非同步提取骨架並儲存。
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.events.observer import SuspectedEvent
from src.lifecycle.skeleton_extractor import SkeletonExtractor

logger = logging.getLogger(__name__)


class SkeletonCollector:
    """骨架收集器 - SuspectedEventObserver 實作

    在 SUSPECTED 事件觸發時記錄，並在事件結束（confirmed/cleared）時
    提取骨架並儲存，包含 outcome 標籤。

    設計原則:
    - SUSPECTED: 只記錄事件，不提取
    - CONFIRMED/CLEARED: 提取骨架，每個事件只提取一次
    - 保證 t-n: buffer 中一定有事件前的資料
    - t+n: 有多少拿多少
    """

    def __init__(
        self,
        rolling_buffer: RollingBuffer,
        output_dir: str = "data/skeletons",
        enabled: bool = True,
        max_workers: int = 2,
        clip_before_sec: float = 5.0,
        clip_after_sec: float = 5.0,
        fps: float = 15.0,
    ):
        self.rolling_buffer = rolling_buffer
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self.clip_before_sec = clip_before_sec
        self.clip_after_sec = clip_after_sec
        self.fps = fps

        self.pending_events: dict[str, SuspectedEvent] = {}
        self.extraction_count = 0
        self.executor = ThreadPoolExecutor(max_workers=max_workers) if enabled else None
        self.extractor = SkeletonExtractor() if enabled else None

    def on_fall_suspected(self, event: SuspectedEvent) -> None:
        """NORMAL → SUSPECTED 時觸發

        只記錄事件，不提取骨架。等待 outcome 確定。
        """
        if not self.enabled:
            return

        logger.info(f"Suspected event recorded: {event.suspected_id}")
        self.pending_events[event.suspected_id] = event

    def on_suspicion_cleared(self, event: SuspectedEvent) -> None:
        """SUSPECTED → NORMAL 時觸發（未確認跌倒）

        提取骨架並標記為 cleared（負樣本）。
        """
        if not self.enabled:
            return

        if event.suspected_id not in self.pending_events:
            return

        logger.info(f"Suspicion cleared: {event.suspected_id}, extracting skeleton...")
        self._extract_and_save_async(event)
        del self.pending_events[event.suspected_id]

    def on_fall_confirmed_update(self, event: SuspectedEvent) -> None:
        """SUSPECTED → CONFIRMED 時由 Pipeline 呼叫

        提取骨架並標記為 confirmed（正樣本）。
        """
        if not self.enabled:
            return

        if event.suspected_id not in self.pending_events:
            return

        logger.info(f"Fall confirmed: {event.suspected_id}, extracting skeleton...")
        self._extract_and_save_async(event)
        del self.pending_events[event.suspected_id]

    def _extract_and_save_async(self, event: SuspectedEvent) -> None:
        """非同步提取並儲存骨架"""
        # 立即從 buffer 取得 frames（避免被覆蓋）
        frames = self.rolling_buffer.get_clip(
            event_time=event.suspected_at,
            before_sec=self.clip_before_sec,
            after_sec=self.clip_after_sec,
        )

        if not frames:
            logger.warning(f"No frames available for {event.suspected_id}")
            return

        self.extraction_count += 1

        # 提交到背景執行緒
        self.executor.submit(self._save_skeleton, event, list(frames))

    def _save_skeleton(self, event: SuspectedEvent, frames: list[FrameData]) -> None:
        """儲存骨架（在背景執行緒中執行）"""
        try:
            sequence = self.extractor.extract_from_frames(
                frames=frames,
                event_id=event.suspected_id,
                fps=self.fps,
            )

            # 檔名包含 outcome 標籤
            filename = f"{event.suspected_id}_{event.outcome}.json"
            output_path = self.output_dir / filename
            sequence.to_json(output_path)

            logger.info(f"Skeleton saved: {output_path} (outcome: {event.outcome})")
        except Exception as e:
            logger.error(f"Failed to save skeleton for {event.suspected_id}: {e}")

    def shutdown(self) -> None:
        """關閉執行緒池"""
        if self.executor:
            self.executor.shutdown(wait=True)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/lifecycle/test_skeleton_collector.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/lifecycle/skeleton_collector.py tests/lifecycle/test_skeleton_collector.py
git commit -m "feat(lifecycle): add SkeletonCollector for async skeleton extraction"
```

---

## Task 5: 更新設定檔結構

**Files:**
- Modify: `src/core/config.py`
- Modify: `config/settings.yaml`

**Step 1: Update config dataclass**

```python
# src/core/config.py - 修改 LifecycleConfig

@dataclass
class LifecycleConfig:
    clip_retention_days: int
    skeleton_retention_days: int
    cleanup_enabled: bool = True
    cleanup_schedule_hours: int = 24
    auto_skeleton_extract: bool = False  # 新增：自動提取骨架
    skeleton_output_dir: str = "data/skeletons"  # 新增
```

**Step 2: Update settings.yaml**

```yaml
# config/settings.yaml

lifecycle:
  clip_retention_days: 7
  skeleton_retention_days: 30
  cleanup_enabled: true
  cleanup_schedule_hours: 24
  auto_skeleton_extract: true   # 新增：事件發生時自動提取骨架
  skeleton_output_dir: "data/skeletons"  # 新增

cloud_sync:
  enabled: true
  gcs_bucket: "${GCS_BUCKET_NAME}"
  upload_on_extract: false
  retry_attempts: 3
  retry_delay_seconds: 5
```

**Step 3: Run existing config tests**

```bash
uv run pytest tests/ -k config -v
```
Expected: PASS

**Step 4: Commit**

```bash
git add src/core/config.py config/settings.yaml
git commit -m "feat(config): add auto_skeleton_extract option"
```

---

## Task 6: 整合至 Pipeline

**Files:**
- Modify: `src/core/pipeline.py`

**Step 1: Update Pipeline to register SkeletonCollector**

```python
# src/core/pipeline.py (修改)

from src.lifecycle.skeleton_collector import SkeletonCollector

class Pipeline:
    def __init__(self, config: Config, db_path: str = "data/fds.db"):
        # ... 現有初始化 ...

        # 新增：骨架收集器
        self.skeleton_collector: SkeletonCollector | None = None
        if config.lifecycle.auto_skeleton_extract:
            self.skeleton_collector = SkeletonCollector(
                rolling_buffer=self.rolling_buffer,
                output_dir=config.lifecycle.skeleton_output_dir,
                enabled=True,
                clip_before_sec=config.recording.clip_before_sec,
                clip_after_sec=config.recording.clip_after_sec,
                fps=config.camera.fps,
            )

        # 註冊 observers（保持原有邏輯）
        self.delay_confirm.add_observer(self.event_logger)
        self.delay_confirm.add_observer(self.notifier)
        self.delay_confirm.add_observer(self)

        # 新增：註冊 suspected observer
        if self.skeleton_collector:
            self.delay_confirm.add_suspected_observer(self.skeleton_collector)

    def on_fall_confirmed(self, event: FallEvent) -> None:
        # 新增：通知 skeleton_collector 更新 outcome
        if self.skeleton_collector and self.delay_confirm.current_suspected:
            self.skeleton_collector.on_fall_confirmed_update(
                self.delay_confirm.current_suspected
            )

        # 現有邏輯保持不變
        frames = self.rolling_buffer.get_clip(
            event_time=event.confirmed_at,
            before_sec=self.config.recording.clip_before_sec,
            after_sec=self.config.recording.clip_after_sec,
        )
        if frames:
            clip_path = self.clip_recorder.save(frames, event.event_id)
            if clip_path:
                self.event_logger.update_clip_path(event.event_id, clip_path)
                logger.info(f"Clip saved: {clip_path}")

    # on_fall_recovered 保持不變

    def run(self) -> None:
        logger.info("Starting fall detection pipeline...")
        try:
            while True:
                frame = self.camera.read()
                if frame is None:
                    continue

                current_time = time.time()
                state = self.process_frame(frame, current_time)

                if state == FallState.CONFIRMED:
                    logger.warning("Fall confirmed!")

        except KeyboardInterrupt:
            logger.info("Stopping pipeline...")
        finally:
            self.camera.release()
            self.event_logger.close()
            # 新增：關閉骨架收集器
            if self.skeleton_collector:
                self.skeleton_collector.shutdown()
```

**Step 2: Run full test suite**

```bash
uv run pytest -v
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add src/core/pipeline.py
git commit -m "feat(pipeline): integrate SkeletonCollector for auto skeleton extraction"
```

---

## Task 7: 更新 CLAUDE.md 文件

**Files:**
- Modify: `CLAUDE.md`

**Step 1: 在 Lifecycle Module 段落後新增說明**

```markdown
### Skeleton Collection (src/lifecycle/skeleton_collector.py)

自動骨架收集，訂閱 SUSPECTED 事件，於 outcome 確定後提取：

**事件流程:**
```
SUSPECTED → 記錄事件（不提取）
    │
    ├─→ CONFIRMED → 提取骨架 (label=confirmed, 正樣本)
    │
    └─→ CLEARED → 提取骨架 (label=cleared, 負樣本)
```

**時間範圍:**
- t-n (事件前): 保證完整 ✅
- t+n (事件後): 取得可用部分

**輸出檔案:**
- `data/skeletons/sus_xxx_confirmed.json` - 確認跌倒（正樣本）
- `data/skeletons/sus_xxx_cleared.json` - 疑似但未確認（負樣本）

**設定:**
```yaml
lifecycle:
  auto_skeleton_extract: true  # 啟用自動骨架提取
  skeleton_output_dir: "data/skeletons"
```
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add SkeletonCollector documentation"
```

---

## 驗證清單

完成所有 Task 後，執行以下驗證：

```bash
# 1. 執行所有測試
uv run pytest -v

# 2. 執行 lint
uv run ruff check .

# 3. 格式化
uv run ruff format .

# 4. 手動測試（使用影片）
uv run python -m scripts.test_with_video tests/fixtures/videos/fall-01-cam0.mp4

# 5. 檢查輸出
ls -la data/skeletons/
```

---

## 最終流程圖

```
                    ┌─────────────────────────────────────────┐
                    │              Pipeline.run()              │
                    └─────────────────────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │           process_frame()               │
                    │  detector → rule_engine → delay_confirm │
                    └─────────────────────────────────────────┘
                                       │
                         ┌─────────────┼─────────────┐
                         ▼             ▼             ▼
                    ┌─────────┐  ┌──────────┐  ┌──────────────┐
                    │ NORMAL  │  │SUSPECTED │  │  CONFIRMED   │
                    └─────────┘  └──────────┘  └──────────────┘
                                       │             │
                              on_fall_suspected      │
                              (記錄，不提取)          │
                                       │             │
                         ┌─────────────┴─────────────┤
                         ▼                           ▼
                on_suspicion_cleared          on_fall_confirmed
                         │                           │
                         ▼                           ├──▶ EventLogger
                ┌────────────────┐                   ├──▶ LineNotifier
                │ SkeletonCollect│                   ├──▶ ClipRecorder
                │ (非同步提取)    │                   │
                │ label=cleared  │                   ▼
                └────────────────┘          on_fall_confirmed_update
                                                     │
                                                     ▼
                                            ┌────────────────┐
                                            │ SkeletonCollect│
                                            │ (非同步提取)    │
                                            │ label=confirmed│
                                            └────────────────┘
```

---

*Plan created: 2025-12-31*
*Design decisions: Single extraction per event, guarantee t-n data, accept available t+n data*
