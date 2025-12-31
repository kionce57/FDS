"""
骨架提取器

從影片檔案提取骨架序列，轉換為標準化的 SkeletonSequence 格式。
"""

import cv2
import time
from datetime import datetime
from pathlib import Path

from src.capture.rolling_buffer import FrameData
from src.detection.detector import PoseDetector
from src.detection.skeleton import Skeleton
from src.lifecycle.schema import (
    Keypoint,
    BBox,
    DerivedFeatures,
    SkeletonFrame,
    SkeletonSequence,
    ExtractorMetadata,
    SkeletonMetadata,
)
from src.lifecycle.schema.formats import COCO17_KEYPOINTS


class SkeletonExtractor:
    """骨架提取器

    使用 YOLOv8 Pose 從影片提取骨架序列。

    Example:
        >>> extractor = SkeletonExtractor()
        >>> sequence = extractor.extract_from_video("data/clips/evt_123.mp4", event_id="evt_123")
        >>> extractor.extract_and_save("data/clips/evt_123.mp4", "data/skeletons/evt_123.json")
    """

    def __init__(self, model_path: str = "yolov8n-pose.pt"):
        """初始化骨架提取器

        Args:
            model_path: YOLOv8 Pose 模型路徑
        """
        self.model_path = model_path
        self.detector = PoseDetector(model_path=model_path, confidence=0.5)

    def extract_from_video(
        self,
        video_path: str | Path,
        event_id: str | None = None,
    ) -> SkeletonSequence:
        """從影片提取骨架序列

        Args:
            video_path: 影片檔案路徑
            event_id: 事件 ID（若不提供則從檔名生成）

        Returns:
            SkeletonSequence 實例

        Raises:
            FileNotFoundError: 影片檔案不存在
            ValueError: 影片無法開啟
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # 生成 event_id
        if event_id is None:
            event_id = f"evt_{int(time.time())}"

        # 開啟影片
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Failed to open video: {video_path}")

        try:
            # 取得影片資訊
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_sec = total_frames / fps if fps > 0 else 0

            # 建立 metadata
            metadata = SkeletonMetadata(
                event_id=event_id,
                timestamp=datetime.now().isoformat(),
                source_video=str(video_path),
                duration_sec=duration_sec,
                fps=fps,
                total_frames=total_frames,
                extractor=ExtractorMetadata(
                    engine="yolov8", model=self.model_path, version="8.0.0"
                ),
            )

            # 提取每一幀的骨架
            sequence = []
            frame_idx = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                timestamp = frame_idx / fps if fps > 0 else 0

                # 使用 detector 提取骨架
                skeletons = self.detector.detect(frame)

                if skeletons:
                    # 只取第一個人的骨架（單人場景）
                    skeleton = skeletons[0]
                    skeleton_frame = self._skeleton_to_frame(
                        skeleton, frame_idx, timestamp, frame.shape[:2]
                    )
                    sequence.append(skeleton_frame)

                frame_idx += 1

            return SkeletonSequence(
                metadata=metadata, keypoint_format="coco17", sequence=sequence, version="1.0"
            )

        finally:
            cap.release()

    def _skeleton_to_frame(
        self, skeleton: Skeleton, frame_idx: int, timestamp: float, frame_shape: tuple[int, int]
    ) -> SkeletonFrame:
        """將 Skeleton 轉換為 SkeletonFrame

        Args:
            skeleton: YOLOv8 Skeleton 物件
            frame_idx: 幀索引
            timestamp: 時間戳記
            frame_shape: 影像形狀 (height, width)

        Returns:
            SkeletonFrame 實例
        """
        height, width = frame_shape

        # 轉換 keypoints (17, 3) -> dict，並正規化座標至 [0, 1]
        keypoints = {}
        for i, kp_name in enumerate(COCO17_KEYPOINTS):
            x, y, conf = skeleton.keypoints[i]
            # 正規化座標
            x_norm = float(x) / width if width > 0 else 0.0
            y_norm = float(y) / height if height > 0 else 0.0
            keypoints[kp_name] = Keypoint(x=x_norm, y=y_norm, confidence=float(conf))

        # 計算 bbox（從關鍵點推算）
        visible_kps = skeleton.keypoints[skeleton.keypoints[:, 2] > 0.3]  # 置信度 > 0.3
        if len(visible_kps) > 0:
            height, width = frame_shape
            x_coords = visible_kps[:, 0] * width
            y_coords = visible_kps[:, 1] * height

            x_min, x_max = int(x_coords.min()), int(x_coords.max())
            y_min, y_max = int(y_coords.min()), int(y_coords.max())

            bbox = BBox(x=x_min, y=y_min, width=x_max - x_min, height=y_max - y_min)
        else:
            bbox = None

        # 計算 derived_features（center_of_mass 使用正規化座標）
        bbox_aspect_ratio = bbox.height / bbox.width if bbox and bbox.width > 0 else 0
        # center_of_mass 已經是正規化座標（從 keypoints 取得）
        center_x = (
            (keypoints["left_hip"].x + keypoints["right_hip"].x) / 2
            if "left_hip" in keypoints and "right_hip" in keypoints
            else 0.5
        )
        center_y = (
            (keypoints["left_hip"].y + keypoints["right_hip"].y) / 2
            if "left_hip" in keypoints and "right_hip" in keypoints
            else 0.5
        )

        derived_features = DerivedFeatures(
            torso_angle=float(skeleton.torso_angle),
            aspect_ratio=float(bbox_aspect_ratio),
            center_of_mass=(float(center_x), float(center_y)),
        )

        return SkeletonFrame(
            frame_idx=frame_idx,
            timestamp=timestamp,
            keypoints=keypoints,
            bbox=bbox,
            derived_features=derived_features,
        )

    def extract_and_save(
        self,
        video_path: str | Path,
        output_path: str | Path,
        event_id: str | None = None,
    ) -> None:
        """提取骨架並儲存為 JSON

        Args:
            video_path: 影片檔案路徑
            output_path: 輸出 JSON 路徑
            event_id: 事件 ID
        """
        sequence = self.extract_from_video(video_path, event_id)
        sequence.to_json(output_path)

    def extract_from_frames(
        self,
        frames: list[FrameData],
        event_id: str,
        fps: float = 15.0,
    ) -> SkeletonSequence:
        """從 FrameData 列表提取骨架序列

        Args:
            frames: RollingBuffer.get_clip() 返回的 FrameData 列表
            event_id: 事件 ID
            fps: 影片幀率

        Returns:
            SkeletonSequence 實例
        """
        if not frames:
            return SkeletonSequence(
                metadata=SkeletonMetadata(
                    event_id=event_id,
                    timestamp=datetime.now().isoformat(),
                    source_video="memory",
                    duration_sec=0,
                    fps=int(fps),
                    total_frames=0,
                    extractor=ExtractorMetadata(
                        engine="yolov8", model=self.model_path, version="8.0.0"
                    ),
                ),
                keypoint_format="coco17",
                sequence=[],
                version="1.0",
            )

        duration_sec = (frames[-1].timestamp - frames[0].timestamp) if len(frames) > 1 else 0
        first_frame = frames[0].frame
        frame_shape = first_frame.shape[:2]  # (height, width)

        metadata = SkeletonMetadata(
            event_id=event_id,
            timestamp=datetime.now().isoformat(),
            source_video="memory",
            duration_sec=duration_sec,
            fps=int(fps),
            total_frames=len(frames),
            extractor=ExtractorMetadata(
                engine="yolov8", model=self.model_path, version="8.0.0"
            ),
        )

        sequence = []
        for idx, frame_data in enumerate(frames):
            skeletons = self.detector.detect(frame_data.frame)
            if skeletons:
                skeleton_frame = self._skeleton_to_frame(
                    skeletons[0], idx, frame_data.timestamp, frame_shape
                )
                sequence.append(skeleton_frame)

        return SkeletonSequence(
            metadata=metadata,
            keypoint_format="coco17",
            sequence=sequence,
            version="1.0",
        )


__all__ = ["SkeletonExtractor"]
