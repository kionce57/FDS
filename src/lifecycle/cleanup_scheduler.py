"""
自動影片清理排程器

使用 APScheduler 在背景定期執行影片清理任務。
"""

import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.core.config import Config
from src.lifecycle.clip_cleanup import ClipCleanup


logger = logging.getLogger(__name__)


class CleanupScheduler:
    """自動影片清理排程器

    在背景定期執行 ClipCleanup，自動清理過期影片檔案。

    Example:
        >>> from src.core.config import load_config
        >>> config = load_config()
        >>> scheduler = CleanupScheduler(config)
        >>> scheduler.start()
        >>> # ... 應用程式執行 ...
        >>> scheduler.stop()
    """

    def __init__(
        self,
        config: Config,
        db_path: str | Path = "data/fds.db",
        clips_dir: str | Path = "data/clips",
    ):
        """初始化排程器

        Args:
            config: 應用程式配置
            db_path: SQLite 資料庫路徑
            clips_dir: 影片檔案目錄
        """
        self.config = config
        self.db_path = Path(db_path)
        self.clips_dir = Path(clips_dir)

        self._scheduler: BackgroundScheduler | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """排程器是否正在執行"""
        return self._is_running

    def start(self) -> None:
        """啟動背景清理排程器

        如果 config.lifecycle.cleanup_enabled 為 False，則不啟動。
        """
        if not self.config.lifecycle.cleanup_enabled:
            logger.info("清理排程器已停用（cleanup_enabled=False）")
            return

        if self._is_running:
            logger.warning("清理排程器已在執行中")
            return

        # 建立排程器
        self._scheduler = BackgroundScheduler(daemon=True)

        # 設定間隔觸發器
        hours = self.config.lifecycle.cleanup_schedule_hours
        trigger = IntervalTrigger(hours=hours)

        # 新增清理任務
        self._scheduler.add_job(
            func=self._run_cleanup,
            trigger=trigger,
            id="clip_cleanup",
            name="影片清理任務",
            replace_existing=True,
        )

        # 啟動排程器
        self._scheduler.start()
        self._is_running = True

        logger.info(
            f"清理排程器已啟動：每 {hours} 小時執行一次，"
            f"保留 {self.config.lifecycle.clip_retention_days} 天內的影片"
        )

    def stop(self) -> None:
        """停止背景清理排程器"""
        if not self._is_running or self._scheduler is None:
            logger.info("清理排程器未在執行中")
            return

        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        self._is_running = False

        logger.info("清理排程器已停止")

    def run_now(self) -> dict:
        """立即執行一次清理（手動觸發）

        Returns:
            清理統計資訊字典
        """
        return self._run_cleanup()

    def _run_cleanup(self) -> dict:
        """執行清理任務（內部方法）

        Returns:
            清理統計資訊字典
        """
        logger.info("開始執行排程清理任務...")

        try:
            cleanup = ClipCleanup(
                db_path=str(self.db_path),
                clips_dir=str(self.clips_dir),
                retention_days=self.config.lifecycle.clip_retention_days,
            )

            result = cleanup.cleanup(dry_run=False)

            # 記錄結果
            if result["deleted_count"] > 0:
                logger.info(
                    f"清理完成：刪除 {result['deleted_count']} 個檔案，"
                    f"釋放 {result['freed_bytes']} bytes，"
                    f"耗時 {result['duration_sec']:.2f} 秒"
                )
            else:
                logger.info("清理完成：沒有需要刪除的過期檔案")

            if result["skipped_count"] > 0:
                logger.warning(f"跳過 {result['skipped_count']} 個缺失檔案")

            return result

        except Exception as e:
            logger.error(f"清理任務執行失敗：{e}")
            return {
                "deleted_count": 0,
                "freed_bytes": 0,
                "skipped_count": 0,
                "error": str(e),
            }


__all__ = ["CleanupScheduler"]
