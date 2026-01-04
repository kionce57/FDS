import pytest
from src.core.config import load_config


class TestConfig:
    @pytest.fixture
    def config_file(self, tmp_path):
        config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolov8n.pt"
  pose_model: "yolo11s-pose.pt"
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
  line_channel_access_token: "${LINE_BOT_CHANNEL_ACCESS_TOKEN}"
  line_user_id: "${LINE_BOT_USER_ID}"
  enabled: true

lifecycle:
  clip_retention_days: 7
  skeleton_retention_days: 30

cloud_sync:
  enabled: true
  gcs_bucket: "fds-skeletons-test-project"
  upload_on_extract: false
  retry_attempts: 3
  retry_delay_seconds: 5
"""
        config_path = tmp_path / "settings.yaml"
        config_path.write_text(config_content)
        return config_path

    def test_load_config(self, config_file):
        config = load_config(str(config_file))
        assert config.camera.fps == 15
        assert config.detection.model == "yolov8n.pt"
        assert config.analysis.fall_threshold == 1.3

    def test_env_variable_substitution(self, config_file, monkeypatch):
        monkeypatch.setenv("LINE_BOT_CHANNEL_ACCESS_TOKEN", "test_token_123")
        monkeypatch.setenv("LINE_BOT_USER_ID", "U1234567890")
        config = load_config(str(config_file))
        assert config.notification.line_channel_access_token == "test_token_123"
        assert config.notification.line_user_id == "U1234567890"

    def test_camera_config(self, config_file):
        config = load_config(str(config_file))
        assert config.camera.source == 0
        assert config.camera.resolution == [640, 480]

    def test_analysis_config(self, config_file):
        config = load_config(str(config_file))
        assert config.analysis.delay_sec == 3.0
        assert config.analysis.same_event_window == 60.0

    def test_config_has_pose_model(self, config_file):
        """Verify DetectionConfig has pose_model field for YOLO11 support."""
        config = load_config(str(config_file))
        assert hasattr(config.detection, "pose_model")
        assert config.detection.pose_model == "yolo11s-pose.pt"

    def test_config_loads_cloud_sync_section(self, config_file):
        """Verify CloudSyncConfig is loaded correctly"""
        config = load_config(str(config_file))

        assert config.cloud_sync.enabled is True
        assert config.cloud_sync.gcs_bucket == "fds-skeletons-test-project"
        assert config.cloud_sync.upload_on_extract is False
        assert config.cloud_sync.retry_attempts == 3
        assert config.cloud_sync.retry_delay_seconds == 5

    def test_cloud_sync_config_substitutes_env_vars(self, tmp_path, monkeypatch):
        """Verify GCS_BUCKET_NAME env var is substituted"""
        monkeypatch.setenv("GCS_BUCKET_NAME", "fds-skeletons-from-env")

        config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolov8n.pt"
  pose_model: "yolo11s-pose.pt"
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
  line_channel_access_token: "test_token"
  line_user_id: "U1234567890"
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

        config_path = tmp_path / "settings.yaml"
        config_path.write_text(config_content)

        config = load_config(str(config_path))

        assert config.cloud_sync.gcs_bucket == "fds-skeletons-from-env"
