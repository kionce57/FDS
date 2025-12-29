"""
JSON Schema 驗證器

提供嚴格的骨架序列資料驗證功能。
"""

import json
from pathlib import Path

try:
    from jsonschema import Draft7Validator

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


class ValidationError(Exception):
    """驗證錯誤"""

    pass


class SkeletonValidator:
    """骨架序列 JSON Schema 驗證器

    提供兩層驗證：
    1. JSON Schema 結構驗證（必須）
    2. 語義驗證（可選，例如檢查 keypoint 數量是否符合格式）

    Example:
        >>> validator = SkeletonValidator()
        >>> validator.validate_file("data/skeletons/evt_123.json")
        True
    """

    def __init__(self, schema_path: str | Path | None = None):
        """初始化驗證器

        Args:
            schema_path: JSON Schema 檔案路徑（預設為 config/skeleton_schema.json）

        Raises:
            ImportError: 若未安裝 jsonschema 套件
            FileNotFoundError: 若 schema 檔案不存在
        """
        if not JSONSCHEMA_AVAILABLE:
            raise ImportError(
                "jsonschema package is required for validation. Install it with: uv add jsonschema"
            )

        if schema_path is None:
            # 預設使用專案根目錄下的 schema
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent
            schema_path = project_root / "config" / "skeleton_schema.json"

        self.schema_path = Path(schema_path)
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.validator = Draft7Validator(self.schema)

    def validate(self, data: dict) -> bool:
        """驗證骨架序列資料

        Args:
            data: 骨架序列資料字典

        Returns:
            驗證通過回傳 True

        Raises:
            ValidationError: 驗證失敗時拋出，包含詳細錯誤訊息
        """
        # JSON Schema 結構驗證
        errors = list(self.validator.iter_errors(data))
        if errors:
            error_messages = []
            for error in errors:
                path = ".".join(str(p) for p in error.path) if error.path else "root"
                error_messages.append(f"  - {path}: {error.message}")

            raise ValidationError("JSON Schema validation failed:\n" + "\n".join(error_messages))

        # 語義驗證
        self._validate_semantics(data)

        return True

    def _validate_semantics(self, data: dict) -> None:
        """語義驗證（額外的業務邏輯檢查）

        Args:
            data: 骨架序列資料字典

        Raises:
            ValidationError: 語義驗證失敗
        """
        # 1. 檢查 keypoint_format 與 keypoints 數量一致性
        keypoint_format = data["keypoint_format"]
        expected_count = 17 if keypoint_format == "coco17" else 33

        for frame in data["sequence"]:
            keypoint_count = len(frame["keypoints"])
            # 允許部分關鍵點缺失（例如遮擋），但不應超過預期數量
            if keypoint_count > expected_count:
                raise ValidationError(
                    f"Frame {frame['frame_idx']}: keypoint count ({keypoint_count}) "
                    f"exceeds expected ({expected_count}) for format '{keypoint_format}'"
                )

        # 2. 檢查 sequence 順序性（frame_idx 應該遞增）
        frame_indices = [frame["frame_idx"] for frame in data["sequence"]]
        if frame_indices != sorted(frame_indices):
            raise ValidationError(f"Frame indices are not in ascending order: {frame_indices}")

        # 3. 檢查 timestamp 單調性
        timestamps = [frame["timestamp"] for frame in data["sequence"]]
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                raise ValidationError(
                    f"Timestamps are not monotonic: frame {i - 1} has {timestamps[i - 1]}, "
                    f"frame {i} has {timestamps[i]}"
                )

        # 4. 檢查 total_frames 與實際幀數的合理性
        total_frames = data["metadata"]["total_frames"]
        sequence_length = len(data["sequence"])
        # sequence 可能是片段，所以只要不超過 total_frames 即可
        if sequence_length > total_frames:
            raise ValidationError(
                f"Sequence length ({sequence_length}) exceeds total_frames ({total_frames})"
            )

        # 5. 如果有 analysis，檢查 fall_frame_idx 是否在有效範圍內
        if data.get("analysis"):
            analysis = data["analysis"]
            if analysis.get("fall_frame_idx") is not None:
                fall_idx = analysis["fall_frame_idx"]
                max_idx = max(frame_indices)
                if fall_idx > max_idx:
                    raise ValidationError(
                        f"analysis.fall_frame_idx ({fall_idx}) exceeds "
                        f"maximum frame index ({max_idx})"
                    )

    def validate_file(self, file_path: str | Path) -> bool:
        """驗證 JSON 檔案

        Args:
            file_path: JSON 檔案路徑

        Returns:
            驗證通過回傳 True

        Raises:
            FileNotFoundError: 檔案不存在
            json.JSONDecodeError: JSON 格式錯誤
            ValidationError: 驗證失敗
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        return self.validate(data)

    def get_schema_version(self) -> str:
        """取得 Schema 版本號

        Returns:
            Schema 版本號
        """
        return self.schema.get("version", "unknown")


__all__ = ["SkeletonValidator", "ValidationError"]
