"""Tests for keypoint smoothing utilities."""

import pytest
import numpy as np

from src.analysis.smoothing.one_euro_filter import OneEuroFilter
from src.analysis.smoothing.keypoint_smoother import KeypointSmoother
from src.detection.skeleton import Skeleton, Keypoint


class TestOneEuroFilter:
    """Test One Euro Filter implementation."""

    def test_first_sample_returns_input(self):
        """First sample should pass through unchanged."""
        f = OneEuroFilter()
        result = f.filter(100.0, timestamp=0.0)
        assert result == 100.0

    def test_smooths_noisy_signal(self):
        """Filter should reduce noise in stationary signal."""
        f = OneEuroFilter(min_cutoff=1.0, beta=0.0)  # beta=0 for consistent smoothing

        # Simulate noisy stationary signal around 100
        np.random.seed(42)
        noisy_values = [100 + np.random.randn() * 5 for _ in range(30)]
        timestamps = [i * 0.033 for i in range(30)]  # 30fps

        filtered_values = [f.filter(v, t) for v, t in zip(noisy_values, timestamps)]

        # Variance of filtered signal should be lower than input
        input_variance = np.var(noisy_values)
        output_variance = np.var(filtered_values)
        assert output_variance < input_variance

    def test_preserves_fast_movements(self):
        """Filter should have less lag for fast movements (with beta > 0)."""
        f_with_beta = OneEuroFilter(min_cutoff=1.0, beta=0.5)
        f_no_beta = OneEuroFilter(min_cutoff=1.0, beta=0.0)

        # Simulate sudden jump
        values = [100.0] * 10 + [200.0] * 10
        timestamps = [i * 0.033 for i in range(20)]

        # Filter with beta should track jump faster
        filtered_with_beta = [f_with_beta.filter(v, t) for v, t in zip(values, timestamps)]
        filtered_no_beta = [f_no_beta.filter(v, t) for v, t in zip(values, timestamps)]

        # At frame 15 (5 frames after jump), with_beta should be closer to 200
        assert filtered_with_beta[15] > filtered_no_beta[15]

    def test_reset_clears_state(self):
        """Reset should clear filter state."""
        f = OneEuroFilter()

        # Filter some values
        f.filter(100.0, 0.0)
        f.filter(101.0, 0.033)

        # Reset
        f.reset()

        # Next value should be passed through (like first sample)
        result = f.filter(50.0, 1.0)
        assert result == 50.0

    def test_invalid_min_cutoff_raises(self):
        """Should raise for non-positive min_cutoff."""
        with pytest.raises(ValueError):
            OneEuroFilter(min_cutoff=0)
        with pytest.raises(ValueError):
            OneEuroFilter(min_cutoff=-1)

    def test_same_timestamp_returns_filtered_value(self):
        """Same timestamp should not cause division by zero."""
        f = OneEuroFilter()
        f.filter(100.0, 0.0)
        # Same timestamp
        result = f.filter(105.0, 0.0)
        # Should still return a valid result
        assert not np.isnan(result)


class TestKeypointSmoother:
    """Test KeypointSmoother for skeleton smoothing."""

    @pytest.fixture
    def smoother(self):
        return KeypointSmoother(min_cutoff=1.0, beta=0.007)

    @pytest.fixture
    def standing_skeleton(self):
        """Create a standing person skeleton."""
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

    def test_smooth_returns_skeleton(self, smoother, standing_skeleton):
        """Smooth should return a Skeleton object."""
        result = smoother.smooth(standing_skeleton, timestamp=0.0)
        assert isinstance(result, Skeleton)
        assert result.keypoints.shape == (17, 3)

    def test_first_frame_passes_through(self, smoother, standing_skeleton):
        """First frame should pass through with minimal change."""
        result = smoother.smooth(standing_skeleton, timestamp=0.0)

        # First frame values should be very close to input
        np.testing.assert_array_almost_equal(
            result.keypoints[:, :2],  # x, y only
            standing_skeleton.keypoints[:, :2],
            decimal=5,
        )

    def test_smooths_noisy_sequence(self, smoother):
        """Smoother should reduce jitter in keypoint sequence."""
        np.random.seed(42)

        # Generate noisy skeleton sequence
        base_keypoints = np.zeros((17, 3))
        base_keypoints[:, 2] = 0.9  # All high confidence
        for i in range(17):
            base_keypoints[i, 0] = 200 + i * 20  # x
            base_keypoints[i, 1] = 100 + i * 25  # y

        # Add noise to each frame
        noisy_skeletons = []
        for _ in range(30):
            noisy = base_keypoints.copy()
            noisy[:, 0] += np.random.randn(17) * 3  # x noise
            noisy[:, 1] += np.random.randn(17) * 3  # y noise
            noisy_skeletons.append(Skeleton(keypoints=noisy))

        # Smooth the sequence
        timestamps = [i * 0.033 for i in range(30)]
        smoothed = smoother.smooth_batch(noisy_skeletons, timestamps)

        # Calculate variance for keypoint 0 (nose)
        noisy_x = [s.keypoints[0, 0] for s in noisy_skeletons]
        smoothed_x = [s.keypoints[0, 0] for s in smoothed]

        # Smoothed variance should be lower
        assert np.var(smoothed_x) < np.var(noisy_x)

    def test_low_confidence_skips_smoothing(self, smoother):
        """Low confidence keypoints should not be smoothed."""
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.NOSE] = [100, 100, 0.1]  # Low confidence
        keypoints[Keypoint.LEFT_SHOULDER] = [200, 200, 0.9]  # High confidence

        skeleton = Skeleton(keypoints=keypoints)

        # First frame
        result1 = smoother.smooth(skeleton, 0.0)

        # Second frame with different values
        keypoints2 = keypoints.copy()
        keypoints2[Keypoint.NOSE] = [150, 150, 0.1]  # Low confidence
        keypoints2[Keypoint.LEFT_SHOULDER] = [205, 205, 0.9]  # High confidence
        skeleton2 = Skeleton(keypoints=keypoints2)

        result2 = smoother.smooth(skeleton2, 0.033)

        # Low confidence nose should keep original value (no smoothing history)
        assert result2.keypoints[Keypoint.NOSE, 0] == 150

        # High confidence shoulder should be smoothed (closer to average)
        assert result2.keypoints[Keypoint.LEFT_SHOULDER, 0] != 205

    def test_reset_clears_all_filters(self, smoother, standing_skeleton):
        """Reset should clear state for all keypoints."""
        # Smooth some frames
        smoother.smooth(standing_skeleton, 0.0)
        smoother.smooth(standing_skeleton, 0.033)

        # Reset
        smoother.reset()

        # Create different skeleton
        new_keypoints = np.ones((17, 3)) * 500
        new_keypoints[:, 2] = 0.9
        new_skeleton = Skeleton(keypoints=new_keypoints)

        # After reset, first frame should pass through
        result = smoother.smooth(new_skeleton, 1.0)
        np.testing.assert_array_almost_equal(
            result.keypoints[:, :2],
            new_skeleton.keypoints[:, :2],
            decimal=5,
        )

    def test_batch_mismatched_lengths_raises(self, smoother, standing_skeleton):
        """Batch with mismatched lengths should raise ValueError."""
        with pytest.raises(ValueError):
            smoother.smooth_batch(
                [standing_skeleton, standing_skeleton],
                [0.0],  # Only one timestamp
            )

    def test_confidence_preserved(self, smoother, standing_skeleton):
        """Confidence values should be preserved (not smoothed)."""
        result = smoother.smooth(standing_skeleton, 0.0)

        # Confidence values should match input
        np.testing.assert_array_equal(
            result.keypoints[:, 2],
            standing_skeleton.keypoints[:, 2],
        )

    def test_reset_keypoint(self, smoother, standing_skeleton):
        """Reset specific keypoint should only affect that keypoint."""
        smoother.smooth(standing_skeleton, 0.0)
        smoother.smooth(standing_skeleton, 0.033)

        # Reset only nose
        smoother.reset_keypoint(Keypoint.NOSE)

        # Next frame for nose should pass through
        new_keypoints = standing_skeleton.keypoints.copy()
        new_keypoints[Keypoint.NOSE] = [500, 500, 0.9]
        new_skeleton = Skeleton(keypoints=new_keypoints)

        result = smoother.smooth(new_skeleton, 0.066)

        # Nose should be near 500 (passed through after reset)
        assert result.keypoints[Keypoint.NOSE, 0] == pytest.approx(500, abs=1)

        # Other keypoints should still be smoothed (different from input)
        # Left shoulder was at 280, now stays around there due to smoothing
        assert result.keypoints[Keypoint.LEFT_SHOULDER, 0] != 500
