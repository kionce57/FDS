import pytest
import numpy as np
from unittest.mock import patch
from src.events.clip_recorder import ClipRecorder
from src.capture.rolling_buffer import FrameData


class TestClipRecorder:
    @pytest.fixture
    def output_dir(self, tmp_path):
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        return clips_dir

    @pytest.fixture
    def recorder(self, output_dir):
        return ClipRecorder(output_dir=str(output_dir), fps=15)

    @pytest.fixture
    def sample_frames(self):
        frames = []
        for i in range(30):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :, 0] = i * 8
            frames.append(FrameData(timestamp=float(i) / 15, frame=frame, bbox=None))
        return frames

    def test_generate_filename(self, recorder):
        filename = recorder._generate_filename("evt_123")
        assert "evt_123" in filename
        assert filename.endswith(".mp4")

    def test_save_creates_file(self, recorder, sample_frames, output_dir):
        with patch("cv2.VideoWriter") as mock_writer:
            mock_instance = mock_writer.return_value
            mock_instance.isOpened.return_value = True

            path = recorder.save(sample_frames, "evt_test")

            assert "evt_test" in path
            mock_instance.write.assert_called()

    def test_save_empty_frames_returns_none(self, recorder):
        result = recorder.save([], "evt_empty")
        assert result is None

    def test_save_writes_all_frames(self, recorder, sample_frames):
        with patch("cv2.VideoWriter") as mock_writer:
            mock_instance = mock_writer.return_value
            mock_instance.isOpened.return_value = True

            recorder.save(sample_frames, "evt_test")

            assert mock_instance.write.call_count == len(sample_frames)


def test_clip_recorder_on_fall_confirmed_saves_clip(tmp_path):
    """ClipRecorder should save clip after delay when fall is confirmed."""
    import time
    import numpy as np
    from src.capture.rolling_buffer import RollingBuffer, FrameData
    from src.events.clip_recorder import ClipRecorder
    from src.events.event_logger import EventLogger
    from src.events.observer import FallEvent

    # Setup
    buffer = RollingBuffer(buffer_seconds=10, fps=15)
    event_time = time.time()

    # Push frames to buffer
    for i in range(30):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_data = FrameData(timestamp=event_time - 1 + i * 0.033, frame=frame, bbox=None)
        buffer.push(frame_data)

    db_path = str(tmp_path / "test.db")
    event_logger = EventLogger(db_path=db_path)
    clip_after_sec = 0.1  # Short delay for testing
    recorder = ClipRecorder(
        rolling_buffer=buffer,
        event_logger=event_logger,
        clip_before_sec=0.5,
        clip_after_sec=clip_after_sec,
        output_dir=str(tmp_path / "clips"),
        fps=15,
    )

    # Create event and trigger observer
    event = FallEvent(
        event_id="evt_123",
        confirmed_at=event_time,
        last_notified_at=event_time,
        notification_count=1,
    )
    event_logger.on_fall_confirmed(event)  # Create DB record first

    # Mock VideoWriter to avoid codec dependency
    with patch("cv2.VideoWriter") as mock_writer:
        mock_instance = mock_writer.return_value
        mock_instance.isOpened.return_value = True

        recorder.on_fall_confirmed(event)

        # Recording is now delayed, verify NOT called immediately
        assert not mock_writer.called

        # Wait for delay + small buffer
        time.sleep(clip_after_sec + 0.2)

        # Verify VideoWriter was called (clip save attempted)
        mock_writer.assert_called_once()
        assert mock_instance.write.call_count > 0

    # Verify event_logger was updated
    events = event_logger.get_recent_events(limit=1)
    assert events[0]["clip_path"] is not None

    event_logger.close()
    recorder.shutdown()
