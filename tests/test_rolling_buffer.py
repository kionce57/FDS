import pytest
import numpy as np
from src.capture.rolling_buffer import RollingBuffer, FrameData


class TestRollingBuffer:
    def test_push_single_frame(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = FrameData(timestamp=0.0, frame=frame, bbox=None)
        buffer.push(frame_data)
        assert len(buffer) == 1

    def test_buffer_max_capacity(self):
        buffer = RollingBuffer(buffer_seconds=1.0, fps=10.0)
        for i in range(15):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            buffer.push(FrameData(timestamp=float(i) * 0.1, frame=frame, bbox=None))
        assert len(buffer) == 10

    def test_get_clip_within_range(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=10.0)
        for i in range(100):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            buffer.push(FrameData(timestamp=float(i) * 0.1, frame=frame, bbox=None))

        clip = buffer.get_clip(event_time=5.0, before_sec=1.0, after_sec=1.0)
        timestamps = [f.timestamp for f in clip]

        assert all(4.0 <= t <= 6.0 for t in timestamps)
        assert len(clip) == 21

    def test_get_clip_empty_buffer(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=10.0)
        clip = buffer.get_clip(event_time=5.0, before_sec=1.0, after_sec=1.0)
        assert len(clip) == 0

    def test_clear_buffer(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=10.0)
        for i in range(10):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            buffer.push(FrameData(timestamp=float(i), frame=frame, bbox=None))
        buffer.clear()
        assert len(buffer) == 0
