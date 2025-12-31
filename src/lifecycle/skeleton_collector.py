"""
骨架收集器

訂閱 SUSPECTED 事件，在 outcome 確定後非同步提取骨架並儲存。
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.events.observer import SuspectedEvent
from src.lifecycle.skeleton_extractor import SkeletonExtractor

logger = logging.getLogger(__name__)


class SkeletonCollector:
    """骨架收集器 - SuspectedEventObserver 實作

    在 SUSPECTED 事件觸發時記錄，並在事件結束（confirmed/cleared）時
    提取骨架並儲存，包含 outcome 標籤。

    設計原則:
    - SUSPECTED: 只記錄事件，不提取
    - CONFIRMED/CLEARED: 提取骨架，每個事件只提取一次
    - 保證 t-n: buffer 中一定有事件前的資料
    - t+n: 有多少拿多少
    """

    def __init__(
        self,
        rolling_buffer: RollingBuffer,
        output_dir: str = "data/skeletons",
        enabled: bool = True,
        max_workers: int = 2,
        clip_before_sec: float = 5.0,
        clip_after_sec: float = 5.0,
        fps: float = 15.0,
    ):
        self.rolling_buffer = rolling_buffer
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self.clip_before_sec = clip_before_sec
        self.clip_after_sec = clip_after_sec
        self.fps = fps

        self.pending_events: dict[str, SuspectedEvent] = {}
        self.extraction_count = 0
        self.executor = ThreadPoolExecutor(max_workers=max_workers) if enabled else None
        self.extractor = SkeletonExtractor() if enabled else None

    def on_fall_suspected(self, event: SuspectedEvent) -> None:
        """NORMAL → SUSPECTED 時觸發

        只記錄事件，不提取骨架。等待 outcome 確定。
        """
        if not self.enabled:
            return

        logger.info(f"Suspected event recorded: {event.suspected_id}")
        self.pending_events[event.suspected_id] = event

    def on_suspicion_cleared(self, event: SuspectedEvent) -> None:
        """SUSPECTED → NORMAL 時觸發（未確認跌倒）

        提取骨架並標記為 cleared（負樣本）。
        """
        if not self.enabled:
            return

        if event.suspected_id not in self.pending_events:
            return

        logger.info(f"Suspicion cleared: {event.suspected_id}, extracting skeleton...")
        self._extract_and_save_async(event)
        del self.pending_events[event.suspected_id]

    def on_fall_confirmed_update(self, event: SuspectedEvent) -> None:
        """SUSPECTED → CONFIRMED 時由 Pipeline 呼叫

        提取骨架並標記為 confirmed（正樣本）。
        """
        if not self.enabled:
            return

        if event.suspected_id not in self.pending_events:
            return

        logger.info(f"Fall confirmed: {event.suspected_id}, extracting skeleton...")
        self._extract_and_save_async(event)
        del self.pending_events[event.suspected_id]

    def _extract_and_save_async(self, event: SuspectedEvent) -> None:
        """非同步提取並儲存骨架"""
        # 立即從 buffer 取得 frames（避免被覆蓋）
        frames = self.rolling_buffer.get_clip(
            event_time=event.suspected_at,
            before_sec=self.clip_before_sec,
            after_sec=self.clip_after_sec,
        )

        if not frames:
            logger.warning(f"No frames available for {event.suspected_id}")
            return

        self.extraction_count += 1

        # 提交到背景執行緒
        self.executor.submit(self._save_skeleton, event, list(frames))

    def _save_skeleton(self, event: SuspectedEvent, frames: list[FrameData]) -> None:
        """儲存骨架（在背景執行緒中執行）"""
        try:
            sequence = self.extractor.extract_from_frames(
                frames=frames,
                event_id=event.suspected_id,
                fps=self.fps,
            )

            # 檔名包含 outcome 標籤
            filename = f"{event.suspected_id}_{event.outcome}.json"
            output_path = self.output_dir / filename
            sequence.to_json(output_path)

            logger.info(f"Skeleton saved: {output_path} (outcome: {event.outcome})")
        except Exception as e:
            logger.error(f"Failed to save skeleton for {event.suspected_id}: {e}")

    def shutdown(self) -> None:
        """關閉執行緒池"""
        if self.executor:
            self.executor.shutdown(wait=True)
