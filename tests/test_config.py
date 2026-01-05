import pytest
from src.core.config import load_config, DetectionConfig


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


class TestDetectionConfigPoseOptions:
    """Test Pose/Smoothing configuration options."""

    def test_detection_config_has_pose_options(self):
        """DetectionConfig should have use_pose and smoothing options."""
        config = DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
            pose_model="yolo11s-pose.pt",
            use_pose=True,
            enable_smoothing=True,
            smoothing_min_cutoff=1.0,
            smoothing_beta=0.007,
        )
        assert config.use_pose is True
        assert config.enable_smoothing is True
        assert config.smoothing_min_cutoff == 1.0
        assert config.smoothing_beta == 0.007

    def test_detection_config_defaults(self):
        """DetectionConfig should have sensible defaults."""
        config = DetectionConfig(
            model="yolo11n.pt",
            confidence=0.5,
            classes=[0],
        )
        assert config.use_pose is False
        assert config.enable_smoothing is False
        assert config.smoothing_min_cutoff == 1.0
        assert config.smoothing_beta == 0.007

    def test_load_config_with_pose_options(self, tmp_path):
        """load_config should parse pose options from YAML."""
        config_content = """
camera:
  source: 0
  fps: 15
  resolution: [640, 480]

detection:
  model: "yolo11n.pt"
  pose_model: "yolo11s-pose.pt"
  confidence: 0.5
  classes: [0]
  use_pose: true
  enable_smoothing: true
  smoothing_min_cutoff: 0.8
  smoothing_beta: 0.01

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
  line_channel_access_token: "test"
  line_user_id: "test"
  enabled: false

lifecycle:
  clip_retention_days: 7
"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config.detection.use_pose is True
        assert config.detection.enable_smoothing is True
        assert config.detection.smoothing_min_cutoff == 0.8
        assert config.detection.smoothing_beta == 0.01
