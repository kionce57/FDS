from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class FrameData:
    timestamp: float
    frame: np.ndarray
    bbox: tuple[int, int, int, int] | None


class RollingBuffer:
    def __init__(self, buffer_seconds: float = 10.0, fps: float = 15.0):
        self.max_frames = int(buffer_seconds * fps)
        self.buffer: deque[FrameData] = deque(maxlen=self.max_frames)

    def push(self, frame_data: FrameData) -> None:
        self.buffer.append(frame_data)

    def get_clip(
        self,
        event_time: float,
        before_sec: float = 5.0,
        after_sec: float = 5.0,
    ) -> list[FrameData]:
        start_time = event_time - before_sec
        end_time = event_time + after_sec
        return [f for f in self.buffer if start_time <= f.timestamp <= end_time]

    def clear(self) -> None:
        self.buffer.clear()

    def __len__(self) -> int:
        return len(self.buffer)
