"""Integration tests for Pipeline with Pose mode and smoothing."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from src.core.pipeline import Pipeline
from src.core.config import (
    Config,
    CameraConfig,
    DetectionConfig,
    AnalysisConfig,
    RecordingConfig,
    NotificationConfig,
    LifecycleConfig,
)
from src.analysis.delay_confirm import FallState
from src.detection.skeleton import Skeleton, Keypoint


@pytest.fixture
def pose_smoothing_config():
    """Config with Pose mode and smoothing enabled."""
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
            pose_model="yolo11s-pose.pt",
            use_pose=True,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        ),
        analysis=AnalysisConfig(
            fall_threshold=60.0,  # Torso angle threshold for Pose mode
            delay_sec=3.0,
            same_event_window=60.0,
            re_notify_interval=120.0,
        ),
        recording=RecordingConfig(
            buffer_seconds=10,
            clip_before_sec=5,
            clip_after_sec=5,
        ),
        notification=NotificationConfig(
            line_channel_access_token="",
            line_user_id="",
            enabled=False,
        ),
        lifecycle=LifecycleConfig(clip_retention_days=7),
    )


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
    # Person lying on side - shoulders and hips nearly horizontal
    keypoints[Keypoint.LEFT_SHOULDER] = [170, 390, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [170, 410, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [350, 390, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 410, 0.9]
    keypoints[Keypoint.LEFT_ANKLE] = [500, 390, 0.9]
    keypoints[Keypoint.RIGHT_ANKLE] = [500, 410, 0.9]
    return Skeleton(keypoints=keypoints)


class TestPipelinePoseSmoothingIntegration:
    """Integration tests for Pose mode with smoothing."""

    def test_smoothing_reduces_false_positives_from_jitter(
        self, pose_smoothing_config, tmp_path
    ):
        """Smoothing should reduce false positives from noisy keypoints."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            # Setup mock detector
            mock_detector_instance = MagicMock()
            mock_pose_detector.return_value = mock_detector_instance

            pipeline = Pipeline(pose_smoothing_config, db_path=db_path)

            # Simulate 30 frames of standing with small jitter
            np.random.seed(42)
            states = []
            base_skeleton = create_standing_skeleton()

            for i in range(30):
                # Add small random noise to keypoints
                noisy_keypoints = base_skeleton.keypoints.copy()
                noisy_keypoints[:, 0] += np.random.randn(17) * 5  # x noise
                noisy_keypoints[:, 1] += np.random.randn(17) * 5  # y noise
                noisy_skeleton = Skeleton(keypoints=noisy_keypoints)

                mock_detector_instance.detect.return_value = [noisy_skeleton]

                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                state = pipeline.process_frame(frame, current_time=i * 0.033)
                states.append(state)

            # All frames should be NORMAL (no false positives from jitter)
            assert all(s == FallState.NORMAL for s in states)

    def test_fall_detection_with_smoothing(self, pose_smoothing_config, tmp_path):
        """Fall should be detected after delay even with smoothing."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            mock_detector_instance = MagicMock()
            mock_pose_detector.return_value = mock_detector_instance

            pipeline = Pipeline(pose_smoothing_config, db_path=db_path)

            fallen_skeleton = create_fallen_skeleton()
            mock_detector_instance.detect.return_value = [fallen_skeleton]

            states = []
            # Simulate 100 frames at 30fps = 3.3 seconds (beyond 3s delay)
            for i in range(100):
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                state = pipeline.process_frame(frame, current_time=i * 0.033)
                states.append(state)

            # Should transition: NORMAL -> SUSPECTED -> CONFIRMED
            assert FallState.SUSPECTED in states
            assert FallState.CONFIRMED in states

    def test_recovery_from_fall_with_smoothing(self, pose_smoothing_config, tmp_path):
        """Person should recover from fall when standing up."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            mock_detector_instance = MagicMock()
            mock_pose_detector.return_value = mock_detector_instance

            pipeline = Pipeline(pose_smoothing_config, db_path=db_path)

            fallen_skeleton = create_fallen_skeleton()
            standing_skeleton = create_standing_skeleton()

            states = []

            # Fall for 4 seconds (beyond delay)
            mock_detector_instance.detect.return_value = [fallen_skeleton]
            for i in range(120):  # 4 seconds at 30fps
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                state = pipeline.process_frame(frame, current_time=i * 0.033)
                states.append(state)

            # Should be CONFIRMED
            assert states[-1] == FallState.CONFIRMED

            # Now stand up
            mock_detector_instance.detect.return_value = [standing_skeleton]
            for i in range(120, 150):  # 1 more second
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                state = pipeline.process_frame(frame, current_time=i * 0.033)
                states.append(state)

            # Should recover to NORMAL
            assert states[-1] == FallState.NORMAL
