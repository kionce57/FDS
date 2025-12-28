"""Skeleton data structure for YOLOv8 Pose keypoints."""
from dataclasses import dataclass
from enum import IntEnum

import numpy as np


class Keypoint(IntEnum):
    """17 keypoints from COCO pose format."""
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16


@dataclass
class Skeleton:
    """Skeleton with 17 keypoints from YOLOv8 Pose."""

    keypoints: np.ndarray  # shape: (17, 3) -> x, y, visibility

    def get_point(self, keypoint: Keypoint) -> tuple[float, float, float]:
        """Get (x, y, visibility) for a specific keypoint."""
        return tuple(self.keypoints[keypoint])

    @property
    def nose(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.NOSE)

    @property
    def left_shoulder(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.LEFT_SHOULDER)

    @property
    def right_shoulder(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.RIGHT_SHOULDER)

    @property
    def left_hip(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.LEFT_HIP)

    @property
    def right_hip(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.RIGHT_HIP)

    @property
    def left_knee(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.LEFT_KNEE)

    @property
    def right_knee(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.RIGHT_KNEE)

    @property
    def left_ankle(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.LEFT_ANKLE)

    @property
    def right_ankle(self) -> tuple[float, float, float]:
        return self.get_point(Keypoint.RIGHT_ANKLE)

    @property
    def hip_center(self) -> tuple[float, float]:
        """Calculate center point between hips."""
        lh = self.left_hip
        rh = self.right_hip
        return ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2)

    @property
    def shoulder_center(self) -> tuple[float, float]:
        """Calculate center point between shoulders."""
        ls = self.left_shoulder
        rs = self.right_shoulder
        return ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)

    @property
    def torso_angle(self) -> float:
        """Calculate torso angle from vertical (degrees).
        
        0° = standing upright
        90° = lying horizontal
        """
        sc = self.shoulder_center
        hc = self.hip_center
        
        dx = sc[0] - hc[0]
        dy = sc[1] - hc[1]
        
        # Calculate angle from vertical (y-axis pointing down in image coords)
        angle_rad = np.arctan2(abs(dx), abs(dy))
        return np.degrees(angle_rad)

    @property
    def hip_height_ratio(self) -> float:
        """Ratio of hip height to total body height.
        
        Standing: hip is around 0.5 of total height
        Fallen: hip is very low (close to ankle level)
        """
        hip_y = self.hip_center[1]
        nose_y = self.nose[1]
        ankle_y = (self.left_ankle[1] + self.right_ankle[1]) / 2
        
        total_height = ankle_y - nose_y
        if abs(total_height) < 1:
            return 0.5
        
        hip_from_top = hip_y - nose_y
        return hip_from_top / total_height
