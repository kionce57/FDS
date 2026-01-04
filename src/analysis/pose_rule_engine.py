"""Pose-based rule engine for fall detection using skeleton keypoints."""

from src.detection.skeleton import Skeleton
from src.analysis.smoothing import KeypointSmoother


class PoseRuleEngine:
    """Analyze skeleton pose to determine if a person has fallen.

    Optionally applies keypoint smoothing to reduce noise and false positives.
    """

    def __init__(
        self,
        torso_angle_threshold: float = 60.0,
        min_visibility: float = 0.3,
        enable_smoothing: bool = False,
        smoothing_min_cutoff: float = 1.0,
        smoothing_beta: float = 0.007,
    ):
        """
        Args:
            torso_angle_threshold: Angle from vertical (degrees) above which
                person is considered fallen. 0=standing, 90=horizontal.
            min_visibility: Minimum keypoint visibility to trust the reading.
            enable_smoothing: Enable One Euro Filter smoothing for keypoints.
            smoothing_min_cutoff: Smoother min_cutoff (lower = more smoothing).
            smoothing_beta: Smoother beta (higher = less lag on fast movements).
        """
        self.torso_angle_threshold = torso_angle_threshold
        self.min_visibility = min_visibility

        self._enable_smoothing = enable_smoothing
        self._smoother: KeypointSmoother | None = None
        if enable_smoothing:
            self._smoother = KeypointSmoother(
                min_cutoff=smoothing_min_cutoff,
                beta=smoothing_beta,
                confidence_threshold=min_visibility,
            )

    def is_fallen(self, skeleton: Skeleton | None, timestamp: float | None = None) -> bool:
        """Determine if the skeleton pose indicates a fall.

        Uses torso angle as the primary indicator:
        - Standing: torso near vertical (angle < threshold)
        - Fallen: torso near horizontal (angle >= threshold)

        Args:
            skeleton: Detected skeleton or None if no detection.
            timestamp: Frame timestamp in seconds. Required if smoothing is enabled.

        Returns:
            True if fall is detected, False otherwise.
        """
        if skeleton is None:
            return False

        # Apply smoothing if enabled and timestamp provided
        if self._smoother is not None and timestamp is not None:
            skeleton = self._smoother.smooth(skeleton, timestamp)

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

    def get_fall_confidence(
        self, skeleton: Skeleton | None, timestamp: float | None = None
    ) -> float:
        """Get confidence score for fall detection (0.0 to 1.0).

        Higher value = more confident the person has fallen.

        Args:
            skeleton: Detected skeleton or None if no detection.
            timestamp: Frame timestamp in seconds. Required if smoothing is enabled.

        Returns:
            Confidence score from 0.0 (definitely not fallen) to 1.0 (definitely fallen).
        """
        if skeleton is None:
            return 0.0

        # Apply smoothing if enabled and timestamp provided
        if self._smoother is not None and timestamp is not None:
            skeleton = self._smoother.smooth(skeleton, timestamp)

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

    def reset_smoother(self) -> None:
        """Reset the keypoint smoother state.

        Call this when tracking is lost or a new person is detected.
        """
        if self._smoother is not None:
            self._smoother.reset()
