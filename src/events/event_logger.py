import sqlite3
import time
from pathlib import Path

from src.events.observer import FallEvent, FallEventObserver


class EventLogger(FallEventObserver):
    def __init__(self, db_path: str = "data/fds.db"):
        """
        Initialize the EventLogger: ensure the database file's parent directories exist, open a SQLite connection (assigned to `self.conn`) configured for use from background threads, and create the required tables.
        
        Parameters:
            db_path (str): Path to the SQLite database file. Defaults to "data/fds.db".
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # check_same_thread=False allows connection to be used from background threads
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._create_tables()

    def _create_tables(self) -> None:
        """
        Ensure the SQLite database contains the events table used to record fall events.
        
        Creates the `events` table if it does not exist with columns:
        - `event_id` (TEXT PRIMARY KEY)
        - `confirmed_at` (REAL NOT NULL)
        - `recovered_at` (REAL, nullable)
        - `notification_count` (INTEGER, default 1)
        - `clip_path` (TEXT)
        - `created_at` (REAL NOT NULL)
        
        Commits the transaction after executing the schema statement.
        """
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