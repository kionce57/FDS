"""
關鍵點格式定義

定義 COCO17 和 MediaPipe33 的關鍵點名稱與映射關係。
"""

from enum import Enum


class KeypointFormat(str, Enum):
    """支援的關鍵點格式"""

    COCO17 = "coco17"
    MEDIAPIPE33 = "mediapipe33"


# COCO17 關鍵點定義（YOLOv8 原生格式）
COCO17_KEYPOINTS = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


# MediaPipe33 關鍵點定義
MEDIAPIPE33_KEYPOINTS = [
    # 臉部 (0-10)
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    # 上半身 (11-22)
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    # 下半身 (23-32)
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


# MediaPipe → COCO17 映射（向下相容）
MEDIAPIPE_TO_COCO17 = {
    "nose": "nose",
    "left_eye": "left_eye",
    "right_eye": "right_eye",
    "left_ear": "left_ear",
    "right_ear": "right_ear",
    "left_shoulder": "left_shoulder",
    "right_shoulder": "right_shoulder",
    "left_elbow": "left_elbow",
    "right_elbow": "right_elbow",
    "left_wrist": "left_wrist",
    "right_wrist": "right_wrist",
    "left_hip": "left_hip",
    "right_hip": "right_hip",
    "left_knee": "left_knee",
    "right_knee": "right_knee",
    "left_ankle": "left_ankle",
    "right_ankle": "right_ankle",
}


# COCO17 骨架連接（用於視覺化）
COCO17_SKELETON = [
    # 頭部
    (0, 1),  # nose -> left_eye
    (0, 2),  # nose -> right_eye
    (1, 3),  # left_eye -> left_ear
    (2, 4),  # right_eye -> right_ear
    # 軀幹
    (5, 6),  # left_shoulder -> right_shoulder
    (5, 11),  # left_shoulder -> left_hip
    (6, 12),  # right_shoulder -> right_hip
    (11, 12),  # left_hip -> right_hip
    # 左手臂
    (5, 7),  # left_shoulder -> left_elbow
    (7, 9),  # left_elbow -> left_wrist
    # 右手臂
    (6, 8),  # right_shoulder -> right_elbow
    (8, 10),  # right_elbow -> right_wrist
    # 左腿
    (11, 13),  # left_hip -> left_knee
    (13, 15),  # left_knee -> left_ankle
    # 右腿
    (12, 14),  # right_hip -> right_knee
    (14, 16),  # right_knee -> right_ankle
]


def get_keypoint_count(format: KeypointFormat) -> int:
    """取得格式的關鍵點數量

    Args:
        format: 關鍵點格式

    Returns:
        關鍵點數量
    """
    if format == KeypointFormat.COCO17:
        return len(COCO17_KEYPOINTS)
    elif format == KeypointFormat.MEDIAPIPE33:
        return len(MEDIAPIPE33_KEYPOINTS)
    else:
        raise ValueError(f"Unknown format: {format}")


def get_keypoint_names(format: KeypointFormat) -> list[str]:
    """取得格式的關鍵點名稱列表

    Args:
        format: 關鍵點格式

    Returns:
        關鍵點名稱列表
    """
    if format == KeypointFormat.COCO17:
        return COCO17_KEYPOINTS.copy()
    elif format == KeypointFormat.MEDIAPIPE33:
        return MEDIAPIPE33_KEYPOINTS.copy()
    else:
        raise ValueError(f"Unknown format: {format}")


__all__ = [
    "KeypointFormat",
    "COCO17_KEYPOINTS",
    "MEDIAPIPE33_KEYPOINTS",
    "MEDIAPIPE_TO_COCO17",
    "COCO17_SKELETON",
    "get_keypoint_count",
    "get_keypoint_names",
]
