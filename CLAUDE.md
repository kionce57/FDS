# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fall Detection System (FDS) - 居家長照跌倒偵測系統。使用 YOLO 進行人體/姿態偵測，透過規則引擎判斷跌倒，並觸發 LINE 通知、影片錄製、事件記錄。

**技術棧:** Python 3.12+, uv, YOLO11/YOLOv8 (Ultralytics), OpenCV, SQLite, ruff, pytest

## Quick Reference

```bash
# 依賴管理
uv sync                    # 安裝/同步依賴
uv sync --all-extras       # 包含 dev 依賴

# 執行
uv run python main.py                              # 即時偵測
uv run python -m scripts.test_with_video <path>    # 影片測試
uv run python -m scripts.test_with_video --use-pose <path>  # Pose 模式
uv run python -m src.web.app                       # Web Dashboard (port 8000)

# 測試
uv run pytest                                      # 全部測試
uv run pytest tests/test_detector.py -v            # 單一模組
uv run pytest --cov=src --cov-report=term-missing  # 覆蓋率

# 程式碼品質
uv run ruff check .         # Lint
uv run ruff check . --fix   # 自動修復
uv run ruff format .        # 格式化

# Docker
docker compose up -d        # 啟動服務
docker compose logs -f fds  # 查看日誌
```

## Core Architecture

### Pipeline Flow (src/core/pipeline.py)

```
Camera → Detector → RuleEngine → DelayConfirm → Observers
           ↓            ↓              ↓              ↓
      YOLO detect   is_fallen?   State Machine    EventLogger (SQLite)
                                                   LineNotifier (LINE API)
                                                   ClipRecorder → SkeletonExtractor → CloudSync (GCS)
```

**關鍵流程:**
1. `Camera.read()` 擷取影像幀
2. `Detector.detect()` 執行 YOLO 推論 → 回傳 BBox 或 Skeleton
3. `RuleEngine.is_fallen()` 套用規則（長寬比 < 1.3 或軀幹角度 < 60°）
4. `DelayConfirm.update()` 狀態機判斷（3 秒延遲確認）
5. 狀態變化時觸發 Observer Pattern 通知所有訂閱者
6. `RollingBuffer` 持續保存 10 秒環形緩衝，跌倒確認時提取前後 5 秒影片

### Detection Modes

| Mode | Model | Rule | Output |
|------|-------|------|--------|
| BBox (預設) | `yolov8n.pt` | `aspect_ratio < 1.3` | `BBox(x, y, w, h, confidence, aspect_ratio)` |
| Pose | `yolo11s-pose.pt` | `torso_angle < 60°` | `Skeleton(keypoints[17], torso_angle, confidence)` |

> **Note:** Pose 模式已從 YOLOv8n-Pose 升級至 YOLO11s-Pose，提供更佳的穩定性。可透過 `config/settings.yaml` 的 `detection.pose_model` 設定自訂模型路徑。

### State Machine (src/analysis/delay_confirm.py)

```
NORMAL → is_fallen=True → SUSPECTED
SUSPECTED → is_fallen=False → NORMAL (reset)
SUSPECTED → elapsed >= 3s → CONFIRMED (trigger observers)
CONFIRMED → is_fallen=False → NORMAL (recovery event)
CONFIRMED → is_fallen=True + elapsed >= 120s → re-notify
```

**Event Window Logic:**
- `same_event_window=60s`: 60 秒內視為同一跌倒事件
- `re_notify_interval=120s`: 持續躺著時每 2 分鐘重複通知

### Observer Pattern (src/events/)

```python
class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...
```

**Observers:** `EventLogger`, `LineNotifier`, `ClipRecorder`, `Pipeline`

### Skeleton Collection (src/lifecycle/skeleton_collector.py)

自動訂閱 SUSPECTED 事件，outcome 確定後提取骨架：
- `CONFIRMED` → `sus_xxx_confirmed.json` (正樣本)
- `CLEARED` → `sus_xxx_cleared.json` (負樣本)

### Configuration (src/core/config.py)

載入順序: `config/settings.yaml` → `_substitute_env_vars()` → 強型別 dataclass

環境變數: `.env` 定義 `LINE_BOT_CHANNEL_ACCESS_TOKEN`, `LINE_BOT_USER_ID`, `GCS_BUCKET_NAME`

## Key Data Structures

| 結構 | 位置 | 用途 |
|------|------|------|
| `BBox` | `src/detection/bbox.py` | Bounding box + aspect_ratio |
| `Skeleton` | `src/detection/skeleton.py` | 17 keypoints + torso_angle |
| `FrameData` | `src/capture/rolling_buffer.py` | 幀資料（含 timestamp, bbox） |
| `FallEvent` | `src/events/observer.py` | 跌倒事件 metadata |
| `SuspectedEvent` | `src/events/observer.py` | 疑似跌倒事件（含 outcome 標籤） |
| `SkeletonSequence` | `src/lifecycle/schema/` | 骨架 JSON 序列化格式 |

## CLI Entry Points

| Command | Module | 用途 |
|---------|--------|------|
| `fds` | `main:main` | 主程式（即時偵測） |
| `fds-test-video` | `scripts.test_with_video:main` | 影片測試 |
| `fds-cleanup` | `scripts.cleanup_clips:main` | 清理過期檔案 |
| `fds-web` | `src.web.app:main` | Web Dashboard |
| `fds-cloud-sync` | `scripts.cloud_sync:main` | 骨架上傳 GCS |

## Important Notes

- **Model files:** 首次執行自動下載 `yolov8n.pt` / `yolo11s-pose.pt`
- **Data directory:** `data/` 由 gitignore，包含 `fds.db`, `clips/`, `skeletons/`
- **Camera source:** 開發用影片測試，正式環境改 camera index 或 RTSP URL
- **LINE Bot:** 配置缺失時通知失敗但不會 crash Pipeline
- **Cleanup:** `lifecycle.clip_retention_days=7`，使用 `fds-cleanup` 執行

## Output
- 總是使用英文思考, 使用繁體中文進行輸出
