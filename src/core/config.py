import os
import re
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

# Load .env file before processing config
load_dotenv()


@dataclass
class CameraConfig:
    source: int | str
    fps: int
    resolution: list[int]


@dataclass
class DetectionConfig:
    model: str
    confidence: float
    classes: list[int]
    pose_model: str = "yolo11s-pose.pt"


@dataclass
class AnalysisConfig:
    fall_threshold: float
    delay_sec: float
    same_event_window: float
    re_notify_interval: float


@dataclass
class RecordingConfig:
    buffer_seconds: int
    clip_before_sec: int
    clip_after_sec: int


@dataclass
class NotificationConfig:
    line_channel_access_token: str
    line_user_id: str
    enabled: bool


@dataclass
class LifecycleConfig:
    clip_retention_days: int
    skeleton_retention_days: int
    cleanup_enabled: bool = True
    cleanup_schedule_hours: int = 24
    auto_skeleton_extract: bool = False
    skeleton_output_dir: str = "data/skeletons"


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
    cloud_sync: CloudSyncConfig


def _substitute_env_vars(value: str) -> str:
    pattern = r"\$\{([^}]+)\}"

    def replace(match):
        env_var = match.group(1)
        return os.environ.get(env_var, match.group(0))

    return re.sub(pattern, replace, value)


def _process_config_values(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _process_config_values(value)
        elif isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config/settings.yaml") -> Config:
    with open(config_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    config_data = _process_config_values(raw_config)

    return Config(
        camera=CameraConfig(**config_data["camera"]),
        detection=DetectionConfig(**config_data["detection"]),
        analysis=AnalysisConfig(**config_data["analysis"]),
        recording=RecordingConfig(**config_data["recording"]),
        notification=NotificationConfig(**config_data["notification"]),
        lifecycle=LifecycleConfig(**config_data["lifecycle"]),
        cloud_sync=CloudSyncConfig(**config_data["cloud_sync"]),
    )
