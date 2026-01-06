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
        """
        Initialize the ClipRecorder and prepare storage, encoding, and timing configuration.
        
        Parameters:
            output_dir (str): Filesystem path where generated clips will be stored; directory is created if missing.
            fps (int): Frames per second to use when encoding saved clips.
            codec (str): Four-character codec identifier for the video writer (e.g., "avc1").
            rolling_buffer (RollingBuffer | None): Optional source that can supply pre- and post-event frames for clip generation.
            event_logger (EventLogger | None): Optional logger that will be updated with saved clip paths.
            clip_before_sec (float): Number of seconds of footage to include before the event time.
            clip_after_sec (float): Number of seconds of footage to include after the event time.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.codec = codec
        self.rolling_buffer = rolling_buffer
        self.event_logger = event_logger
        self.clip_before_sec = clip_before_sec
        self.clip_after_sec = clip_after_sec
        self._pending_recordings: list[threading.Timer] = []

    def _generate_filename(self, event_id: str) -> str:
        """
        Generate a filename for a clip using the current datetime and the provided event identifier.
        
        Parameters:
            event_id (str): Unique identifier for the event to include in the filename.
        
        Returns:
            str: Filename formatted as YYYYMMDD_HHMMSS_<event_id>.mp4
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{event_id}.mp4"

    def save(self, frames: list[FrameData], event_id: str) -> str | None:
        """
        Save a sequence of frames as a video clip and return its filesystem path.
        
        Saves the provided frames to a new video file whose name includes the given event_id.
        If `frames` is empty or the video writer cannot be opened, no file is created and `None` is returned.
        
        Parameters:
            frames (list[FrameData]): Ordered sequence of frame containers; each item must expose a `frame`
                attribute containing an image array compatible with OpenCV (height x width x channels).
            event_id (str): Identifier to include in the generated filename for the saved clip.
        
        Returns:
            str | None: The string path to the saved video file if successful, `None` if no clip was written.
        """
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
        """
        Schedule a delayed clip save for the given fall event.
        
        Creates and starts a daemon timer that will invoke the recorder's delayed save after the configured delay and tracks the timer so it can be cancelled during shutdown.
        
        Parameters:
            event (FallEvent): The fall event to generate a clip for.
        """
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
        self._pending_recordings.append(timer)
        logger.info(f"Scheduled clip recording in {self.clip_after_sec}s for event {event.event_id}")

    def _save_clip_delayed(self, event: FallEvent) -> None:
        """
        Save the recorded clip for a confirmed fall event using frames from the rolling buffer.
        
        Retrieve frames around the event's confirmation time using the configured before/after durations, write the frames to a video file, and if saved successfully, update the event logger with the clip path and emit an info log.
        
        Parameters:
            event (FallEvent): The fall event whose `confirmed_at` timestamp and `event_id` are used to obtain and name the clip.
        """
        if self.rolling_buffer is None:
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
        """
        Handle a fall recovery event; this implementation performs no action.
        
        Parameters:
            event (FallEvent): The fall event that was recovered.
        """
        pass

    def shutdown(self) -> None:
        """
        Cancel and clear all pending clip recording timers.
        
        Cancels each scheduled Timer in the recorder's pending list, clears that list, and logs the shutdown action.
        """
        for timer in self._pending_recordings:
            timer.cancel()
        self._pending_recordings.clear()
        logger.info("ClipRecorder shutdown: cancelled pending recordings")