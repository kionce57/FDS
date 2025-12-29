import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.lifecycle.cloud_sync import CloudStorageUploader


class TestCloudPathGeneration:
    def test_generate_cloud_path(self):
        """Test cloud path generation from event_id"""
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=":memory:",
            retry_attempts=3,
            retry_delay=1,
        )

        # Event ID format: evt_{timestamp}
        # timestamp 1735459200 = 2024-12-29 00:00:00 UTC
        event_id = "evt_1735459200.000"

        result = uploader._generate_cloud_path(event_id)

        # Expected format: YYYY/MM/DD/evt_{timestamp}.json
        assert result == "2024/12/29/evt_1735459200.000.json"

    def test_generate_cloud_path_with_different_date(self):
        """Test cloud path generation with different timestamp"""
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=":memory:",
            retry_attempts=3,
            retry_delay=1,
        )

        # timestamp 1704067200 = 2024-01-01 00:00:00 UTC
        event_id = "evt_1704067200.123"

        result = uploader._generate_cloud_path(event_id)

        assert result == "2024/01/01/evt_1704067200.123.json"


class TestUploadSkeleton:
    @pytest.fixture
    def temp_db(self):
        """Create temporary database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield str(db_path)

    @pytest.fixture
    def temp_skeleton_file(self):
        """Create temporary skeleton JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"keypoints": [], "timestamp": 1735459200.0}')
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @patch("src.lifecycle.cloud_sync.storage.Client")
    def test_upload_skeleton_success(self, mock_client_class, temp_db, temp_skeleton_file):
        """Test successful skeleton upload"""
        # Setup mock GCS client
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create uploader
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=temp_db,
            retry_attempts=3,
            retry_delay=1,
        )

        # Create event in database first
        uploader.event_logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, created_at)
            VALUES (?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, 1735459200.0),
        )
        uploader.event_logger.conn.commit()

        # Upload skeleton
        event_id = "evt_1735459200.000"
        result = uploader.upload_skeleton(event_id, temp_skeleton_file)

        # Verify upload was called
        assert result is True
        mock_bucket.blob.assert_called_once_with("2024/12/29/evt_1735459200.000.json")
        mock_blob.upload_from_filename.assert_called_once_with(temp_skeleton_file)

        # Verify database was updated
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_cloud_path, skeleton_upload_status FROM events WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "2024/12/29/evt_1735459200.000.json"
        assert row[1] == "uploaded"

    @patch("src.lifecycle.cloud_sync.storage.Client")
    @patch("src.lifecycle.cloud_sync.time.sleep")  # Mock sleep to speed up test
    def test_upload_skeleton_retries_on_network_error(
        self, mock_sleep, mock_client_class, temp_db, temp_skeleton_file
    ):
        """Test that upload retries on network error"""
        from google.cloud.exceptions import GoogleCloudError

        # Setup mock GCS client
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # First 2 attempts fail, 3rd succeeds
        mock_blob.upload_from_filename.side_effect = [
            GoogleCloudError("Network error 1"),
            GoogleCloudError("Network error 2"),
            None,  # Success on 3rd attempt
        ]

        # Create uploader
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=temp_db,
            retry_attempts=3,
            retry_delay=1,
        )

        # Create event in database first
        uploader.event_logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, created_at)
            VALUES (?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, 1735459200.0),
        )
        uploader.event_logger.conn.commit()

        # Upload skeleton
        event_id = "evt_1735459200.000"
        result = uploader.upload_skeleton(event_id, temp_skeleton_file)

        # Verify upload was retried 3 times
        assert result is True
        assert mock_blob.upload_from_filename.call_count == 3

        # Verify sleep was called 2 times (after 1st and 2nd failure)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1)

        # Verify database was updated with success
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "uploaded"

    @patch("src.lifecycle.cloud_sync.storage.Client")
    @patch("builtins.print")  # Mock print to verify dry_run message
    def test_upload_skeleton_dry_run_does_not_upload(
        self, mock_print, mock_client_class, temp_db, temp_skeleton_file
    ):
        """Test that dry_run mode doesn't actually upload"""
        # Setup mock GCS client
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create uploader
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=temp_db,
            retry_attempts=3,
            retry_delay=1,
        )

        # Upload skeleton in dry_run mode
        event_id = "evt_1735459200.000"
        result = uploader.upload_skeleton(event_id, temp_skeleton_file, dry_run=True)

        # Verify result is True
        assert result is True

        # Verify print was called with expected message
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "[DRY RUN]" in call_args
        assert "test-bucket" in call_args
        assert "2024/12/29/evt_1735459200.000.json" in call_args

        # Verify GCS methods were NOT called
        mock_bucket.blob.assert_not_called()
        mock_blob.upload_from_filename.assert_not_called()

    @patch("src.lifecycle.cloud_sync.storage.Client")
    def test_upload_skeleton_file_not_found(self, mock_client_class, temp_db):
        """Test upload fails when local file doesn't exist"""
        # Setup mock GCS client
        mock_client = Mock()
        mock_bucket = Mock()

        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket

        # Create uploader
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=temp_db,
            retry_attempts=3,
            retry_delay=1,
        )

        # Create event in database first
        uploader.event_logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, created_at)
            VALUES (?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, 1735459200.0),
        )
        uploader.event_logger.conn.commit()

        # Try to upload non-existent file
        event_id = "evt_1735459200.000"
        result = uploader.upload_skeleton(event_id, "/nonexistent/file.json")

        # Verify upload failed
        assert result is False

        # Verify database was updated with error
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_upload_error FROM events WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "failed"
        assert "not found" in row[1].lower()

    @patch("src.lifecycle.cloud_sync.storage.Client")
    @patch("src.lifecycle.cloud_sync.time.sleep")  # Mock sleep to speed up test
    def test_upload_skeleton_max_retries_exceeded(
        self, mock_sleep, mock_client_class, temp_db, temp_skeleton_file
    ):
        """Test upload fails after max retries exceeded"""
        from google.cloud.exceptions import GoogleCloudError

        # Setup mock GCS client
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # All attempts fail
        mock_blob.upload_from_filename.side_effect = GoogleCloudError("Network error")

        # Create uploader
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=temp_db,
            retry_attempts=3,
            retry_delay=1,
        )

        # Create event in database first
        uploader.event_logger.conn.execute(
            """INSERT INTO events
            (event_id, confirmed_at, created_at)
            VALUES (?, ?, ?)""",
            ("evt_1735459200.000", 1735459200.0, 1735459200.0),
        )
        uploader.event_logger.conn.commit()

        # Upload skeleton
        event_id = "evt_1735459200.000"
        result = uploader.upload_skeleton(event_id, temp_skeleton_file)

        # Verify upload failed
        assert result is False

        # Verify upload was attempted 3 times
        assert mock_blob.upload_from_filename.call_count == 3

        # Verify database was updated with error
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_upload_error FROM events WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        assert row[0] == "failed"
        assert "3 attempts" in row[1]
