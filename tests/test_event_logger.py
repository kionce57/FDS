import pytest
import sqlite3
from src.events.event_logger import EventLogger
from src.events.observer import FallEvent


class TestEventLogger:
    @pytest.fixture
    def db_path(self, tmp_path):
        return tmp_path / "test.db"

    @pytest.fixture
    def logger(self, db_path):
        logger = EventLogger(db_path=str(db_path))
        yield logger
        logger.close()

    def test_creates_database(self, db_path):
        logger = EventLogger(db_path=str(db_path))
        logger.close()
        assert db_path.exists()

    def test_creates_events_table(self, logger, db_path):
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_log_event(self, logger, db_path):
        event = FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1,
        )
        logger.on_fall_confirmed(event)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT * FROM events WHERE event_id = ?", ("evt_123",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "evt_123"

    def test_log_recovery(self, logger, db_path):
        event = FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1,
        )
        logger.on_fall_confirmed(event)
        logger.on_fall_recovered(event)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT recovered_at FROM events WHERE event_id = ?", ("evt_123",))
        row = cursor.fetchone()
        conn.close()

        assert row[0] is not None

    def test_get_recent_events(self, logger):
        for i in range(5):
            event = FallEvent(
                event_id=f"evt_{i}",
                confirmed_at=float(i * 100),
                last_notified_at=float(i * 100),
                notification_count=1,
            )
            logger.on_fall_confirmed(event)

        events = logger.get_recent_events(limit=3)
        assert len(events) == 3

    def test_database_has_cloud_sync_columns(self, db_path):
        """Verify events table has skeleton_cloud_path, skeleton_upload_status, skeleton_upload_error columns"""
        logger = EventLogger(str(db_path))

        # Check schema
        cursor = logger.conn.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}

        assert "skeleton_cloud_path" in columns
        assert "skeleton_upload_status" in columns
        assert "skeleton_upload_error" in columns

        logger.close()

    def test_event_logger_initializes_upload_status_as_pending(self, logger):
        """Verify skeleton_upload_status defaults to 'pending'"""
        event = FallEvent(
            event_id="evt_test_001",
            confirmed_at=1234567890.0,
            last_notified_at=1234567890.0,
            notification_count=1
        )
        logger.on_fall_confirmed(event)

        cursor = logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?",
            ("evt_test_001",)
        )
        status = cursor.fetchone()[0]
        assert status == "pending"

    def test_update_skeleton_upload_success(self, logger):
        """Verify update_skeleton_upload marks as uploaded"""
        event = FallEvent(
            event_id="evt_test_002",
            confirmed_at=1234567890.0,
            last_notified_at=1234567890.0,
            notification_count=1
        )
        logger.on_fall_confirmed(event)

        logger.update_skeleton_upload(
            event_id="evt_test_002",
            cloud_path="2025/12/29/evt_test_002.json",
            status="uploaded",
            error=None
        )

        cursor = logger.conn.execute(
            "SELECT skeleton_cloud_path, skeleton_upload_status, skeleton_upload_error FROM events WHERE event_id = ?",
            ("evt_test_002",)
        )
        cloud_path, status, error = cursor.fetchone()

        assert cloud_path == "2025/12/29/evt_test_002.json"
        assert status == "uploaded"
        assert error is None

    def test_update_skeleton_upload_failed(self, logger):
        """Verify update_skeleton_upload marks as failed with error"""
        event = FallEvent(
            event_id="evt_test_003",
            confirmed_at=1234567890.0,
            last_notified_at=1234567890.0,
            notification_count=1
        )
        logger.on_fall_confirmed(event)

        logger.update_skeleton_upload(
            event_id="evt_test_003",
            cloud_path=None,
            status="failed",
            error="NetworkError: Connection timeout"
        )

        cursor = logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_upload_error FROM events WHERE event_id = ?",
            ("evt_test_003",)
        )
        status, error = cursor.fetchone()

        assert status == "failed"
        assert error == "NetworkError: Connection timeout"
