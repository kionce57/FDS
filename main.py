import logging
import signal
import sys
import time

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.analysis.rule_engine import RuleEngine
from src.capture.camera import Camera
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import load_config
from src.detection.bbox import BBox
from src.detection.detector import Detector, PoseDetector
from src.events.clip_recorder import ClipRecorder
from src.events.event_logger import EventLogger
from src.events.notifier import LineNotifier
from src.lifecycle.cleanup_scheduler import CleanupScheduler

logger = logging.getLogger(__name__)


def process_frame(
    frame: np.ndarray,
    current_time: float,
    detector: Detector | PoseDetector,
    rule_engine: RuleEngine | PoseRuleEngine,
    delay_confirm: DelayConfirm,
    rolling_buffer: RollingBuffer,
    use_pose: bool,
) -> FallState:
    """Process a single frame through the detection pipeline."""
    detections = detector.detect(frame)
    detection = detections[0] if detections else None

    if use_pose:
        is_fallen = rule_engine.is_fallen(detection, timestamp=current_time)
        bbox_tuple = None
    else:
        is_fallen = rule_engine.is_fallen(detection)
        bbox_tuple = None
        if detection and isinstance(detection, BBox):
            bbox_tuple = (detection.x, detection.y, detection.width, detection.height)

    frame_data = FrameData(timestamp=current_time, frame=frame.copy(), bbox=bbox_tuple)
    rolling_buffer.push(frame_data)

    return delay_confirm.update(is_fallen=is_fallen, current_time=current_time)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()
    use_pose = config.detection.use_pose

    # === Component Creation ===
    camera = Camera(
        source=config.camera.source,
        fps=config.camera.fps,
        resolution=(config.camera.resolution[0], config.camera.resolution[1]),
    )

    if use_pose:
        detector: Detector | PoseDetector = PoseDetector(
            model_path=config.detection.pose_model,
            confidence=config.detection.confidence,
        )
        rule_engine: RuleEngine | PoseRuleEngine = PoseRuleEngine(
            torso_angle_threshold=config.analysis.fall_threshold,
            enable_smoothing=config.detection.enable_smoothing,
            smoothing_min_cutoff=config.detection.smoothing_min_cutoff,
            smoothing_beta=config.detection.smoothing_beta,
        )
    else:
        detector = Detector(
            model_path=config.detection.model,
            confidence=config.detection.confidence,
            classes=config.detection.classes,
        )
        rule_engine = RuleEngine(fall_threshold=config.analysis.fall_threshold)

    rolling_buffer = RollingBuffer(
        buffer_seconds=config.recording.buffer_seconds,
        fps=config.camera.fps,
    )

    event_logger = EventLogger(db_path="data/fds.db")

    clip_recorder = ClipRecorder(
        rolling_buffer=rolling_buffer,
        event_logger=event_logger,
        clip_before_sec=config.recording.clip_before_sec,
        clip_after_sec=config.recording.clip_after_sec,
        fps=config.camera.fps,
    )

    notifier = LineNotifier(
        channel_access_token=config.notification.line_channel_access_token,
        user_id=config.notification.line_user_id,
        enabled=config.notification.enabled,
    )

    delay_confirm = DelayConfirm(
        delay_sec=config.analysis.delay_sec,
        same_event_window=config.analysis.same_event_window,
        re_notify_interval=config.analysis.re_notify_interval,
    )

    # === Wire Observers ===
    delay_confirm.add_observer(event_logger)
    delay_confirm.add_observer(notifier)
    delay_confirm.add_observer(clip_recorder)

    # === Lifecycle ===
    cleanup_scheduler = CleanupScheduler(config)
    cleanup_scheduler.start()

    def signal_handler(_signum: int, _frame: object) -> None:
        logger.info("收到終止訊號，正在關閉...")
        cleanup_scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # === Main Loop ===
    mode = "Pose" if use_pose else "BBox"
    logger.info(f"Starting fall detection (mode: {mode})...")
    if use_pose and config.detection.enable_smoothing:
        logger.info("Keypoint smoothing: enabled")

    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue

            current_time = time.time()
            state = process_frame(
                frame=frame,
                current_time=current_time,
                detector=detector,
                rule_engine=rule_engine,
                delay_confirm=delay_confirm,
                rolling_buffer=rolling_buffer,
                use_pose=use_pose,
            )

            if state == FallState.CONFIRMED:
                logger.warning("Fall confirmed!")

    except KeyboardInterrupt:
        logger.info("Stopping detection...")
    finally:
        camera.release()
        event_logger.close()
        cleanup_scheduler.stop()


if __name__ == "__main__":
    main()
