import pytest
import numpy as np
from unittest.mock import patch
from src.capture.camera import Camera, CameraError


class TestCamera:
    def test_camera_init(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.isOpened.return_value = True
            camera = Camera(source=0)
            assert camera.source == 0

    def test_camera_not_opened_raises_error(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.isOpened.return_value = False
            with pytest.raises(CameraError, match="Failed to open camera"):
                Camera(source=0)

    def test_read_frame_success(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

            camera = Camera(source=0)
            frame = camera.read()

            assert frame is not None
            assert frame.shape == (480, 640, 3)

    def test_read_frame_failure_returns_none(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (False, None)

            camera = Camera(source=0)
            frame = camera.read()

            assert frame is None

    def test_consecutive_failures_raise_error(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.read.return_value = (False, None)

            camera = Camera(source=0, max_retries=3)
            camera.read()
            camera.read()

            with pytest.raises(CameraError, match="consecutive failures"):
                camera.read()

    def test_release_camera(self):
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True

            camera = Camera(source=0)
            camera.release()

            mock_instance.release.assert_called_once()
