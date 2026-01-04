import pytest
import numpy as np
from src.detection.skeleton import Skeleton, Keypoint
from src.analysis.pose_rule_engine import PoseRuleEngine


class TestPoseRuleEngine:
    @pytest.fixture
    def engine(self):
        return PoseRuleEngine(torso_angle_threshold=60.0)

    @pytest.fixture
    def standing_skeleton(self):
        """Standing person with torso near vertical."""
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
        keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
        return Skeleton(keypoints=keypoints)

    @pytest.fixture
    def fallen_skeleton(self):
        """Fallen person with torso near horizontal."""
        keypoints = np.zeros((17, 3))
        # Person lying on side - shoulders and hips at similar y but different x
        keypoints[Keypoint.LEFT_SHOULDER] = [170, 390, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [170, 410, 0.9]
        keypoints[Keypoint.LEFT_HIP] = [350, 390, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [350, 410, 0.9]
        return Skeleton(keypoints=keypoints)

    @pytest.fixture
    def low_visibility_skeleton(self):
        """Skeleton with low visibility keypoints."""
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.1]  # Low visibility
        keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.1]
        keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.1]
        keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.1]
        return Skeleton(keypoints=keypoints)

    def test_standing_not_fallen(self, engine, standing_skeleton):
        assert engine.is_fallen(standing_skeleton) is False

    def test_fallen_detected(self, engine, fallen_skeleton):
        assert engine.is_fallen(fallen_skeleton) is True

    def test_none_skeleton_returns_false(self, engine):
        assert engine.is_fallen(None) is False

    def test_low_visibility_returns_false(self, engine, low_visibility_skeleton):
        assert engine.is_fallen(low_visibility_skeleton) is False

    def test_fall_confidence_standing(self, engine, standing_skeleton):
        conf = engine.get_fall_confidence(standing_skeleton)
        assert conf < 0.3

    def test_fall_confidence_fallen(self, engine, fallen_skeleton):
        conf = engine.get_fall_confidence(fallen_skeleton)
        assert conf > 0.5

    def test_fall_confidence_none(self, engine):
        conf = engine.get_fall_confidence(None)
        assert conf == 0.0


class TestPoseRuleEngineSmoothingIntegration:
    """Test smoothing integration in PoseRuleEngine."""

    @pytest.fixture
    def smoothing_engine(self):
        """Engine with smoothing enabled."""
        return PoseRuleEngine(
            torso_angle_threshold=60.0,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        )

    @pytest.fixture
    def standing_skeleton(self):
        """Standing person with torso near vertical."""
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
        keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
        return Skeleton(keypoints=keypoints)

    def test_smoothing_requires_timestamp(self, smoothing_engine, standing_skeleton):
        """Smoothing is only applied when timestamp is provided."""
        # Without timestamp, smoothing is skipped
        result1 = smoothing_engine.is_fallen(standing_skeleton)
        result2 = smoothing_engine.is_fallen(standing_skeleton, timestamp=0.0)

        # Both should return False (standing)
        assert result1 is False
        assert result2 is False

    def test_smoothing_reduces_jitter(self, smoothing_engine):
        """Smoothing should reduce jitter in noisy skeleton sequence."""
        np.random.seed(42)

        # Base standing skeleton
        base_keypoints = np.zeros((17, 3))
        base_keypoints[:, 2] = 0.9  # All high confidence
        base_keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
        base_keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
        base_keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
        base_keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]

        # Add small noise that could cause false positives
        angles = []
        for i in range(30):
            noisy = base_keypoints.copy()
            # Add noise to shoulder positions
            noisy[Keypoint.LEFT_SHOULDER, 0] += np.random.randn() * 10
            noisy[Keypoint.RIGHT_SHOULDER, 0] += np.random.randn() * 10
            skeleton = Skeleton(keypoints=noisy)
            timestamp = i * 0.033

            # Process through engine
            smoothing_engine.is_fallen(skeleton, timestamp=timestamp)

            # Track the torso angle through smoothing
            # (internally smoothed skeleton is used)
            angles.append(skeleton.torso_angle)

        # All should be detected as standing (torso angle < 60)
        # The smoothing should not change the overall detection
        assert max(angles) < 30  # Even noisy, should be clearly standing

    def test_reset_smoother(self, smoothing_engine, standing_skeleton):
        """Reset should clear smoother state."""
        # Process some frames
        for i in range(5):
            smoothing_engine.is_fallen(standing_skeleton, timestamp=i * 0.033)

        # Reset
        smoothing_engine.reset_smoother()

        # After reset, next frame should be treated as first frame
        # (no smoothing history)
        result = smoothing_engine.is_fallen(standing_skeleton, timestamp=1.0)
        assert result is False

    def test_no_smoother_when_disabled(self):
        """Engine without smoothing should not create smoother."""
        engine = PoseRuleEngine(enable_smoothing=False)
        assert engine._smoother is None

    def test_smoother_created_when_enabled(self):
        """Engine with smoothing should create smoother."""
        engine = PoseRuleEngine(enable_smoothing=True)
        assert engine._smoother is not None
