import pytest
from src.lifecycle.schema.formats import (
    KeypointFormat,
    COCO17_KEYPOINTS,
    MEDIAPIPE33_KEYPOINTS,
    MEDIAPIPE_TO_COCO17,
    COCO17_SKELETON,
    get_keypoint_count,
    get_keypoint_names,
)


class TestKeypointFormat:
    def test_coco17_format(self):
        assert KeypointFormat.COCO17 == "coco17"

    def test_mediapipe33_format(self):
        assert KeypointFormat.MEDIAPIPE33 == "mediapipe33"


class TestCOCO17Keypoints:
    def test_coco17_keypoint_count(self):
        assert len(COCO17_KEYPOINTS) == 17

    def test_coco17_has_nose(self):
        assert "nose" in COCO17_KEYPOINTS

    def test_coco17_has_shoulders(self):
        assert "left_shoulder" in COCO17_KEYPOINTS
        assert "right_shoulder" in COCO17_KEYPOINTS

    def test_coco17_has_hips(self):
        assert "left_hip" in COCO17_KEYPOINTS
        assert "right_hip" in COCO17_KEYPOINTS

    def test_coco17_has_ankles(self):
        assert "left_ankle" in COCO17_KEYPOINTS
        assert "right_ankle" in COCO17_KEYPOINTS


class TestMediaPipe33Keypoints:
    def test_mediapipe33_keypoint_count(self):
        assert len(MEDIAPIPE33_KEYPOINTS) == 33

    def test_mediapipe33_has_face_landmarks(self):
        assert "nose" in MEDIAPIPE33_KEYPOINTS
        assert "left_eye_inner" in MEDIAPIPE33_KEYPOINTS
        assert "mouth_left" in MEDIAPIPE33_KEYPOINTS

    def test_mediapipe33_has_hand_landmarks(self):
        assert "left_pinky" in MEDIAPIPE33_KEYPOINTS
        assert "left_index" in MEDIAPIPE33_KEYPOINTS
        assert "left_thumb" in MEDIAPIPE33_KEYPOINTS

    def test_mediapipe33_has_foot_landmarks(self):
        assert "left_heel" in MEDIAPIPE33_KEYPOINTS
        assert "left_foot_index" in MEDIAPIPE33_KEYPOINTS


class TestMediaPipeToCOCO17Mapping:
    def test_mapping_count(self):
        """映射應該包含 17 個關鍵點"""
        assert len(MEDIAPIPE_TO_COCO17) == 17

    def test_nose_mapping(self):
        assert MEDIAPIPE_TO_COCO17["nose"] == "nose"

    def test_shoulder_mapping(self):
        assert MEDIAPIPE_TO_COCO17["left_shoulder"] == "left_shoulder"
        assert MEDIAPIPE_TO_COCO17["right_shoulder"] == "right_shoulder"

    def test_all_coco17_covered(self):
        """所有 COCO17 關鍵點都應該在映射中"""
        mapped_values = set(MEDIAPIPE_TO_COCO17.values())
        coco17_set = set(COCO17_KEYPOINTS)
        assert mapped_values == coco17_set


class TestCOCO17Skeleton:
    def test_skeleton_connections_count(self):
        """COCO17 應該有 16 條骨架連接"""
        assert len(COCO17_SKELETON) == 16

    def test_skeleton_connections_valid(self):
        """所有連接的索引應該在 [0, 16] 範圍內"""
        for start, end in COCO17_SKELETON:
            assert 0 <= start < 17
            assert 0 <= end < 17

    def test_nose_connections(self):
        """鼻子應該連接到眼睛"""
        connections = set(COCO17_SKELETON)
        assert (0, 1) in connections  # nose -> left_eye
        assert (0, 2) in connections  # nose -> right_eye


class TestGetKeypointCount:
    def test_coco17_count(self):
        count = get_keypoint_count(KeypointFormat.COCO17)
        assert count == 17

    def test_mediapipe33_count(self):
        count = get_keypoint_count(KeypointFormat.MEDIAPIPE33)
        assert count == 33

    def test_invalid_format_raises_error(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_keypoint_count("invalid_format")


class TestGetKeypointNames:
    def test_coco17_names(self):
        names = get_keypoint_names(KeypointFormat.COCO17)
        assert len(names) == 17
        assert names[0] == "nose"
        assert "left_shoulder" in names

    def test_mediapipe33_names(self):
        names = get_keypoint_names(KeypointFormat.MEDIAPIPE33)
        assert len(names) == 33
        assert names[0] == "nose"
        assert "left_pinky" in names

    def test_returns_copy(self):
        """應該回傳副本而非原始列表"""
        names1 = get_keypoint_names(KeypointFormat.COCO17)
        names2 = get_keypoint_names(KeypointFormat.COCO17)
        assert names1 is not names2
        assert names1 == names2

    def test_invalid_format_raises_error(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_keypoint_names("invalid_format")
