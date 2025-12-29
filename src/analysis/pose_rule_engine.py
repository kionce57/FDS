"""Pose-based rule engine for fall detection using skeleton keypoints."""

from src.detection.skeleton import Skeleton


class PoseRuleEngine:
    """Analyze skeleton pose to determine if a person has fallen."""

    def __init__(
        self,
        torso_angle_threshold: float = 60.0,
        min_visibility: float = 0.3,
    ):
        """
        Args:
            torso_angle_threshold: Angle from vertical (degrees) above which
                person is considered fallen. 0=standing, 90=horizontal.
            min_visibility: Minimum keypoint visibility to trust the reading.
        """
        self.torso_angle_threshold = torso_angle_threshold
        self.min_visibility = min_visibility

    def is_fallen(self, skeleton: Skeleton | None) -> bool:
        """Determine if the skeleton pose indicates a fall.

        Uses torso angle as the primary indicator:
        - Standing: torso near vertical (angle < threshold)
        - Fallen: torso near horizontal (angle >= threshold)
        """
        if skeleton is None:
            return False

        # Check if key points have sufficient visibility
        if not self._has_valid_keypoints(skeleton):
            return False

        # Primary check: torso angle
        torso_angle = skeleton.torso_angle
        return bool(torso_angle >= self.torso_angle_threshold)

    def _has_valid_keypoints(self, skeleton: Skeleton) -> bool:
        """Check if required keypoints have sufficient visibility."""
        required_points = [
            skeleton.left_shoulder,
            skeleton.right_shoulder,
            skeleton.left_hip,
            skeleton.right_hip,
        ]

        for point in required_points:
            if point[2] < self.min_visibility:
                return False
        return True

    def get_fall_confidence(self, skeleton: Skeleton | None) -> float:
        """Get confidence score for fall detection (0.0 to 1.0).

        Higher value = more confident the person has fallen.
        """
        if skeleton is None:
            return 0.0

        if not self._has_valid_keypoints(skeleton):
            return 0.0

        torso_angle = skeleton.torso_angle

        # Map torso angle to confidence
        # 0-30 degrees: low confidence (standing)
        # 30-60 degrees: medium confidence (crouching/sitting)
        # 60-90 degrees: high confidence (fallen)
        if torso_angle < 30:
            return 0.0
        elif torso_angle < 60:
            return (torso_angle - 30) / 60  # 0.0 to 0.5
        else:
            return 0.5 + min((torso_angle - 60) / 60, 0.5)  # 0.5 to 1.0
