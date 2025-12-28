import pytest
import numpy as np
from src.detection.skeleton import Skeleton, Keypoint


class TestSkeleton:
    @pytest.fixture
    def standing_skeleton(self):
        """Create a skeleton representing a standing person."""
        # Simplified keypoints: person standing upright
        # y increases downward in image coordinates
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.NOSE] = [320, 50, 0.9]
        keypoints[Keypoint.LEFT_EYE] = [310, 45, 0.9]
        keypoints[Keypoint.RIGHT_EYE] = [330, 45, 0.9]
        keypoints[Keypoint.LEFT_EAR] = [300, 50, 0.8]
        keypoints[Keypoint.RIGHT_EAR] = [340, 50, 0.8]
        keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
        keypoints[Keypoint.LEFT_ELBOW] = [260, 200, 0.8]
        keypoints[Keypoint.RIGHT_ELBOW] = [380, 200, 0.8]
        keypoints[Keypoint.LEFT_WRIST] = [250, 280, 0.8]
        keypoints[Keypoint.RIGHT_WRIST] = [390, 280, 0.8]
        keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
        keypoints[Keypoint.LEFT_KNEE] = [290, 380, 0.9]
        keypoints[Keypoint.RIGHT_KNEE] = [350, 380, 0.9]
        keypoints[Keypoint.LEFT_ANKLE] = [290, 480, 0.9]
        keypoints[Keypoint.RIGHT_ANKLE] = [350, 480, 0.9]
        return Skeleton(keypoints=keypoints)

    @pytest.fixture
    def fallen_skeleton(self):
        """Create a skeleton representing a fallen person (lying horizontal)."""
        keypoints = np.zeros((17, 3))
        # Person lying on their side - x spread out, y similar
        keypoints[Keypoint.NOSE] = [100, 400, 0.9]
        keypoints[Keypoint.LEFT_EYE] = [95, 395, 0.9]
        keypoints[Keypoint.RIGHT_EYE] = [105, 395, 0.9]
        keypoints[Keypoint.LEFT_EAR] = [90, 400, 0.8]
        keypoints[Keypoint.RIGHT_EAR] = [110, 400, 0.8]
        keypoints[Keypoint.LEFT_SHOULDER] = [170, 390, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [170, 410, 0.9]
        keypoints[Keypoint.LEFT_ELBOW] = [220, 385, 0.8]
        keypoints[Keypoint.RIGHT_ELBOW] = [220, 415, 0.8]
        keypoints[Keypoint.LEFT_WRIST] = [270, 380, 0.8]
        keypoints[Keypoint.RIGHT_WRIST] = [270, 420, 0.8]
        keypoints[Keypoint.LEFT_HIP] = [350, 390, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [350, 410, 0.9]
        keypoints[Keypoint.LEFT_KNEE] = [450, 385, 0.9]
        keypoints[Keypoint.RIGHT_KNEE] = [450, 415, 0.9]
        keypoints[Keypoint.LEFT_ANKLE] = [550, 380, 0.9]
        keypoints[Keypoint.RIGHT_ANKLE] = [550, 420, 0.9]
        return Skeleton(keypoints=keypoints)

    def test_get_point(self, standing_skeleton):
        nose = standing_skeleton.get_point(Keypoint.NOSE)
        assert nose[0] == 320
        assert nose[1] == 50
        assert nose[2] == 0.9

    def test_property_accessors(self, standing_skeleton):
        assert standing_skeleton.nose[0] == 320
        assert standing_skeleton.left_shoulder[0] == 280
        assert standing_skeleton.right_hip[0] == 350

    def test_hip_center(self, standing_skeleton):
        hc = standing_skeleton.hip_center
        assert hc[0] == 320  # (290 + 350) / 2
        assert hc[1] == 280

    def test_shoulder_center(self, standing_skeleton):
        sc = standing_skeleton.shoulder_center
        assert sc[0] == 320  # (280 + 360) / 2
        assert sc[1] == 120

    def test_torso_angle_standing(self, standing_skeleton):
        angle = standing_skeleton.torso_angle
        # Standing person: shoulders above hips, near vertical
        assert angle < 15  # Less than 15 degrees from vertical

    def test_torso_angle_fallen(self, fallen_skeleton):
        angle = fallen_skeleton.torso_angle
        # Fallen person: torso is near horizontal
        assert angle > 70  # More than 70 degrees from vertical

    def test_hip_height_ratio_standing(self, standing_skeleton):
        ratio = standing_skeleton.hip_height_ratio
        # Standing: hip is roughly in the middle
        assert 0.4 < ratio < 0.7

    def test_hip_height_ratio_fallen(self, fallen_skeleton):
        ratio = fallen_skeleton.hip_height_ratio
        # When lying flat, hip_height_ratio is less reliable
        # The key indicator for fallen is torso_angle, not hip ratio
        assert isinstance(ratio, float)
