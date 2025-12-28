#!/usr/bin/env python3
"""
Web Dashboard 功能驗證腳本

此腳本用於驗證 Web Dashboard 的 API 和頁面功能。

Usage:
    # 先在另一個終端啟動 Web Server
    uv run python scripts/run_web.py

    # 然後執行此腳本
    uv run python scripts/demo_web_dashboard.py
"""

import sqlite3
import time
from pathlib import Path

import requests


def create_test_database():
    """建立測試資料庫"""
    db_path = Path("data/fds.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))

    # 建立 events 資料表（如果不存在）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            clip_path TEXT,
            created_at REAL,
            notification_count INTEGER DEFAULT 0
        )
    """)

    # 插入測試資料
    current_time = time.time()
    test_events = [
        ("evt_demo_001", None, current_time - 3600, 1),  # 1 小時前
        ("evt_demo_002", None, current_time - 7200, 2),  # 2 小時前
        ("evt_demo_003", None, current_time - 86400, 1),  # 1 天前
        ("evt_demo_004", None, current_time - 172800, 0),  # 2 天前
        ("evt_demo_005", None, current_time - 259200, 1),  # 3 天前
    ]

    for event in test_events:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO events (event_id, clip_path, created_at, notification_count) VALUES (?, ?, ?, ?)",
                event,
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

    print(f"✓ 建立測試資料庫: {db_path}")
    print(f"  插入 {len(test_events)} 筆測試事件")


def test_api_endpoints(base_url: str = "http://localhost:8000"):
    """測試 API 端點"""
    print("\n" + "=" * 50)
    print("測試 API 端點")
    print("=" * 50)

    tests = [
        ("GET /api/status", f"{base_url}/api/status"),
        ("GET /api/stats", f"{base_url}/api/stats"),
        ("GET /api/events", f"{base_url}/api/events"),
        ("GET /api/events?page=1&per_page=3", f"{base_url}/api/events?page=1&per_page=3"),
    ]

    all_passed = True

    for name, url in tests:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ {name}")

                # 顯示部分回應
                if "status" in data:
                    print(f"    狀態: {data['status']}, 版本: {data.get('version', 'N/A')}")
                elif "total_events" in data:
                    print(f"    總事件: {data['total_events']}, 今日: {data['today_events']}")
                elif "events" in data:
                    print(f"    總數: {data['total']}, 頁數: {data['page']}/{data['total_pages']}")
            else:
                print(f"✗ {name} - HTTP {response.status_code}")
                all_passed = False
        except requests.exceptions.ConnectionError:
            print(f"✗ {name} - 連線失敗（請確認 Web Server 已啟動）")
            all_passed = False
        except Exception as e:
            print(f"✗ {name} - {e}")
            all_passed = False

    return all_passed


def test_pages(base_url: str = "http://localhost:8000"):
    """測試頁面"""
    print("\n" + "=" * 50)
    print("測試頁面")
    print("=" * 50)

    pages = [
        ("儀表板", f"{base_url}/"),
        ("事件列表", f"{base_url}/events"),
        ("API 文檔", f"{base_url}/docs"),
    ]

    all_passed = True

    for name, url in pages:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                size = len(response.content)
                print(f"✓ {name}")
                print(f"    URL: {url}")
                print(f"    大小: {size} bytes")
            else:
                print(f"✗ {name} - HTTP {response.status_code}")
                all_passed = False
        except requests.exceptions.ConnectionError:
            print(f"✗ {name} - 連線失敗")
            all_passed = False
        except Exception as e:
            print(f"✗ {name} - {e}")
            all_passed = False

    return all_passed


def main():
    print("=" * 50)
    print("🌐 FDS Web Dashboard 功能驗證")
    print("=" * 50)

    # 步驟 1: 建立測試資料庫
    print("\n📦 Step 1: 準備測試資料")
    create_test_database()

    # 步驟 2: 測試 API
    print("\n🔌 Step 2: 測試 API 端點")
    api_ok = test_api_endpoints()

    # 步驟 3: 測試頁面
    print("\n📄 Step 3: 測試頁面")
    pages_ok = test_pages()

    # 結果
    print("\n" + "=" * 50)
    print("驗證結果")
    print("=" * 50)

    if api_ok and pages_ok:
        print("🎉 所有測試通過！")
        print("\n請在瀏覽器訪問以下頁面查看 UI：")
        print("  - http://localhost:8000          (儀表板)")
        print("  - http://localhost:8000/events   (事件列表)")
        print("  - http://localhost:8000/docs     (API 文檔)")
    else:
        print("⚠️ 部分測試失敗")
        print("\n請確認：")
        print("  1. Web Server 是否已啟動？")
        print("     uv run python scripts/run_web.py")
        print("  2. 是否可以訪問 http://localhost:8000 ？")


if __name__ == "__main__":
    main()
