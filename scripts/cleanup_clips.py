#!/usr/bin/env python3
"""
影片清理腳本

手動觸發清理超過保留期限的影片檔案。

Usage:
    uv run python -m scripts.cleanup_clips
    uv run python -m scripts.cleanup_clips --dry-run
    uv run python -m scripts.cleanup_clips --retention-days 14
"""

import argparse
from pathlib import Path

from src.core.config import load_config
from src.lifecycle.clip_cleanup import ClipCleanup


def format_bytes(bytes_count: int) -> str:
    """格式化 bytes 為易讀格式"""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_count < 1024:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.2f} TB"


def main():
    parser = argparse.ArgumentParser(description="清理過期影片檔案")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="乾運行模式，不實際刪除檔案",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="保留天數（預設從 config 讀取）",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/fds.db",
        help="資料庫路徑（預設: data/fds.db）",
    )
    parser.add_argument(
        "--clips-dir",
        type=str,
        default="data/clips",
        help="影片目錄（預設: data/clips）",
    )

    args = parser.parse_args()

    # 讀取配置
    config = load_config()
    retention_days = (
        args.retention_days
        if args.retention_days is not None
        else config.lifecycle.clip_retention_days
    )

    # 初始化清理器
    cleanup = ClipCleanup(
        db_path=args.db_path,
        clips_dir=args.clips_dir,
        retention_days=retention_days,
    )

    print("影片清理排程器")
    print("=" * 50)
    print(f"資料庫路徑: {args.db_path}")
    print(f"影片目錄: {args.clips_dir}")
    print(f"保留天數: {retention_days} 天")
    print(f"模式: {'乾運行（不刪除）' if args.dry_run else '正式刪除'}")
    print("=" * 50)

    # 查詢過期影片
    expired = cleanup.get_expired_clips()
    print(f"\n找到 {len(expired)} 個過期影片記錄")

    if len(expired) == 0:
        print("✓ 沒有需要清理的檔案")
        return

    # 顯示過期影片清單
    print("\n過期影片清單:")
    for record in expired:
        clip_path = Path(record["clip_path"])
        exists = "✓" if clip_path.exists() else "✗ (缺失)"
        size = format_bytes(clip_path.stat().st_size) if clip_path.exists() else "N/A"
        print(f"  - {record['event_id']}: {clip_path.name} ({size}) {exists}")

    # 執行清理
    print(f"\n{'模擬' if args.dry_run else '執行'}清理...")
    result = cleanup.cleanup(dry_run=args.dry_run)

    # 顯示結果
    print("\n清理結果:")
    print(f"  執行時間: {result['duration_sec']:.2f} 秒")

    if args.dry_run:
        print(f"  將刪除: {result['would_delete_count']} 個檔案")
        print(f"  跳過（缺失）: {result['skipped_count']} 個檔案")
    else:
        print(f"  已刪除: {result['deleted_count']} 個檔案")
        print(f"  釋放空間: {format_bytes(result['freed_bytes'])}")
        print(f"  跳過（缺失）: {result['skipped_count']} 個檔案")
        print("\n✓ 清理完成")


if __name__ == "__main__":
    main()
