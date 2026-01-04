import pytest
import numpy as np
from unittest.mock import patch

from src.lifecycle.skeleton_extractor import SkeletonExtractor
from src.lifecycle.schema import SkeletonSequence
from src.detection.skeleton import Skeleton
from src.capture.rolling_buffer import FrameData


class TestSkeletonExtractor:
    @pytest.fixture
    def extractor(self):
        return SkeletonExtractor(model_path="yolov8n-pose.pt")

    @pytest.fixture
    def mock_video_frames(self):
        """模擬影片幀"""
        frames = []
        for i in range(3):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frames.append(frame)
        return frames

    @pytest.fixture
    def mock_skeleton(self):
        """模擬 YOLOv8 Skeleton 輸出（像素座標，基於 640x480 影像）"""
        # YOLOv8 回傳像素座標，這些值會被 extractor 正規化至 [0, 1]
        keypoints = np.array(
            [
                [332.8, 72.0, 0.95],  # nose (normalized: 0.52, 0.15)
                [307.2, 57.6, 0.92],  # left_eye (normalized: 0.48, 0.12)
                [358.4, 57.6, 0.91],  # right_eye (normalized: 0.56, 0.12)
                [288.0, 67.2, 0.85],  # left_ear (normalized: 0.45, 0.14)
                [377.6, 67.2, 0.87],  # right_ear (normalized: 0.59, 0.14)
                [288.0, 134.4, 0.98],  # left_shoulder (normalized: 0.45, 0.28)
                [371.2, 129.6, 0.97],  # right_shoulder (normalized: 0.58, 0.27)
                [268.8, 201.6, 0.90],  # left_elbow (normalized: 0.42, 0.42)
                [390.4, 196.8, 0.89],  # right_elbow (normalized: 0.61, 0.41)
                [256.0, 268.8, 0.75],  # left_wrist (normalized: 0.40, 0.56)
                [403.2, 264.0, 0.78],  # right_wrist (normalized: 0.63, 0.55)
                [300.8, 288.0, 0.96],  # left_hip (normalized: 0.47, 0.60)
                [339.2, 288.0, 0.95],  # right_hip (normalized: 0.53, 0.60)
                [294.4, 374.4, 0.92],  # left_knee (normalized: 0.46, 0.78)
                [345.6, 374.4, 0.91],  # right_knee (normalized: 0.54, 0.78)
                [288.0, 456.0, 0.88],  # left_ankle (normalized: 0.45, 0.95)
                [352.0, 456.0, 0.87],  # right_ankle (normalized: 0.55, 0.95)
            ]
        )
        return Skeleton(keypoints=keypoints)

    def test_extractor_init(self, extractor):
        """測試提取器初始化"""
        assert extractor.model_path == "yolov8n-pose.pt"
        assert extractor.detector is not None

    def test_extract_from_video_returns_skeleton_sequence(self, extractor, tmp_path, mock_skeleton):
        """測試從影片提取骨架序列"""
        with (
            patch("cv2.VideoCapture") as mock_cap,
            patch.object(extractor.detector, "detect") as mock_detect,  # noqa: F841
            patch("pathlib.Path.exists", return_value=True),
        ):
            # 模擬影片
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {
                5: 15.0,  # CAP_PROP_FPS
                7: 3.0,  # CAP_PROP_FRAME_COUNT
            }.get(prop, 0)

            # 模擬三幀
            mock_instance.read.side_effect = [
                (True, np.zeros((480, 640, 3), dtype=np.uint8)),
                (True, np.zeros((480, 640, 3), dtype=np.uint8)),
                (True, np.zeros((480, 640, 3), dtype=np.uint8)),
                (False, None),
            ]

            mock_detect.return_value = [mock_skeleton]

            # 執行提取
            result = extractor.extract_from_video("test.mp4", event_id="evt_123")

            # 驗證結果
            assert isinstance(result, SkeletonSequence)
            assert result.metadata.event_id == "evt_123"
            assert result.keypoint_format == "coco17"
            assert len(result.sequence) == 3

    def test_extract_skeleton_sequence_has_correct_metadata(self, extractor, tmp_path):
        """測試提取的序列包含正確的 metadata"""
        with (
            patch("cv2.VideoCapture") as mock_cap,
            patch.object(extractor.detector, "detect") as mock_detect,  # noqa: F841
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {5: 15.0, 7: 10.0}.get(prop, 0)
            mock_instance.read.return_value = (False, None)

            result = extractor.extract_from_video("test.mp4", event_id="evt_123")

            assert result.metadata.fps == 15
            assert result.metadata.total_frames == 10
            assert result.metadata.extractor.engine == "yolo11"
            assert "pose" in result.metadata.extractor.model

    def test_extract_converts_skeleton_to_coco17_keypoints(self, extractor, mock_skeleton):
        """測試 Skeleton 正確轉換為 COCO17 格式"""
        with (
            patch("cv2.VideoCapture") as mock_cap,
            patch.object(extractor.detector, "detect") as mock_detect,  # noqa: F841
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {5: 15.0, 7: 1.0}.get(prop, 0)
            mock_instance.read.side_effect = [
                (True, np.zeros((480, 640, 3), dtype=np.uint8)),
                (False, None),
            ]
            mock_detect.return_value = [mock_skeleton]

            result = extractor.extract_from_video("test.mp4", event_id="evt_123")

            frame = result.sequence[0]
            assert "nose" in frame.keypoints
            assert "left_shoulder" in frame.keypoints
            assert frame.keypoints["nose"].x == 0.52
            assert frame.keypoints["nose"].confidence == 0.95

    def test_extract_handles_no_detection(self, extractor):
        """測試處理無偵測結果的情況"""
        with (
            patch("cv2.VideoCapture") as mock_cap,
            patch.object(extractor.detector, "detect") as mock_detect,  # noqa: F841
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {5: 15.0, 7: 1.0}.get(prop, 0)
            mock_instance.read.side_effect = [
                (True, np.zeros((480, 640, 3), dtype=np.uint8)),
                (False, None),
            ]
            mock_detect.return_value = []  # 無偵測結果

            result = extractor.extract_from_video("test.mp4", event_id="evt_123")

            # 仍然應該有序列，但 keypoints 可能為空或缺少該幀
            assert isinstance(result, SkeletonSequence)

    def test_extract_and_save(self, extractor, tmp_path, mock_skeleton):
        """測試提取並儲存為 JSON"""
        output_path = tmp_path / "test_skeleton.json"

        with (
            patch("cv2.VideoCapture") as mock_cap,
            patch.object(extractor.detector, "detect") as mock_detect,  # noqa: F841
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_instance = mock_cap.return_value
            mock_instance.isOpened.return_value = True
            mock_instance.get.side_effect = lambda prop: {5: 15.0, 7: 1.0}.get(prop, 0)
            mock_instance.read.side_effect = [
                (True, np.zeros((480, 640, 3), dtype=np.uint8)),
                (False, None),
            ]
            mock_detect.return_value = [mock_skeleton]

            extractor.extract_and_save("test.mp4", output_path, event_id="evt_123")

            assert output_path.exists()

            # 驗證可以被 Schema validator 驗證
            from src.lifecycle.schema.validator import SkeletonValidator

            validator = SkeletonValidator()
            assert validator.validate_file(output_path)


class TestExtractFromFrames:
    @pytest.fixture
    def extractor(self):
        return SkeletonExtractor(model_path="yolov8n-pose.pt")

    @pytest.fixture
    def mock_skeleton(self):
        """模擬 YOLOv8 Skeleton 輸出（像素座標，基於 640x480 影像）"""
        keypoints = np.array(
            [
                [332.8, 72.0, 0.95],  # nose
                [307.2, 57.6, 0.92],  # left_eye
                [358.4, 57.6, 0.91],  # right_eye
                [288.0, 67.2, 0.85],  # left_ear
                [377.6, 67.2, 0.87],  # right_ear
                [288.0, 134.4, 0.98],  # left_shoulder
                [371.2, 129.6, 0.97],  # right_shoulder
                [268.8, 201.6, 0.90],  # left_elbow
                [390.4, 196.8, 0.89],  # right_elbow
                [256.0, 268.8, 0.75],  # left_wrist
                [403.2, 264.0, 0.78],  # right_wrist
                [300.8, 288.0, 0.96],  # left_hip
                [339.2, 288.0, 0.95],  # right_hip
                [294.4, 374.4, 0.92],  # left_knee
                [345.6, 374.4, 0.91],  # right_knee
                [288.0, 456.0, 0.88],  # left_ankle
                [352.0, 456.0, 0.87],  # right_ankle
            ]
        )
        return Skeleton(keypoints=keypoints)

    def test_extract_from_frames_returns_sequence(self, extractor, mock_skeleton):
        """測試從 FrameData 列表提取骨架序列"""
        frames = [
            FrameData(
                timestamp=i * 0.066,  # 15fps
                frame=np.zeros((480, 640, 3), dtype=np.uint8),
                bbox=None,
            )
            for i in range(10)
        ]

        with patch.object(extractor.detector, "detect") as mock_detect:
            mock_detect.return_value = [mock_skeleton]

            result = extractor.extract_from_frames(
                frames=frames,
                event_id="test_evt",
                fps=15.0,
            )

            assert result is not None
            assert result.metadata.event_id == "test_evt"
            assert result.keypoint_format == "coco17"

    def test_extract_from_frames_empty_list(self, extractor):
        """測試空列表輸入"""
        result = extractor.extract_from_frames(
            frames=[],
            event_id="empty_evt",
            fps=15.0,
        )

        assert result.sequence == []
        assert result.metadata.event_id == "empty_evt"
