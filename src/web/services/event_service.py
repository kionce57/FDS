"""
事件服務

提供事件查詢、統計等功能。
"""

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Event:
    """事件資料結構"""

    event_id: str
    created_at: float
    clip_path: str | None
    notification_count: int = 0

    @property
    def has_clip(self) -> bool:
        """是否有影片檔案"""
        if not self.clip_path:
            return False
        return Path(self.clip_path).exists()

    @property
    def created_at_iso(self) -> str:
        """ISO 格式時間戳記"""
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(self.created_at, tz=timezone.utc)
        return dt.isoformat()

    @property
    def created_at_local(self) -> str:
        """本地時間格式"""
        from datetime import datetime

        dt = datetime.fromtimestamp(self.created_at)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "event_id": self.event_id,
            "created_at": self.created_at,
            "created_at_iso": self.created_at_iso,
            "created_at_local": self.created_at_local,
            "clip_path": self.clip_path,
            "has_clip": self.has_clip,
            "notification_count": self.notification_count,
        }


@dataclass
class EventStats:
    """事件統計資料"""

    total_events: int
    today_events: int
    this_week_events: int
    total_clips_size_mb: float

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "total_events": self.total_events,
            "today_events": self.today_events,
            "this_week_events": self.this_week_events,
            "total_clips_size_mb": round(self.total_clips_size_mb, 2),
        }


class EventService:
    """事件服務

    提供事件查詢、統計、刪除等功能。

    Example:
        >>> service = EventService("data/fds.db")
        >>> events = service.get_events(page=1, per_page=10)
        >>> stats = service.get_stats()
    """

    def __init__(self, db_path: str | Path = "data/fds.db"):
        """初始化事件服務

        Args:
            db_path: SQLite 資料庫路徑
        """
        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """取得資料庫連線"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        return sqlite3.connect(str(self.db_path))

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        """檢查資料表是否存在"""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def get_events(
        self,
        page: int = 1,
        per_page: int = 10,
        date_from: float | None = None,
        date_to: float | None = None,
    ) -> tuple[list[Event], int]:
        """查詢事件列表

        Args:
            page: 頁碼（從 1 開始）
            per_page: 每頁數量
            date_from: 起始時間戳記（可選）
            date_to: 結束時間戳記（可選）

        Returns:
            (事件列表, 總數量)
        """
        conn = self._get_connection()

        # 檢查資料表是否存在
        if not self._table_exists(conn, "events"):
            conn.close()
            return [], 0

        # 建構查詢條件
        conditions = []
        params: list = []

        if date_from is not None:
            conditions.append("created_at >= ?")
            params.append(date_from)

        if date_to is not None:
            conditions.append("created_at <= ?")
            params.append(date_to)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # 查詢總數
        count_query = f"SELECT COUNT(*) FROM events {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        # 查詢分頁資料
        offset = (page - 1) * per_page
        query = f"""
            SELECT event_id, created_at, clip_path, notification_count
            FROM events
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = conn.execute(query, params + [per_page, offset])

        events = []
        for row in cursor.fetchall():
            events.append(
                Event(
                    event_id=row[0],
                    created_at=row[1],
                    clip_path=row[2],
                    notification_count=row[3] if len(row) > 3 else 0,
                )
            )

        conn.close()
        return events, total

    def get_event(self, event_id: str) -> Event | None:
        """查詢單一事件

        Args:
            event_id: 事件 ID

        Returns:
            事件物件，若不存在則回傳 None
        """
        conn = self._get_connection()

        # 檢查資料表是否存在
        if not self._table_exists(conn, "events"):
            conn.close()
            return None

        cursor = conn.execute(
            "SELECT event_id, created_at, clip_path, notification_count FROM events WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return Event(
            event_id=row[0],
            created_at=row[1],
            clip_path=row[2],
            notification_count=row[3] if len(row) > 3 else 0,
        )

    def get_stats(self) -> EventStats:
        """取得事件統計資訊

        Returns:
            事件統計物件
        """
        conn = self._get_connection()

        # 檢查資料表是否存在
        if not self._table_exists(conn, "events"):
            conn.close()
            return EventStats(
                total_events=0,
                today_events=0,
                this_week_events=0,
                total_clips_size_mb=0.0,
            )

        # 總事件數
        cursor = conn.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]

        # 今日事件數
        today_start = time.time() - (time.time() % 86400)  # 今日 0:00 UTC
        cursor = conn.execute(
            "SELECT COUNT(*) FROM events WHERE created_at >= ?",
            (today_start,),
        )
        today_events = cursor.fetchone()[0]

        # 本週事件數
        week_start = time.time() - (7 * 86400)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM events WHERE created_at >= ?",
            (week_start,),
        )
        this_week_events = cursor.fetchone()[0]

        # 影片總大小
        cursor = conn.execute("SELECT clip_path FROM events WHERE clip_path IS NOT NULL")
        total_size = 0
        for row in cursor.fetchall():
            clip_path = Path(row[0])
            if clip_path.exists():
                total_size += clip_path.stat().st_size

        conn.close()

        return EventStats(
            total_events=total_events,
            today_events=today_events,
            this_week_events=this_week_events,
            total_clips_size_mb=total_size / (1024 * 1024),
        )

    def delete_event(self, event_id: str, delete_clip: bool = True) -> bool:
        """刪除事件

        Args:
            event_id: 事件 ID
            delete_clip: 是否同時刪除影片檔案

        Returns:
            是否成功刪除
        """
        event = self.get_event(event_id)
        if event is None:
            return False

        # 刪除影片檔案
        if delete_clip and event.clip_path:
            clip_path = Path(event.clip_path)
            if clip_path.exists():
                clip_path.unlink()

        # 刪除資料庫記錄
        conn = self._get_connection()
        conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        conn.commit()
        conn.close()

        return True

    def get_recent_events(self, limit: int = 5) -> list[Event]:
        """取得最近事件

        Args:
            limit: 數量限制

        Returns:
            事件列表
        """
        events, _ = self.get_events(page=1, per_page=limit)
        return events


__all__ = ["Event", "EventStats", "EventService"]
