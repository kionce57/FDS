import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
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
