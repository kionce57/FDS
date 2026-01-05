"""Tests for Pipeline Pose mode integration."""

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
def pose_config():
    """Config with Pose mode enabled."""
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


@pytest.fixture
def bbox_config():
    """Config with BBox mode (default)."""
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
            use_pose=False,
        ),
        analysis=AnalysisConfig(
            fall_threshold=1.3,
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


@pytest.fixture
def standing_skeleton():
    """Standing person skeleton (torso angle ~10 degrees)."""
    keypoints = np.zeros((17, 3))
    keypoints[Keypoint.NOSE] = [320, 50, 0.9]
    keypoints[Keypoint.LEFT_SHOULDER] = [280, 120, 0.9]
    keypoints[Keypoint.RIGHT_SHOULDER] = [360, 120, 0.9]
    keypoints[Keypoint.LEFT_HIP] = [290, 280, 0.9]
    keypoints[Keypoint.RIGHT_HIP] = [350, 280, 0.9]
    keypoints[Keypoint.LEFT_ANKLE] = [290, 400, 0.9]
    keypoints[Keypoint.RIGHT_ANKLE] = [350, 400, 0.9]
    return Skeleton(keypoints=keypoints)


@pytest.fixture
def fallen_skeleton():
    """Fallen person skeleton (torso angle ~85 degrees)."""
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


class TestPipelinePoseMode:
    """Test Pipeline with Pose mode."""

    def test_pipeline_uses_pose_detector_when_configured(self, pose_config, tmp_path):
        """Pipeline should use PoseDetector when use_pose=True."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector,
            patch("src.core.pipeline.Detector") as mock_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")
            Pipeline(pose_config, db_path=db_path)

            # Should have created PoseDetector, not Detector
            mock_pose_detector.assert_called_once()
            mock_detector.assert_not_called()

    def test_pipeline_uses_pose_rule_engine_when_configured(self, pose_config, tmp_path):
        """Pipeline should use PoseRuleEngine when use_pose=True."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector"),
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")
            pipeline = Pipeline(pose_config, db_path=db_path)

            # Should have PoseRuleEngine with smoothing
            from src.analysis.pose_rule_engine import PoseRuleEngine

            assert isinstance(pipeline.rule_engine, PoseRuleEngine)
            assert pipeline.rule_engine._enable_smoothing is True

    def test_pipeline_uses_bbox_detector_when_not_configured(
        self, bbox_config, tmp_path
    ):
        """Pipeline should use Detector when use_pose=False."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector,
            patch("src.core.pipeline.Detector") as mock_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")
            Pipeline(bbox_config, db_path=db_path)

            # Should have created Detector, not PoseDetector
            mock_detector.assert_called_once()
            mock_pose_detector.assert_not_called()

    def test_process_frame_with_pose_mode_standing(
        self, pose_config, standing_skeleton, tmp_path
    ):
        """process_frame should return NORMAL for standing person in Pose mode."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector_cls,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            # Mock detector to return standing skeleton
            mock_detector = MagicMock()
            mock_detector.detect.return_value = [standing_skeleton]
            mock_pose_detector_cls.return_value = mock_detector

            pipeline = Pipeline(pose_config, db_path=db_path)

            # Process a frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.5)

            # Should return NORMAL for standing person
            assert state == FallState.NORMAL

    def test_process_frame_with_pose_mode_fallen(
        self, pose_config, fallen_skeleton, tmp_path
    ):
        """process_frame should return SUSPECTED for fallen person in Pose mode."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector_cls,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            # Mock detector to return fallen skeleton
            mock_detector = MagicMock()
            mock_detector.detect.return_value = [fallen_skeleton]
            mock_pose_detector_cls.return_value = mock_detector

            pipeline = Pipeline(pose_config, db_path=db_path)

            # Process a frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.5)

            # Should return SUSPECTED for fallen person (first detection)
            assert state == FallState.SUSPECTED

    def test_process_frame_passes_timestamp_for_smoothing(
        self, pose_config, standing_skeleton, tmp_path
    ):
        """process_frame should pass timestamp to rule_engine for Pose mode."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector_cls,
            patch("src.core.pipeline.PoseRuleEngine") as mock_pose_rule_engine_cls,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            # Mock detector
            mock_detector = MagicMock()
            mock_detector.detect.return_value = [standing_skeleton]
            mock_pose_detector_cls.return_value = mock_detector

            # Mock rule engine
            mock_rule_engine = MagicMock()
            mock_rule_engine.is_fallen.return_value = False
            mock_pose_rule_engine_cls.return_value = mock_rule_engine

            pipeline = Pipeline(pose_config, db_path=db_path)

            # Process frame with specific timestamp
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            pipeline.process_frame(frame, current_time=1.5)

            # Verify is_fallen was called with timestamp
            mock_rule_engine.is_fallen.assert_called_once()
            call_kwargs = mock_rule_engine.is_fallen.call_args.kwargs
            assert "timestamp" in call_kwargs
            assert call_kwargs["timestamp"] == 1.5

    def test_process_frame_no_detection_pose_mode(self, pose_config, tmp_path):
        """process_frame should return NORMAL when no person detected in Pose mode."""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.PoseDetector") as mock_pose_detector_cls,
            patch("src.core.pipeline.EventLogger"),
        ):
            db_path = str(tmp_path / "test.db")

            # Mock detector to return empty list
            mock_detector = MagicMock()
            mock_detector.detect.return_value = []
            mock_pose_detector_cls.return_value = mock_detector

            pipeline = Pipeline(pose_config, db_path=db_path)

            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.5)

            assert state == FallState.NORMAL
