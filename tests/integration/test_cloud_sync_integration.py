# tests/integration/test_cloud_sync_integration.py
"""Integration test for Cloud Sync

Tests full workflow:
1. Create skeleton JSON file
2. Upload to GCS (mocked)
3. Verify database status
4. Test retry logic
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from src.lifecycle.cloud_sync import CloudStorageUploader
from src.events.observer import FallEvent


def test_full_cloud_sync_workflow():
    """Test complete workflow: extract -> upload -> verify"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        skeleton_dir = Path(tmpdir) / "skeletons"
        skeleton_dir.mkdir()

        # Create skeleton file
        skeleton_file = skeleton_dir / "evt_1735459200.json"
        skeleton_file.write_text('{"metadata": {"event_id": "evt_1735459200"}}')

        # Initialize uploader
        uploader = CloudStorageUploader(
            bucket_name="test-bucket", db_path=str(db_path), retry_attempts=3, retry_delay=0.1
        )

        # Mock GCS
        mock_blob = Mock()
        uploader.bucket.blob = Mock(return_value=mock_blob)

        # Step 1: Create event (simulating fall detection)
        event = FallEvent(
            event_id="evt_1735459200",
            confirmed_at=1735459200.0,
            last_notified_at=1735459200.0,
            notification_count=1,
        )
        uploader.event_logger.on_fall_confirmed(event)

        # Verify status is pending
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?", ("evt_1735459200",)
        )
        assert cursor.fetchone()[0] == "pending"

        # Step 2: Upload skeleton
        success = uploader.upload_skeleton("evt_1735459200", str(skeleton_file))

        assert success is True
        mock_blob.upload_from_filename.assert_called_once()

        # Verify status changed to uploaded
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_cloud_path FROM events WHERE event_id = ?",
            ("evt_1735459200",),
        )
        status, cloud_path = cursor.fetchone()
        assert status == "uploaded"
        assert cloud_path == "2024/12/29/evt_1735459200.json"

        # Step 3: Test batch upload (no pending items)
        result = uploader.upload_pending(skeleton_dir=str(skeleton_dir))
        assert result["success"] == 0
        assert result["failed"] == 0

        uploader.event_logger.close()


def test_network_failure_recovery_workflow():
    """Test workflow with network failure and retry"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        skeleton_dir = Path(tmpdir) / "skeletons"
        skeleton_dir.mkdir()

        # Use proper timestamp-based event_id
        event_id = "evt_1735460000"
        skeleton_file = skeleton_dir / f"{event_id}.json"
        skeleton_file.write_text('{"test": "data"}')

        uploader = CloudStorageUploader(
            bucket_name="test-bucket", db_path=str(db_path), retry_attempts=2, retry_delay=0.1
        )

        # Create event
        event = FallEvent(
            event_id=event_id,
            confirmed_at=1735460000.0,
            last_notified_at=1735460000.0,
            notification_count=1,
        )
        uploader.event_logger.on_fall_confirmed(event)

        # Mock GCS to fail first, then succeed
        mock_blob = Mock()
        from google.cloud.exceptions import GoogleCloudError

        mock_blob.upload_from_filename.side_effect = [
            GoogleCloudError("Network timeout"),  # First attempt fails
            None,  # Second attempt succeeds
        ]
        uploader.bucket.blob = Mock(return_value=mock_blob)

        # Upload (should succeed on retry)
        success = uploader.upload_skeleton(event_id, str(skeleton_file))

        assert success is True
        assert mock_blob.upload_from_filename.call_count == 2  # Failed once, succeeded once

        # Verify final status is uploaded
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?", (event_id,)
        )
        assert cursor.fetchone()[0] == "uploaded"

        uploader.event_logger.close()
