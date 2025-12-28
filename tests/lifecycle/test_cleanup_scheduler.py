"""
清理排程器單元測試
"""

import sqlite3
import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import Config, LifecycleConfig
from src.lifecycle.cleanup_scheduler import CleanupScheduler


@pytest.fixture
def mock_config():
    """建立模擬配置"""
    config = MagicMock(spec=Config)
    config.lifecycle = MagicMock(spec=LifecycleConfig)
    config.lifecycle.cleanup_enabled = True
    config.lifecycle.cleanup_schedule_hours = 24
    config.lifecycle.clip_retention_days = 7
    return config


@pytest.fixture
def mock_config_disabled():
    """建立清理功能停用的模擬配置"""
    config = MagicMock(spec=Config)
    config.lifecycle = MagicMock(spec=LifecycleConfig)
    config.lifecycle.cleanup_enabled = False
    config.lifecycle.cleanup_schedule_hours = 24
    config.lifecycle.clip_retention_days = 7
    return config


@pytest.fixture
def temp_db(tmp_path):
    """建立臨時資料庫"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            clip_path TEXT,
            created_at REAL
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


class TestCleanupScheduler:
    """清理排程器測試"""

    def test_scheduler_init(self, mock_config, tmp_path):
        """測試排程器初始化"""
        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=tmp_path / "db.sqlite",
            clips_dir=tmp_path / "clips",
        )

        assert scheduler.config == mock_config
        assert scheduler.db_path == tmp_path / "db.sqlite"
        assert scheduler.clips_dir == tmp_path / "clips"
        assert scheduler.is_running is False

    def test_scheduler_start_stop(self, mock_config, tmp_path):
        """測試排程器啟動和停止"""
        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=tmp_path / "db.sqlite",
            clips_dir=tmp_path / "clips",
        )

        # 啟動
        scheduler.start()
        assert scheduler.is_running is True

        # 停止
        scheduler.stop()
        assert scheduler.is_running is False

    def test_scheduler_start_disabled(self, mock_config_disabled, tmp_path):
        """測試清理功能停用時不啟動排程器"""
        scheduler = CleanupScheduler(
            config=mock_config_disabled,
            db_path=tmp_path / "db.sqlite",
            clips_dir=tmp_path / "clips",
        )

        scheduler.start()
        assert scheduler.is_running is False

    def test_scheduler_double_start(self, mock_config, tmp_path):
        """測試重複啟動排程器"""
        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=tmp_path / "db.sqlite",
            clips_dir=tmp_path / "clips",
        )

        scheduler.start()
        assert scheduler.is_running is True

        # 再次啟動應該不會有問題
        scheduler.start()
        assert scheduler.is_running is True

        scheduler.stop()

    def test_scheduler_stop_when_not_running(self, mock_config, tmp_path):
        """測試停止未執行的排程器"""
        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=tmp_path / "db.sqlite",
            clips_dir=tmp_path / "clips",
        )

        # 未啟動就停止應該不會有問題
        scheduler.stop()
        assert scheduler.is_running is False

    def test_run_now_executes_cleanup(self, mock_config, temp_db, tmp_path):
        """測試立即執行清理"""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()

        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=temp_db,
            clips_dir=clips_dir,
        )

        result = scheduler.run_now()

        assert "deleted_count" in result
        assert "freed_bytes" in result
        assert result["deleted_count"] == 0  # 空資料庫，沒有過期檔案

    def test_run_now_with_expired_clips(self, mock_config, temp_db, tmp_path):
        """測試清理過期影片"""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()

        # 建立測試影片檔案
        test_clip = clips_dir / "old_clip.mp4"
        test_clip.write_bytes(b"0" * 1000)  # 1000 bytes

        # 插入過期記錄（8 天前）
        conn = sqlite3.connect(str(temp_db))
        old_timestamp = time.time() - (8 * 24 * 60 * 60)
        conn.execute(
            "INSERT INTO events (event_id, clip_path, created_at) VALUES (?, ?, ?)",
            ("evt_123", str(test_clip), old_timestamp),
        )
        conn.commit()
        conn.close()

        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=temp_db,
            clips_dir=clips_dir,
        )

        result = scheduler.run_now()

        assert result["deleted_count"] == 1
        assert result["freed_bytes"] == 1000
        assert not test_clip.exists()

    def test_run_now_handles_error(self, mock_config, tmp_path):
        """測試清理失敗時的錯誤處理"""
        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=tmp_path / "nonexistent.db",  # 不存在的資料庫
            clips_dir=tmp_path / "clips",
        )

        result = scheduler.run_now()

        assert "error" in result
        assert result["deleted_count"] == 0


class TestCleanupSchedulerIntegration:
    """清理排程器整合測試"""

    def test_scheduler_runs_cleanup_on_schedule(self, mock_config, temp_db, tmp_path):
        """測試排程器定時執行清理"""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()

        # 修改排程間隔為 1 秒以加速測試
        mock_config.lifecycle.cleanup_schedule_hours = 1 / 3600  # 1 秒

        scheduler = CleanupScheduler(
            config=mock_config,
            db_path=temp_db,
            clips_dir=clips_dir,
        )

        with patch.object(scheduler, "_run_cleanup") as mock_cleanup:
            scheduler.start()

            # 等待足夠時間讓排程器執行
            time.sleep(1.5)

            scheduler.stop()

            # 確認清理函數被調用
            assert mock_cleanup.call_count >= 1
