"""Keypoint smoother for reducing pose estimation jitter.

Uses One Euro Filter to smooth each keypoint coordinate independently,
providing adaptive noise reduction while preserving fast movements.
"""

import numpy as np

from src.detection.skeleton import Skeleton, Keypoint
from .one_euro_filter import OneEuroFilter


class KeypointSmoother:
    """Smoother for 17-keypoint pose estimation (COCO format).

    Applies One Euro Filter to each keypoint's x and y coordinates to reduce
    noise and jitter in pose estimation while preserving quick movements.

    Args:
        min_cutoff: Minimum cutoff frequency. Lower = more smoothing.
                   Default 1.0 for typical 30fps video.
        beta: Speed coefficient. Higher = less smoothing during fast motion.
              Default 0.007 tuned for human pose tracking.
        d_cutoff: Derivative cutoff for speed estimation. Default 1.0.
        confidence_threshold: Minimum confidence to apply smoothing.
                             Below this, the keypoint is reset. Default 0.3.

    Example:
        >>> smoother = KeypointSmoother(min_cutoff=1.0, beta=0.007)
        >>> smoothed = smoother.smooth(skeleton, timestamp=0.033)
    """

    NUM_KEYPOINTS = 17  # COCO format

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
        confidence_threshold: float = 0.3,
    ):
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff
        self._confidence_threshold = confidence_threshold

        # Create filters for each keypoint's x and y coordinates
        self._filters_x: list[OneEuroFilter] = []
        self._filters_y: list[OneEuroFilter] = []
        self._init_filters()

        # Track which keypoints have valid history
        self._keypoint_initialized: list[bool] = [False] * self.NUM_KEYPOINTS

    def _init_filters(self) -> None:
        """Initialize One Euro filters for all keypoints."""
        self._filters_x = [
            OneEuroFilter(self._min_cutoff, self._beta, self._d_cutoff)
            for _ in range(self.NUM_KEYPOINTS)
        ]
        self._filters_y = [
            OneEuroFilter(self._min_cutoff, self._beta, self._d_cutoff)
            for _ in range(self.NUM_KEYPOINTS)
        ]

    def smooth(self, skeleton: Skeleton, timestamp: float) -> Skeleton:
        """Apply smoothing to skeleton keypoints.

        Args:
            skeleton: Input skeleton with raw keypoint coordinates
            timestamp: Current frame timestamp in seconds

        Returns:
            New Skeleton with smoothed keypoint coordinates
        """
        smoothed_keypoints = skeleton.keypoints.copy()

        for i in range(self.NUM_KEYPOINTS):
            x, y, conf = skeleton.keypoints[i]

            if conf < self._confidence_threshold:
                # Low confidence - reset filter for this keypoint
                if self._keypoint_initialized[i]:
                    self._filters_x[i].reset()
                    self._filters_y[i].reset()
                    self._keypoint_initialized[i] = False
                # Keep original values (no smoothing)
                continue

            # Apply One Euro Filter to x and y
            smoothed_x = self._filters_x[i].filter(x, timestamp)
            smoothed_y = self._filters_y[i].filter(y, timestamp)
            self._keypoint_initialized[i] = True

            smoothed_keypoints[i] = [smoothed_x, smoothed_y, conf]

        return Skeleton(keypoints=smoothed_keypoints)

    def smooth_batch(
        self, skeletons: list[Skeleton], timestamps: list[float]
    ) -> list[Skeleton]:
        """Smooth a batch of skeletons with corresponding timestamps.

        Args:
            skeletons: List of Skeleton objects in temporal order
            timestamps: List of timestamps (seconds) for each skeleton

        Returns:
            List of smoothed Skeleton objects

        Raises:
            ValueError: If skeletons and timestamps have different lengths
        """
        if len(skeletons) != len(timestamps):
            raise ValueError(
                f"skeletons ({len(skeletons)}) and timestamps ({len(timestamps)}) "
                "must have same length"
            )

        return [self.smooth(s, t) for s, t in zip(skeletons, timestamps)]

    def reset(self) -> None:
        """Reset all filters for a new tracking session."""
        self._init_filters()
        self._keypoint_initialized = [False] * self.NUM_KEYPOINTS

    def reset_keypoint(self, keypoint: Keypoint) -> None:
        """Reset filter for a specific keypoint.

        Args:
            keypoint: The keypoint index to reset
        """
        idx = int(keypoint)
        self._filters_x[idx].reset()
        self._filters_y[idx].reset()
        self._keypoint_initialized[idx] = False


__all__ = ["KeypointSmoother"]
