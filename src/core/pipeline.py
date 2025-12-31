import logging
import time

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.capture.camera import Camera
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import Config
from src.detection.bbox import BBox
from src.detection.detector import Detector
from src.events.clip_recorder import ClipRecorder
from src.events.event_logger import EventLogger
from src.events.notifier import LineNotifier
from src.events.observer import FallEvent
from src.lifecycle.skeleton_collector import SkeletonCollector

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: Config, db_path: str = "data/fds.db"):
        self.config = config

        self.camera = Camera(
            source=config.camera.source,
            fps=config.camera.fps,
            resolution=(config.camera.resolution[0], config.camera.resolution[1]),
        )

        self.detector = Detector(
            model_path=config.detection.model,
            confidence=config.detection.confidence,
            classes=config.detection.classes,
        )

        self.rule_engine = RuleEngine(fall_threshold=config.analysis.fall_threshold)

        self.delay_confirm = DelayConfirm(
            delay_sec=config.analysis.delay_sec,
            same_event_window=config.analysis.same_event_window,
            re_notify_interval=config.analysis.re_notify_interval,
        )

        self.rolling_buffer = RollingBuffer(
            buffer_seconds=config.recording.buffer_seconds,
            fps=config.camera.fps,
        )

        self.event_logger = EventLogger(db_path=db_path)
        self.clip_recorder = ClipRecorder(fps=config.camera.fps)
        self.notifier = LineNotifier(
            channel_access_token=config.notification.line_channel_access_token,
            user_id=config.notification.line_user_id,
            enabled=config.notification.enabled,
        )

        self.delay_confirm.add_observer(self.event_logger)
        self.delay_confirm.add_observer(self.notifier)
        self.delay_confirm.add_observer(self)

        # SkeletonCollector for auto skeleton extraction
        self.skeleton_collector: SkeletonCollector | None = None
        if config.lifecycle.auto_skeleton_extract:
            self.skeleton_collector = SkeletonCollector(
                rolling_buffer=self.rolling_buffer,
                output_dir=config.lifecycle.skeleton_output_dir,
                enabled=True,
                clip_before_sec=config.recording.clip_before_sec,
                clip_after_sec=config.recording.clip_after_sec,
                fps=config.camera.fps,
            )
            self.delay_confirm.add_suspected_observer(self.skeleton_collector)

        self._current_bbox: BBox | None = None

    def on_fall_confirmed(self, event: FallEvent) -> None:
        # Notify skeleton_collector to extract with confirmed outcome
        if self.skeleton_collector and self.delay_confirm.current_suspected:
            self.skeleton_collector.on_fall_confirmed_update(self.delay_confirm.current_suspected)

        frames = self.rolling_buffer.get_clip(
            event_time=event.confirmed_at,
            before_sec=self.config.recording.clip_before_sec,
            after_sec=self.config.recording.clip_after_sec,
        )
        if frames:
            clip_path = self.clip_recorder.save(frames, event.event_id)
            if clip_path:
                self.event_logger.update_clip_path(event.event_id, clip_path)
                logger.info(f"Clip saved: {clip_path}")

    def on_fall_recovered(self, event: FallEvent) -> None:
        logger.info(f"Fall recovered: {event.event_id}")

    def process_frame(self, frame: np.ndarray, current_time: float) -> FallState:
        bboxes = self.detector.detect(frame)

        self._current_bbox = bboxes[0] if bboxes else None

        is_fallen = self.rule_engine.is_fallen(self._current_bbox)

        bbox_tuple = None
        if self._current_bbox:
            bbox_tuple = (
                self._current_bbox.x,
                self._current_bbox.y,
                self._current_bbox.width,
                self._current_bbox.height,
            )

        frame_data = FrameData(
            timestamp=current_time,
            frame=frame.copy(),
            bbox=bbox_tuple,
        )
        self.rolling_buffer.push(frame_data)

        state = self.delay_confirm.update(is_fallen=is_fallen, current_time=current_time)

        return state

    def run(self) -> None:
        logger.info("Starting fall detection pipeline...")
        try:
            while True:
                frame = self.camera.read()
                if frame is None:
                    continue

                current_time = time.time()
                state = self.process_frame(frame, current_time)

                if state == FallState.CONFIRMED:
                    logger.warning("Fall confirmed!")

        except KeyboardInterrupt:
            logger.info("Stopping pipeline...")
        finally:
            self.camera.release()
            self.event_logger.close()
            if self.skeleton_collector:
                self.skeleton_collector.shutdown()
