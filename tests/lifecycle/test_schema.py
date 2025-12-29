import json
import pytest
from src.lifecycle.schema import (
    Keypoint,
    BBox,
    DerivedFeatures,
    SkeletonFrame,
    ExtractorMetadata,
    SkeletonMetadata,
    SkeletonAnalysis,
    SkeletonSequence,
)


class TestKeypoint:
    def test_create_keypoint(self):
        kp = Keypoint(x=0.5, y=0.3, confidence=0.95)
        assert kp.x == 0.5
        assert kp.y == 0.3
        assert kp.confidence == 0.95

    def test_keypoint_normalized_coordinates(self):
        """關鍵點座標應該是正規化的 [0, 1]"""
        kp = Keypoint(x=0.0, y=1.0, confidence=1.0)
        assert 0.0 <= kp.x <= 1.0
        assert 0.0 <= kp.y <= 1.0


class TestBBox:
    def test_create_bbox(self):
        bbox = BBox(x=100, y=50, width=200, height=300)
        assert bbox.x == 100
        assert bbox.y == 50
        assert bbox.width == 200
        assert bbox.height == 300


class TestDerivedFeatures:
    def test_create_derived_features(self):
        features = DerivedFeatures(torso_angle=12.5, aspect_ratio=1.75, center_of_mass=(0.50, 0.48))
        assert features.torso_angle == 12.5
        assert features.aspect_ratio == 1.75
        assert features.center_of_mass == (0.50, 0.48)


class TestSkeletonFrame:
    @pytest.fixture
    def sample_keypoints(self):
        return {
            "nose": Keypoint(x=0.52, y=0.15, confidence=0.95),
            "left_shoulder": Keypoint(x=0.45, y=0.28, confidence=0.98),
            "right_shoulder": Keypoint(x=0.58, y=0.27, confidence=0.97),
        }

    def test_create_skeleton_frame(self, sample_keypoints):
        frame = SkeletonFrame(frame_idx=0, timestamp=0.0, keypoints=sample_keypoints)
        assert frame.frame_idx == 0
        assert frame.timestamp == 0.0
        assert len(frame.keypoints) == 3
        assert frame.keypoints["nose"].x == 0.52

    def test_skeleton_frame_with_bbox(self, sample_keypoints):
        bbox = BBox(x=120, y=80, width=200, height=350)
        frame = SkeletonFrame(frame_idx=0, timestamp=0.0, keypoints=sample_keypoints, bbox=bbox)
        assert frame.bbox.width == 200
        assert frame.bbox.height == 350

    def test_skeleton_frame_with_derived_features(self, sample_keypoints):
        features = DerivedFeatures(torso_angle=12.5, aspect_ratio=1.75, center_of_mass=(0.50, 0.48))
        frame = SkeletonFrame(
            frame_idx=0, timestamp=0.0, keypoints=sample_keypoints, derived_features=features
        )
        assert frame.derived_features.torso_angle == 12.5


class TestExtractorMetadata:
    def test_create_extractor_metadata_yolo(self):
        meta = ExtractorMetadata(engine="yolov8", model="yolov8n-pose.pt", version="8.0.0")
        assert meta.engine == "yolov8"
        assert meta.model == "yolov8n-pose.pt"

    def test_create_extractor_metadata_mediapipe(self):
        meta = ExtractorMetadata(engine="mediapipe", model="pose_landmarker_full", version="0.10.0")
        assert meta.engine == "mediapipe"


class TestSkeletonMetadata:
    @pytest.fixture
    def extractor_meta(self):
        return ExtractorMetadata(engine="yolov8", model="yolov8n-pose.pt", version="8.0.0")

    def test_create_skeleton_metadata(self, extractor_meta):
        meta = SkeletonMetadata(
            event_id="evt_1735372800",
            timestamp="2025-12-28T14:30:00Z",
            source_video="data/clips/test.mp4",
            duration_sec=10.0,
            fps=15,
            total_frames=150,
            extractor=extractor_meta,
        )
        assert meta.event_id == "evt_1735372800"
        assert meta.fps == 15
        assert meta.total_frames == 150


class TestSkeletonAnalysis:
    def test_create_analysis_fall_detected(self):
        analysis = SkeletonAnalysis(
            fall_detected=True,
            fall_frame_idx=45,
            fall_timestamp=3.0,
            recovery_frame_idx=105,
            rule_triggered="aspect_ratio_change",
        )
        assert analysis.fall_detected is True
        assert analysis.fall_frame_idx == 45
        assert analysis.rule_triggered == "aspect_ratio_change"

    def test_create_analysis_no_fall(self):
        analysis = SkeletonAnalysis(fall_detected=False)
        assert analysis.fall_detected is False
        assert analysis.fall_frame_idx is None


class TestSkeletonSequence:
    @pytest.fixture
    def sample_metadata(self):
        return SkeletonMetadata(
            event_id="evt_123",
            timestamp="2025-12-28T14:30:00Z",
            source_video="data/clips/test.mp4",
            duration_sec=1.0,
            fps=15,
            total_frames=15,
            extractor=ExtractorMetadata(engine="yolov8", model="yolov8n-pose.pt", version="8.0.0"),
        )

    @pytest.fixture
    def sample_frames(self):
        return [
            SkeletonFrame(
                frame_idx=0,
                timestamp=0.0,
                keypoints={
                    "nose": Keypoint(x=0.52, y=0.15, confidence=0.95),
                    "left_shoulder": Keypoint(x=0.45, y=0.28, confidence=0.98),
                },
            ),
            SkeletonFrame(
                frame_idx=1,
                timestamp=0.067,
                keypoints={
                    "nose": Keypoint(x=0.53, y=0.16, confidence=0.94),
                    "left_shoulder": Keypoint(x=0.46, y=0.29, confidence=0.97),
                },
            ),
        ]

    def test_create_skeleton_sequence(self, sample_metadata, sample_frames):
        seq = SkeletonSequence(
            metadata=sample_metadata, keypoint_format="coco17", sequence=sample_frames
        )
        assert seq.version == "1.0"
        assert seq.metadata.event_id == "evt_123"
        assert seq.keypoint_format == "coco17"
        assert len(seq.sequence) == 2

    def test_skeleton_sequence_with_analysis(self, sample_metadata, sample_frames):
        analysis = SkeletonAnalysis(fall_detected=True, fall_frame_idx=1, fall_timestamp=0.067)
        seq = SkeletonSequence(
            metadata=sample_metadata,
            keypoint_format="coco17",
            sequence=sample_frames,
            analysis=analysis,
        )
        assert seq.analysis.fall_detected is True
        assert seq.analysis.fall_frame_idx == 1

    def test_to_json(self, sample_metadata, sample_frames, tmp_path):
        """測試序列化為 JSON"""
        seq = SkeletonSequence(
            metadata=sample_metadata, keypoint_format="coco17", sequence=sample_frames
        )

        output_path = tmp_path / "test_skeleton.json"
        seq.to_json(output_path)

        assert output_path.exists()

        # 驗證 JSON 結構
        data = json.loads(output_path.read_text())
        assert data["version"] == "1.0"
        assert data["metadata"]["event_id"] == "evt_123"
        assert data["keypoint_format"] == "coco17"
        assert len(data["sequence"]) == 2
        assert data["sequence"][0]["frame_idx"] == 0
        assert "nose" in data["sequence"][0]["keypoints"]
        assert data["sequence"][0]["keypoints"]["nose"]["x"] == 0.52

    def test_to_json_with_bbox_and_features(self, sample_metadata, tmp_path):
        """測試包含 bbox 和 derived_features 的序列化"""
        frames = [
            SkeletonFrame(
                frame_idx=0,
                timestamp=0.0,
                keypoints={"nose": Keypoint(x=0.5, y=0.3, confidence=0.9)},
                bbox=BBox(x=100, y=50, width=200, height=300),
                derived_features=DerivedFeatures(
                    torso_angle=15.0, aspect_ratio=1.5, center_of_mass=(0.5, 0.5)
                ),
            )
        ]

        seq = SkeletonSequence(metadata=sample_metadata, keypoint_format="coco17", sequence=frames)

        output_path = tmp_path / "test_full.json"
        seq.to_json(output_path)

        data = json.loads(output_path.read_text())
        assert data["sequence"][0]["bbox"]["width"] == 200
        assert data["sequence"][0]["derived_features"]["torso_angle"] == 15.0
        assert data["sequence"][0]["derived_features"]["center_of_mass"]["x"] == 0.5

    def test_to_json_with_analysis(self, sample_metadata, sample_frames, tmp_path):
        """測試包含分析結果的序列化"""
        analysis = SkeletonAnalysis(
            fall_detected=True,
            fall_frame_idx=1,
            fall_timestamp=0.067,
            rule_triggered="aspect_ratio_change",
        )

        seq = SkeletonSequence(
            metadata=sample_metadata,
            keypoint_format="coco17",
            sequence=sample_frames,
            analysis=analysis,
        )

        output_path = tmp_path / "test_analysis.json"
        seq.to_json(output_path)

        data = json.loads(output_path.read_text())
        assert data["analysis"]["fall_detected"] is True
        assert data["analysis"]["fall_frame_idx"] == 1
        assert data["analysis"]["rule_triggered"] == "aspect_ratio_change"
