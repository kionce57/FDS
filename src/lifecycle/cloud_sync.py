"""Cloud storage synchronization for skeleton data"""

import time
from datetime import datetime
from pathlib import Path

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from src.events.event_logger import EventLogger


class UploadError(Exception):
    """Base exception for upload errors"""

    pass


class NetworkError(UploadError):
    """Network-related errors (retryable)"""

    pass


class AuthenticationError(UploadError):
    """Authentication errors (not retryable)"""

    pass


class CloudStorageUploader:
    """Upload skeleton JSON files to Google Cloud Storage"""

    def __init__(
        self,
        bucket_name: str,
        db_path: str = "data/fds.db",
        retry_attempts: int = 3,
        retry_delay: int = 5,
    ):
        self.bucket_name = bucket_name
        self.db_path = db_path
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        # Initialize GCS client (uses Application Default Credentials)
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

        # Initialize database logger
        self.event_logger = EventLogger(db_path)

    def _generate_cloud_path(self, event_id: str) -> str:
        """Generate GCS path from event_id

        Args:
            event_id: Event ID in format "evt_{timestamp}"

        Returns:
            Cloud path in format "YYYY/MM/DD/evt_{timestamp}.json"
        """
        # Extract timestamp from event_id (format: evt_{timestamp})
        timestamp_str = event_id.replace("evt_", "")
        timestamp = float(timestamp_str)

        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp)

        # Generate path: YYYY/MM/DD/evt_{timestamp}.json
        year = dt.strftime("%Y")
        month = dt.strftime("%m")
        day = dt.strftime("%d")

        return f"{year}/{month}/{day}/{event_id}.json"

    def upload_skeleton(
        self, event_id: str, local_path: str | Path, dry_run: bool = False
    ) -> bool:
        """Upload skeleton JSON file to GCS with retry logic

        Args:
            event_id: Event ID
            local_path: Path to local skeleton JSON file
            dry_run: If True, print message but don't actually upload

        Returns:
            True if upload successful, False otherwise
        """
        local_path = Path(local_path)

        # Check if file exists
        if not local_path.exists():
            error_msg = f"Local file not found: {local_path}"
            self.event_logger.update_skeleton_upload(
                event_id=event_id,
                cloud_path=None,
                status="failed",
                error=error_msg,
            )
            return False

        # Generate cloud path
        cloud_path = self._generate_cloud_path(event_id)

        # Dry run mode
        if dry_run:
            print(f"[DRY RUN] Would upload {local_path} to gs://{self.bucket_name}/{cloud_path}")
            return True

        # Retry loop
        last_error = None
        for attempt in range(self.retry_attempts):
            try:
                # Upload to GCS
                blob = self.bucket.blob(cloud_path)
                blob.upload_from_filename(str(local_path))

                # Update database on success
                self.event_logger.update_skeleton_upload(
                    event_id=event_id,
                    cloud_path=cloud_path,
                    status="uploaded",
                    error=None,
                )
                return True

            except GoogleCloudError as e:
                last_error = e
                if attempt < self.retry_attempts - 1:
                    # Sleep before retry
                    time.sleep(self.retry_delay)
                    continue
                else:
                    # Max retries reached
                    break

        # Upload failed after all retries
        error_msg = f"Upload failed after {self.retry_attempts} attempts: {last_error}"
        self.event_logger.update_skeleton_upload(
            event_id=event_id,
            cloud_path=None,
            status="failed",
            error=error_msg,
        )
        return False
