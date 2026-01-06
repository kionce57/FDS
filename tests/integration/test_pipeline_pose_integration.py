"""Integration tests for Pose mode detection flow."""

import numpy as np
from unittest.mock import MagicMock

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.capture.rolling_buffer import RollingBuffer
from src.detection.skeleton import Skeleton, Keypoint
from main import process_frame


def create_standing_skeleton() -> Skeleton:
    """Create a standing person skeleton (torso angle ~10 degrees)."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.NOSE] = [320, 50, 0.9]
    keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
    keypoints[Keypoint.LEFT_ANKLE] = [290, 400, 0.9]
    keypoints[Keypoint.RIGHT_ANKLE] = [350, 400, 0.9]
    return Skeleton(keypoints=keypoints)


def create_fallen_skeleton() -> Skeleton:
    """Create a fallen person skeleton (torso angle ~85 degrees)."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.NOSE] = [100, 400, 0.9]
    keypoints[Keypoint.LEFT_SHOULDER] = [170, 390, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [170, 410, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [350, 390, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 410, 0.9]
    keypoints[Keypoint.LEFT_ANKLE] = [500, 390, 0.9]
    keypoints[Keypoint.RIGHT_ANKLE] = [500, 410, 0.9]
    return Skeleton(keypoints=keypoints)


class TestPoseModeDetectionFlow:
    def test_pose_fall_detection(self):
        """Test Pose mode: standing -> fall -> confirm"""
        detector = MagicMock()
        rule_engine = PoseRuleEngine(torso_angle_threshold=60.0, enable_smoothing=False)
        delay_confirm = DelayConfirm(delay_sec=0.1)
        buffer = RollingBuffer(buffer_seconds=2, fps=15)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Standing
        detector.detect.return_value = [create_standing_skeleton()]
        state = process_frame(frame, 0.0, detector, rule_engine, delay_confirm, buffer, True)
        assert state == FallState.NORMAL

        # Fallen
        detector.detect.return_value = [create_fallen_skeleton()]
        state = process_frame(frame, 1.0, detector, rule_engine, delay_confirm, buffer, True)
        assert state == FallState.SUSPECTED

        state = process_frame(frame, 1.2, detector, rule_engine, delay_confirm, buffer, True)
        assert state == FallState.CONFIRMED

    def test_pose_smoothing_reduces_jitter(self):
        """Smoothing should reduce false positives from noisy keypoints."""
        detector = MagicMock()
        rule_engine = PoseRuleEngine(
            torso_angle_threshold=60.0,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        )
        delay_confirm = DelayConfirm(delay_sec=3.0)
        buffer = RollingBuffer(buffer_seconds=2, fps=15)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        np.random.seed(42)
        base_skeleton = create_standing_skeleton()
        states = []

        for i in range(30):
            noisy_keypoints = base_skeleton.keypoints.copy()
            noisy_keypoints[:, 0] += np.random.randn(17) * 5
            noisy_keypoints[:, 1] += np.random.randn(17) * 5
            noisy_skeleton = Skeleton(keypoints=noisy_keypoints)

            detector.detect.return_value = [noisy_skeleton]
            state = process_frame(
                frame, i * 0.033, detector, rule_engine, delay_confirm, buffer, True
            )
            states.append(state)

        assert all(s == FallState.NORMAL for s in states)
