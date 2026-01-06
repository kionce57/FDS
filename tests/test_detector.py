import numpy as np
from unittest.mock import patch, MagicMock
from src.detection.detector import Detector, PoseDetector
from src.detection.bbox import BBox


class TestDetector:
    def test_detector_init(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            detector = Detector(model_path="yolov8n.pt", confidence=0.5)
            assert detector.confidence == 0.5
            mock_yolo.assert_called_once_with("yolov8n.pt")

    def test_detect_returns_bboxes(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_result = MagicMock()
            mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = np.array(
                [
                    [100, 50, 200, 250],
                    [300, 100, 400, 300],
                ]
            )
            mock_result.boxes.cls.cpu.return_value.numpy.return_value = np.array([0, 0])
            mock_result.boxes.conf.cpu.return_value.numpy.return_value = np.array([0.9, 0.8])

            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_result]

            detector = Detector(model_path="yolov8n.pt", confidence=0.5, classes=[0])
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            bboxes = detector.detect(frame)

            assert len(bboxes) == 2
            assert isinstance(bboxes[0], BBox)
            assert bboxes[0].x == 100
            assert bboxes[0].width == 100
            assert bboxes[0].height == 200

    def test_detect_filters_by_class(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_result = MagicMock()
            mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = np.array(
                [
                    [100, 50, 200, 250],
                    [300, 100, 400, 300],
                ]
            )
            mock_result.boxes.cls.cpu.return_value.numpy.return_value = np.array([0, 1])
            mock_result.boxes.conf.cpu.return_value.numpy.return_value = np.array([0.9, 0.8])

            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_result]

            detector = Detector(model_path="yolov8n.pt", confidence=0.5, classes=[0])
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            bboxes = detector.detect(frame)

            assert len(bboxes) == 1

    def test_detect_empty_result(self):
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_result = MagicMock()
            mock_result.boxes.xyxy.cpu.return_value.numpy.return_value = np.array([]).reshape(0, 4)
            mock_result.boxes.cls.cpu.return_value.numpy.return_value = np.array([])
            mock_result.boxes.conf.cpu.return_value.numpy.return_value = np.array([])

            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_result]

            detector = Detector(model_path="yolov8n.pt")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            bboxes = detector.detect(frame)

            assert len(bboxes) == 0


class TestPoseDetector:
    def test_pose_detector_uses_yolo11_by_default(self):
        """Verify PoseDetector defaults to yolo11s-pose.pt."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            _ = PoseDetector()
            mock_yolo.assert_called_once_with("yolo11s-pose.pt")

    def test_pose_detector_accepts_model_path(self):
        """Verify PoseDetector accepts custom model path."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            _ = PoseDetector(model_path="custom-pose.pt")
            mock_yolo.assert_called_once_with("custom-pose.pt")
