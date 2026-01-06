# Cloud Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Cloud Sync functionality to upload skeleton JSON files to GCP Cloud Storage with automatic retry and status tracking.

**Architecture:** Manual trigger CLI tool with database-backed status tracking. Upload failures are logged and retryable. Configuration supports ADC authentication. Integration point via EventLogger database extension.

**Tech Stack:** Python 3.12+, google-cloud-storage, sqlite3, argparse, pytest

---

## Prerequisites Verification

**Before starting, verify:**
```bash
# GCP authentication should be set up
gcloud auth application-default print-access-token

# Bucket should exist
gsutil ls gs://fds-skeletons-project-4d7321d9-f65d-4955-953

# Dependencies installed
uv sync
```

---

## Task 1: Database Migration (Add Cloud Sync Columns)

**Files:**
- Modify: `src/events/event_logger.py:16-27`
- Test: `tests/events/test_event_logger.py`

**Step 1: Write the failing test**

Create test file to verify new columns:

```python
# tests/events/test_event_logger.py
import tempfile
from pathlib import Path
import sqlite3

from src.events.event_logger import EventLogger
from src.events.observer import FallEvent


def test_database_has_cloud_sync_columns():
    """Verify events table has skeleton_cloud_path, skeleton_upload_status, skeleton_upload_error columns"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        logger = EventLogger(str(db_path))

        # Check schema
        cursor = logger.conn.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}

        assert "skeleton_cloud_path" in columns
        assert "skeleton_upload_status" in columns
        assert "skeleton_upload_error" in columns

        logger.close()


def test_event_logger_initializes_upload_status_as_pending():
    """Verify skeleton_upload_status defaults to 'pending'"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        logger = EventLogger(str(db_path))

        event = FallEvent(
            event_id="evt_test_001",
            confirmed_at=1234567890.0,
            notification_count=1
        )
        logger.on_fall_confirmed(event)

        cursor = logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?",
            ("evt_test_001",)
        )
        status = cursor.fetchone()[0]
        assert status == "pending"

        logger.close()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_event_logger.py::test_database_has_cloud_sync_columns -v`

Expected: FAIL with "AssertionError: assert 'skeleton_cloud_path' in columns"

**Step 3: Update database schema**

Modify `src/events/event_logger.py`:

```python
# src/events/event_logger.py (line 16-27)
def _create_tables(self) -> None:
    self.conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            confirmed_at REAL NOT NULL,
            recovered_at REAL,
            notification_count INTEGER DEFAULT 1,
            clip_path TEXT,
            skeleton_cloud_path TEXT,
            skeleton_upload_status TEXT DEFAULT 'pending',
            skeleton_upload_error TEXT,
            created_at REAL NOT NULL
        )
    """)
    self.conn.commit()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_event_logger.py::test_database_has_cloud_sync_columns -v`

Expected: PASS

Run: `uv run pytest tests/events/test_event_logger.py::test_event_logger_initializes_upload_status_as_pending -v`

Expected: PASS

**Step 5: Add method to update upload status**

Add to `src/events/event_logger.py`:

```python
# src/events/event_logger.py (after update_clip_path method)
def update_skeleton_upload(
    self, event_id: str, cloud_path: str | None, status: str, error: str | None = None
) -> None:
    """Update skeleton upload status

    Args:
        event_id: Event ID
        cloud_path: GCS path (e.g., "2025/12/29/evt_123.json")
        status: 'pending', 'uploaded', or 'failed'
        error: Error message if status is 'failed'
    """
    self.conn.execute(
        """UPDATE events
        SET skeleton_cloud_path = ?, skeleton_upload_status = ?, skeleton_upload_error = ?
        WHERE event_id = ?""",
        (cloud_path, status, error, event_id),
    )
    self.conn.commit()
```

**Step 6: Test the new method**

Add test:

```python
# tests/events/test_event_logger.py
def test_update_skeleton_upload_success():
    """Verify update_skeleton_upload marks as uploaded"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        logger = EventLogger(str(db_path))

        event = FallEvent(event_id="evt_test_002", confirmed_at=1234567890.0, notification_count=1)
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

        logger.close()


def test_update_skeleton_upload_failed():
    """Verify update_skeleton_upload marks as failed with error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        logger = EventLogger(str(db_path))

        event = FallEvent(event_id="evt_test_003", confirmed_at=1234567890.0, notification_count=1)
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

        logger.close()
```

Run: `uv run pytest tests/events/test_event_logger.py -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/events/event_logger.py tests/events/test_event_logger.py
git commit -m "feat(db): add cloud sync columns to events table

- Add skeleton_cloud_path, skeleton_upload_status, skeleton_upload_error columns
- Add update_skeleton_upload() method to EventLogger
- Default status is 'pending'
- Tests verify schema and status updates"
```

---

## Task 2: Configuration Extension (Cloud Sync Config)

**Files:**
- Modify: `src/core/config.py:43-58`
- Modify: `config/settings.yaml:29-34`
- Test: `tests/core/test_config.py`

**Step 1: Write the failing test**

```python
# tests/core/test_config.py
import tempfile
from pathlib import Path

from src.core.config import load_config


def test_config_loads_cloud_sync_section():
    """Verify CloudSyncConfig is loaded correctly"""
    config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolov8n.pt"
  confidence: 0.5
  classes: [0]

analysis:
  fall_threshold: 1.3
  delay_sec: 3.0
  same_event_window: 60.0
  re_notify_interval: 120.0

recording:
  buffer_seconds: 10
  clip_before_sec: 5
  clip_after_sec: 5

notification:
  line_token: "test_token"
  enabled: true

lifecycle:
  clip_retention_days: 7
  skeleton_retention_days: 30
  cleanup_enabled: true
  cleanup_schedule_hours: 24

cloud_sync:
  enabled: true
  gcs_bucket: "fds-skeletons-test-project"
  upload_on_extract: false
  retry_attempts: 3
  retry_delay_seconds: 5
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "settings.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config.cloud_sync.enabled is True
        assert config.cloud_sync.gcs_bucket == "fds-skeletons-test-project"
        assert config.cloud_sync.upload_on_extract is False
        assert config.cloud_sync.retry_attempts == 3
        assert config.cloud_sync.retry_delay_seconds == 5


def test_cloud_sync_config_substitutes_env_vars(monkeypatch):
    """Verify GCS_BUCKET_NAME env var is substituted"""
    monkeypatch.setenv("GCS_BUCKET_NAME", "fds-skeletons-from-env")

    config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolov8n.pt"
  confidence: 0.5
  classes: [0]

analysis:
  fall_threshold: 1.3
  delay_sec: 3.0
  same_event_window: 60.0
  re_notify_interval: 120.0

recording:
  buffer_seconds: 10
  clip_before_sec: 5
  clip_after_sec: 5

notification:
  line_token: "test_token"
  enabled: true

lifecycle:
  clip_retention_days: 7
  skeleton_retention_days: 30
  cleanup_enabled: true
  cleanup_schedule_hours: 24

cloud_sync:
  enabled: true
  gcs_bucket: "${GCS_BUCKET_NAME}"
  upload_on_extract: false
  retry_attempts: 3
  retry_delay_seconds: 5
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "settings.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config.cloud_sync.gcs_bucket == "fds-skeletons-from-env"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_config.py::test_config_loads_cloud_sync_section -v`

Expected: FAIL with "AttributeError: 'Config' object has no attribute 'cloud_sync'"

**Step 3: Add CloudSyncConfig dataclass**

Modify `src/core/config.py`:

```python
# src/core/config.py (add after LifecycleConfig)
@dataclass
class CloudSyncConfig:
    enabled: bool
    gcs_bucket: str
    upload_on_extract: bool
    retry_attempts: int
    retry_delay_seconds: int


@dataclass
class Config:
    camera: CameraConfig
    detection: DetectionConfig
    analysis: AnalysisConfig
    recording: RecordingConfig
    notification: NotificationConfig
    lifecycle: LifecycleConfig
    cloud_sync: CloudSyncConfig  # Add this line
```

Update `load_config()` function:

```python
# src/core/config.py (line 83-96)
def load_config(config_path: str = "config/settings.yaml") -> Config:
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    config_data = _process_config_values(raw_config)

    return Config(
        camera=CameraConfig(**config_data["camera"]),
        detection=DetectionConfig(**config_data["detection"]),
        analysis=AnalysisConfig(**config_data["analysis"]),
        recording=RecordingConfig(**config_data["recording"]),
        notification=NotificationConfig(**config_data["notification"]),
        lifecycle=LifecycleConfig(**config_data["lifecycle"]),
        cloud_sync=CloudSyncConfig(**config_data["cloud_sync"]),  # Add this line
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_config.py::test_config_loads_cloud_sync_section -v`

Expected: PASS

Run: `uv run pytest tests/core/test_config.py::test_cloud_sync_config_substitutes_env_vars -v`

Expected: PASS

**Step 5: Update config/settings.yaml**

Add cloud_sync section:

```yaml
# config/settings.yaml (add at end)
cloud_sync:
  enabled: true
  gcs_bucket: "${GCS_BUCKET_NAME}"
  upload_on_extract: false
  retry_attempts: 3
  retry_delay_seconds: 5
```

**Step 6: Verify production config loads**

Run: `uv run python -c "from src.core.config import load_config; c = load_config(); print(c.cloud_sync)"`

Expected: Should print CloudSyncConfig (bucket name from env or literal)

**Step 7: Commit**

```bash
git add src/core/config.py config/settings.yaml tests/core/test_config.py
git commit -m "feat(config): add CloudSyncConfig dataclass

- Add cloud_sync section to settings.yaml
- Support ${GCS_BUCKET_NAME} env var substitution
- Add retry_attempts and retry_delay_seconds config
- Tests verify config loading and env substitution"
```

---

## Task 3: Cloud Storage Uploader Core Logic

**Files:**
- Create: `src/lifecycle/cloud_sync.py`
- Test: `tests/lifecycle/test_cloud_sync.py`

**Step 1: Write the failing test for path generation**

```python
# tests/lifecycle/test_cloud_sync.py
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.lifecycle.cloud_sync import CloudStorageUploader


def test_generate_cloud_path():
    """Verify cloud path is generated as YYYY/MM/DD/evt_{timestamp}.json"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=str(db_path),
            retry_attempts=3,
            retry_delay=5
        )

        # Test with specific timestamp
        event_id = "evt_1735459200"  # 2024-12-29 12:00:00 UTC
        path = uploader._generate_cloud_path(event_id)

        # Should be YYYY/MM/DD/evt_{timestamp}.json
        assert path.endswith(f"{event_id}.json")
        assert "/" in path  # Should have date hierarchy
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_generate_cloud_path -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'src.lifecycle.cloud_sync'"

**Step 3: Implement minimal CloudStorageUploader**

Create `src/lifecycle/cloud_sync.py`:

```python
"""Cloud Storage uploader for skeleton JSON files

Upload skeleton sequences to GCP Cloud Storage with automatic retry.
"""

import time
from datetime import datetime
from pathlib import Path

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from src.events.event_logger import EventLogger


class UploadError(Exception):
    """Base class for upload errors"""
    pass


class NetworkError(UploadError):
    """Network error (retryable)"""
    pass


class AuthenticationError(UploadError):
    """Authentication error (not retryable)"""
    pass


class CloudStorageUploader:
    """Upload skeleton JSON files to GCP Cloud Storage

    Example:
        >>> uploader = CloudStorageUploader(bucket_name="fds-skeletons-project-123")
        >>> uploader.upload_skeleton("evt_123", "data/skeletons/evt_123.json")
        >>> uploader.upload_pending()
        >>> uploader.retry_failed()
    """

    def __init__(
        self,
        bucket_name: str,
        db_path: str = "data/fds.db",
        retry_attempts: int = 3,
        retry_delay: int = 5
    ):
        """Initialize uploader

        Args:
            bucket_name: GCS bucket name
            db_path: Database path for status tracking
            retry_attempts: Number of retry attempts on failure
            retry_delay: Delay between retries (seconds)
        """
        self.bucket_name = bucket_name
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.event_logger = EventLogger(db_path=db_path)

        # Initialize GCS client (uses ADC)
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)

    def _generate_cloud_path(self, event_id: str) -> str:
        """Generate cloud path for event_id

        Args:
            event_id: Event ID (e.g., "evt_1735459200")

        Returns:
            Cloud path (e.g., "2025/12/29/evt_1735459200.json")
        """
        # Extract timestamp from event_id (format: evt_<timestamp>)
        timestamp_str = event_id.replace("evt_", "")
        timestamp = int(timestamp_str)

        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp)

        # Generate path: YYYY/MM/DD/evt_{timestamp}.json
        return f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}/{event_id}.json"

    def upload_skeleton(
        self, event_id: str, local_path: str | Path, dry_run: bool = False
    ) -> bool:
        """Upload single skeleton JSON to GCS

        Args:
            event_id: Event ID
            local_path: Local JSON file path
            dry_run: If True, don't actually upload (for testing)

        Returns:
            True if upload succeeded, False otherwise
        """
        raise NotImplementedError

    def upload_pending(self, dry_run: bool = False) -> dict:
        """Upload all pending skeletons

        Args:
            dry_run: If True, don't actually upload

        Returns:
            Dict with success/failed counts
        """
        raise NotImplementedError

    def retry_failed(self, dry_run: bool = False) -> dict:
        """Retry all failed uploads

        Args:
            dry_run: If True, don't actually upload

        Returns:
            Dict with success/failed counts
        """
        raise NotImplementedError

    def close(self):
        """Close database connection"""
        self.event_logger.close()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_generate_cloud_path -v`

Expected: PASS

**Step 5: Write test for upload_skeleton success case**

```python
# tests/lifecycle/test_cloud_sync.py
def test_upload_skeleton_success(monkeypatch):
    """Verify upload_skeleton uploads file and updates database"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        local_file = Path(tmpdir) / "evt_1735459200.json"
        local_file.write_text('{"test": "data"}')

        # Mock GCS upload
        mock_blob = Mock()
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob

        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=str(db_path),
            retry_attempts=3,
            retry_delay=1
        )
        uploader.bucket = mock_bucket

        # Create event first
        from src.events.observer import FallEvent
        event = FallEvent(event_id="evt_1735459200", confirmed_at=1735459200.0, notification_count=1)
        uploader.event_logger.on_fall_confirmed(event)

        # Upload
        success = uploader.upload_skeleton("evt_1735459200", str(local_file))

        # Verify upload was called
        assert success is True
        mock_blob.upload_from_filename.assert_called_once_with(str(local_file))

        # Verify database was updated
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_cloud_path FROM events WHERE event_id = ?",
            ("evt_1735459200",)
        )
        status, cloud_path = cursor.fetchone()
        assert status == "uploaded"
        assert cloud_path == "2024/12/29/evt_1735459200.json"

        uploader.close()
```

**Step 6: Implement upload_skeleton**

Update `src/lifecycle/cloud_sync.py`:

```python
def upload_skeleton(
    self, event_id: str, local_path: str | Path, dry_run: bool = False
) -> bool:
    """Upload single skeleton JSON to GCS

    Args:
        event_id: Event ID
        local_path: Local JSON file path
        dry_run: If True, don't actually upload (for testing)

    Returns:
        True if upload succeeded, False otherwise
    """
    local_path = Path(local_path)
    if not local_path.exists():
        error_msg = f"FileNotFoundError: {local_path}"
        self.event_logger.update_skeleton_upload(event_id, None, "failed", error_msg)
        return False

    cloud_path = self._generate_cloud_path(event_id)

    if dry_run:
        print(f"[DRY RUN] Would upload: {local_path} -> gs://{self.bucket_name}/{cloud_path}")
        return True

    # Retry loop
    last_error = None
    for attempt in range(1, self.retry_attempts + 1):
        try:
            blob = self.bucket.blob(cloud_path)
            blob.upload_from_filename(str(local_path))

            # Success - update database
            self.event_logger.update_skeleton_upload(event_id, cloud_path, "uploaded", None)
            return True

        except GoogleCloudError as e:
            last_error = f"{e.__class__.__name__}: {e}"
            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay)
            continue

    # All retries failed
    error_msg = f"{last_error} (attempt {self.retry_attempts}/{self.retry_attempts})"
    self.event_logger.update_skeleton_upload(event_id, None, "failed", error_msg)
    return False
```

**Step 7: Run test to verify it passes**

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_upload_skeleton_success -v`

Expected: PASS

**Step 8: Test upload_skeleton network error with retry**

```python
# tests/lifecycle/test_cloud_sync.py
def test_upload_skeleton_retries_on_network_error():
    """Verify upload_skeleton retries 3 times on network error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        local_file = Path(tmpdir) / "evt_test.json"
        local_file.write_text('{"test": "data"}')

        # Mock GCS to raise error
        mock_blob = Mock()
        mock_blob.upload_from_filename.side_effect = GoogleCloudError("Connection timeout")
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob

        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=str(db_path),
            retry_attempts=3,
            retry_delay=0.1  # Short delay for testing
        )
        uploader.bucket = mock_bucket

        # Create event
        from src.events.observer import FallEvent
        event = FallEvent(event_id="evt_test", confirmed_at=1234567890.0, notification_count=1)
        uploader.event_logger.on_fall_confirmed(event)

        # Upload should fail after 3 retries
        success = uploader.upload_skeleton("evt_test", str(local_file))

        assert success is False
        assert mock_blob.upload_from_filename.call_count == 3  # Retried 3 times

        # Verify database marked as failed
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_upload_error FROM events WHERE event_id = ?",
            ("evt_test",)
        )
        status, error = cursor.fetchone()
        assert status == "failed"
        assert "GoogleCloudError" in error
        assert "attempt 3/3" in error

        uploader.close()
```

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_upload_skeleton_retries_on_network_error -v`

Expected: PASS

**Step 9: Test dry_run mode**

```python
# tests/lifecycle/test_cloud_sync.py
def test_upload_skeleton_dry_run_does_not_upload():
    """Verify dry_run mode does not actually upload"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        local_file = Path(tmpdir) / "evt_dryrun.json"
        local_file.write_text('{"test": "data"}')

        mock_blob = Mock()
        mock_bucket = Mock()
        mock_bucket.blob.return_value = mock_blob

        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=str(db_path),
            retry_attempts=3,
            retry_delay=1
        )
        uploader.bucket = mock_bucket

        # Create event
        from src.events.observer import FallEvent
        event = FallEvent(event_id="evt_dryrun", confirmed_at=1234567890.0, notification_count=1)
        uploader.event_logger.on_fall_confirmed(event)

        # Dry run
        success = uploader.upload_skeleton("evt_dryrun", str(local_file), dry_run=True)

        assert success is True
        mock_blob.upload_from_filename.assert_not_called()  # Should NOT upload

        uploader.close()
```

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_upload_skeleton_dry_run_does_not_upload -v`

Expected: PASS

**Step 10: Commit**

```bash
git add src/lifecycle/cloud_sync.py tests/lifecycle/test_cloud_sync.py
git commit -m "feat(cloud-sync): implement CloudStorageUploader core logic

- Add CloudStorageUploader class with upload_skeleton()
- Generate cloud path as YYYY/MM/DD/evt_{timestamp}.json
- Retry 3 times on network error with configurable delay
- Update database status (pending -> uploaded/failed)
- Support dry_run mode for testing
- Tests verify upload success, retry logic, and dry_run"
```

---

## Task 4: Batch Upload and Query Methods

**Files:**
- Modify: `src/lifecycle/cloud_sync.py`
- Modify: `src/events/event_logger.py`
- Test: `tests/lifecycle/test_cloud_sync.py`

**Step 1: Add database query methods to EventLogger**

First, write the test:

```python
# tests/events/test_event_logger.py
def test_get_pending_uploads():
    """Verify get_pending_uploads returns events with status='pending'"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        logger = EventLogger(str(db_path))

        # Create events
        from src.events.observer import FallEvent
        logger.on_fall_confirmed(FallEvent("evt_001", 1000.0, 1))
        logger.on_fall_confirmed(FallEvent("evt_002", 2000.0, 1))
        logger.on_fall_confirmed(FallEvent("evt_003", 3000.0, 1))

        # Mark one as uploaded
        logger.update_skeleton_upload("evt_002", "2025/12/29/evt_002.json", "uploaded", None)

        # Query pending
        pending = logger.get_pending_uploads()

        assert len(pending) == 2
        event_ids = {e["event_id"] for e in pending}
        assert event_ids == {"evt_001", "evt_003"}

        logger.close()


def test_get_failed_uploads():
    """Verify get_failed_uploads returns events with status='failed'"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        logger = EventLogger(str(db_path))

        # Create events
        from src.events.observer import FallEvent
        logger.on_fall_confirmed(FallEvent("evt_001", 1000.0, 1))
        logger.on_fall_confirmed(FallEvent("evt_002", 2000.0, 1))

        # Mark one as failed
        logger.update_skeleton_upload("evt_002", None, "failed", "Network error")

        # Query failed
        failed = logger.get_failed_uploads()

        assert len(failed) == 1
        assert failed[0]["event_id"] == "evt_002"
        assert failed[0]["skeleton_upload_error"] == "Network error"

        logger.close()
```

Run: `uv run pytest tests/events/test_event_logger.py::test_get_pending_uploads -v`

Expected: FAIL with "AttributeError: 'EventLogger' object has no attribute 'get_pending_uploads'"

**Step 2: Implement query methods in EventLogger**

Add to `src/events/event_logger.py`:

```python
# src/events/event_logger.py (after update_skeleton_upload)
def get_pending_uploads(self) -> list[dict]:
    """Get all events with skeleton_upload_status='pending'

    Returns:
        List of event dicts with event_id, confirmed_at, etc.
    """
    cursor = self.conn.execute(
        """SELECT event_id, confirmed_at, skeleton_upload_status
        FROM events
        WHERE skeleton_upload_status = 'pending'
        ORDER BY confirmed_at ASC"""
    )
    columns = ["event_id", "confirmed_at", "skeleton_upload_status"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_failed_uploads(self) -> list[dict]:
    """Get all events with skeleton_upload_status='failed'

    Returns:
        List of event dicts with event_id, error message, etc.
    """
    cursor = self.conn.execute(
        """SELECT event_id, confirmed_at, skeleton_upload_status, skeleton_upload_error
        FROM events
        WHERE skeleton_upload_status = 'failed'
        ORDER BY confirmed_at ASC"""
    )
    columns = ["event_id", "confirmed_at", "skeleton_upload_status", "skeleton_upload_error"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

Run: `uv run pytest tests/events/test_event_logger.py::test_get_pending_uploads -v`

Expected: PASS

Run: `uv run pytest tests/events/test_event_logger.py::test_get_failed_uploads -v`

Expected: PASS

**Step 3: Implement upload_pending in CloudStorageUploader**

Write test first:

```python
# tests/lifecycle/test_cloud_sync.py
def test_upload_pending_batch():
    """Verify upload_pending uploads all pending events"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Create skeleton files
        skeleton_dir = Path(tmpdir) / "skeletons"
        skeleton_dir.mkdir()
        (skeleton_dir / "evt_001.json").write_text('{"test": 1}')
        (skeleton_dir / "evt_002.json").write_text('{"test": 2}')

        # Create events
        uploader = CloudStorageUploader("test-bucket", str(db_path), retry_attempts=1, retry_delay=0)
        from src.events.observer import FallEvent
        uploader.event_logger.on_fall_confirmed(FallEvent("evt_001", 1000.0, 1))
        uploader.event_logger.on_fall_confirmed(FallEvent("evt_002", 2000.0, 1))

        # Mock GCS
        mock_blob = Mock()
        uploader.bucket.blob = Mock(return_value=mock_blob)

        # Upload pending
        result = uploader.upload_pending(skeleton_dir=str(skeleton_dir))

        assert result["success"] == 2
        assert result["failed"] == 0
        assert mock_blob.upload_from_filename.call_count == 2

        uploader.close()
```

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_upload_pending_batch -v`

Expected: FAIL with "TypeError: upload_pending() got an unexpected keyword argument 'skeleton_dir'"

**Step 4: Implement upload_pending**

Update `src/lifecycle/cloud_sync.py`:

```python
def upload_pending(
    self, skeleton_dir: str | Path = "data/skeletons", dry_run: bool = False
) -> dict:
    """Upload all pending skeletons

    Args:
        skeleton_dir: Directory containing skeleton JSON files
        dry_run: If True, don't actually upload

    Returns:
        Dict with success/failed counts: {"success": 2, "failed": 1}
    """
    skeleton_dir = Path(skeleton_dir)
    pending = self.event_logger.get_pending_uploads()

    success_count = 0
    failed_count = 0

    for event in pending:
        event_id = event["event_id"]
        local_path = skeleton_dir / f"{event_id}.json"

        if not local_path.exists():
            print(f"⚠️  Skeleton file not found: {local_path}")
            failed_count += 1
            continue

        if self.upload_skeleton(event_id, local_path, dry_run=dry_run):
            success_count += 1
        else:
            failed_count += 1

    return {"success": success_count, "failed": failed_count}
```

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_upload_pending_batch -v`

Expected: PASS

**Step 5: Implement retry_failed**

Write test:

```python
# tests/lifecycle/test_cloud_sync.py
def test_retry_failed():
    """Verify retry_failed retries all failed uploads"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        skeleton_dir = Path(tmpdir) / "skeletons"
        skeleton_dir.mkdir()
        (skeleton_dir / "evt_failed.json").write_text('{"test": "retry"}')

        uploader = CloudStorageUploader("test-bucket", str(db_path), retry_attempts=1, retry_delay=0)

        # Create event and mark as failed
        from src.events.observer import FallEvent
        uploader.event_logger.on_fall_confirmed(FallEvent("evt_failed", 1000.0, 1))
        uploader.event_logger.update_skeleton_upload("evt_failed", None, "failed", "Network error")

        # Mock GCS (now succeeds)
        mock_blob = Mock()
        uploader.bucket.blob = Mock(return_value=mock_blob)

        # Retry failed
        result = uploader.retry_failed(skeleton_dir=str(skeleton_dir))

        assert result["success"] == 1
        assert result["failed"] == 0

        # Verify status changed to uploaded
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?",
            ("evt_failed",)
        )
        status = cursor.fetchone()[0]
        assert status == "uploaded"

        uploader.close()
```

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_retry_failed -v`

Expected: FAIL with "TypeError: retry_failed() got an unexpected keyword argument 'skeleton_dir'"

Implement retry_failed:

```python
def retry_failed(
    self, skeleton_dir: str | Path = "data/skeletons", dry_run: bool = False
) -> dict:
    """Retry all failed uploads

    Args:
        skeleton_dir: Directory containing skeleton JSON files
        dry_run: If True, don't actually upload

    Returns:
        Dict with success/failed counts
    """
    skeleton_dir = Path(skeleton_dir)
    failed = self.event_logger.get_failed_uploads()

    success_count = 0
    failed_count = 0

    for event in failed:
        event_id = event["event_id"]
        local_path = skeleton_dir / f"{event_id}.json"

        if not local_path.exists():
            print(f"⚠️  Skeleton file not found: {local_path}")
            failed_count += 1
            continue

        if self.upload_skeleton(event_id, local_path, dry_run=dry_run):
            success_count += 1
        else:
            failed_count += 1

    return {"success": success_count, "failed": failed_count}
```

Run: `uv run pytest tests/lifecycle/test_cloud_sync.py::test_retry_failed -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/lifecycle/cloud_sync.py src/events/event_logger.py tests/
git commit -m "feat(cloud-sync): add batch upload and retry methods

- Add get_pending_uploads() and get_failed_uploads() to EventLogger
- Implement upload_pending() to upload all pending skeletons
- Implement retry_failed() to retry failed uploads
- Tests verify batch operations and database queries"
```

---

## Task 5: CLI Tool (fds-cloud-sync)

**Files:**
- Create: `scripts/cloud_sync.py`
- Modify: `pyproject.toml:30-34`
- Test: Manual CLI testing

**Step 1: Create CLI script skeleton**

Create `scripts/cloud_sync.py`:

```python
#!/usr/bin/env python3
"""Cloud Sync CLI tool

Upload skeleton JSON files to GCP Cloud Storage.

Usage:
    fds-cloud-sync --upload-pending        # Upload all pending skeletons
    fds-cloud-sync --retry-failed          # Retry failed uploads
    fds-cloud-sync --event-id evt_123      # Upload specific event
    fds-cloud-sync --status                # Show upload status
    fds-cloud-sync --dry-run --upload-pending  # Dry run mode
"""

import argparse
import sys
from pathlib import Path

from src.core.config import load_config
from src.lifecycle.cloud_sync import CloudStorageUploader


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Sync - Upload skeleton JSON to GCP Cloud Storage"
    )
    parser.add_argument(
        "--upload-pending",
        action="store_true",
        help="Upload all pending skeletons"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry all failed uploads"
    )
    parser.add_argument(
        "--event-id",
        type=str,
        help="Upload specific event by ID (e.g., evt_1735459200)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show upload status summary"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (don't actually upload)"
    )
    parser.add_argument(
        "--skeleton-dir",
        type=str,
        default="data/skeletons",
        help="Skeleton JSON directory (default: data/skeletons)"
    )

    args = parser.parse_args()

    # Load config
    config = load_config()

    if not config.cloud_sync.enabled:
        print("❌ Cloud Sync is disabled in config/settings.yaml")
        sys.exit(1)

    # Initialize uploader
    uploader = CloudStorageUploader(
        bucket_name=config.cloud_sync.gcs_bucket,
        retry_attempts=config.cloud_sync.retry_attempts,
        retry_delay=config.cloud_sync.retry_delay_seconds
    )

    try:
        if args.status:
            show_status(uploader)
        elif args.upload_pending:
            upload_pending(uploader, args.skeleton_dir, args.dry_run)
        elif args.retry_failed:
            retry_failed(uploader, args.skeleton_dir, args.dry_run)
        elif args.event_id:
            upload_event(uploader, args.event_id, args.skeleton_dir, args.dry_run)
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        uploader.close()


def show_status(uploader: CloudStorageUploader):
    """Show upload status summary"""
    pending = uploader.event_logger.get_pending_uploads()
    failed = uploader.event_logger.get_failed_uploads()

    cursor = uploader.event_logger.conn.execute(
        "SELECT COUNT(*) FROM events WHERE skeleton_upload_status = 'uploaded'"
    )
    uploaded_count = cursor.fetchone()[0]

    print("📊 Cloud Sync Status")
    print(f"  ✅ Uploaded: {uploaded_count}")
    print(f"  ⏳ Pending:  {len(pending)}")
    print(f"  ❌ Failed:   {len(failed)}")

    if failed:
        print("\n❌ Failed uploads:")
        for event in failed[:5]:  # Show first 5
            print(f"  - {event['event_id']}: {event['skeleton_upload_error']}")


def upload_pending(uploader: CloudStorageUploader, skeleton_dir: str, dry_run: bool):
    """Upload all pending skeletons"""
    print("📤 Uploading pending skeletons...")
    result = uploader.upload_pending(skeleton_dir=skeleton_dir, dry_run=dry_run)
    print(f"✅ Success: {result['success']}")
    print(f"❌ Failed:  {result['failed']}")


def retry_failed(uploader: CloudStorageUploader, skeleton_dir: str, dry_run: bool):
    """Retry failed uploads"""
    print("🔄 Retrying failed uploads...")
    result = uploader.retry_failed(skeleton_dir=skeleton_dir, dry_run=dry_run)
    print(f"✅ Success: {result['success']}")
    print(f"❌ Failed:  {result['failed']}")


def upload_event(uploader: CloudStorageUploader, event_id: str, skeleton_dir: str, dry_run: bool):
    """Upload specific event"""
    skeleton_path = Path(skeleton_dir) / f"{event_id}.json"

    if not skeleton_path.exists():
        print(f"❌ Skeleton file not found: {skeleton_path}")
        sys.exit(1)

    print(f"📤 Uploading {event_id}...")
    success = uploader.upload_skeleton(event_id, skeleton_path, dry_run=dry_run)

    if success:
        print(f"✅ Uploaded successfully")
    else:
        print(f"❌ Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Add CLI entry point to pyproject.toml**

Modify `pyproject.toml`:

```toml
[project.scripts]
fds = "main:main"
fds-test-video = "scripts.test_with_video:main"
fds-cleanup = "scripts.cleanup_clips:main"
fds-web = "src.web.app:main"
fds-cloud-sync = "scripts.cloud_sync:main"  # Add this line
```

**Step 3: Test CLI installation**

Run: `uv sync`

Run: `fds-cloud-sync --help`

Expected: Should print help message with all options

**Step 4: Test --status command**

Run: `fds-cloud-sync --status`

Expected: Should print status summary (uploaded/pending/failed counts)

**Step 5: Test --dry-run mode**

Run: `fds-cloud-sync --upload-pending --dry-run`

Expected: Should print "[DRY RUN] Would upload: ..." without actually uploading

**Step 6: Commit**

```bash
git add scripts/cloud_sync.py pyproject.toml
git commit -m "feat(cli): add fds-cloud-sync CLI tool

- Add scripts/cloud_sync.py with argparse interface
- Support --upload-pending, --retry-failed, --event-id, --status
- Support --dry-run mode for testing
- Add fds-cloud-sync entry point to pyproject.toml
- CLI loads config and initializes CloudStorageUploader"
```

---

## Task 6: Integration Testing

**Files:**
- Create: `tests/integration/test_cloud_sync_integration.py`

**Step 1: Write end-to-end integration test**

```python
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
            bucket_name="test-bucket",
            db_path=str(db_path),
            retry_attempts=3,
            retry_delay=0.1
        )

        # Mock GCS
        mock_blob = Mock()
        uploader.bucket.blob = Mock(return_value=mock_blob)

        # Step 1: Create event (simulating fall detection)
        event = FallEvent(event_id="evt_1735459200", confirmed_at=1735459200.0, notification_count=1)
        uploader.event_logger.on_fall_confirmed(event)

        # Verify status is pending
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?",
            ("evt_1735459200",)
        )
        assert cursor.fetchone()[0] == "pending"

        # Step 2: Upload skeleton
        success = uploader.upload_skeleton("evt_1735459200", str(skeleton_file))

        assert success is True
        mock_blob.upload_from_filename.assert_called_once()

        # Verify status changed to uploaded
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status, skeleton_cloud_path FROM events WHERE event_id = ?",
            ("evt_1735459200",)
        )
        status, cloud_path = cursor.fetchone()
        assert status == "uploaded"
        assert cloud_path == "2024/12/29/evt_1735459200.json"

        # Step 3: Test batch upload (no pending items)
        result = uploader.upload_pending(skeleton_dir=str(skeleton_dir))
        assert result["success"] == 0
        assert result["failed"] == 0

        uploader.close()


def test_network_failure_recovery_workflow():
    """Test workflow with network failure and retry"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        skeleton_dir = Path(tmpdir) / "skeletons"
        skeleton_dir.mkdir()

        skeleton_file = skeleton_dir / "evt_retry.json"
        skeleton_file.write_text('{"test": "data"}')

        uploader = CloudStorageUploader(
            bucket_name="test-bucket",
            db_path=str(db_path),
            retry_attempts=2,
            retry_delay=0.1
        )

        # Create event
        event = FallEvent(event_id="evt_retry", confirmed_at=1000.0, notification_count=1)
        uploader.event_logger.on_fall_confirmed(event)

        # Mock GCS to fail first, then succeed
        mock_blob = Mock()
        from google.cloud.exceptions import GoogleCloudError
        mock_blob.upload_from_filename.side_effect = [
            GoogleCloudError("Network timeout"),  # First attempt fails
            None  # Second attempt succeeds
        ]
        uploader.bucket.blob = Mock(return_value=mock_blob)

        # Upload (should succeed on retry)
        success = uploader.upload_skeleton("evt_retry", str(skeleton_file))

        assert success is True
        assert mock_blob.upload_from_filename.call_count == 2  # Failed once, succeeded once

        # Verify final status is uploaded
        cursor = uploader.event_logger.conn.execute(
            "SELECT skeleton_upload_status FROM events WHERE event_id = ?",
            ("evt_retry",)
        )
        assert cursor.fetchone()[0] == "uploaded"

        uploader.close()
```

**Step 2: Run integration tests**

Run: `uv run pytest tests/integration/test_cloud_sync_integration.py -v`

Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/integration/test_cloud_sync_integration.py
git commit -m "test(cloud-sync): add integration tests

- Test full workflow: create event -> upload -> verify status
- Test network failure recovery with retry
- Tests use mocked GCS to avoid real uploads"
```

---

## Task 7: Documentation Updates

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md with Cloud Sync commands**

Add to `CLAUDE.md`:

```markdown
## Cloud Sync Commands

**上傳骨架到 GCS:**
```bash
# 上傳所有待上傳的骨架
fds-cloud-sync --upload-pending

# 重試失敗的上傳
fds-cloud-sync --retry-failed

# 上傳特定事件
fds-cloud-sync --event-id evt_1735459200

# 查看上傳狀態
fds-cloud-sync --status

# 乾運行模式（測試用）
fds-cloud-sync --upload-pending --dry-run
```

**GCP 設定:**
參閱 `docs/plans/2025-12-29-cloud-sync-design.md` Section 5 完整設定指南。
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Cloud Sync commands to CLAUDE.md

- Add fds-cloud-sync CLI usage examples
- Reference design doc for GCP setup guide"
```

---

## Task 8: Final Verification and Cleanup

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`

Expected: All tests PASS

**Step 2: Verify CLI works end-to-end**

```bash
# Check status
fds-cloud-sync --status

# Dry run
fds-cloud-sync --upload-pending --dry-run

# (Optional) Real upload if GCP is configured
# fds-cloud-sync --upload-pending
```

**Step 3: Check code quality**

Run: `uv run ruff check src/ tests/ scripts/`

Expected: No errors

Run: `uv run ruff format src/ tests/ scripts/`

Expected: All files formatted

**Step 4: Final commit**

```bash
git add .
git commit -m "chore: final cleanup and formatting

- Run ruff format on all Python files
- Verify all tests pass
- Cloud Sync implementation complete"
```

---

## Completion Checklist

After completing all tasks, verify:

- [x] Database has 3 new columns (skeleton_cloud_path, skeleton_upload_status, skeleton_upload_error)
- [x] Config loads CloudSyncConfig from settings.yaml
- [x] CloudStorageUploader can upload single file with retry
- [x] CloudStorageUploader can batch upload pending files
- [x] CloudStorageUploader can retry failed uploads
- [x] CLI tool `fds-cloud-sync` is installed and working
- [x] All unit tests pass
- [x] All integration tests pass
- [x] Documentation updated
- [x] Code passes ruff checks

---

## Next Steps

**After implementation:**

1. **Manual GCP Testing** - Upload a real skeleton file to verify GCS access
2. **Web Dashboard Integration** - Add cloud upload status to event list UI
3. **Automatic Upload** - Set `upload_on_extract: true` in config to enable auto-upload
4. **Lifecycle Policy** - Apply GCS lifecycle rules for automatic storage class transitions

**Optional Enhancements:**

- Add progress bar for batch uploads (using `tqdm`)
- Add webhook notification on upload success/failure
- Add BigQuery integration for skeleton data analysis
- Add cloud path to Web Dashboard event details

---

**Plan created:** 2025-12-29
**Estimated time:** 2-3 hours (8 tasks × 15-20 minutes each)
**Prerequisite:** GCP authentication configured (gcloud ADC)
