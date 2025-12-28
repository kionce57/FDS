"""
影片清理排程器

自動清理超過保留期限的影片檔案。
"""

import sqlite3
import time
from pathlib import Path


class ClipCleanup:
    """影片清理排程器

    根據資料庫記錄和保留天數，自動清理過期影片檔案。

    Example:
        >>> cleanup = ClipCleanup(db_path="data/fds.db", clips_dir="data/clips", retention_days=7)
        >>> result = cleanup.cleanup()
        >>> print(f"刪除 {result['deleted_count']} 個檔案，釋放 {result['freed_bytes']} bytes")
    """

    def __init__(self, db_path: str, clips_dir: str, retention_days: int = 7):
        """初始化清理器

        Args:
            db_path: SQLite 資料庫路徑
            clips_dir: 影片檔案目錄
            retention_days: 保留天數（預設 7 天）
        """
        self.db_path = Path(db_path)
        self.clips_dir = Path(clips_dir)
        self.retention_days = retention_days

    def get_expired_clips(self) -> list[dict]:
        """查詢超過保留期限的影片記錄

        Returns:
            過期影片記錄列表，每筆記錄包含 event_id, clip_path, created_at
        """
        cutoff_time = time.time() - (self.retention_days * 24 * 60 * 60)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            """
            SELECT event_id, clip_path, created_at
            FROM events
            WHERE created_at < ? AND clip_path IS NOT NULL
            ORDER BY created_at ASC
            """,
            (cutoff_time,),
        )

        columns = ["event_id", "clip_path", "created_at"]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()

        return results

    def cleanup(self, dry_run: bool = False) -> dict:
        """執行清理

        Args:
            dry_run: 乾運行模式，不實際刪除檔案（預設 False）

        Returns:
            清理統計資訊字典：
            - deleted_count: 刪除檔案數
            - freed_bytes: 釋放空間（bytes）
            - skipped_count: 跳過的檔案數（檔案不存在）
            - would_delete_count: 乾運行模式下會刪除的檔案數
            - duration_sec: 執行時間（秒）
        """
        start_time = time.time()
        deleted_count = 0
        freed_bytes = 0
        skipped_count = 0
        would_delete_count = 0

        expired_clips = self.get_expired_clips()

        conn = sqlite3.connect(str(self.db_path))

        for record in expired_clips:
            clip_path = Path(record["clip_path"])

            # 檢查檔案是否存在
            if not clip_path.exists():
                skipped_count += 1
                continue

            # 記錄檔案大小
            file_size = clip_path.stat().st_size

            if dry_run:
                # 乾運行模式：不實際刪除
                would_delete_count += 1
            else:
                # 刪除檔案
                clip_path.unlink()
                deleted_count += 1
                freed_bytes += file_size

                # 更新資料庫：將 clip_path 設為 NULL
                conn.execute(
                    "UPDATE events SET clip_path = NULL WHERE event_id = ?",
                    (record["event_id"],),
                )

        if not dry_run:
            conn.commit()

        conn.close()

        duration_sec = time.time() - start_time

        return {
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "skipped_count": skipped_count,
            "would_delete_count": would_delete_count,
            "duration_sec": duration_sec,
        }


__all__ = ["ClipCleanup"]
