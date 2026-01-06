import logging
import signal
import sys

import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.analysis.rule_engine import RuleEngine
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.core.config import load_config
from src.core.pipeline import Pipeline
from src.detection.bbox import BBox
from src.detection.detector import Detector, PoseDetector
from src.lifecycle.cleanup_scheduler import CleanupScheduler


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

    # 啟動清理排程器
    cleanup_scheduler = CleanupScheduler(config)
    cleanup_scheduler.start()

    # 設定訊號處理器，確保優雅關閉
    def signal_handler(_signum: int, _frame: object) -> None:
        logging.info("收到終止訊號，正在關閉...")
        cleanup_scheduler.stop()
        sys.exit(0)

    _ = signal.signal(signal.SIGINT, signal_handler)
    _ = signal.signal(signal.SIGTERM, signal_handler)

    try:
        pipeline = Pipeline(config=config)
        pipeline.run()
    finally:
        cleanup_scheduler.stop()


if __name__ == "__main__":
    main()
