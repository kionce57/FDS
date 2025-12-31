import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.events.observer import SuspectedEvent
from src.lifecycle.skeleton_collector import SkeletonCollector


class TestSkeletonCollector:
    def test_on_fall_suspected_records_event(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=True,
        )

        event = SuspectedEvent(
            suspected_id="sus_123",
            suspected_at=100.0,
        )

        collector.on_fall_suspected(event)

        # 只記錄，不提取
        assert "sus_123" in collector.pending_events
        assert collector.extraction_count == 0

    def test_on_suspicion_cleared_extracts_skeleton(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        # 預先填入一些 frames
        for i in range(30):
            buffer.push(
                FrameData(
                    timestamp=i * 0.066,
                    frame=np.zeros((480, 640, 3), dtype=np.uint8),
                    bbox=None,
                )
            )

        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=True,
        )

        event = SuspectedEvent(
            suspected_id="sus_123",
            suspected_at=1.0,
            outcome="cleared",
            outcome_at=2.0,
        )

        collector.on_fall_suspected(event)
        collector.on_suspicion_cleared(event)

        # 事件已處理，從 pending 移除
        assert "sus_123" not in collector.pending_events

    def test_disabled_collector_does_nothing(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=False,  # 停用
        )

        event = SuspectedEvent(
            suspected_id="sus_123",
            suspected_at=100.0,
        )

        collector.on_fall_suspected(event)

        assert "sus_123" not in collector.pending_events

    def test_on_fall_confirmed_update_extracts_skeleton(self):
        buffer = RollingBuffer(buffer_seconds=10.0, fps=15.0)
        # 預先填入一些 frames
        for i in range(30):
            buffer.push(
                FrameData(
                    timestamp=i * 0.066,
                    frame=np.zeros((480, 640, 3), dtype=np.uint8),
                    bbox=None,
                )
            )

        collector = SkeletonCollector(
            rolling_buffer=buffer,
            output_dir="data/skeletons",
            enabled=True,
        )

        event = SuspectedEvent(
            suspected_id="sus_456",
            suspected_at=1.0,
            outcome="confirmed",
            outcome_at=4.0,
        )

        collector.on_fall_suspected(event)
        collector.on_fall_confirmed_update(event)

        # 事件已處理，從 pending 移除
        assert "sus_456" not in collector.pending_events
        assert collector.extraction_count == 1
