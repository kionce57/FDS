"""Tests for delayed clip recording (post-event recording)."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.events.clip_recorder import ClipRecorder
from src.events.observer import FallEvent


class TestDelayedRecording:
    """Tests for delayed clip recording after fall confirmed."""

    @pytest.fixture
    def rolling_buffer(self):
        """
        Create a RollingBuffer preloaded with approximately 4 seconds of test frames and return it along with the reference event timestamp.
        
        The buffer is instantiated with 10 seconds of capacity at 15 FPS and seeded with 60 FrameData objects. Each frame is a zeroed 480x640 RGB numpy array; timestamps start at event_time - 2 seconds and advance by ~0.066 seconds (≈15 FPS), covering roughly event_time - 2 to event_time + 1.9.
        
        Returns:
            tuple: (RollingBuffer, float) — the preloaded rolling buffer and the generated event_time timestamp.
        """
        buffer = RollingBuffer(buffer_seconds=10, fps=15)
        event_time = time.time()
        for i in range(60):  # 4 seconds of frames
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame_data = FrameData(
                timestamp=event_time - 2 + i * 0.066,  # ~15fps
                frame=frame,
                bbox=None,
            )
            buffer.push(frame_data)
        return buffer, event_time

    @pytest.fixture
    def fall_event(self, rolling_buffer):
        """
        Create a FallEvent using the event_time extracted from a rolling_buffer fixture.
        
        Parameters:
            rolling_buffer (tuple): A pair (rolling_buffer_obj, event_time); the second element is the timestamp to use for the event's confirmation and last notification.
        
        Returns:
            FallEvent: An event with id "test_delayed", `confirmed_at` and `last_notified_at` set to the rolling buffer's event_time, and `notification_count` set to 1.
        """
        _, event_time = rolling_buffer
        return FallEvent(
            event_id="test_delayed",
            confirmed_at=event_time,
            last_notified_at=event_time,
            notification_count=1,
        )

    def test_recording_is_delayed_by_clip_after_sec(self, rolling_buffer, fall_event, tmp_path):
        """Recording should happen after clip_after_sec delay, not immediately."""
        buffer, _ = rolling_buffer
        clip_after_sec = 0.2

        recorder = ClipRecorder(
            rolling_buffer=buffer,
            clip_before_sec=1.0,
            clip_after_sec=clip_after_sec,
            output_dir=str(tmp_path / "clips"),
            fps=15,
        )

        with patch.object(recorder, "save", return_value="/fake/path.mp4") as mock_save:
            recorder.on_fall_confirmed(fall_event)

            # Should NOT be called immediately
            assert not mock_save.called

            # Wait for delay + buffer
            time.sleep(clip_after_sec + 0.1)

            # Now should be called
            mock_save.assert_called_once()

        recorder.shutdown()

    def test_recording_not_called_if_shutdown_before_delay(self, rolling_buffer, fall_event, tmp_path):
        """Shutdown should cancel pending recordings before they execute."""
        buffer, _ = rolling_buffer
        clip_after_sec = 0.5  # Longer delay

        recorder = ClipRecorder(
            rolling_buffer=buffer,
            clip_before_sec=1.0,
            clip_after_sec=clip_after_sec,
            output_dir=str(tmp_path / "clips"),
            fps=15,
        )

        with patch.object(recorder, "save", return_value="/fake/path.mp4") as mock_save:
            recorder.on_fall_confirmed(fall_event)

            # Shutdown before delay completes
            time.sleep(0.1)
            recorder.shutdown()

            # Wait past original delay time
            time.sleep(clip_after_sec)

            # Save should NOT have been called (timer was cancelled)
            assert not mock_save.called

    def test_shutdown_clears_pending_recordings_list(self, rolling_buffer, fall_event, tmp_path):
        """shutdown() should clear the _pending_recordings list."""
        buffer, _ = rolling_buffer

        recorder = ClipRecorder(
            rolling_buffer=buffer,
            clip_before_sec=1.0,
            clip_after_sec=1.0,
            output_dir=str(tmp_path / "clips"),
            fps=15,
        )

        recorder.on_fall_confirmed(fall_event)
        assert len(recorder._pending_recordings) == 1

        recorder.shutdown()
        assert len(recorder._pending_recordings) == 0

    def test_multiple_events_create_multiple_timers(self, rolling_buffer, tmp_path):
        """Multiple fall events should create multiple pending timers."""
        buffer, event_time = rolling_buffer

        recorder = ClipRecorder(
            rolling_buffer=buffer,
            clip_before_sec=1.0,
            clip_after_sec=1.0,
            output_dir=str(tmp_path / "clips"),
            fps=15,
        )

        events = [
            FallEvent(f"evt_{i}", event_time + i, event_time + i, 1)
            for i in range(3)
        ]

        for event in events:
            recorder.on_fall_confirmed(event)

        assert len(recorder._pending_recordings) == 3

        recorder.shutdown()
        assert len(recorder._pending_recordings) == 0


class TestRollingBufferThreadSafety:
    """Tests for RollingBuffer thread safety."""

    def test_concurrent_push_and_get_clip(self):
        """Buffer should handle concurrent push and get_clip safely."""
        import threading

        buffer = RollingBuffer(buffer_seconds=5, fps=30)
        errors = []
        event_time = time.time()

        def pusher():
            """
            Pushes 100 synthetic frames into the shared RollingBuffer to simulate a producer load for concurrency tests.
            
            Each pushed FrameData uses a zeroed 100x100 RGB frame and a timestamp starting at `event_time` incremented by ~0.033s per frame; a short sleep is performed between pushes to stagger production. Any exception raised during the loop is appended to the `errors` list.
            """
            try:
                for i in range(100):
                    frame = np.zeros((100, 100, 3), dtype=np.uint8)
                    buffer.push(FrameData(event_time + i * 0.033, frame, None))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def reader():
            """
            Worker that repeatedly requests 1.0s-before and 1.0s-after clips from the rolling buffer to exercise concurrent access and record any exceptions.
            
            Runs 50 iterations, calling buffer.get_clip(event_time, before_sec=1.0, after_sec=1.0) and sleeping 0.002 seconds between calls. Any exception raised is appended to the outer-scope `errors` list.
            """
            try:
                for _ in range(50):
                    buffer.get_clip(event_time, before_sec=1.0, after_sec=1.0)
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=pusher),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_concurrent_push_and_len(self):
        """Buffer should handle concurrent push and __len__ safely."""
        import threading

        buffer = RollingBuffer(buffer_seconds=2, fps=30)
        errors = []

        def pusher():
            """
            Pushes 100 empty frames with increasing timestamps into the shared rolling buffer and records any exception.
            
            Each pushed frame is a 100x100 RGB array of zeros with a timestamp of 0.0 through 99.0. If an exception occurs during pushing, it is appended to the `errors` list.
            """
            try:
                for i in range(100):
                    frame = np.zeros((100, 100, 3), dtype=np.uint8)
                    buffer.push(FrameData(float(i), frame, None))
            except Exception as e:
                errors.append(e)

        def checker():
            """
            Attempt to call len(buffer) repeatedly and record any exception.
            
            Calls len(buffer) 100 times in a loop; if an exception is raised during these calls,
            the exception is appended to the outer-scope `errors` list.
            """
            try:
                for _ in range(100):
                    _ = len(buffer)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=pusher),
            threading.Thread(target=checker),
            threading.Thread(target=checker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"