"""
FDS Skeleton Sequence Schema

資料格式定義，用於骨架序列的儲存與交換。
支援 COCO17 和 MediaPipe33 兩種關鍵點格式。
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class Keypoint:
    """關鍵點資料結構

    座標使用正規化格式 [0, 1]，相對於影像寬高
    """

    x: float  # 正規化 x 座標 [0, 1]
    y: float  # 正規化 y 座標 [0, 1]
    confidence: float  # 置信度 [0, 1]


@dataclass
class BBox:
    """Bounding Box 資料結構

    使用絕對像素座標
    """

    x: int
    y: int
    width: int
    height: int


@dataclass
class DerivedFeatures:
    """衍生特徵

    從骨架計算得出的額外特徵
    """

    torso_angle: float  # 軀幹角度（度）
    aspect_ratio: float  # 長寬比
    center_of_mass: tuple[float, float]  # 質心座標 (x, y)


@dataclass
class SkeletonFrame:
    """單幀骨架資料"""

    frame_idx: int
    timestamp: float
    keypoints: dict[str, Keypoint]
    bbox: BBox | None = None
    derived_features: DerivedFeatures | None = None


@dataclass
class ExtractorMetadata:
    """提取器元資料"""

    engine: Literal["yolov8", "yolo11", "mediapipe"]
    model: str
    version: str


@dataclass
class SkeletonMetadata:
    """骨架序列元資料"""

    event_id: str
    timestamp: str  # ISO 8601 格式
    source_video: str
    duration_sec: float
    fps: int
    total_frames: int
    extractor: ExtractorMetadata


@dataclass
class SkeletonAnalysis:
    """跌倒分析結果"""

    fall_detected: bool
    fall_frame_idx: int | None = None
    fall_timestamp: float | None = None
    recovery_frame_idx: int | None = None
    rule_triggered: str | None = None


@dataclass
class SkeletonSequence:
    """完整骨架序列

    這是頂層資料結構，包含完整的骨架序列資訊。
    可以序列化為 JSON 或轉換為 Parquet。
    """

    metadata: SkeletonMetadata
    keypoint_format: Literal["coco17", "mediapipe33"]
    sequence: list[SkeletonFrame]
    version: str = "1.0"
    analysis: SkeletonAnalysis | None = None

    def to_json(self, path: str | Path) -> None:
        """序列化為 JSON 檔案

        Args:
            path: 輸出檔案路徑
        """
        data = {
            "version": self.version,
            "metadata": {
                "event_id": self.metadata.event_id,
                "timestamp": self.metadata.timestamp,
                "source_video": self.metadata.source_video,
                "duration_sec": self.metadata.duration_sec,
                "fps": self.metadata.fps,
                "total_frames": self.metadata.total_frames,
                "extractor": {
                    "engine": self.metadata.extractor.engine,
                    "model": self.metadata.extractor.model,
                    "version": self.metadata.extractor.version,
                },
            },
            "keypoint_format": self.keypoint_format,
            "sequence": [
                {
                    "frame_idx": frame.frame_idx,
                    "timestamp": frame.timestamp,
                    "keypoints": {
                        name: {"x": kp.x, "y": kp.y, "confidence": kp.confidence}
                        for name, kp in frame.keypoints.items()
                    },
                    "bbox": {
                        "x": frame.bbox.x,
                        "y": frame.bbox.y,
                        "width": frame.bbox.width,
                        "height": frame.bbox.height,
                    }
                    if frame.bbox
                    else None,
                    "derived_features": {
                        "torso_angle": frame.derived_features.torso_angle,
                        "aspect_ratio": frame.derived_features.aspect_ratio,
                        "center_of_mass": {
                            "x": frame.derived_features.center_of_mass[0],
                            "y": frame.derived_features.center_of_mass[1],
                        },
                    }
                    if frame.derived_features
                    else None,
                }
                for frame in self.sequence
            ],
            "analysis": {
                "fall_detected": self.analysis.fall_detected,
                "fall_frame_idx": self.analysis.fall_frame_idx,
                "fall_timestamp": self.analysis.fall_timestamp,
                "recovery_frame_idx": self.analysis.recovery_frame_idx,
                "rule_triggered": self.analysis.rule_triggered,
            }
            if self.analysis
            else None,
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def from_json(cls, path: str | Path) -> "SkeletonSequence":
        """從 JSON 檔案反序列化

        Args:
            path: JSON 檔案路徑

        Returns:
            SkeletonSequence 實例
        """
        data = json.loads(Path(path).read_text())

        # 解析 metadata
        extractor = ExtractorMetadata(
            engine=data["metadata"]["extractor"]["engine"],
            model=data["metadata"]["extractor"]["model"],
            version=data["metadata"]["extractor"]["version"],
        )

        metadata = SkeletonMetadata(
            event_id=data["metadata"]["event_id"],
            timestamp=data["metadata"]["timestamp"],
            source_video=data["metadata"]["source_video"],
            duration_sec=data["metadata"]["duration_sec"],
            fps=data["metadata"]["fps"],
            total_frames=data["metadata"]["total_frames"],
            extractor=extractor,
        )

        # 解析 sequence
        sequence = []
        for frame_data in data["sequence"]:
            keypoints = {
                name: Keypoint(x=kp["x"], y=kp["y"], confidence=kp["confidence"])
                for name, kp in frame_data["keypoints"].items()
            }

            bbox = None
            if frame_data.get("bbox"):
                bbox = BBox(
                    x=frame_data["bbox"]["x"],
                    y=frame_data["bbox"]["y"],
                    width=frame_data["bbox"]["width"],
                    height=frame_data["bbox"]["height"],
                )

            derived_features = None
            if frame_data.get("derived_features"):
                df = frame_data["derived_features"]
                derived_features = DerivedFeatures(
                    torso_angle=df["torso_angle"],
                    aspect_ratio=df["aspect_ratio"],
                    center_of_mass=(df["center_of_mass"]["x"], df["center_of_mass"]["y"]),
                )

            frame = SkeletonFrame(
                frame_idx=frame_data["frame_idx"],
                timestamp=frame_data["timestamp"],
                keypoints=keypoints,
                bbox=bbox,
                derived_features=derived_features,
            )
            sequence.append(frame)

        # 解析 analysis (可選)
        analysis = None
        if data.get("analysis"):
            analysis = SkeletonAnalysis(
                fall_detected=data["analysis"]["fall_detected"],
                fall_frame_idx=data["analysis"].get("fall_frame_idx"),
                fall_timestamp=data["analysis"].get("fall_timestamp"),
                recovery_frame_idx=data["analysis"].get("recovery_frame_idx"),
                rule_triggered=data["analysis"].get("rule_triggered"),
            )

        return cls(
            version=data["version"],
            metadata=metadata,
            keypoint_format=data["keypoint_format"],
            sequence=sequence,
            analysis=analysis,
        )


__all__ = [
    "Keypoint",
    "BBox",
    "DerivedFeatures",
    "SkeletonFrame",
    "ExtractorMetadata",
    "SkeletonMetadata",
    "SkeletonAnalysis",
    "SkeletonSequence",
]
