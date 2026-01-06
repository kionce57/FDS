"""Integration tests for full detection flow."""

import numpy as np
from unittest.mock import MagicMock

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.capture.rolling_buffer import RollingBuffer
from src.detection.bbox import BBox
from main import process_frame


class TestFullDetectionFlow:
    def test_fall_detection_flow(self):
        """Test complete flow: standing -> fall -> confirm -> recover"""
        # Setup
        detector = MagicMock()
        rule_engine = RuleEngine(fall_threshold=1.3)
        delay_confirm = DelayConfirm(
            delay_sec=0.1, same_event_window=60.0, re_notify_interval=120.0
        )
        buffer = RollingBuffer(buffer_seconds=2, fps=15)

        standing_bbox = BBox(x=100, y=50, width=100, height=200)
        fallen_bbox = BBox(x=100, y=50, width=200, height=100)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Standing - NORMAL
        detector.detect.return_value = [standing_bbox]
        state = process_frame(frame, 0.0, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.NORMAL

        # Fallen - SUSPECTED
        detector.detect.return_value = [fallen_bbox]
        state = process_frame(frame, 1.0, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.SUSPECTED

        # Still fallen after delay - CONFIRMED
        state = process_frame(frame, 1.2, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.CONFIRMED

        # Standing again - NORMAL
        detector.detect.return_value = [standing_bbox]
        state = process_frame(frame, 2.0, detector, rule_engine, delay_confirm, buffer, False)
        assert state == FallState.NORMAL
