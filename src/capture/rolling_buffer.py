import threading
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
        """
        Initialize the rolling buffer with capacity determined by time window and frame rate.
        
        Parameters:
        	buffer_seconds (float): Number of seconds of video to retain in the buffer.
        	fps (float): Expected frames per second used to compute the buffer capacity.
        """
        self.max_frames = int(buffer_seconds * fps)
        self.buffer: deque[FrameData] = deque(maxlen=self.max_frames)
        self._lock = threading.Lock()

    def push(self, frame_data: FrameData) -> None:
        """
        Append a FrameData item to the rolling buffer using the internal lock to ensure thread safety.
        
        The buffer is bounded by its configured capacity; if full, appending will discard the oldest frame.
        
        Parameters:
            frame_data (FrameData): The frame to store (includes timestamp, image, and optional bbox).
        """
        with self._lock:
            self.buffer.append(frame_data)

    def get_clip(
        self,
        event_time: float,
        before_sec: float = 5.0,
        after_sec: float = 5.0,
    ) -> list[FrameData]:
        """
        Retrieve frames whose timestamps fall within a time window centered on the given event time.
        
        Parameters:
            event_time (float): Reference timestamp in seconds for the clip.
            before_sec (float): Seconds before `event_time` to include.
            after_sec (float): Seconds after `event_time` to include.
        
        Returns:
            list[FrameData]: Frames with timestamps between `event_time - before_sec` and `event_time + after_sec` (inclusive).
        """
        start_time = event_time - before_sec
        end_time = event_time + after_sec
        with self._lock:
            return [f for f in self.buffer if start_time <= f.timestamp <= end_time]

    def clear(self) -> None:
        """
        Clear all stored frames from the rolling buffer in a thread-safe manner.
        
        This removes every FrameData currently held so subsequent reads see an empty buffer.
        """
        with self._lock:
            self.buffer.clear()

    def __len__(self) -> int:
        """
        Return the number of frames currently stored in the rolling buffer.
        
        This method acquires the internal lock to provide a thread-safe count of stored FrameData entries.
        
        Returns:
            int: The number of FrameData objects in the buffer.
        """
        with self._lock:
            return len(self.buffer)