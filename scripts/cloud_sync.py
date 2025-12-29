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
