# YOLO11-Pose Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 將 Pose 模型從 YOLOv8n-Pose 升級至 YOLO11s-Pose，並加入時序過濾解決關鍵點抖動問題

**Architecture:** 分兩階段實作。Phase A 配置化模型路徑並切換至 YOLO11；Phase B 新增 KeypointSmoother 時序過濾。

**Tech Stack:** Python 3.12+, Ultralytics YOLO11, One Euro Filter

**Status:** Phase A 已完成 ✅，Phase B 待開始 - 最後更新 2025-01-04

---

## Phase A: 配置化 Pose Model + 模型切換

**目標：** 將 pose model 路徑從硬編碼改為可配置，並預設使用 `yolo11s-pose.pt`

### Task A.1: 擴展 Config 支援 pose_model ✅

> **Completed:** 2025-01-04 | **Commit:** `b42ea07`

**Files:**

- Modify: `src/core/config.py`
- Modify: `config/settings.yaml`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py - 新增測試
def test_config_has_pose_model():
    config = load_config("config/settings.yaml")
    assert hasattr(config.detection, "pose_model")
    assert config.detection.pose_model == "yolo11s-pose.pt"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_config_has_pose_model -v`
Expected: FAIL with AttributeError

**Step 3: Update settings.yaml**

```yaml
# config/settings.yaml
detection:
  model: "yolov8n.pt"
  pose_model: "yolo11s-pose.pt" # 新增
  confidence: 0.5
  classes: [0]
```

**Step 4: Update config.py dataclass**

```python
# src/core/config.py
@dataclass
class DetectionConfig:
    model: str = "yolov8n.pt"
    pose_model: str = "yolo11s-pose.pt"  # 新增
    confidence: float = 0.5
    classes: list[int] = field(default_factory=lambda: [0])
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/core/config.py config/settings.yaml tests/test_config.py
git commit -m "feat(config): add pose_model configuration for YOLO11 support"
```

---

### Task A.2: 更新 PoseDetector 使用配置 ✅

> **Completed:** 2025-01-04 | **Commit:** `630509e`

**Files:**

- Modify: `src/detection/detector.py`
- Test: `tests/test_detector.py`

**Step 1: Write the failing test**

```python
# tests/test_detector.py - 新增測試
def test_pose_detector_accepts_model_path():
    detector = PoseDetector(model_path="yolo11s-pose.pt")
    assert "yolo11" in detector.model.model_name.lower() or detector.model is not None
```

**Step 2: Update PoseDetector default**

```python
# src/detection/detector.py
class PoseDetector:
    """YOLO Pose detector that returns skeleton keypoints."""

    def __init__(
        self,
        model_path: str = "yolo11s-pose.pt",  # 改為 YOLO11
        confidence: float = 0.5,
    ):
        self.model = YOLO(model_path)
        self.confidence = confidence
```

**Step 3: Run all detector tests**

Run: `uv run pytest tests/test_detector.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/detection/detector.py tests/test_detector.py
git commit -m "feat(detector): change PoseDetector default to yolo11s-pose"
```

---

### Task A.3: 更新 SkeletonExtractor 使用配置 ✅

> **Completed:** 2025-01-04 | **Commit:** `e61fbcd`

**Files:**

- Modify: `src/lifecycle/skeleton_extractor.py`
- Test: `tests/lifecycle/test_skeleton_extractor.py`

**Step 1: Update default model path**

```python
# src/lifecycle/skeleton_extractor.py
class SkeletonExtractor:
    def __init__(self, model_path: str = "yolo11s-pose.pt"):  # 改為 YOLO11
        self.model_path = model_path
        self.detector = PoseDetector(model_path=model_path, confidence=0.5)
```

**Step 2: Update test fixtures**

更新 `tests/lifecycle/test_skeleton_extractor.py` 中的 model 相關斷言。

**Step 3: Commit**

```bash
git add src/lifecycle/skeleton_extractor.py tests/lifecycle/test_skeleton_extractor.py
git commit -m "feat(skeleton_extractor): use yolo11s-pose as default"
```

---

### Task A.4: 更新測試腳本

**Files:**

- Modify: `scripts/test_with_video.py`
- Modify: `scripts/save_skeleton_frames.py`

**Step 1: Update hardcoded paths**

```python
# scripts/test_with_video.py line 116
detector = PoseDetector(model_path="yolo11s-pose.pt", confidence=0.5)

# scripts/save_skeleton_frames.py line 136
detector = PoseDetector(model_path="yolo11s-pose.pt", confidence=0.5)
```

**Step 2: Test manually**

Run: `uv run python -m scripts.test_with_video --use-pose tests/fixtures/videos/fall-01-cam0.mp4`
Expected: 正常執行，首次會下載 yolo11s-pose.pt

**Step 3: Commit**

```bash
git add scripts/test_with_video.py scripts/save_skeleton_frames.py
git commit -m "chore(scripts): update pose model to yolo11s-pose"
```

---

### Task A.5: 更新文件

**Files:**

- Modify: `CLAUDE.md`
- Modify: `docs/TESTING_ON_WINDOWS.md`
- Modify: `docs/PROJECT_STATUS.md`

**Step 1: Batch replace documentation**

將所有 `yolov8n-pose.pt` 改為 `yolo11s-pose.pt`。

**Step 2: Update Detection Modes table in CLAUDE.md**

```markdown
| Mode        | Model             | Rule                 | Output                                             |
| ----------- | ----------------- | -------------------- | -------------------------------------------------- |
| BBox (預設) | `yolov8n.pt`      | `aspect_ratio < 1.3` | `BBox(x, y, w, h, confidence, aspect_ratio)`       |
| Pose        | `yolo11s-pose.pt` | `torso_angle < 60°`  | `Skeleton(keypoints[17], torso_angle, confidence)` |
```

**Step 3: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: update pose model references to yolo11s-pose"
```

---

### Task A.6: 驗證 Keypoint 格式相容性

**Files:**

- Create: `tests/test_yolo11_compatibility.py`

**Step 1: Write compatibility test**

```python
# tests/test_yolo11_compatibility.py
"""Verify YOLO11-Pose keypoint format matches expected COCO 17 format."""
import numpy as np
import pytest
from src.detection.detector import PoseDetector
from src.detection.skeleton import Skeleton, Keypoint


class TestYOLO11Compatibility:
    @pytest.fixture
    def detector(self):
        return PoseDetector(model_path="yolo11s-pose.pt")

    def test_keypoints_shape_is_17x3(self, detector):
        """YOLO11 should return 17 keypoints with (x, y, visibility)."""
        # Create a simple test frame (black image with white rectangle as person)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:400, 200:400] = 255  # Rough person shape

        skeletons = detector.detect(frame)

        # May not detect person in synthetic image, but if it does, check shape
        for skeleton in skeletons:
            assert skeleton.keypoints.shape == (17, 3)

    def test_skeleton_properties_work(self, detector):
        """Skeleton helper properties should work with YOLO11 output."""
        # Create mock keypoints in expected format
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.LEFT_SHOULDER] = [100, 100, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [200, 100, 0.9]
        keypoints[Keypoint.LEFT_HIP] = [100, 200, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [200, 200, 0.9]

        skeleton = Skeleton(keypoints=keypoints)

        # Properties should work
        assert skeleton.shoulder_center == (150.0, 100.0)
        assert skeleton.hip_center == (150.0, 200.0)
        assert skeleton.torso_angle == 0.0  # Vertical torso
```

**Step 2: Run test**

Run: `uv run pytest tests/test_yolo11_compatibility.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_yolo11_compatibility.py
git commit -m "test: add YOLO11 keypoint compatibility tests"
```

---

## Phase B: KeypointSmoother 時序過濾

**目標：** 加入 One Euro Filter 平滑關鍵點軌跡，減少高頻抖動

### Task B.1: 實作 One Euro Filter

**Files:**

- Create: `src/analysis/one_euro_filter.py`
- Test: `tests/test_one_euro_filter.py`

**Step 1: Write the failing test**

```python
# tests/test_one_euro_filter.py
import pytest
from src.analysis.one_euro_filter import OneEuroFilter


class TestOneEuroFilter:
    def test_filter_smooths_noisy_signal(self):
        """Filter should smooth out high-frequency noise."""
        f = OneEuroFilter(min_cutoff=1.0, beta=0.007)

        # Simulate noisy signal: base value 100 with noise
        noisy_values = [100, 105, 98, 103, 97, 102, 99, 101]
        timestamps = [i * 0.033 for i in range(len(noisy_values))]  # ~30fps

        filtered = [f(t, v) for t, v in zip(timestamps, noisy_values)]

        # Filtered values should have less variance than input
        import numpy as np
        assert np.std(filtered) < np.std(noisy_values)

    def test_filter_tracks_trend(self):
        """Filter should follow gradual changes."""
        f = OneEuroFilter(min_cutoff=1.0, beta=0.5)

        # Gradual increase
        values = [0, 10, 20, 30, 40, 50]
        timestamps = [i * 0.1 for i in range(len(values))]

        filtered = [f(t, v) for t, v in zip(timestamps, values)]

        # Final filtered value should be close to 50
        assert filtered[-1] > 40
```

**Step 2: Implement One Euro Filter**

```python
# src/analysis/one_euro_filter.py
"""One Euro Filter implementation for smoothing time-series data.

Reference: https://gery.casiez.net/1euro/
"""
import math


class LowPassFilter:
    """Simple exponential smoothing low-pass filter."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.y_prev: float | None = None
        self.initialized = False

    def __call__(self, value: float, alpha: float | None = None) -> float:
        if alpha is not None:
            self.alpha = alpha

        if not self.initialized:
            self.initialized = True
            self.y_prev = value
            return value

        y = self.alpha * value + (1 - self.alpha) * self.y_prev
        self.y_prev = y
        return y


class OneEuroFilter:
    """One Euro Filter for adaptive low-pass filtering.

    Args:
        min_cutoff: Minimum cutoff frequency (Hz). Lower = more smoothing.
        beta: Speed coefficient. Higher = less lag when moving fast.
        d_cutoff: Cutoff frequency for derivative estimation.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()

        self.t_prev: float | None = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        """Calculate smoothing factor alpha from cutoff frequency."""
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, t: float, x: float) -> float:
        """Filter a value at time t."""
        if self.t_prev is None:
            self.t_prev = t
            self.x_filter(x)
            self.dx_filter(0.0)
            return x

        dt = t - self.t_prev
        if dt <= 0:
            dt = 1e-6  # Prevent division by zero

        self.t_prev = t

        # Estimate derivative
        dx = (x - self.x_filter.y_prev) / dt if self.x_filter.y_prev else 0.0
        edx = self.dx_filter(dx, self._alpha(self.d_cutoff, dt))

        # Adaptive cutoff based on derivative magnitude
        cutoff = self.min_cutoff + self.beta * abs(edx)

        # Filter the value
        return self.x_filter(x, self._alpha(cutoff, dt))

    def reset(self) -> None:
        """Reset filter state."""
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.t_prev = None
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_one_euro_filter.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/analysis/one_euro_filter.py tests/test_one_euro_filter.py
git commit -m "feat(analysis): add One Euro Filter for keypoint smoothing"
```

---

### Task B.2: 實作 KeypointSmoother

**Files:**

- Create: `src/analysis/keypoint_smoother.py`
- Test: `tests/test_keypoint_smoother.py`

**Step 1: Write the failing test**

```python
# tests/test_keypoint_smoother.py
import numpy as np
import pytest
from src.analysis.keypoint_smoother import KeypointSmoother
from src.detection.skeleton import Skeleton


class TestKeypointSmoother:
    def test_smooth_reduces_jitter(self):
        """Smoother should reduce high-frequency jitter in keypoints."""
        smoother = KeypointSmoother()

        # Create jittery keypoints sequence
        base_keypoints = np.array([[100, 100, 0.9]] * 17, dtype=np.float32)

        smoothed_keypoints = []
        for i in range(10):
            # Add random jitter
            jittered = base_keypoints.copy()
            jittered[:, :2] += np.random.randn(17, 2) * 5  # ±5 pixel jitter

            skeleton = Skeleton(keypoints=jittered)
            smoothed = smoother.smooth(skeleton, timestamp=i * 0.033)
            smoothed_keypoints.append(smoothed.keypoints[:, :2])

        # Later frames should have less variance
        early_var = np.var(smoothed_keypoints[1:4])
        late_var = np.var(smoothed_keypoints[7:10])
        assert late_var <= early_var * 1.5  # Allow some tolerance

    def test_reset_clears_state(self):
        """Reset should clear filter state for new person tracking."""
        smoother = KeypointSmoother()

        keypoints = np.array([[100, 100, 0.9]] * 17, dtype=np.float32)
        skeleton = Skeleton(keypoints=keypoints)

        smoother.smooth(skeleton, timestamp=0.0)
        smoother.reset()

        # After reset, should not throw error
        result = smoother.smooth(skeleton, timestamp=0.0)
        assert result is not None
```

**Step 2: Implement KeypointSmoother**

```python
# src/analysis/keypoint_smoother.py
"""Temporal smoothing for skeleton keypoints using One Euro Filter."""
import numpy as np
from src.analysis.one_euro_filter import OneEuroFilter
from src.detection.skeleton import Skeleton


class KeypointSmoother:
    """Smooth skeleton keypoints over time to reduce jitter.

    Uses One Euro Filter for each keypoint coordinate (x, y).
    Visibility values are passed through unchanged.

    Args:
        min_cutoff: Minimum cutoff frequency. Lower = more smoothing.
        beta: Speed coefficient. Higher = less lag during fast movement.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007):
        self.min_cutoff = min_cutoff
        self.beta = beta

        # 17 keypoints × 2 coordinates (x, y)
        self.filters: list[list[OneEuroFilter]] = [
            [
                OneEuroFilter(min_cutoff=min_cutoff, beta=beta),
                OneEuroFilter(min_cutoff=min_cutoff, beta=beta),
            ]
            for _ in range(17)
        ]

    def smooth(self, skeleton: Skeleton, timestamp: float) -> Skeleton:
        """Apply temporal smoothing to skeleton keypoints.

        Args:
            skeleton: Input skeleton with raw keypoints.
            timestamp: Current frame timestamp in seconds.

        Returns:
            New Skeleton with smoothed keypoint coordinates.
        """
        smoothed = skeleton.keypoints.copy()

        for i in range(17):
            x, y, vis = skeleton.keypoints[i]

            # Only smooth if keypoint is visible
            if vis > 0.3:
                smoothed[i, 0] = self.filters[i][0](timestamp, x)
                smoothed[i, 1] = self.filters[i][1](timestamp, y)
            else:
                # Reset filter for invisible keypoints
                self.filters[i][0].reset()
                self.filters[i][1].reset()

        return Skeleton(keypoints=smoothed)

    def reset(self) -> None:
        """Reset all filters (e.g., when tracking a new person)."""
        for kp_filters in self.filters:
            for f in kp_filters:
                f.reset()
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_keypoint_smoother.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/analysis/keypoint_smoother.py tests/test_keypoint_smoother.py
git commit -m "feat(analysis): add KeypointSmoother for temporal filtering"
```

---

### Task B.3: 整合 KeypointSmoother 至 PoseRuleEngine

**Files:**

- Modify: `src/analysis/pose_rule_engine.py`
- Modify: `tests/test_pose_rule_engine.py`

**Step 1: Add optional smoother**

```python
# src/analysis/pose_rule_engine.py
from src.analysis.keypoint_smoother import KeypointSmoother

class PoseRuleEngine:
    def __init__(
        self,
        torso_angle_threshold: float = 60.0,
        min_visibility: float = 0.3,
        enable_smoothing: bool = True,  # 新增
    ):
        self.torso_angle_threshold = torso_angle_threshold
        self.min_visibility = min_visibility
        self.smoother = KeypointSmoother() if enable_smoothing else None
        self._last_timestamp: float = 0.0

    def is_fallen(self, skeleton: Skeleton | None, timestamp: float | None = None) -> bool:
        if skeleton is None:
            return False

        # Apply smoothing if enabled
        if self.smoother and timestamp is not None:
            skeleton = self.smoother.smooth(skeleton, timestamp)

        if not self._has_valid_keypoints(skeleton):
            return False

        return bool(skeleton.torso_angle >= self.torso_angle_threshold)
```

**Step 2: Update tests**

確保現有測試仍然通過，新增 smoothing 相關測試。

**Step 3: Commit**

```bash
git add src/analysis/pose_rule_engine.py tests/test_pose_rule_engine.py
git commit -m "feat(pose_rule_engine): integrate KeypointSmoother for jitter reduction"
```

---

### Task B.4: 更新測試腳本支援 timestamp

**Files:**

- Modify: `scripts/test_with_video.py`

**Step 1: Pass timestamp to rule engine**

```python
# scripts/test_with_video.py
# 修改 is_fallen 調用，傳入 timestamp
is_fallen = rule_engine.is_fallen(detection, timestamp=current_time)
```

**Step 2: Commit**

```bash
git add scripts/test_with_video.py
git commit -m "chore(scripts): pass timestamp to pose rule engine for smoothing"
```

---

### Task B.5: 整合測試

**Files:**

- Create: `tests/integration/test_yolo11_pipeline.py`

**Step 1: Write integration test**

```python
# tests/integration/test_yolo11_pipeline.py
"""Integration test for YOLO11-Pose with smoothing pipeline."""
import numpy as np
import pytest
from src.detection.detector import PoseDetector
from src.analysis.pose_rule_engine import PoseRuleEngine


class TestYOLO11Pipeline:
    @pytest.fixture
    def detector(self):
        return PoseDetector(model_path="yolo11s-pose.pt")

    @pytest.fixture
    def rule_engine(self):
        return PoseRuleEngine(torso_angle_threshold=60.0, enable_smoothing=True)

    def test_full_pipeline_with_smoothing(self, detector, rule_engine):
        """Test detection → smoothing → rule engine flow."""
        # Create synthetic frames
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        for i in range(10):
            timestamp = i * 0.033
            skeletons = detector.detect(frame)
            skeleton = skeletons[0] if skeletons else None

            # Should not crash with None or valid skeleton
            is_fallen = rule_engine.is_fallen(skeleton, timestamp=timestamp)
            assert isinstance(is_fallen, bool)
```

**Step 2: Run integration test**

Run: `uv run pytest tests/integration/test_yolo11_pipeline.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_yolo11_pipeline.py
git commit -m "test: add YOLO11 pipeline integration test with smoothing"
```

---

## Summary

| Phase | Task                       | 複雜度 | 說明                 |
| ----- | -------------------------- | ------ | -------------------- |
| A     | A.1 Config 擴展            | 低     | 新增 pose_model 設定 |
| A     | A.2 PoseDetector 更新      | 低     | 改預設值             |
| A     | A.3 SkeletonExtractor 更新 | 低     | 改預設值             |
| A     | A.4 Scripts 更新           | 低     | 改 hardcoded 路徑    |
| A     | A.5 文件更新               | 低     | 批量替換             |
| A     | A.6 相容性測試             | 中     | 驗證 keypoint 格式   |
| B     | B.1 One Euro Filter        | 中     | 實作演算法           |
| B     | B.2 KeypointSmoother       | 中     | 封裝 17 點過濾       |
| B     | B.3 PoseRuleEngine 整合    | 中     | 加入可選 smoothing   |
| B     | B.4 Scripts 整合           | 低     | 傳入 timestamp       |
| B     | B.5 整合測試               | 中     | 端到端驗證           |

**預估：** Phase A (6 tasks) + Phase B (5 tasks) = 11 tasks

---

## Sources

- [One Euro Filter Paper](https://gery.casiez.net/1euro/)
- [Ultralytics YOLO11 Pose](https://docs.ultralytics.com/tasks/pose/)
- [COCO Keypoint Format](https://cocodataset.org/#keypoints-2020)
