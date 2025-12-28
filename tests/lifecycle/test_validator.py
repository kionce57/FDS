import json
import pytest
from pathlib import Path

# 先嘗試 import，如果失敗則跳過所有測試
pytest.importorskip("jsonschema")

from src.lifecycle.schema.validator import SkeletonValidator, ValidationError


class TestSkeletonValidator:
    @pytest.fixture
    def validator(self):
        """建立驗證器實例"""
        return SkeletonValidator()

    @pytest.fixture
    def valid_data(self):
        """最小有效骨架序列資料"""
        return {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 15,
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 0,
                    "timestamp": 0.0,
                    "keypoints": {
                        "nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}
                    }
                }
            ]
        }

    def test_validator_init(self, validator):
        """測試驗證器初始化"""
        assert validator.schema is not None
        assert validator.validator is not None

    def test_get_schema_version(self, validator):
        """測試取得 schema 版本"""
        version = validator.get_schema_version()
        assert version == "1.0.0"

    def test_validate_valid_data(self, validator, valid_data):
        """測試驗證有效資料"""
        assert validator.validate(valid_data) is True

    def test_validate_missing_required_field(self, validator, valid_data):
        """測試缺少必要欄位"""
        del valid_data["metadata"]
        with pytest.raises(ValidationError, match="validation failed"):
            validator.validate(valid_data)

    def test_validate_invalid_event_id_format(self, validator, valid_data):
        """測試 event_id 格式錯誤"""
        valid_data["metadata"]["event_id"] = "invalid_id"
        with pytest.raises(ValidationError):
            validator.validate(valid_data)

    def test_validate_invalid_engine(self, validator, valid_data):
        """測試無效的提取引擎"""
        valid_data["metadata"]["extractor"]["engine"] = "invalid_engine"
        with pytest.raises(ValidationError):
            validator.validate(valid_data)

    def test_validate_invalid_keypoint_format(self, validator, valid_data):
        """測試無效的關鍵點格式"""
        valid_data["keypoint_format"] = "invalid_format"
        with pytest.raises(ValidationError):
            validator.validate(valid_data)

    def test_validate_keypoint_coords_out_of_range(self, validator, valid_data):
        """測試關鍵點座標超出範圍"""
        valid_data["sequence"][0]["keypoints"]["nose"]["x"] = 1.5  # 超出 [0, 1]
        with pytest.raises(ValidationError):
            validator.validate(valid_data)

    def test_validate_negative_confidence(self, validator, valid_data):
        """測試負數置信度"""
        valid_data["sequence"][0]["keypoints"]["nose"]["confidence"] = -0.1
        with pytest.raises(ValidationError):
            validator.validate(valid_data)

    def test_validate_with_bbox(self, validator, valid_data):
        """測試包含 bbox 的資料"""
        valid_data["sequence"][0]["bbox"] = {
            "x": 100,
            "y": 50,
            "width": 200,
            "height": 300
        }
        assert validator.validate(valid_data) is True

    def test_validate_with_derived_features(self, validator, valid_data):
        """測試包含衍生特徵的資料"""
        valid_data["sequence"][0]["derived_features"] = {
            "torso_angle": 12.5,
            "aspect_ratio": 1.75,
            "center_of_mass": {"x": 0.5, "y": 0.5}
        }
        assert validator.validate(valid_data) is True

    def test_validate_with_analysis(self, validator, valid_data):
        """測試包含分析結果的資料"""
        valid_data["analysis"] = {
            "fall_detected": True,
            "fall_frame_idx": 0,
            "fall_timestamp": 0.0,
            "recovery_frame_idx": None,
            "rule_triggered": "aspect_ratio_change"
        }
        assert validator.validate(valid_data) is True


class TestSemanticValidation:
    """語義驗證測試"""

    @pytest.fixture
    def validator(self):
        return SkeletonValidator()

    def test_too_many_keypoints_for_coco17(self, validator):
        """測試 COCO17 格式但關鍵點數量過多"""
        data = {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 15,
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 0,
                    "timestamp": 0.0,
                    "keypoints": {f"kp_{i}": {"x": 0.5, "y": 0.5, "confidence": 0.9} for i in range(20)}
                }
            ]
        }
        with pytest.raises(ValidationError, match="exceeds expected"):
            validator.validate(data)

    def test_frame_indices_not_sorted(self, validator):
        """測試幀索引未排序"""
        data = {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 15,
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 1,
                    "timestamp": 0.0,
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                },
                {
                    "frame_idx": 0,
                    "timestamp": 0.1,
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                }
            ]
        }
        with pytest.raises(ValidationError, match="not in ascending order"):
            validator.validate(data)

    def test_timestamps_not_monotonic(self, validator):
        """測試時間戳記非單調"""
        data = {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 15,
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 0,
                    "timestamp": 0.1,
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                },
                {
                    "frame_idx": 1,
                    "timestamp": 0.05,  # 時間倒退
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                }
            ]
        }
        with pytest.raises(ValidationError, match="not monotonic"):
            validator.validate(data)

    def test_sequence_exceeds_total_frames(self, validator):
        """測試序列長度超過 total_frames"""
        data = {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 1,  # 只有 1 幀
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 0,
                    "timestamp": 0.0,
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                },
                {
                    "frame_idx": 1,
                    "timestamp": 0.1,
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                }
            ]
        }
        with pytest.raises(ValidationError, match="exceeds total_frames"):
            validator.validate(data)

    def test_fall_frame_idx_out_of_range(self, validator):
        """測試 fall_frame_idx 超出範圍"""
        data = {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 15,
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 0,
                    "timestamp": 0.0,
                    "keypoints": {"nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}}
                }
            ],
            "analysis": {
                "fall_detected": True,
                "fall_frame_idx": 10,  # 超出 sequence 範圍
                "fall_timestamp": 0.5
            }
        }
        with pytest.raises(ValidationError, match="exceeds maximum frame index"):
            validator.validate(data)


class TestValidateFile:
    """檔案驗證測試"""

    @pytest.fixture
    def validator(self):
        return SkeletonValidator()

    def test_validate_nonexistent_file(self, validator):
        """測試驗證不存在的檔案"""
        with pytest.raises(FileNotFoundError):
            validator.validate_file("nonexistent.json")

    def test_validate_invalid_json_file(self, validator, tmp_path):
        """測試驗證格式錯誤的 JSON 檔案"""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{invalid json")

        with pytest.raises(ValidationError, match="Invalid JSON"):
            validator.validate_file(invalid_json)

    def test_validate_valid_file(self, validator, tmp_path):
        """測試驗證有效的 JSON 檔案"""
        valid_data = {
            "version": "1.0",
            "metadata": {
                "event_id": "evt_123",
                "timestamp": "2025-12-28T14:30:00Z",
                "source_video": "test.mp4",
                "duration_sec": 1.0,
                "fps": 15,
                "total_frames": 15,
                "extractor": {
                    "engine": "yolov8",
                    "model": "yolov8n-pose.pt",
                    "version": "8.0.0"
                }
            },
            "keypoint_format": "coco17",
            "sequence": [
                {
                    "frame_idx": 0,
                    "timestamp": 0.0,
                    "keypoints": {
                        "nose": {"x": 0.5, "y": 0.3, "confidence": 0.9}
                    }
                }
            ]
        }

        valid_file = tmp_path / "valid.json"
        valid_file.write_text(json.dumps(valid_data))

        assert validator.validate_file(valid_file) is True
