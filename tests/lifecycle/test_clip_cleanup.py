import pytest
import sqlite3
import time
from pathlib import Path

from src.lifecycle.clip_cleanup import ClipCleanup


class TestClipCleanup:
    @pytest.fixture
    def test_db(self, tmp_path):
        """建立測試資料庫"""
        db_path = tmp_path / "test_fds.db"
        conn = sqlite3.connect(str(db_path))

        # 建立 events 表（與 EventLogger 相同結構）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                confirmed_at REAL NOT NULL,
                recovered_at REAL,
                notification_count INTEGER DEFAULT 1,
                clip_path TEXT,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        return db_path

    @pytest.fixture
    def clips_dir(self, tmp_path):
        """建立測試影片目錄"""
        clips = tmp_path / "clips"
        clips.mkdir()
        return clips

    @pytest.fixture
    def cleanup(self, test_db, clips_dir):
        """建立 ClipCleanup 實例"""
        return ClipCleanup(db_path=str(test_db), clips_dir=str(clips_dir), retention_days=7)

    def test_cleanup_init(self, cleanup, test_db, clips_dir):
        """測試清理器初始化"""
        assert cleanup.db_path == Path(test_db)
        assert cleanup.clips_dir == Path(clips_dir)
        assert cleanup.retention_days == 7

    def test_get_expired_clips_empty_db(self, cleanup):
        """測試空資料庫回傳空列表"""
        expired = cleanup.get_expired_clips()
        assert expired == []

    def test_get_expired_clips_no_expired(self, cleanup, test_db, clips_dir):
        """測試沒有過期影片時回傳空列表"""
        # 插入 3 天前的記錄（未過期）
        three_days_ago = time.time() - (3 * 24 * 60 * 60)
        conn = sqlite3.connect(str(test_db))
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_123", three_days_ago, str(clips_dir / "evt_123.mp4"), three_days_ago),
        )
        conn.commit()
        conn.close()

        expired = cleanup.get_expired_clips()
        assert expired == []

    def test_get_expired_clips_returns_old_records(self, cleanup, test_db, clips_dir):
        """測試回傳過期影片記錄"""
        # 插入 10 天前的記錄（已過期）
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        conn = sqlite3.connect(str(test_db))
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_old", ten_days_ago, str(clips_dir / "evt_old.mp4"), ten_days_ago),
        )
        conn.commit()
        conn.close()

        expired = cleanup.get_expired_clips()
        assert len(expired) == 1
        assert expired[0]["event_id"] == "evt_old"
        assert expired[0]["clip_path"] == str(clips_dir / "evt_old.mp4")

    def test_get_expired_clips_mixed_records(self, cleanup, test_db, clips_dir):
        """測試混合新舊記錄時只回傳過期的"""
        conn = sqlite3.connect(str(test_db))

        # 插入 3 天前的記錄（未過期）
        three_days_ago = time.time() - (3 * 24 * 60 * 60)
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_new", three_days_ago, str(clips_dir / "evt_new.mp4"), three_days_ago),
        )

        # 插入 10 天前的記錄（已過期）
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_old", ten_days_ago, str(clips_dir / "evt_old.mp4"), ten_days_ago),
        )

        conn.commit()
        conn.close()

        expired = cleanup.get_expired_clips()
        assert len(expired) == 1
        assert expired[0]["event_id"] == "evt_old"

    def test_cleanup_deletes_expired_files(self, cleanup, test_db, clips_dir):
        """測試清理功能刪除過期影片檔案"""
        # 建立過期影片檔案
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        clip_path = clips_dir / "evt_old.mp4"
        clip_path.write_text("fake video data")

        # 插入資料庫記錄
        conn = sqlite3.connect(str(test_db))
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_old", ten_days_ago, str(clip_path), ten_days_ago),
        )
        conn.commit()
        conn.close()

        # 執行清理
        assert clip_path.exists()
        result = cleanup.cleanup()

        # 驗證檔案被刪除
        assert not clip_path.exists()
        assert result["deleted_count"] == 1
        assert result["freed_bytes"] > 0

    def test_cleanup_skips_missing_files(self, cleanup, test_db, clips_dir):
        """測試清理時跳過已不存在的檔案"""
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        clip_path = clips_dir / "evt_missing.mp4"

        # 插入資料庫記錄，但不建立實際檔案
        conn = sqlite3.connect(str(test_db))
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_missing", ten_days_ago, str(clip_path), ten_days_ago),
        )
        conn.commit()
        conn.close()

        # 執行清理不應報錯
        result = cleanup.cleanup()
        assert result["deleted_count"] == 0
        assert result["skipped_count"] == 1

    def test_cleanup_updates_database(self, cleanup, test_db, clips_dir):
        """測試清理後更新資料庫記錄"""
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        clip_path = clips_dir / "evt_old.mp4"
        clip_path.write_text("fake video data")

        conn = sqlite3.connect(str(test_db))
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_old", ten_days_ago, str(clip_path), ten_days_ago),
        )
        conn.commit()
        conn.close()

        # 執行清理
        cleanup.cleanup()

        # 驗證資料庫中 clip_path 被設為 NULL
        conn = sqlite3.connect(str(test_db))
        cursor = conn.execute("SELECT clip_path FROM events WHERE event_id = ?", ("evt_old",))
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] is None  # clip_path 應該被設為 NULL

    def test_cleanup_dry_run(self, cleanup, test_db, clips_dir):
        """測試乾運行模式（不實際刪除）"""
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        clip_path = clips_dir / "evt_old.mp4"
        clip_path.write_text("fake video data")

        conn = sqlite3.connect(str(test_db))
        conn.execute(
            """
            INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("evt_old", ten_days_ago, str(clip_path), ten_days_ago),
        )
        conn.commit()
        conn.close()

        # 乾運行模式
        result = cleanup.cleanup(dry_run=True)

        # 檔案應該還在
        assert clip_path.exists()
        assert result["deleted_count"] == 0
        assert result["would_delete_count"] == 1

    def test_cleanup_statistics(self, cleanup, test_db, clips_dir):
        """測試清理統計資訊完整性"""
        # 建立多個過期檔案
        ten_days_ago = time.time() - (10 * 24 * 60 * 60)
        conn = sqlite3.connect(str(test_db))

        for i in range(3):
            clip_path = clips_dir / f"evt_{i}.mp4"
            clip_path.write_bytes(b"x" * 1000)  # 1000 bytes

            conn.execute(
                """
                INSERT INTO events (event_id, confirmed_at, clip_path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (f"evt_{i}", ten_days_ago, str(clip_path), ten_days_ago),
            )

        conn.commit()
        conn.close()

        result = cleanup.cleanup()

        assert result["deleted_count"] == 3
        assert result["freed_bytes"] == 3000
        assert result["skipped_count"] == 0
        assert "duration_sec" in result
