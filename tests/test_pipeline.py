import pytest
import numpy as np
from unittest.mock import patch
from src.core.pipeline import Pipeline
from src.core.config import (
    Config,
    CameraConfig,
    DetectionConfig,
    AnalysisConfig,
    RecordingConfig,
    NotificationConfig,
    LifecycleConfig,
    CloudSyncConfig,
)
from src.detection.bbox import BBox
from src.analysis.delay_confirm import FallState


@pytest.fixture
def mock_config():
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(model="yolov8n.pt", confidence=0.5, classes=[0]),
        analysis=AnalysisConfig(
            fall_threshold=1.3, delay_sec=3.0, same_event_window=60.0, re_notify_interval=120.0
        ),
        recording=RecordingConfig(buffer_seconds=10, clip_before_sec=5, clip_after_sec=5),
        notification=NotificationConfig(line_token="test", enabled=False),
        lifecycle=LifecycleConfig(clip_retention_days=7, skeleton_retention_days=30),
        cloud_sync=CloudSyncConfig(enabled=False, gcs_bucket="", upload_on_extract=False, retry_attempts=3, retry_delay_seconds=5),
    )


class TestPipeline:
    def test_pipeline_init(self, mock_config):
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.Detector"),
            patch("src.core.pipeline.EventLogger"),
        ):
            pipeline = Pipeline(config=mock_config)
            assert pipeline.config == mock_config

    def test_process_frame_no_detection(self, mock_config):
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.Detector") as mock_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            mock_detector.return_value.detect.return_value = []

            pipeline = Pipeline(config=mock_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.0)

            assert state == FallState.NORMAL

    def test_process_frame_standing_person(self, mock_config):
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.Detector") as mock_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            standing_bbox = BBox(x=100, y=50, width=100, height=200)
            mock_detector.return_value.detect.return_value = [standing_bbox]

            pipeline = Pipeline(config=mock_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.0)

            assert state == FallState.NORMAL

    def test_process_frame_fallen_person_suspected(self, mock_config):
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.Detector") as mock_detector,
            patch("src.core.pipeline.EventLogger"),
        ):
            fallen_bbox = BBox(x=100, y=50, width=200, height=100)
            mock_detector.return_value.detect.return_value = [fallen_bbox]

            pipeline = Pipeline(config=mock_config)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            state = pipeline.process_frame(frame, current_time=0.0)

            assert state == FallState.SUSPECTED
