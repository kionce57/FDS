import pytest
import numpy as np
from unittest.mock import patch
from src.core.config import (
    Config,
    CameraConfig,
    DetectionConfig,
    AnalysisConfig,
    RecordingConfig,
    NotificationConfig,
    LifecycleConfig,
)
from src.core.pipeline import Pipeline
from src.detection.bbox import BBox
from src.analysis.delay_confirm import FallState


@pytest.fixture
def test_config(tmp_path):
    return Config(
        camera=CameraConfig(source=0, fps=15, resolution=[640, 480]),
        detection=DetectionConfig(model="yolov8n.pt", confidence=0.5, classes=[0]),
        analysis=AnalysisConfig(
            fall_threshold=1.3, delay_sec=0.1, same_event_window=60.0, re_notify_interval=120.0
        ),
        recording=RecordingConfig(buffer_seconds=2, clip_before_sec=1, clip_after_sec=1),
        notification=NotificationConfig(
            line_channel_access_token="test", line_user_id="U123", enabled=False
        ),
        lifecycle=LifecycleConfig(clip_retention_days=7),
    )


class TestFullPipeline:
    def test_fall_detection_flow(self, test_config, tmp_path):
        """Test complete flow: standing -> fall -> confirm -> recover"""
        with (
            patch("src.core.pipeline.Camera"),
            patch("src.core.pipeline.Detector") as mock_detector,
        ):
            standing_bbox = BBox(x=100, y=50, width=100, height=200)
            fallen_bbox = BBox(x=100, y=50, width=200, height=100)

            db_path = str(tmp_path / "test_fds.db")
            pipeline = Pipeline(config=test_config, db_path=db_path)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            mock_detector.return_value.detect.return_value = [standing_bbox]
            state = pipeline.process_frame(frame, current_time=0.0)
            assert state == FallState.NORMAL

            mock_detector.return_value.detect.return_value = [fallen_bbox]
            state = pipeline.process_frame(frame, current_time=1.0)
            assert state == FallState.SUSPECTED

            state = pipeline.process_frame(frame, current_time=1.2)
            assert state == FallState.CONFIRMED

            mock_detector.return_value.detect.return_value = [standing_bbox]
            state = pipeline.process_frame(frame, current_time=2.0)
            assert state == FallState.NORMAL
