import tempfile
from pathlib import Path

import pytest

from src.events.event_logger import EventLogger


class TestEventLoggerQueryMethods:
    @pytest.fixture
    def temp_db(self):
        """Create temporary database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield str(db_path)

    def test_get_pending_uploads(self, temp_db):
        """Test get_pending_uploads returns only pending events"""
        logger = EventLogger(db_path=temp_db)

        # Create test events with different statuses
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, "pending", 1735459200.0),
        )
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459300.000", 1735459300.0, "uploaded", 1735459300.0),
        )
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459400.000", 1735459400.0, "pending", 1735459400.0),
        )
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459500.000", 1735459500.0, "failed", 1735459500.0),
        )
        logger.conn.commit()

        # Get pending uploads
        pending = logger.get_pending_uploads()

        # Should return only 2 pending events
        assert len(pending) == 2
        assert pending[0]["event_id"] == "evt_1735459200.000"
        assert pending[0]["skeleton_upload_status"] == "pending"
        assert pending[1]["event_id"] == "evt_1735459400.000"
        assert pending[1]["skeleton_upload_status"] == "pending"

        # Verify order is by confirmed_at ASC
        assert pending[0]["confirmed_at"] == 1735459200.0
        assert pending[1]["confirmed_at"] == 1735459400.0

    def test_get_pending_uploads_empty(self, temp_db):
        """Test get_pending_uploads returns empty list when no pending events"""
        logger = EventLogger(db_path=temp_db)

        # Create events with non-pending status
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, "uploaded", 1735459200.0),
        )
        logger.conn.commit()

        # Get pending uploads
        pending = logger.get_pending_uploads()

        # Should be empty
        assert len(pending) == 0

    def test_get_failed_uploads(self, temp_db):
        """Test get_failed_uploads returns only failed events"""
        logger = EventLogger(db_path=temp_db)

        # Create test events with different statuses
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, skeleton_upload_error, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, "failed", "Network error", 1735459200.0),
        )
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459300.000", 1735459300.0, "uploaded", 1735459300.0),
        )
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, skeleton_upload_error, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            ("evt_1735459400.000", 1735459400.0, "failed", "File not found", 1735459400.0),
        )
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459500.000", 1735459500.0, "pending", 1735459500.0),
        )
        logger.conn.commit()

        # Get failed uploads
        failed = logger.get_failed_uploads()

        # Should return only 2 failed events
        assert len(failed) == 2
        assert failed[0]["event_id"] == "evt_1735459200.000"
        assert failed[0]["skeleton_upload_status"] == "failed"
        assert failed[0]["skeleton_upload_error"] == "Network error"
        assert failed[1]["event_id"] == "evt_1735459400.000"
        assert failed[1]["skeleton_upload_status"] == "failed"
        assert failed[1]["skeleton_upload_error"] == "File not found"

        # Verify order is by confirmed_at ASC
        assert failed[0]["confirmed_at"] == 1735459200.0
        assert failed[1]["confirmed_at"] == 1735459400.0

    def test_get_failed_uploads_empty(self, temp_db):
        """Test get_failed_uploads returns empty list when no failed events"""
        logger = EventLogger(db_path=temp_db)

        # Create events with non-failed status
        logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, skeleton_upload_status, created_at)
            VALUES (?, ?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, "uploaded", 1735459200.0),
        )
        logger.conn.commit()

        # Get failed uploads
        failed = logger.get_failed_uploads()

        # Should be empty
        assert len(failed) == 0
