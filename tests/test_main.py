import numpy as np
from unittest.mock import MagicMock

from src.analysis.delay_confirm import FallState


def test_process_frame_returns_state():
    """process_frame should return FallState from delay_confirm."""
    from main import process_frame
    from src.capture.rolling_buffer import RollingBuffer
    from src.analysis.delay_confirm import DelayConfirm
    from src.analysis.rule_engine import RuleEngine
    from src.detection.bbox import BBox

    # Mock detector
    detector = MagicMock()
    standing_bbox = BBox(x=100, y=50, width=100, height=200)
    detector.detect.return_value = [standing_bbox]

    rule_engine = RuleEngine(fall_threshold=1.3)
    delay_confirm = DelayConfirm(delay_sec=3.0)
    buffer = RollingBuffer(buffer_seconds=10, fps=15)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    state = process_frame(
        frame=frame,
        current_time=0.0,
        detector=detector,
        rule_engine=rule_engine,
        delay_confirm=delay_confirm,
        rolling_buffer=buffer,
        use_pose=False,
    )

    assert state == FallState.NORMAL
