"""One Euro Filter for real-time signal smoothing.

Implementation based on the paper:
"1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems"
by Géry Casiez, Nicolas Roussel, and Daniel Vogel (CHI 2012)

The One Euro Filter is a simple real-time filter that adaptively adjusts its
cutoff frequency based on the rate of change of the signal. This provides:
- Low latency for fast movements (less smoothing)
- Strong smoothing for slow movements or stationary signals

Reference: https://cristal.univ-lille.fr/~casiez/1euro/
"""

import math


class LowPassFilter:
    """Simple exponential smoothing low-pass filter."""

    def __init__(self, alpha: float = 1.0):
        self._alpha = alpha
        self._initialized = False
        self._raw_value: float = 0.0
        self._stored_value: float = 0.0

    @property
    def last_raw_value(self) -> float:
        return self._raw_value

    def filter(self, value: float, alpha: float | None = None) -> float:
        """Apply low-pass filter to value.

        Args:
            value: Input value to filter
            alpha: Optional smoothing factor override (0 = max smooth, 1 = no smooth)

        Returns:
            Filtered value
        """
        if alpha is not None:
            self._alpha = alpha

        self._raw_value = value
        if self._initialized:
            self._stored_value = self._alpha * value + (1 - self._alpha) * self._stored_value
        else:
            self._stored_value = value
            self._initialized = True

        return self._stored_value


class OneEuroFilter:
    """One Euro Filter for adaptive low-pass filtering.

    This filter balances between smoothing (noise reduction) and responsiveness
    (low latency) by adapting the cutoff frequency based on signal speed.

    Args:
        min_cutoff: Minimum cutoff frequency (Hz). Lower values = more smoothing.
                   Default 1.0 works well for 30fps keypoint tracking.
        beta: Speed coefficient. Higher values = less smoothing during fast motion.
              Default 0.007 is tuned for human pose keypoint tracking.
        d_cutoff: Derivative cutoff frequency for speed estimation.
                  Default 1.0 usually works well.

    Example:
        >>> filter_x = OneEuroFilter(min_cutoff=1.0, beta=0.007)
        >>> # First frame at t=0.0
        >>> smoothed_x = filter_x.filter(320.5, timestamp=0.0)
        >>> # Next frame at t=0.033 (30fps)
        >>> smoothed_x = filter_x.filter(321.2, timestamp=0.033)
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        if min_cutoff <= 0:
            raise ValueError("min_cutoff must be positive")
        if d_cutoff <= 0:
            raise ValueError("d_cutoff must be positive")

        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff

        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_timestamp: float | None = None

    @staticmethod
    def _smoothing_factor(te: float, cutoff: float) -> float:
        """Calculate smoothing factor alpha.

        Args:
            te: Time period between samples (seconds)
            cutoff: Cutoff frequency (Hz)

        Returns:
            Alpha value in range (0, 1]
        """
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / te)

    def filter(self, value: float, timestamp: float) -> float:
        """Apply One Euro Filter to a value.

        Args:
            value: Current measurement
            timestamp: Current timestamp in seconds

        Returns:
            Filtered value
        """
        if self._last_timestamp is None:
            # First sample - initialize and return as-is
            self._last_timestamp = timestamp
            self._dx_filter.filter(0.0, 1.0)
            return self._x_filter.filter(value, 1.0)

        # Calculate time period
        te = timestamp - self._last_timestamp
        if te <= 0:
            # Same or earlier timestamp - return last value
            return self._x_filter.filter(value, 1.0)

        self._last_timestamp = timestamp

        # Estimate derivative (rate of change)
        dx = (value - self._x_filter.last_raw_value) / te

        # Filter the derivative
        alpha_d = self._smoothing_factor(te, self._d_cutoff)
        dx_hat = self._dx_filter.filter(dx, alpha_d)

        # Adaptive cutoff based on speed
        cutoff = self._min_cutoff + self._beta * abs(dx_hat)

        # Filter the signal
        alpha = self._smoothing_factor(te, cutoff)
        return self._x_filter.filter(value, alpha)

    def reset(self) -> None:
        """Reset filter state for a new tracking session."""
        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_timestamp = None


__all__ = ["OneEuroFilter"]
