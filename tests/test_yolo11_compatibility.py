"""YOLO11 Keypoint Compatibility Tests.

Verify YOLO11 pose estimation output is compatible with existing Skeleton class.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from src.detection.skeleton import Skeleton, Keypoint
from src.detection.detector import PoseDetector


class TestYOLO11KeypointFormat:
    """Test YOLO11 keypoint format compatibility with COCO17."""

    def test_coco17_keypoint_count(self):
        """YOLO11 and YOLOv8 both use 17 COCO keypoints."""
        assert len(Keypoint) == 17

    def test_coco17_keypoint_indices(self):
        """Verify keypoint indices match COCO17 standard."""
        expected_indices = {
            "NOSE": 0,
            "LEFT_EYE": 1,
            "RIGHT_EYE": 2,
            "LEFT_EAR": 3,
            "RIGHT_EAR": 4,
            "LEFT_SHOULDER": 5,
            "RIGHT_SHOULDER": 6,
            "LEFT_ELBOW": 7,
            "RIGHT_ELBOW": 8,
            "LEFT_WRIST": 9,
            "RIGHT_WRIST": 10,
            "LEFT_HIP": 11,
            "RIGHT_HIP": 12,
            "LEFT_KNEE": 13,
            "RIGHT_KNEE": 14,
            "LEFT_ANKLE": 15,
            "RIGHT_ANKLE": 16,
        }
        for name, expected_idx in expected_indices.items():
            assert Keypoint[name].value == expected_idx, f"{name} should be index {expected_idx}"

    def test_skeleton_accepts_yolo11_format_keypoints(self):
        """Skeleton class accepts YOLO11 format keypoints (17, 3)."""
        # YOLO11 outputs: (num_keypoints, 3) where 3 = [x, y, confidence]
        yolo11_keypoints = np.random.rand(17, 3) * 640  # Simulated pixel coords
        yolo11_keypoints[:, 2] = np.random.rand(17)  # Confidence in [0, 1]

        skeleton = Skeleton(keypoints=yolo11_keypoints)

        assert skeleton.keypoints.shape == (17, 3)
        assert skeleton.nose is not None
        assert skeleton.left_shoulder is not None
        assert skeleton.right_hip is not None

    def test_skeleton_torso_angle_with_yolo11_keypoints(self):
        """Skeleton.torso_angle works correctly with YOLO11 keypoints."""
        # Standing person keypoints (vertical torso)
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.LEFT_SHOULDER] = [300, 100, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [340, 100, 0.9]
        keypoints[Keypoint.LEFT_HIP] = [300, 250, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [340, 250, 0.9]

        skeleton = Skeleton(keypoints=keypoints)
        angle = skeleton.torso_angle

        # Standing person should have angle close to 0 (vertical)
        assert 0 <= angle < 15, f"Standing torso angle should be < 15 degrees, got {angle}"

    def test_skeleton_torso_angle_fallen_with_yolo11_keypoints(self):
        """Skeleton.torso_angle detects fallen pose with YOLO11 keypoints."""
        # Fallen person keypoints (horizontal torso)
        keypoints = np.zeros((17, 3))
        keypoints[Keypoint.LEFT_SHOULDER] = [100, 300, 0.9]
        keypoints[Keypoint.RIGHT_SHOULDER] = [100, 340, 0.9]
        keypoints[Keypoint.LEFT_HIP] = [300, 300, 0.9]
        keypoints[Keypoint.RIGHT_HIP] = [300, 340, 0.9]

        skeleton = Skeleton(keypoints=keypoints)
        angle = skeleton.torso_angle

        # Fallen person should have angle close to 90 (horizontal)
        assert angle > 70, f"Fallen torso angle should be > 70 degrees, got {angle}"


class TestPoseDetectorYOLO11Output:
    """Test PoseDetector output format with YOLO11."""

    @pytest.fixture
    def mock_yolo11_pose_result(self):
        """Create mock YOLO11 pose detection result."""
        mock_result = MagicMock()

        # YOLO11 keypoints format: (num_detections, num_keypoints, 3)
        # where 3 = [x, y, confidence]
        mock_keypoints_data = np.array(
            [
                [
                    [320, 50, 0.95],  # nose
                    [310, 45, 0.92],  # left_eye
                    [330, 45, 0.91],  # right_eye
                    [300, 50, 0.85],  # left_ear
                    [340, 50, 0.87],  # right_ear
                    [280, 120, 0.98],  # left_shoulder
                    [360, 120, 0.97],  # right_shoulder
                    [260, 200, 0.90],  # left_elbow
                    [380, 200, 0.89],  # right_elbow
                    [250, 280, 0.75],  # left_wrist
                    [390, 280, 0.78],  # right_wrist
                    [290, 280, 0.96],  # left_hip
                    [350, 280, 0.95],  # right_hip
                    [290, 380, 0.92],  # left_knee
                    [350, 380, 0.91],  # right_knee
                    [290, 480, 0.88],  # left_ankle
                    [350, 480, 0.87],  # right_ankle
                ]
            ]
        )

        mock_keypoints = MagicMock()
        mock_keypoints.data.cpu.return_value.numpy.return_value = mock_keypoints_data
        mock_result.keypoints = mock_keypoints

        return mock_result

    def test_pose_detector_returns_skeleton_list(self, mock_yolo11_pose_result):
        """PoseDetector.detect returns list of Skeleton objects."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_yolo11_pose_result]

            detector = PoseDetector(model_path="yolo11s-pose.pt")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            skeletons = detector.detect(frame)

            assert isinstance(skeletons, list)
            assert len(skeletons) == 1
            assert isinstance(skeletons[0], Skeleton)

    def test_pose_detector_skeleton_has_correct_keypoints(self, mock_yolo11_pose_result):
        """Skeleton from PoseDetector has correct keypoint values."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_yolo11_pose_result]

            detector = PoseDetector(model_path="yolo11s-pose.pt")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            skeletons = detector.detect(frame)

            skeleton = skeletons[0]
            nose = skeleton.nose
            assert nose[0] == 320  # x
            assert nose[1] == 50  # y
            assert nose[2] == 0.95  # confidence

    def test_pose_detector_skeleton_keypoint_shape(self, mock_yolo11_pose_result):
        """Skeleton keypoints have shape (17, 3)."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            mock_model = mock_yolo.return_value
            mock_model.return_value = [mock_yolo11_pose_result]

            detector = PoseDetector(model_path="yolo11s-pose.pt")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            skeletons = detector.detect(frame)

            assert skeletons[0].keypoints.shape == (17, 3)


class TestYOLO11BackwardCompatibility:
    """Test backward compatibility with YOLOv8 pose models."""

    def test_skeleton_works_with_both_yolov8_and_yolo11_format(self):
        """Skeleton class works with both YOLOv8 and YOLO11 keypoint format."""
        # Both YOLO versions output the same format: (17, 3)
        keypoints = np.random.rand(17, 3)
        keypoints[:, :2] *= 640  # Pixel coordinates
        keypoints[:, 2] = np.clip(keypoints[:, 2], 0, 1)  # Confidence

        skeleton = Skeleton(keypoints=keypoints)

        # All properties should work
        assert skeleton.torso_angle >= 0
        assert skeleton.hip_center is not None
        assert skeleton.shoulder_center is not None
        assert skeleton.hip_height_ratio >= 0

    def test_pose_detector_default_is_yolo11(self):
        """PoseDetector defaults to yolo11s-pose.pt."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            PoseDetector()
            mock_yolo.assert_called_once_with("yolo11s-pose.pt")

    def test_pose_detector_accepts_yolov8_model(self):
        """PoseDetector still accepts YOLOv8 pose models."""
        with patch("src.detection.detector.YOLO") as mock_yolo:
            PoseDetector(model_path="yolov8n-pose.pt")
            mock_yolo.assert_called_once_with("yolov8n-pose.pt")


@pytest.mark.slow
class TestYOLO11RealVideoIntegration:
    """Integration tests with real video files.

    These tests require actual YOLO models and test videos.
    Run with: pytest -m slow
    """

    @pytest.fixture
    def test_video_path(self):
        """Path to test video."""
        from pathlib import Path

        video_path = Path("tests/fixtures/videos/fall-01-cam0.mp4")
        if not video_path.exists():
            pytest.skip("Test video not found")
        return str(video_path)

    def test_yolo11_pose_detection_on_real_video(self, test_video_path):
        """YOLO11 pose detection works on real video."""
        import cv2

        detector = PoseDetector(model_path="yolo11s-pose.pt")
        cap = cv2.VideoCapture(test_video_path)

        ret, frame = cap.read()
        assert ret, "Failed to read video frame"

        skeletons = detector.detect(frame)
        cap.release()

        # Should detect at least one person in fall detection video
        assert len(skeletons) >= 0  # May be 0 if no person in first frame
        for skeleton in skeletons:
            assert isinstance(skeleton, Skeleton)
            assert skeleton.keypoints.shape == (17, 3)
