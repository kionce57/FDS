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
