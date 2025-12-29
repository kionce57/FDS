#!/usr/bin/env python3
"""
清理排程器功能驗證腳本

此腳本用於在正式部署前驗證清理功能是否正常運作：
1. 建立測試資料庫和影片檔案
2. 模擬過期記錄（設定為 8 天前）
3. 啟動排程器並觀察清理過程
4. 驗證結果

Usage:
    uv run python scripts/demo_cleanup_scheduler.py
"""

import shutil
import sqlite3
import time
from pathlib import Path

from src.core.config import load_config
from src.lifecycle.cleanup_scheduler import CleanupScheduler


def create_test_environment(base_dir: Path) -> tuple[Path, Path]:
    """建立測試環境

    Returns:
        (db_path, clips_dir) 測試資料庫和影片目錄路徑
    """
    # 清理舊的測試目錄
    if base_dir.exists():
        shutil.rmtree(base_dir)

    base_dir.mkdir(parents=True)

    db_path = base_dir / "test_fds.db"
    clips_dir = base_dir / "clips"
    clips_dir.mkdir()

    # 建立資料庫
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            clip_path TEXT,
            created_at REAL
        )
    """)
    conn.commit()
    conn.close()

    return db_path, clips_dir


def create_test_clips(db_path: Path, clips_dir: Path) -> list[dict]:
    """建立測試影片和記錄

    建立 5 個測試影片：
    - 3 個過期（8, 10, 14 天前）
    - 2 個未過期（3, 5 天前）
    """
    current_time = time.time()
    day_seconds = 24 * 60 * 60

    test_clips = [
        # 過期影片（超過 7 天）
        {"event_id": "evt_001", "days_ago": 8, "size_kb": 100},
        {"event_id": "evt_002", "days_ago": 10, "size_kb": 200},
        {"event_id": "evt_003", "days_ago": 14, "size_kb": 150},
        # 未過期影片（7 天內）
        {"event_id": "evt_004", "days_ago": 3, "size_kb": 80},
        {"event_id": "evt_005", "days_ago": 5, "size_kb": 120},
    ]

    conn = sqlite3.connect(str(db_path))

    for clip in test_clips:
        # 建立影片檔案
        clip_path = clips_dir / f"{clip['event_id']}.mp4"
        clip_path.write_bytes(b"0" * (clip["size_kb"] * 1024))

        # 插入資料庫記錄
        timestamp = current_time - (clip["days_ago"] * day_seconds)
        conn.execute(
            "INSERT INTO events (event_id, clip_path, created_at) VALUES (?, ?, ?)",
            (clip["event_id"], str(clip_path), timestamp),
        )

        clip["path"] = clip_path
        clip["timestamp"] = timestamp

    conn.commit()
    conn.close()

    return test_clips


def print_status(db_path: Path, clips_dir: Path, test_clips: list[dict]) -> None:
    """顯示當前狀態"""
    print("\n" + "=" * 60)
    print("當前狀態")
    print("=" * 60)

    # 檢查磁碟上的檔案
    existing_files = list(clips_dir.glob("*.mp4"))
    print(f"\n📁 磁碟上的影片檔案: {len(existing_files)} 個")

    # 檢查資料庫記錄
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT event_id, clip_path, created_at FROM events")
    records = cursor.fetchall()
    conn.close()

    current_time = time.time()
    day_seconds = 24 * 60 * 60

    print(f"💾 資料庫記錄: {len(records)} 筆\n")

    print(f"{'事件 ID':<12} {'天數前':<8} {'檔案狀態':<12} {'clip_path'}")
    print("-" * 60)

    for event_id, clip_path, created_at in records:
        days_ago = int((current_time - created_at) / day_seconds)

        if clip_path:
            file_exists = Path(clip_path).exists()
            file_status = "✓ 存在" if file_exists else "✗ 缺失"
        else:
            file_status = "— 已清理"

        path_display = Path(clip_path).name if clip_path else "NULL"
        expired_mark = "[過期]" if days_ago > 7 else ""

        print(f"{event_id:<12} {days_ago:<8} {file_status:<12} {path_display} {expired_mark}")


def run_demo():
    """執行完整演示"""
    print("=" * 60)
    print("🧹 清理排程器功能驗證")
    print("=" * 60)
    print("\n此腳本將：")
    print("1. 建立測試環境（資料庫 + 影片檔案）")
    print("2. 建立 5 個測試影片（3 個過期 + 2 個未過期）")
    print("3. 執行即時清理驗證")
    print("4. 顯示清理結果\n")

    # 設定測試目錄
    test_dir = Path("data/demo_cleanup")

    # Step 1: 建立測試環境
    print("📦 Step 1: 建立測試環境...")
    db_path, clips_dir = create_test_environment(test_dir)
    print(f"   資料庫: {db_path}")
    print(f"   影片目錄: {clips_dir}")

    # Step 2: 建立測試資料
    print("\n📝 Step 2: 建立測試資料...")
    test_clips = create_test_clips(db_path, clips_dir)

    total_size = sum(c["size_kb"] for c in test_clips)
    expired_count = sum(1 for c in test_clips if c["days_ago"] > 7)

    print(f"   建立 {len(test_clips)} 個測試影片（總計 {total_size} KB）")
    print(f"   - 過期影片: {expired_count} 個（超過 7 天）")
    print(f"   - 未過期影片: {len(test_clips) - expired_count} 個（7 天內）")

    # 顯示初始狀態
    print_status(db_path, clips_dir, test_clips)

    # Step 3: 執行清理
    print("\n" + "=" * 60)
    print("🚀 Step 3: 執行即時清理")
    print("=" * 60)

    # 建立配置（模擬真實配置）
    config = load_config()

    # 建立排程器
    scheduler = CleanupScheduler(
        config=config,
        db_path=db_path,
        clips_dir=clips_dir,
    )

    print("\n執行 run_now() 進行即時清理...")
    print("-" * 40)

    result = scheduler.run_now()

    print("\n📊 清理結果:")
    print(f"   刪除檔案數: {result['deleted_count']}")
    print(f"   釋放空間: {result['freed_bytes'] / 1024:.1f} KB")
    print(f"   跳過檔案數: {result['skipped_count']}")
    print(f"   執行時間: {result['duration_sec']:.3f} 秒")

    # Step 4: 驗證結果
    print("\n" + "=" * 60)
    print("✅ Step 4: 驗證結果")
    print("=" * 60)

    print_status(db_path, clips_dir, test_clips)

    # 驗證邏輯
    remaining_files = list(clips_dir.glob("*.mp4"))
    expected_remaining = len(test_clips) - expired_count

    print("\n" + "-" * 60)

    if len(remaining_files) == expected_remaining:
        print("🎉 驗證成功！")
        print(f"   - 過期影片已刪除: {expired_count} 個")
        print(f"   - 未過期影片保留: {expected_remaining} 個")
        print("   - 資料庫 clip_path 已更新為 NULL")
    else:
        print("⚠️ 驗證失敗！")
        print(f"   預期剩餘 {expected_remaining} 個檔案，實際 {len(remaining_files)} 個")

    # 清理選項
    print("\n" + "=" * 60)
    print("🧪 測試排程器背景執行（可選）")
    print("=" * 60)

    try:
        response = input("\n是否測試背景排程器？每 10 秒執行一次清理 (y/N): ").strip().lower()

        if response == "y":
            print("\n啟動背景排程器（10 秒間隔）...")
            print("按 Ctrl+C 停止\n")

            # 重新建立一些測試檔案
            create_test_clips(db_path, clips_dir)

            # 修改配置為 10 秒間隔
            config.lifecycle.cleanup_schedule_hours = 10 / 3600  # 10 秒

            scheduler2 = CleanupScheduler(
                config=config,
                db_path=db_path,
                clips_dir=clips_dir,
            )
            scheduler2.start()

            try:
                while True:
                    time.sleep(5)
                    print_status(db_path, clips_dir, test_clips)
            except KeyboardInterrupt:
                print("\n\n停止排程器...")
                scheduler2.stop()
                print("排程器已停止")

    except EOFError:
        print("\n跳過背景測試（非互動模式）")

    # 清理測試環境
    print("\n" + "=" * 60)

    try:
        cleanup_response = input("是否清理測試環境？(Y/n): ").strip().lower()
        if cleanup_response != "n":
            shutil.rmtree(test_dir)
            print("✓ 測試環境已清理")
        else:
            print(f"保留測試環境: {test_dir}")
    except EOFError:
        shutil.rmtree(test_dir)
        print("✓ 測試環境已清理")

    print("\n演示完成！")


if __name__ == "__main__":
    run_demo()
