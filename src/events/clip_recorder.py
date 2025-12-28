from datetime import datetime
from pathlib import Path

import cv2

from src.capture.rolling_buffer import FrameData


class ClipRecorder:
    def __init__(
        self,
        output_dir: str = "data/clips",
        fps: int = 15,
        codec: str = "mp4v",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.codec = codec

    def _generate_filename(self, event_id: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{event_id}.mp4"

    def save(self, frames: list[FrameData], event_id: str) -> str | None:
        if not frames:
            return None

        filename = self._generate_filename(event_id)
        output_path = self.output_dir / filename

        first_frame = frames[0].frame
        height, width = first_frame.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        writer = cv2.VideoWriter(str(output_path), fourcc, self.fps, (width, height))

        if not writer.isOpened():
            return None

        try:
            for frame_data in frames:
                writer.write(frame_data.frame)
        finally:
            writer.release()

        return str(output_path)
