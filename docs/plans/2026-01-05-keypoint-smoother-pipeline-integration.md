# KeypointSmoother Pipeline Integration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate KeypointSmoother into main Pipeline, enabling Pose mode with optional smoothing via configuration.

**Architecture:** Extend existing Pipeline to support dual detection modes (BBox/Pose). Add smoothing config to `DetectionConfig`, modify Pipeline initialization to conditionally use `PoseDetector` + `PoseRuleEngine` with smoothing.

**Tech Stack:** Python 3.12+, pytest, YOLO11

---

## Current State Analysis

**Already Implemented:**
- `src/analysis/smoothing/one_euro_filter.py` - One Euro Filter (complete)
- `src/analysis/smoothing/keypoint_smoother.py` - 17-keypoint smoother (complete)
- `src/analysis/pose_rule_engine.py` - PoseRuleEngine with smoothing integration (complete)
- `scripts/test_with_video.py` - CLI with `--use-pose --enable-smoothing` (complete)

**The Gap:**
- `src/core/pipeline.py` only uses BBox mode (Detector + RuleEngine)
- `config/settings.yaml` lacks Pose/smoothing options
- `src/core/config.py` lacks smoothing configuration

---

## Task 1: Extend DetectionConfig with Pose/Smoothing Options

**Files:**
- Modify: `src/core/config.py:20-25`
- Modify: `config/settings.yaml:9-14`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Tests for configuration loading."""

import pytest
import tempfile
import os
from pathlib import Path

from src.core.config import load_config, DetectionConfig


class TestDetectionConfigPoseOptions:
    """Test Pose/Smoothing configuration options."""

    def test_detection_config_has_pose_options(self):
        """DetectionConfig should have use_pose and smoothing options."""
        config = DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
            pose_model="yolo11s-pose.pt",
            use_pose=True,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        )
        assert config.use_pose is True
        assert config.enable_smoothing is True
        assert config.smoothing_min_cutoff == 1.0
        assert config.smoothing_beta == 0.007

    def test_detection_config_defaults(self):
        """DetectionConfig should have sensible defaults."""
        config = DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
        )
        assert config.use_pose is False
        assert config.enable_smoothing is False
        assert config.smoothing_min_cutoff == 1.0
        assert config.smoothing_beta == 0.007

    def test_load_config_with_pose_options(self, tmp_path):
        """load_config should parse pose options from YAML."""
        config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolo11n.pt"
  pose_model: "yolo11s-pose.pt"
  confidence: 0.5
  classes: [0]
  use_pose: true
  enable_smoothing: true
  smoothing_min_cutoff: 0.8
  smoothing_beta: 0.01

analysis:
  fall_threshold: 1.3
  delay_sec: 3.0
  same_event_window: 60.0
  re_notify_interval: 120.0

recording:
  buffer_seconds: 10
  clip_before_sec: 5
  clip_after_sec: 5

notification:
  line_channel_access_token: "test"
  line_user_id: "test"
  enabled: false

lifecycle:
  clip_retention_days: 7
"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config.detection.use_pose is True
        assert config.detection.enable_smoothing is True
        assert config.detection.smoothing_min_cutoff == 0.8
        assert config.detection.smoothing_beta == 0.01
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`

Expected: FAIL with `TypeError: DetectionConfig.__init__() got an unexpected keyword argument 'use_pose'`

**Step 3: Update DetectionConfig dataclass**

Edit `src/core/config.py:20-25`:

```python
@dataclass
class DetectionConfig:
    model: str
    confidence: float
    classes: list[int]
    pose_model: str = "yolo11s-pose.pt"
    use_pose: bool = False
    enable_smoothing: bool = False
    smoothing_min_cutoff: float = 1.0
    smoothing_beta: float = 0.007
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`

Expected: PASS

**Step 5: Update config/settings.yaml with new options**

Add to `config/settings.yaml` under `detection:`:

```yaml
detection:
  model: "yolo11n.pt"
  pose_model: "yolo11s-pose.pt"
  confidence: 0.5
  classes: [0]
  use_pose: false
  enable_smoothing: false
  smoothing_min_cutoff: 1.0
  smoothing_beta: 0.007
```

**Step 6: Commit**

```bash
git add src/core/config.py config/settings.yaml tests/test_config.py
git commit -m "feat(config): add Pose mode and smoothing options to DetectionConfig"
```

---

## Task 2: Extend Pipeline to Support Pose Mode

**Files:**
- Modify: `src/core/pipeline.py:1-125`
- Test: `tests/test_pipeline_pose.py`

**Step 1: Write the failing test**

Create `tests/test_pipeline_pose.py`:

```python
"""Tests for Pipeline Pose mode integration."""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.core.pipeline import Pipeline
from src.core.config import (
    Config,
    CameraConfig,
    DetectionConfig,
    AnalysisConfig,
    RecordingConfig,
    NotificationConfig,
    LifecycleConfig,
)
from src.analysis.delay_confirm import FallState
from src.detection.skeleton import Skeleton, Keypoint


@pytest.fixture
def pose_config():
    """Config with Pose mode enabled."""
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
            pose_model="yolo11s-pose.pt",
            use_pose=True,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        ),
        analysis=AnalysisConfig(
            fall_threshold=1.3,
            delay_sec=3.0,
            same_event_window=60.0,
            re_notify_interval=120.0,
        ),
        recording=RecordingConfig(
            buffer_seconds=10,
            clip_before_sec=5,
            clip_after_sec=5,
        ),
        notification=NotificationConfig(
            line_channel_access_token="",
            line_user_id="",
            enabled=False,
        ),
        lifecycle=LifecycleConfig(clip_retention_days=7),
    )


@pytest.fixture
def standing_skeleton():
    """Standing person skeleton."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
    return Skeleton(keypoints=keypoints)


class TestPipelinePoseMode:
    """Test Pipeline with Pose mode."""

    @patch("src.core.pipeline.Camera")
    @patch("src.core.pipeline.PoseDetector")
    @patch("src.core.pipeline.EventLogger")
    def test_pipeline_uses_pose_detector_when_configured(
        self, mock_logger, mock_pose_detector, mock_camera, pose_config, tmp_path
    ):
        """Pipeline should use PoseDetector when use_pose=True."""
        db_path = str(tmp_path / "test.db")
        pipeline = Pipeline(pose_config, db_path=db_path)

        # Should have created PoseDetector, not Detector
        mock_pose_detector.assert_called_once()

    @patch("src.core.pipeline.Camera")
    @patch("src.core.pipeline.PoseDetector")
    @patch("src.core.pipeline.EventLogger")
    def test_pipeline_uses_pose_rule_engine_when_configured(
        self, mock_logger, mock_pose_detector, mock_camera, pose_config, tmp_path
    ):
        """Pipeline should use PoseRuleEngine when use_pose=True."""
        db_path = str(tmp_path / "test.db")
        pipeline = Pipeline(pose_config, db_path=db_path)

        # Should have PoseRuleEngine with smoothing
        from src.analysis.pose_rule_engine import PoseRuleEngine
        assert isinstance(pipeline.rule_engine, PoseRuleEngine)
        assert pipeline.rule_engine._enable_smoothing is True

    @patch("src.core.pipeline.Camera")
    @patch("src.core.pipeline.PoseDetector")
    @patch("src.core.pipeline.EventLogger")
    def test_process_frame_with_pose_mode(
        self, mock_logger, mock_pose_detector_cls, mock_camera, pose_config, standing_skeleton, tmp_path
    ):
        """process_frame should work with Pose mode and pass timestamp."""
        db_path = str(tmp_path / "test.db")

        # Mock detector to return skeleton
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [standing_skeleton]
        mock_pose_detector_cls.return_value = mock_detector

        pipeline = Pipeline(pose_config, db_path=db_path)

        # Process a frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        state = pipeline.process_frame(frame, current_time=0.5)

        # Should return valid state
        assert state == FallState.NORMAL
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline_pose.py -v`

Expected: FAIL with `ImportError` or `AttributeError` (PoseDetector not imported in pipeline)

**Step 3: Update Pipeline imports and __init__**

Edit `src/core/pipeline.py`:

```python
import logging
import time

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.capture.camera import Camera
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import Config
from src.detection.bbox import BBox
from src.detection.skeleton import Skeleton
from src.detection.detector import Detector, PoseDetector
from src.events.clip_recorder import ClipRecorder
from src.events.event_logger import EventLogger
from src.events.notifier import LineNotifier
from src.events.observer import FallEvent

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: Config, db_path: str = "data/fds.db"):
        self.config = config

        self.camera = Camera(
            source=config.camera.source,
            fps=config.camera.fps,
            resolution=(config.camera.resolution[0], config.camera.resolution[1]),
        )

        # Select detector and rule engine based on mode
        if config.detection.use_pose:
            self.detector = PoseDetector(
                model_path=config.detection.pose_model,
                confidence=config.detection.confidence,
            )
            self.rule_engine = PoseRuleEngine(
                torso_angle_threshold=config.analysis.fall_threshold,
                enable_smoothing=config.detection.enable_smoothing,
                smoothing_min_cutoff=config.detection.smoothing_min_cutoff,
                smoothing_beta=config.detection.smoothing_beta,
            )
        else:
            self.detector = Detector(
                model_path=config.detection.model,
                confidence=config.detection.confidence,
                classes=config.detection.classes,
            )
            self.rule_engine = RuleEngine(fall_threshold=config.analysis.fall_threshold)

        self.delay_confirm = DelayConfirm(
            delay_sec=config.analysis.delay_sec,
            same_event_window=config.analysis.same_event_window,
            re_notify_interval=config.analysis.re_notify_interval,
        )

        self.rolling_buffer = RollingBuffer(
            buffer_seconds=config.recording.buffer_seconds,
            fps=config.camera.fps,
        )

        self.event_logger = EventLogger(db_path=db_path)
        self.clip_recorder = ClipRecorder(fps=config.camera.fps)
        self.notifier = LineNotifier(
            channel_access_token=config.notification.line_channel_access_token,
            user_id=config.notification.line_user_id,
            enabled=config.notification.enabled,
        )

        self.delay_confirm.add_observer(self.event_logger)
        self.delay_confirm.add_observer(self.notifier)
        self.delay_confirm.add_observer(self)

        self._current_detection: BBox | Skeleton | None = None
        self._use_pose = config.detection.use_pose

    def on_fall_confirmed(self, event: FallEvent) -> None:
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

    def on_fall_recovered(self, event: FallEvent) -> None:
        logger.info(f"Fall recovered: {event.event_id}")

    def process_frame(self, frame: np.ndarray, current_time: float) -> FallState:
        detections = self.detector.detect(frame)
        self._current_detection = detections[0] if detections else None

        # Pose mode requires timestamp for smoothing
        if self._use_pose:
            is_fallen = self.rule_engine.is_fallen(self._current_detection, timestamp=current_time)
        else:
            is_fallen = self.rule_engine.is_fallen(self._current_detection)

        # Build bbox_tuple for rolling buffer
        bbox_tuple = None
        if not self._use_pose and self._current_detection:
            bbox_tuple = (
                self._current_detection.x,
                self._current_detection.y,
                self._current_detection.width,
                self._current_detection.height,
            )

        frame_data = FrameData(
            timestamp=current_time,
            frame=frame.copy(),
            bbox=bbox_tuple,
        )
        self.rolling_buffer.push(frame_data)

        state = self.delay_confirm.update(is_fallen=is_fallen, current_time=current_time)

        return state

    def run(self) -> None:
        logger.info("Starting fall detection pipeline...")
        mode = "Pose" if self._use_pose else "BBox"
        logger.info(f"Detection mode: {mode}")
        if self._use_pose and self.config.detection.enable_smoothing:
            logger.info("Keypoint smoothing: enabled")

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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pipeline_pose.py -v`

Expected: PASS

**Step 5: Run all tests to ensure no regression**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/core/pipeline.py tests/test_pipeline_pose.py
git commit -m "feat(pipeline): add Pose mode with KeypointSmoother integration"
```

---

## Task 3: Add Integration Test for End-to-End Pose + Smoothing

**Files:**
- Create: `tests/integration/test_pipeline_pose_integration.py`

**Step 1: Write the integration test**

Create `tests/integration/test_pipeline_pose_integration.py`:

```python
"""Integration tests for Pipeline with Pose mode and smoothing."""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from src.core.pipeline import Pipeline
from src.core.config import (
    Config,
    CameraConfig,
    DetectionConfig,
    AnalysisConfig,
    RecordingConfig,
    NotificationConfig,
    LifecycleConfig,
)
from src.analysis.delay_confirm import FallState
from src.detection.skeleton import Skeleton, Keypoint


@pytest.fixture
def pose_smoothing_config():
    """Config with Pose mode and smoothing enabled."""
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
            pose_model="yolo11s-pose.pt",
            use_pose=True,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        ),
        analysis=AnalysisConfig(
            fall_threshold=60.0,  # Torso angle threshold for Pose mode
            delay_sec=3.0,
            same_event_window=60.0,
            re_notify_interval=120.0,
        ),
        recording=RecordingConfig(
            buffer_seconds=10,
            clip_before_sec=5,
            clip_after_sec=5,
        ),
        notification=NotificationConfig(
            line_channel_access_token="",
            line_user_id="",
            enabled=False,
        ),
        lifecycle=LifecycleConfig(clip_retention_days=7),
    )


def create_standing_skeleton() -> Skeleton:
    """Create a standing person skeleton (torso angle ~10 degrees)."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
    return Skeleton(keypoints=keypoints)


def create_fallen_skeleton() -> Skeleton:
    """Create a fallen person skeleton (torso angle ~85 degrees)."""
    keypoints = np.zeros((17, 3))
    # Person lying on side
    keypoints[Keypoint.LEFT_SHOULDER] = [170, 390, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [170, 410, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [350, 390, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 410, 0.9]
    return Skeleton(keypoints=keypoints)


class TestPipelinePoseSmoothingIntegration:
    """Integration tests for Pose mode with smoothing."""

    @pytest.fixture
    def mock_pose_detector(self, mocker):
        """Mock PoseDetector to return controlled skeletons."""
        mock = mocker.patch("src.core.pipeline.PoseDetector")
        return mock

    @pytest.fixture
    def mock_camera(self, mocker):
        """Mock Camera."""
        mock = mocker.patch("src.core.pipeline.Camera")
        return mock

    def test_smoothing_reduces_false_positives_from_jitter(
        self, mock_pose_detector, mock_camera, pose_smoothing_config, tmp_path
    ):
        """Smoothing should reduce false positives from noisy keypoints."""
        db_path = str(tmp_path / "test.db")

        # Setup mock detector
        mock_detector_instance = mock_pose_detector.return_value

        pipeline = Pipeline(pose_smoothing_config, db_path=db_path)

        # Simulate 30 frames of standing with small jitter
        np.random.seed(42)
        states = []
        base_skeleton = create_standing_skeleton()

        for i in range(30):
            # Add small random noise to keypoints
            noisy_keypoints = base_skeleton.keypoints.copy()
            noisy_keypoints[:, 0] += np.random.randn(17) * 5  # x noise
            noisy_keypoints[:, 1] += np.random.randn(17) * 5  # y noise
            noisy_skeleton = Skeleton(keypoints=noisy_keypoints)

            mock_detector_instance.detect.return_value = [noisy_skeleton]

            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=i * 0.033)
            states.append(state)

        # All frames should be NORMAL (no false positives from jitter)
        assert all(s == FallState.NORMAL for s in states)

    def test_fall_detection_with_smoothing(
        self, mock_pose_detector, mock_camera, pose_smoothing_config, tmp_path
    ):
        """Fall should be detected after delay even with smoothing."""
        db_path = str(tmp_path / "test.db")

        mock_detector_instance = mock_pose_detector.return_value

        pipeline = Pipeline(pose_smoothing_config, db_path=db_path)

        fallen_skeleton = create_fallen_skeleton()
        mock_detector_instance.detect.return_value = [fallen_skeleton]

        states = []
        # Simulate 100 frames at 30fps = 3.3 seconds (beyond 3s delay)
        for i in range(100):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=i * 0.033)
            states.append(state)

        # Should transition: NORMAL -> SUSPECTED -> CONFIRMED
        assert FallState.SUSPECTED in states
        assert FallState.CONFIRMED in states
```

**Step 2: Run integration test**

Run: `uv run pytest tests/integration/test_pipeline_pose_integration.py -v`

Expected: PASS (if Task 2 is complete)

**Step 3: Commit**

```bash
git add tests/integration/test_pipeline_pose_integration.py
git commit -m "test(integration): add Pipeline Pose mode integration tests"
```

---

## Task 4: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md Quick Reference**

Add to `CLAUDE.md` Quick Reference section:

```markdown
# 執行 (Pose 模式 + Smoothing)
uv run python main.py  # 需設定 config/settings.yaml use_pose: true
```

Update Configuration section:

```markdown
### Configuration (src/core/config.py)

**Detection Config Options:**
- `use_pose`: 啟用 Pose 模式（預設 false，使用 BBox）
- `enable_smoothing`: 啟用 Keypoint 平滑（僅 Pose 模式）
- `smoothing_min_cutoff`: 平滑強度（越低越平滑，預設 1.0）
- `smoothing_beta`: 快速動作反應（越高 lag 越低，預設 0.007）
```

**Step 2: Update README.md with Pose mode instructions**

Add to README.md settings section:

```markdown
### Pose 模式設定

```yaml
detection:
  use_pose: true           # 啟用骨架姿態偵測
  enable_smoothing: true   # 啟用 Keypoint 平滑減少誤報
  smoothing_min_cutoff: 1.0
  smoothing_beta: 0.007
```
```

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add Pose mode and smoothing configuration guide"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Extend DetectionConfig with Pose/Smoothing options | `config.py`, `settings.yaml`, `test_config.py` |
| 2 | Extend Pipeline to support Pose mode | `pipeline.py`, `test_pipeline_pose.py` |
| 3 | Add integration tests | `test_pipeline_pose_integration.py` |
| 4 | Update documentation | `CLAUDE.md`, `README.md` |

**Estimated commits:** 4
