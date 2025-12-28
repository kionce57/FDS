# FDS Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an end-to-end fall detection system that detects falls via camera, confirms with delay logic, records clips, logs events, and sends LINE notifications.

**Architecture:** Edge-based processing with YOLOv8 for person detection, aspect ratio rules for fall detection, state machine for confirmation, and observer pattern for event handling.

**Tech Stack:** Python 3.12+, YOLOv8 (ultralytics), OpenCV, SQLite, LINE Notify API, pytest

---

## Task 1: Project Setup

**Files:**
- Modify: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/detection/__init__.py`
- Create: `src/detection/bbox.py`
- Create: `tests/__init__.py`
- Create: `tests/test_bbox.py`
- Create: `config/settings.yaml`

**Step 1: Update pyproject.toml with dependencies**

```toml
[project]
name = "fds"
version = "0.1.0"
description = "Fall Detection System for elderly home care"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "opencv-python>=4.8.0",
    "ultralytics>=8.0.0",
    "pyyaml>=6.0",
    "requests>=2.31.0",
    "numpy>=1.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.14.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
```

**Step 2: Create directory structure**

Run:
```bash
mkdir -p src/capture src/detection src/analysis src/events src/lifecycle src/core
mkdir -p tests/fixtures config data/clips data/snapshots
touch src/__init__.py src/capture/__init__.py src/detection/__init__.py
touch src/analysis/__init__.py src/events/__init__.py src/lifecycle/__init__.py src/core/__init__.py
touch tests/__init__.py
```

**Step 3: Create base config file**

Create `config/settings.yaml`:
```yaml
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolov8n.pt"
  confidence: 0.5
  classes: [0]

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
  line_token: "${LINE_NOTIFY_TOKEN}"
  enabled: true

lifecycle:
  clip_retention_days: 7
  skeleton_retention_days: 30
```

**Step 4: Update .gitignore**

Append to `.gitignore`:
```
data/
*.pt
.env
```

**Step 5: Install dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: setup project structure and dependencies"
```

---

## Task 2: BBox Data Structure

**Files:**
- Create: `src/detection/bbox.py`
- Create: `tests/test_bbox.py`

**Step 1: Write the failing test**

Create `tests/test_bbox.py`:
```python
import pytest
from src.detection.bbox import BBox


class TestBBox:
    def test_create_bbox(self):
        bbox = BBox(x=10, y=20, width=100, height=200)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 200

    def test_aspect_ratio_standing(self):
        bbox = BBox(x=0, y=0, width=100, height=200)
        assert bbox.aspect_ratio == 2.0

    def test_aspect_ratio_fallen(self):
        bbox = BBox(x=0, y=0, width=200, height=100)
        assert bbox.aspect_ratio == 0.5

    def test_center_point(self):
        bbox = BBox(x=100, y=100, width=50, height=80)
        cx, cy = bbox.center
        assert cx == 125
        assert cy == 140

    def test_area(self):
        bbox = BBox(x=0, y=0, width=100, height=200)
        assert bbox.area == 20000
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bbox.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.detection.bbox'"

**Step 3: Write minimal implementation**

Create `src/detection/bbox.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        if self.width == 0:
            return 0.0
        return self.height / self.width

    @property
    def center(self) -> tuple[int, int]:
        cx = self.x + self.width // 2
        cy = self.y + self.height // 2
        return cx, cy

    @property
    def area(self) -> int:
        return self.width * self.height
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bbox.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/detection/bbox.py tests/test_bbox.py
git commit -m "feat: add BBox data structure with aspect ratio calculation"
```

---

## Task 3: Rule Engine

**Files:**
- Create: `src/analysis/rule_engine.py`
- Create: `tests/test_rule_engine.py`

**Step 1: Write the failing test**

Create `tests/test_rule_engine.py`:
```python
import pytest
from src.detection.bbox import BBox
from src.analysis.rule_engine import RuleEngine


class TestRuleEngine:
    @pytest.fixture
    def engine(self):
        return RuleEngine(fall_threshold=1.3)

    def test_standing_not_fallen(self, engine):
        bbox = BBox(x=0, y=0, width=100, height=200)
        assert engine.is_fallen(bbox) is False

    def test_boundary_standing(self, engine):
        bbox = BBox(x=0, y=0, width=100, height=130)
        assert engine.is_fallen(bbox) is False

    def test_just_below_threshold_is_fallen(self, engine):
        bbox = BBox(x=0, y=0, width=100, height=129)
        assert engine.is_fallen(bbox) is True

    def test_clearly_fallen(self, engine):
        bbox = BBox(x=0, y=0, width=200, height=100)
        assert engine.is_fallen(bbox) is True

    def test_none_bbox_returns_false(self, engine):
        assert engine.is_fallen(None) is False

    @pytest.mark.parametrize("width,height,expected", [
        (100, 200, False),
        (100, 130, False),
        (100, 120, True),
        (200, 100, True),
        (100, 100, True),
    ])
    def test_various_ratios(self, engine, width, height, expected):
        bbox = BBox(x=0, y=0, width=width, height=height)
        assert engine.is_fallen(bbox) == expected
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rule_engine.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/analysis/rule_engine.py`:
```python
from src.detection.bbox import BBox


class RuleEngine:
    def __init__(self, fall_threshold: float = 1.3):
        self.fall_threshold = fall_threshold

    def is_fallen(self, bbox: BBox | None) -> bool:
        if bbox is None:
            return False
        return bbox.aspect_ratio < self.fall_threshold
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rule_engine.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add src/analysis/rule_engine.py tests/test_rule_engine.py
git commit -m "feat: add RuleEngine for aspect ratio fall detection"
```

---

## Task 4: Observer Protocol

**Files:**
- Create: `src/events/observer.py`
- Create: `tests/test_observer.py`

**Step 1: Write the failing test**

Create `tests/test_observer.py`:
```python
import pytest
from src.events.observer import FallEvent, FallEventObserver


class MockObserver:
    def __init__(self):
        self.confirmed_events: list[FallEvent] = []
        self.recovered_events: list[FallEvent] = []

    def on_fall_confirmed(self, event: FallEvent) -> None:
        self.confirmed_events.append(event)

    def on_fall_recovered(self, event: FallEvent) -> None:
        self.recovered_events.append(event)


class TestFallEvent:
    def test_create_event(self):
        event = FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1
        )
        assert event.event_id == "evt_123"
        assert event.confirmed_at == 1000.0
        assert event.notification_count == 1

    def test_event_is_mutable(self):
        event = FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1
        )
        event.notification_count = 2
        event.last_notified_at = 1100.0
        assert event.notification_count == 2
        assert event.last_notified_at == 1100.0


class TestMockObserver:
    def test_observer_receives_confirmed_event(self):
        observer = MockObserver()
        event = FallEvent("evt_1", 100.0, 100.0, 1)
        observer.on_fall_confirmed(event)
        assert len(observer.confirmed_events) == 1
        assert observer.confirmed_events[0].event_id == "evt_1"

    def test_observer_receives_recovered_event(self):
        observer = MockObserver()
        event = FallEvent("evt_1", 100.0, 100.0, 1)
        observer.on_fall_recovered(event)
        assert len(observer.recovered_events) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_observer.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/events/observer.py`:
```python
from dataclasses import dataclass
from typing import Protocol


@dataclass
class FallEvent:
    event_id: str
    confirmed_at: float
    last_notified_at: float
    notification_count: int


class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_observer.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/events/observer.py tests/test_observer.py
git commit -m "feat: add FallEvent and FallEventObserver protocol"
```

---

## Task 5: Delay Confirm State Machine

**Files:**
- Create: `src/analysis/delay_confirm.py`
- Create: `tests/test_delay_confirm.py`

**Step 1: Write the failing test**

Create `tests/test_delay_confirm.py`:
```python
import pytest
from src.analysis.delay_confirm import DelayConfirm, FallState
from src.events.observer import FallEvent


class MockObserver:
    def __init__(self):
        self.confirmed_events: list[FallEvent] = []
        self.recovered_events: list[FallEvent] = []

    def on_fall_confirmed(self, event: FallEvent) -> None:
        self.confirmed_events.append(event)

    def on_fall_recovered(self, event: FallEvent) -> None:
        self.recovered_events.append(event)

    @property
    def confirm_count(self) -> int:
        return len(self.confirmed_events)


class TestDelayConfirmStates:
    def test_initial_state_is_normal(self):
        dc = DelayConfirm(delay_sec=3.0)
        assert dc.state == FallState.NORMAL

    def test_normal_to_suspected_on_fall(self):
        dc = DelayConfirm(delay_sec=3.0)
        state = dc.update(is_fallen=True, current_time=0.0)
        assert state == FallState.SUSPECTED

    def test_suspected_to_normal_on_recovery(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        state = dc.update(is_fallen=False, current_time=1.0)
        assert state == FallState.NORMAL

    def test_suspected_stays_before_delay(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        state = dc.update(is_fallen=True, current_time=2.9)
        assert state == FallState.SUSPECTED

    def test_suspected_to_confirmed_after_delay(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=2.0)
        state = dc.update(is_fallen=True, current_time=3.1)
        assert state == FallState.CONFIRMED

    def test_confirmed_to_normal_on_recovery(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        state = dc.update(is_fallen=False, current_time=5.0)
        assert state == FallState.NORMAL


class TestDelayConfirmObservers:
    def test_observer_notified_on_confirm(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)

        assert observer.confirm_count == 1

    def test_observer_notified_on_recovery(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        dc.update(is_fallen=False, current_time=5.0)

        assert len(observer.recovered_events) == 1

    def test_same_event_window_deduplication(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0, same_event_window=60.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        dc.update(is_fallen=False, current_time=10.0)
        dc.update(is_fallen=True, current_time=15.0)
        dc.update(is_fallen=True, current_time=19.0)

        assert observer.confirm_count == 1

    def test_re_notify_after_interval(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0, re_notify_interval=120.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        dc.update(is_fallen=True, current_time=125.0)

        assert observer.confirm_count == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_delay_confirm.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/analysis/delay_confirm.py`:
```python
from enum import Enum

from src.events.observer import FallEvent, FallEventObserver


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
        self.observers: list[FallEventObserver] = []

    def add_observer(self, observer: FallEventObserver) -> None:
        self.observers.append(observer)

    def update(self, is_fallen: bool, current_time: float) -> FallState:
        match self.state:
            case FallState.NORMAL:
                if is_fallen:
                    self.state = FallState.SUSPECTED
                    self.suspected_since = current_time

            case FallState.SUSPECTED:
                if not is_fallen:
                    self._reset()
                elif current_time - self.suspected_since >= self.delay_sec:
                    self._confirm_fall(current_time)

            case FallState.CONFIRMED:
                if not is_fallen:
                    self._recover(current_time)
                else:
                    self._check_re_notify(current_time)

        return self.state

    def _confirm_fall(self, current_time: float) -> None:
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

    def _reset(self) -> None:
        self.state = FallState.NORMAL
        self.suspected_since = None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_delay_confirm.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add src/analysis/delay_confirm.py tests/test_delay_confirm.py
git commit -m "feat: add DelayConfirm state machine with observer pattern"
```

---

## Task 6: Rolling Buffer

**Files:**
- Create: `src/capture/rolling_buffer.py`
- Create: `tests/test_rolling_buffer.py`

**Step 1: Write the failing test**

Create `tests/test_rolling_buffer.py`:
```python
import pytest
import numpy as np
from src.capture.rolling_buffer import RollingBuffer, FrameData


class TestRollingBuffer:
    def test_push_single_frame(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = FrameData(timestamp=0.0, frame=frame, bbox=None)
        buffer.push(frame_data)
        assert len(buffer) == 1

    def test_buffer_max_capacity(self):
        buffer = RollingBuffer(buffer_seconds=1.0, fps=10.0)
        for i in range(15):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            buffer.push(FrameData(timestamp=float(i) * 0.1, frame=frame, bbox=None))
        assert len(buffer) == 10

    def test_get_clip_within_range(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=10.0)
        for i in range(100):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            buffer.push(FrameData(timestamp=float(i) * 0.1, frame=frame, bbox=None))

        clip = buffer.get_clip(event_time=5.0, before_sec=1.0, after_sec=1.0)
        timestamps = [f.timestamp for f in clip]

        assert all(4.0 <= t <= 6.0 for t in timestamps)
        assert len(clip) == 21

    def test_get_clip_empty_buffer(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=10.0)
        clip = buffer.get_clip(event_time=5.0, before_sec=1.0, after_sec=1.0)
        assert len(clip) == 0

    def test_clear_buffer(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=10.0)
        for i in range(10):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            buffer.push(FrameData(timestamp=float(i), frame=frame, bbox=None))
        buffer.clear()
        assert len(buffer) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rolling_buffer.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/capture/rolling_buffer.py`:
```python
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class FrameData:
    timestamp: float
    frame: np.ndarray
    bbox: tuple[int, int, int, int] | None


class RollingBuffer:
    def __init__(self, buffer_seconds: float = 10.0, fps: float = 15.0):
        self.max_frames = int(buffer_seconds * fps)
        self.buffer: deque[FrameData] = deque(maxlen=self.max_frames)

    def push(self, frame_data: FrameData) -> None:
        self.buffer.append(frame_data)

    def get_clip(
        self,
        event_time: float,
        before_sec: float = 5.0,
        after_sec: float = 5.0,
    ) -> list[FrameData]:
        start_time = event_time - before_sec
        end_time = event_time + after_sec
        return [f for f in self.buffer if start_time <= f.timestamp <= end_time]

    def clear(self) -> None:
        self.buffer.clear()

    def __len__(self) -> int:
        return len(self.buffer)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rolling_buffer.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/capture/rolling_buffer.py tests/test_rolling_buffer.py
git commit -m "feat: add RollingBuffer for pre-event video capture"
```

---

## Task 7: Camera Capture

**Files:**
- Create: `src/capture/camera.py`
- Create: `tests/test_camera.py`

**Step 1: Write the failing test**

Create `tests/test_camera.py`:
```python
import pytest
import numpy as np
from unittest.mock import Mock, patch
from src.capture.camera import Camera, CameraError


class TestCamera:
    def test_camera_init(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.isOpened.return_value = True
            camera = Camera(source=0)
            assert camera.source == 0

    def test_camera_not_opened_raises_error(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.isOpened.return_value = False
            with pytest.raises(CameraError, match="Failed to open camera"):
                Camera(source=0)

    def test_read_frame_success(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

            camera = Camera(source=0)
            frame = camera.read()

            assert frame is not None
            assert frame.shape == (480, 640, 3)

    def test_read_frame_failure_returns_none(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (False, None)

            camera = Camera(source=0)
            frame = camera.read()

            assert frame is None

    def test_consecutive_failures_raise_error(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (False, None)

            camera = Camera(source=0, max_retries=3)
            camera.read()
            camera.read()

            with pytest.raises(CameraError, match="consecutive failures"):
                camera.read()

    def test_release_camera(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True

            camera = Camera(source=0)
            camera.release()

            mock_instance.release.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_camera.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/capture/camera.py`:
```python
import cv2
import numpy as np


class CameraError(Exception):
    """Camera-related errors."""


class Camera:
    def __init__(
        self,
        source: int | str = 0,
        fps: int = 15,
        resolution: tuple[int, int] = (640, 480),
        max_retries: int = 3,
    ):
        self.source = source
        self.fps = fps
        self.resolution = resolution
        self.max_retries = max_retries
        self._consecutive_failures = 0

        self._capture = cv2.VideoCapture(source)

        if not self._capture.isOpened():
            raise CameraError(f"Failed to open camera: {source}")

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
        self._capture.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> np.ndarray | None:
        ret, frame = self._capture.read()

        if not ret or frame is None:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.max_retries:
                raise CameraError(
                    f"Camera {self.source} has {self._consecutive_failures} consecutive failures"
                )
            return None

        self._consecutive_failures = 0
        return frame

    def release(self) -> None:
        if self._capture:
            self._capture.release()

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_camera.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/capture/camera.py tests/test_camera.py
git commit -m "feat: add Camera capture with retry logic"
```

---

## Task 8: YOLOv8 Detector

**Files:**
- Create: `src/detection/detector.py`
- Create: `tests/test_detector.py`

**Step 1: Write the failing test**

Create `tests/test_detector.py`:
```python
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.detection.detector import Detector
from src.detection.bbox import BBox


class TestDetector:
    def test_detector_init(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            detector = Detector(model_path="yolov8n.pt", confidence=0.5)
            assert detector.confidence == 0.5
            mock_yolo.assert_called_once_with("yolov8n.pt")

    def test_detect_returns_bboxes(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_result = MagicMock()
            mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = np.array([
                [100, 50, 200, 250],
                [300, 100, 400, 300],
            ])
            mock_result.boxes.cls.cpu.return_value.numpy.return_value = np.array([0, 0])
            mock_result.boxes.conf.cpu.return_value.numpy.return_value = np.array([0.9, 0.8])

            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_result]

            detector = Detector(model_path="yolov8n.pt", confidence=0.5, classes=[0])
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            bboxes = detector.detect(frame)

            assert len(bboxes) == 2
            assert isinstance(bboxes[0], BBox)
            assert bboxes[0].x == 100
            assert bboxes[0].width == 100
            assert bboxes[0].height == 200

    def test_detect_filters_by_class(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_result = MagicMock()
            mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = np.array([
                [100, 50, 200, 250],
                [300, 100, 400, 300],
            ])
            mock_result.boxes.cls.cpu.return_value.numpy.return_value = np.array([0, 1])
            mock_result.boxes.conf.cpu.return_value.numpy.return_value = np.array([0.9, 0.8])

            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_result]

            detector = Detector(model_path="yolov8n.pt", confidence=0.5, classes=[0])
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            bboxes = detector.detect(frame)

            assert len(bboxes) == 1

    def test_detect_empty_result(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_result = MagicMock()
            mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = np.array([]).reshape(0, 4)
            mock_result.boxes.cls.cpu.return_value.numpy.return_value = np.array([])
            mock_result.boxes.conf.cpu.return_value.numpy.return_value = np.array([])

            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_result]

            detector = Detector(model_path="yolov8n.pt")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            bboxes = detector.detect(frame)

            assert len(bboxes) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_detector.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/detection/detector.py`:
```python
import numpy as np
from ultralytics import YOLO

from src.detection.bbox import BBox


class Detector:
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        classes: list[int] | None = None,
    ):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.classes = classes if classes is not None else [0]

    def detect(self, frame: np.ndarray) -> list[BBox]:
        results = self.model(frame, conf=self.confidence, verbose=False)

        bboxes = []
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()

            for box, cls, conf in zip(boxes, classes, confs):
                if int(cls) not in self.classes:
                    continue

                x1, y1, x2, y2 = map(int, box)
                bboxes.append(
                    BBox(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    )
                )

        return bboxes
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_detector.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/detection/detector.py tests/test_detector.py
git commit -m "feat: add YOLOv8 Detector for person detection"
```

---

## Task 9: Event Logger (SQLite)

**Files:**
- Create: `src/events/event_logger.py`
- Create: `tests/test_event_logger.py`

**Step 1: Write the failing test**

Create `tests/test_event_logger.py`:
```python
import pytest
import sqlite3
from pathlib import Path
from src.events.event_logger import EventLogger
from src.events.observer import FallEvent


class TestEventLogger:
    @pytest.fixture
    def db_path(self, tmp_path):
        return tmp_path / "test.db"

    @pytest.fixture
    def logger(self, db_path):
        logger = EventLogger(db_path=str(db_path))
        yield logger
        logger.close()

    def test_creates_database(self, db_path):
        logger = EventLogger(db_path=str(db_path))
        logger.close()
        assert db_path.exists()

    def test_creates_events_table(self, logger, db_path):
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_log_event(self, logger, db_path):
        event = FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1,
        )
        logger.on_fall_confirmed(event)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT * FROM events WHERE event_id = ?", ("evt_123",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "evt_123"

    def test_log_recovery(self, logger, db_path):
        event = FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1,
        )
        logger.on_fall_confirmed(event)
        logger.on_fall_recovered(event)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT recovered_at FROM events WHERE event_id = ?", ("evt_123",)
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] is not None

    def test_get_recent_events(self, logger):
        for i in range(5):
            event = FallEvent(
                event_id=f"evt_{i}",
                confirmed_at=float(i * 100),
                last_notified_at=float(i * 100),
                notification_count=1,
            )
            logger.on_fall_confirmed(event)

        events = logger.get_recent_events(limit=3)
        assert len(events) == 3
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_logger.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/events/event_logger.py`:
```python
import sqlite3
import time
from pathlib import Path

from src.events.observer import FallEvent, FallEventObserver


class EventLogger(FallEventObserver):
    def __init__(self, db_path: str = "data/fds.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                confirmed_at REAL NOT NULL,
                recovered_at REAL,
                notification_count INTEGER DEFAULT 1,
                clip_path TEXT,
                created_at REAL NOT NULL
            )
        """)
        self.conn.commit()

    def on_fall_confirmed(self, event: FallEvent) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO events
            (event_id, confirmed_at, notification_count, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event.event_id, event.confirmed_at, event.notification_count, time.time()),
        )
        self.conn.commit()

    def on_fall_recovered(self, event: FallEvent) -> None:
        self.conn.execute(
            "UPDATE events SET recovered_at = ? WHERE event_id = ?",
            (time.time(), event.event_id),
        )
        self.conn.commit()

    def update_clip_path(self, event_id: str, clip_path: str) -> None:
        self.conn.execute(
            "UPDATE events SET clip_path = ? WHERE event_id = ?",
            (clip_path, event_id),
        )
        self.conn.commit()

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        cursor = self.conn.execute(
            """
            SELECT event_id, confirmed_at, recovered_at, notification_count, clip_path
            FROM events
            ORDER BY confirmed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = ["event_id", "confirmed_at", "recovered_at", "notification_count", "clip_path"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_event_logger.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/events/event_logger.py tests/test_event_logger.py
git commit -m "feat: add EventLogger with SQLite storage"
```

---

## Task 10: Clip Recorder

**Files:**
- Create: `src/events/clip_recorder.py`
- Create: `tests/test_clip_recorder.py`

**Step 1: Write the failing test**

Create `tests/test_clip_recorder.py`:
```python
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.events.clip_recorder import ClipRecorder
from src.capture.rolling_buffer import FrameData


class TestClipRecorder:
    @pytest.fixture
    def output_dir(self, tmp_path):
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        return clips_dir

    @pytest.fixture
    def recorder(self, output_dir):
        return ClipRecorder(output_dir=str(output_dir), fps=15)

    @pytest.fixture
    def sample_frames(self):
        frames = []
        for i in range(30):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :, 0] = i * 8
            frames.append(FrameData(timestamp=float(i) / 15, frame=frame, bbox=None))
        return frames

    def test_generate_filename(self, recorder):
        filename = recorder._generate_filename("evt_123")
        assert "evt_123" in filename
        assert filename.endswith(".mp4")

    def test_save_creates_file(self, recorder, sample_frames, output_dir):
        with patch("cv2.VideoWriter") as mock_writer:
            mock_instance = mock_writer.return_value
            mock_instance.isOpened.return_value = True

            path = recorder.save(sample_frames, "evt_test")

            assert "evt_test" in path
            mock_instance.write.assert_called()

    def test_save_empty_frames_returns_none(self, recorder):
        result = recorder.save([], "evt_empty")
        assert result is None

    def test_save_writes_all_frames(self, recorder, sample_frames):
        with patch("cv2.VideoWriter") as mock_writer:
            mock_instance = mock_writer.return_value
            mock_instance.isOpened.return_value = True

            recorder.save(sample_frames, "evt_test")

            assert mock_instance.write.call_count == len(sample_frames)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_clip_recorder.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/events/clip_recorder.py`:
```python
from datetime import datetime
from pathlib import Path

import cv2

from src.capture.rolling_buffer import FrameData


class ClipRecorder:
    def __init__(
        self,
        output_dir: str = "data/clips",
        fps: int = 15,
        codec: str = "mp4v",
    ):
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_clip_recorder.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/events/clip_recorder.py tests/test_clip_recorder.py
git commit -m "feat: add ClipRecorder for saving event video clips"
```

---

## Task 11: LINE Notifier

**Files:**
- Create: `src/events/notifier.py`
- Create: `tests/test_notifier.py`

**Step 1: Write the failing test**

Create `tests/test_notifier.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from src.events.notifier import LineNotifier
from src.events.observer import FallEvent


class TestLineNotifier:
    @pytest.fixture
    def notifier(self):
        return LineNotifier(token="test_token", enabled=True)

    @pytest.fixture
    def sample_event(self):
        return FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1,
        )

    def test_notifier_disabled(self, sample_event):
        notifier = LineNotifier(token="test", enabled=False)
        with patch("requests.post") as mock_post:
            notifier.on_fall_confirmed(sample_event)
            mock_post.assert_not_called()

    def test_send_notification_success(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.on_fall_confirmed(sample_event)
            mock_post.assert_called_once()

    def test_notification_message_format(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.on_fall_confirmed(sample_event)

            call_args = mock_post.call_args
            message = call_args.kwargs.get("data", {}).get("message", "")
            assert "evt_123" in message or "跌倒" in message

    def test_notification_failure_adds_to_queue(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            notifier.on_fall_confirmed(sample_event)

            assert len(notifier._pending_queue) == 1

    def test_retry_pending_success(self, notifier, sample_event):
        notifier._pending_queue.append(sample_event)

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.retry_pending()

            assert len(notifier._pending_queue) == 0

    def test_recovery_notification(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.on_fall_recovered(sample_event)

            call_args = mock_post.call_args
            message = call_args.kwargs.get("data", {}).get("message", "")
            assert "恢復" in message or "recovered" in message.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_notifier.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/events/notifier.py`:
```python
import logging
from collections import deque
from datetime import datetime

import requests

from src.events.observer import FallEvent, FallEventObserver

logger = logging.getLogger(__name__)


class LineNotifier(FallEventObserver):
    API_URL = "https://notify-api.line.me/api/notify"

    def __init__(self, token: str, enabled: bool = True):
        self.token = token
        self.enabled = enabled
        self._pending_queue: deque[FallEvent] = deque()

    def on_fall_confirmed(self, event: FallEvent) -> None:
        if not self.enabled:
            return

        timestamp = datetime.fromtimestamp(event.confirmed_at).strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"\n🚨 跌倒警報!\n"
            f"事件 ID: {event.event_id}\n"
            f"時間: {timestamp}\n"
            f"通知次數: {event.notification_count}"
        )
        self._send(event, message)

    def on_fall_recovered(self, event: FallEvent) -> None:
        if not self.enabled:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"\n✅ 已恢復\n"
            f"事件 ID: {event.event_id}\n"
            f"恢復時間: {timestamp}"
        )
        self._send(event, message)

    def _send(self, event: FallEvent, message: str) -> bool:
        try:
            response = requests.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.token}"},
                data={"message": message},
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f"Notification sent for {event.event_id}")
                return True
            else:
                logger.warning(f"Notification failed: {response.status_code}")
                self._pending_queue.append(event)
                return False
        except Exception as e:
            logger.error(f"Notification error: {e}")
            self._pending_queue.append(event)
            return False

    def retry_pending(self) -> None:
        while self._pending_queue:
            event = self._pending_queue[0]
            timestamp = datetime.fromtimestamp(event.confirmed_at).strftime("%Y-%m-%d %H:%M:%S")
            message = (
                f"\n🚨 跌倒警報 (重試)!\n"
                f"事件 ID: {event.event_id}\n"
                f"時間: {timestamp}"
            )
            try:
                response = requests.post(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {self.token}"},
                    data={"message": message},
                    timeout=10,
                )
                if response.status_code == 200:
                    self._pending_queue.popleft()
                else:
                    break
            except Exception:
                break
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_notifier.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/events/notifier.py tests/test_notifier.py
git commit -m "feat: add LineNotifier with retry queue"
```

---

## Task 12: Config Loader

**Files:**
- Create: `src/core/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

Create `tests/test_config.py`:
```python
import pytest
import os
from pathlib import Path
from src.core.config import Config, load_config


class TestConfig:
    @pytest.fixture
    def config_file(self, tmp_path):
        config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolov8n.pt"
  confidence: 0.5
  classes: [0]

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
  line_token: "${LINE_NOTIFY_TOKEN}"
  enabled: true

lifecycle:
  clip_retention_days: 7
  skeleton_retention_days: 30
"""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(config_content)
        return config_path

    def test_load_config(self, config_file):
        config = load_config(str(config_file))
        assert config.camera.fps == 15
        assert config.detection.model == "yolov8n.pt"
        assert config.analysis.fall_threshold == 1.3

    def test_env_variable_substitution(self, config_file, monkeypatch):
        monkeypatch.setenv("LINE_NOTIFY_TOKEN", "test_token_123")
        config = load_config(str(config_file))
        assert config.notification.line_token == "test_token_123"

    def test_camera_config(self, config_file):
        config = load_config(str(config_file))
        assert config.camera.source == 0
        assert config.camera.resolution == [640, 480]

    def test_analysis_config(self, config_file):
        config = load_config(str(config_file))
        assert config.analysis.delay_sec == 3.0
        assert config.analysis.same_event_window == 60.0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/core/config.py`:
```python
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CameraConfig:
    source: int | str
    fps: int
    resolution: list[int]


@dataclass
class DetectionConfig:
    model: str
    confidence: float
    classes: list[int]


@dataclass
class AnalysisConfig:
    fall_threshold: float
    delay_sec: float
    same_event_window: float
    re_notify_interval: float


@dataclass
class RecordingConfig:
    buffer_seconds: int
    clip_before_sec: int
    clip_after_sec: int


@dataclass
class NotificationConfig:
    line_token: str
    enabled: bool


@dataclass
class LifecycleConfig:
    clip_retention_days: int
    skeleton_retention_days: int


@dataclass
class Config:
    camera: CameraConfig
    detection: DetectionConfig
    analysis: AnalysisConfig
    recording: RecordingConfig
    notification: NotificationConfig
    lifecycle: LifecycleConfig


def _substitute_env_vars(value: str) -> str:
    pattern = r"\$\{([^}]+)\}"

    def replace(match):
        env_var = match.group(1)
        return os.environ.get(env_var, match.group(0))

    return re.sub(pattern, replace, value)


def _process_config_values(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _process_config_values(value)
        elif isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config/settings.yaml") -> Config:
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    config_data = _process_config_values(raw_config)

    return Config(
        camera=CameraConfig(**config_data["camera"]),
        detection=DetectionConfig(**config_data["detection"]),
        analysis=AnalysisConfig(**config_data["analysis"]),
        recording=RecordingConfig(**config_data["recording"]),
        notification=NotificationConfig(**config_data["notification"]),
        lifecycle=LifecycleConfig(**config_data["lifecycle"]),
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/core/config.py tests/test_config.py
git commit -m "feat: add Config loader with env variable substitution"
```

---

## Task 13: Pipeline Integration

**Files:**
- Create: `src/core/pipeline.py`
- Create: `tests/test_pipeline.py`
- Modify: `main.py`

**Step 1: Write the failing test**

Create `tests/test_pipeline.py`:
```python
import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from src.core.pipeline import Pipeline
from src.core.config import (
    Config, CameraConfig, DetectionConfig, AnalysisConfig,
    RecordingConfig, NotificationConfig, LifecycleConfig
)
from src.detection.bbox import BBox
from src.analysis.delay_confirm import FallState


@pytest.fixture
def mock_config():
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(model="yolov8n.pt", confidence=0.5, classes=[0]),
        analysis=AnalysisConfig(
            fall_threshold=1.3, delay_sec=3.0,
            same_event_window=60.0, re_notify_interval=120.0
        ),
        recording=RecordingConfig(buffer_seconds=10, clip_before_sec=5, clip_after_sec=5),
        notification=NotificationConfig(line_token="test", enabled=False),
        lifecycle=LifecycleConfig(clip_retention_days=7, skeleton_retention_days=30),
    )


class TestPipeline:
    def test_pipeline_init(self, mock_config):
        with patch("src.core.pipeline.Camera"), \
             patch("src.core.pipeline.Detector"), \
             patch("src.core.pipeline.EventLogger"):
            pipeline = Pipeline(config=mock_config)
            assert pipeline.config == mock_config

    def test_process_frame_no_detection(self, mock_config):
        with patch("src.core.pipeline.Camera"), \
             patch("src.core.pipeline.Detector") as mock_detector, \
             patch("src.core.pipeline.EventLogger"):

            mock_detector.return_value.detect.return_value = []

            pipeline = Pipeline(config=mock_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.0)

            assert state == FallState.NORMAL

    def test_process_frame_standing_person(self, mock_config):
        with patch("src.core.pipeline.Camera"), \
             patch("src.core.pipeline.Detector") as mock_detector, \
             patch("src.core.pipeline.EventLogger"):

            standing_bbox = BBox(x=100, y=50, width=100, height=200)
            mock_detector.return_value.detect.return_value = [standing_bbox]

            pipeline = Pipeline(config=mock_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.0)

            assert state == FallState.NORMAL

    def test_process_frame_fallen_person_suspected(self, mock_config):
        with patch("src.core.pipeline.Camera"), \
             patch("src.core.pipeline.Detector") as mock_detector, \
             patch("src.core.pipeline.EventLogger"):

            fallen_bbox = BBox(x=100, y=50, width=200, height=100)
            mock_detector.return_value.detect.return_value = [fallen_bbox]

            pipeline = Pipeline(config=mock_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.0)

            assert state == FallState.SUSPECTED
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `src/core/pipeline.py`:
```python
import logging
import time

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.capture.camera import Camera
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import Config
from src.detection.bbox import BBox
from src.detection.detector import Detector
from src.events.clip_recorder import ClipRecorder
from src.events.event_logger import EventLogger
from src.events.notifier import LineNotifier
from src.events.observer import FallEvent

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: Config):
        self.config = config

        self.camera = Camera(
            source=config.camera.source,
            fps=config.camera.fps,
            resolution=tuple(config.camera.resolution),
        )

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

        self.event_logger = EventLogger()
        self.clip_recorder = ClipRecorder(fps=config.camera.fps)
        self.notifier = LineNotifier(
            token=config.notification.line_token,
            enabled=config.notification.enabled,
        )

        self.delay_confirm.add_observer(self.event_logger)
        self.delay_confirm.add_observer(self.notifier)
        self.delay_confirm.add_observer(self)

        self._current_bbox: BBox | None = None

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
        bboxes = self.detector.detect(frame)

        self._current_bbox = bboxes[0] if bboxes else None

        is_fallen = self.rule_engine.is_fallen(self._current_bbox)

        bbox_tuple = None
        if self._current_bbox:
            bbox_tuple = (
                self._current_bbox.x,
                self._current_bbox.y,
                self._current_bbox.width,
                self._current_bbox.height,
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

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 4 tests PASS

**Step 5: Update main.py**

```python
import logging

from src.core.config import load_config
from src.core.pipeline import Pipeline


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()
    pipeline = Pipeline(config=config)
    pipeline.run()


if __name__ == "__main__":
    main()
```

**Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/core/pipeline.py tests/test_pipeline.py main.py
git commit -m "feat: add Pipeline integration and update main entry point"
```

---

## Task 14: Final Integration Test

**Files:**
- Create: `tests/integration/test_full_pipeline.py`

**Step 1: Write the integration test**

Create `tests/integration/__init__.py` and `tests/integration/test_full_pipeline.py`:
```python
import pytest
import numpy as np
import time
from unittest.mock import patch, MagicMock
from src.core.config import (
    Config, CameraConfig, DetectionConfig, AnalysisConfig,
    RecordingConfig, NotificationConfig, LifecycleConfig
)
from src.core.pipeline import Pipeline
from src.detection.bbox import BBox
from src.analysis.delay_confirm import FallState


@pytest.fixture
def test_config(tmp_path):
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(model="yolov8n.pt", confidence=0.5, classes=[0]),
        analysis=AnalysisConfig(
            fall_threshold=1.3, delay_sec=0.1,
            same_event_window=60.0, re_notify_interval=120.0
        ),
        recording=RecordingConfig(buffer_seconds=2, clip_before_sec=1, clip_after_sec=1),
        notification=NotificationConfig(line_token="test", enabled=False),
        lifecycle=LifecycleConfig(clip_retention_days=7, skeleton_retention_days=30),
    )


class TestFullPipeline:
    def test_fall_detection_flow(self, test_config, tmp_path):
        """Test complete flow: standing -> fall -> confirm -> recover"""
        with patch("src.core.pipeline.Camera") as mock_camera, \
             patch("src.core.pipeline.Detector") as mock_detector, \
             patch("src.events.event_logger.Path") as mock_path:

            mock_path.return_value.parent.mkdir = MagicMock()

            standing_bbox = BBox(x=100, y=50, width=100, height=200)
            fallen_bbox = BBox(x=100, y=50, width=200, height=100)

            pipeline = Pipeline(config=test_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            mock_detector.return_value.detect.return_value = [standing_bbox]
            state = pipeline.process_frame(frame, current_time=0.0)
            assert state == FallState.NORMAL

            mock_detector.return_value.detect.return_value = [fallen_bbox]
            state = pipeline.process_frame(frame, current_time=1.0)
            assert state == FallState.SUSPECTED

            state = pipeline.process_frame(frame, current_time=1.2)
            assert state == FallState.CONFIRMED

            mock_detector.return_value.detect.return_value = [standing_bbox]
            state = pipeline.process_frame(frame, current_time=2.0)
            assert state == FallState.NORMAL
```

**Step 2: Run integration test**

Run: `uv run pytest tests/integration/ -v`
Expected: All tests PASS

**Step 3: Run full test suite**

Run: `uv run pytest -v --cov=src --cov-report=term-missing`
Expected: All tests PASS with coverage report

**Step 4: Commit**

```bash
mkdir -p tests/integration
git add tests/integration/
git commit -m "test: add integration tests for full pipeline flow"
```

---

## Task 15: Final Cleanup and Documentation

**Step 1: Run linter**

Run: `uv run ruff check . --fix`
Expected: No errors (or auto-fixed)

**Step 2: Run formatter**

Run: `uv run ruff format .`
Expected: Files formatted

**Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: lint and format codebase"
```

**Step 5: Tag release**

```bash
git tag -a v0.1.0 -m "Phase 1: Core fall detection system"
```

---

## Summary

**Total Tasks:** 15

**Components Built:**
1. BBox data structure
2. Rule Engine (aspect ratio)
3. Observer Protocol
4. Delay Confirm state machine
5. Rolling Buffer
6. Camera capture
7. YOLOv8 Detector
8. Event Logger (SQLite)
9. Clip Recorder
10. LINE Notifier
11. Config loader
12. Pipeline integration

**Test Coverage:** Unit tests + Integration tests for all components

**Next Phase Candidates:**
- Skeleton extractor (MediaPipe)
- Data lifecycle cleanup
- Cloud sync
- Multiple camera support
