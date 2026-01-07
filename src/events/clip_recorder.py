from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from src.capture.rolling_buffer import FrameData
from src.events.observer import FallEvent, FallEventObserver

if TYPE_CHECKING:
    from src.capture.rolling_buffer import RollingBuffer
    from src.events.event_logger import EventLogger

logger = logging.getLogger(__name__)


class ClipRecorder(FallEventObserver):
    def __init__(
        self,
        output_dir: str = "data/clips",
        fps: int = 15,
        codec: str = "avc1",
        rolling_buffer: RollingBuffer | None = None,
        event_logger: EventLogger | None = None,
        clip_before_sec: float = 5.0,
        clip_after_sec: float = 5.0,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.codec = codec
        self.rolling_buffer = rolling_buffer
        self.event_logger = event_logger
        self.clip_before_sec = clip_before_sec
        self.clip_after_sec = clip_after_sec
        self._pending_recordings: list[threading.Timer] = []
        self._recordings_lock = threading.Lock()

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

    def on_fall_confirmed(self, event: FallEvent) -> None:
        """Schedule clip recording after clip_after_sec delay."""
        if self.rolling_buffer is None:
            logger.warning("on_fall_confirmed called without rolling_buffer configured")
            return

        timer = threading.Timer(
            self.clip_after_sec,
            self._save_clip_delayed,
            args=[event],
        )
        timer.daemon = True
        timer.start()
        with self._recordings_lock:
            self._pending_recordings.append(timer)
        logger.info(f"Scheduled clip recording in {self.clip_after_sec}s for event {event.event_id}")

    def _save_clip_delayed(self, event: FallEvent) -> None:
        """Execute the actual clip saving after delay."""
        # Remove completed timer from pending list
        current_thread = threading.current_thread()
        with self._recordings_lock:
            self._pending_recordings = [
                t for t in self._pending_recordings if t.ident != current_thread.ident
            ]

        if self.rolling_buffer is None:
            logger.warning(f"Cannot save clip for event {event.event_id}: rolling_buffer is None")
            return

        frames = self.rolling_buffer.get_clip(
            event_time=event.confirmed_at,
            before_sec=self.clip_before_sec,
            after_sec=self.clip_after_sec,
        )

        clip_path = self.save(frames, event.event_id)

        if clip_path and self.event_logger:
            self.event_logger.update_clip_path(event.event_id, clip_path)
            logger.info(f"Clip saved: {clip_path}")

    def on_fall_recovered(self, event: FallEvent) -> None:
        pass

    def shutdown(self) -> None:
        """Cancel all pending recording timers."""
        with self._recordings_lock:
            for timer in self._pending_recordings:
                timer.cancel()
            self._pending_recordings.clear()
        logger.info("ClipRecorder shutdown: cancelled pending recordings")
