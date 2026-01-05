import logging
import time

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.analysis.rule_engine import RuleEngine
from src.capture.camera import Camera
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import Config
from src.detection.bbox import BBox
from src.detection.detector import Detector, PoseDetector
from src.detection.skeleton import Skeleton
from src.events.clip_recorder import ClipRecorder
from src.events.event_logger import EventLogger
from src.events.notifier import LineNotifier
from src.events.observer import FallEvent

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: Config, db_path: str = "data/fds.db"):
        self.config = config
        self._use_pose = config.detection.use_pose

        self.camera = Camera(
            source=config.camera.source,
            fps=config.camera.fps,
            resolution=(config.camera.resolution[0], config.camera.resolution[1]),
        )

        # Select detector and rule engine based on mode
        if self._use_pose:
            self.detector: Detector | PoseDetector = PoseDetector(
                model_path=config.detection.pose_model,
                confidence=config.detection.confidence,
            )
            self.rule_engine: RuleEngine | PoseRuleEngine = PoseRuleEngine(
                torso_angle_threshold=config.analysis.fall_threshold,
                enable_smoothing=config.detection.enable_smoothing,
                smoothing_min_cutoff=config.detection.smoothing_min_cutoff,
                smoothing_beta=config.detection.smoothing_beta,
            )
        else:
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

        self._current_detection: BBox | Skeleton | None = None

    def on_fall_confirmed(self, event: FallEvent) -> None:
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
        detections = self.detector.detect(frame)
        self._current_detection = detections[0] if detections else None

        # Pose mode requires timestamp for smoothing
        if self._use_pose:
            is_fallen = self.rule_engine.is_fallen(
                self._current_detection, timestamp=current_time  # type: ignore[arg-type]
            )
            bbox_tuple = None  # Pose mode doesn't track bbox
        else:
            is_fallen = self.rule_engine.is_fallen(self._current_detection)  # type: ignore[arg-type]
            bbox_tuple = None
            if self._current_detection and isinstance(self._current_detection, BBox):
                bbox_tuple = (
                    self._current_detection.x,
                    self._current_detection.y,
                    self._current_detection.width,
                    self._current_detection.height,
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
        mode = "Pose" if self._use_pose else "BBox"
        logger.info(f"Starting fall detection pipeline (mode: {mode})...")
        if self._use_pose and self.config.detection.enable_smoothing:
            logger.info("Keypoint smoothing: enabled")
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
