import sqlite3
import time
from pathlib import Path

from src.events.observer import FallEvent, FallEventObserver


class EventLogger(FallEventObserver):
    def __init__(self, db_path: str = "data/fds.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                confirmed_at REAL NOT NULL,
                recovered_at REAL,
                notification_count INTEGER DEFAULT 1,
                clip_path TEXT,
                created_at REAL NOT NULL
            )
        """)
        self.conn.commit()

    def on_fall_confirmed(self, event: FallEvent) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO events
            (event_id, confirmed_at, notification_count, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event.event_id, event.confirmed_at, event.notification_count, time.time()),
        )
        self.conn.commit()

    def on_fall_recovered(self, event: FallEvent) -> None:
        self.conn.execute(
            "UPDATE events SET recovered_at = ? WHERE event_id = ?",
            (time.time(), event.event_id),
        )
        self.conn.commit()

    def update_clip_path(self, event_id: str, clip_path: str) -> None:
        self.conn.execute(
            "UPDATE events SET clip_path = ? WHERE event_id = ?",
            (clip_path, event_id),
        )
        self.conn.commit()

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        cursor = self.conn.execute(
            """
            SELECT event_id, confirmed_at, recovered_at, notification_count, clip_path
            FROM events
            ORDER BY confirmed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = ["event_id", "confirmed_at", "recovered_at", "notification_count", "clip_path"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
