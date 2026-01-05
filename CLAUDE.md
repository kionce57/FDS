# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fall Detection System (FDS) - 居家長照跌倒偵測系統。使用 YOLO 進行人體/姿態偵測，透過規則引擎判斷跌倒，並觸發 LINE 通知、影片錄製、事件記錄。

**技術棧:** Python 3.12+, uv, YOLO11 (Ultralytics), OpenCV, SQLite, ruff, pytest

## Quick Reference

```bash
# 依賴管理
uv sync                    # 安裝/同步依賴
uv sync --all-extras       # 包含 dev 依賴

# 執行
uv run python main.py                              # 即時偵測
uv run python -m scripts.test_with_video <path>    # 影片測試 (BBox 模式)
uv run python -m scripts.test_with_video <path> --use-pose                 # Pose 模式
uv run python -m scripts.test_with_video <path> --use-pose --enable-smoothing  # Pose + 平滑

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

詳細架構請參考 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，包含 C4 Model、Sequence Diagram 與 SA/SD 分析。

### Pipeline Flow (src/core/pipeline.py)

```
Camera → Detector → RuleEngine → DelayConfirm → Observers
           ↓            ↓              ↓              ↓
      YOLO detect   is_fallen?   State Machine    EventLogger (SQLite)
                                                   LineNotifier (LINE API)
                                                   ClipRecorder (影片錄製)
```

**關鍵流程:**

1. `Camera.read()` 擷取影像幀
2. `Detector.detect()` 執行 YOLO 推論 → 回傳 BBox 或 Skeleton
3. `RuleEngine.is_fallen()` 套用規則（長寬比 < 1.3 或軀幹角度 < 60°）
4. `DelayConfirm.update()` 狀態機判斷（3 秒延遲確認）
5. 狀態變化時觸發 Observer Pattern 通知所有訂閱者
6. `RollingBuffer` 持續保存 10 秒環形緩衝，跌倒確認時提取前後 5 秒影片

### Detection Modes

| Mode        | Model             | Rule                 | Output                                             |
| ----------- | ----------------- | -------------------- | -------------------------------------------------- |
| BBox (預設) | `yolo11n.pt`      | `aspect_ratio < 1.3` | `BBox(x, y, w, h, confidence, aspect_ratio)`       |
| Pose        | `yolo11s-pose.pt` | `torso_angle < 60°`  | `Skeleton(keypoints[17], torso_angle, confidence)` |

### Keypoint Smoothing (src/analysis/smoothing/)

Pose 模式可選啟用 **One Euro Filter** 平滑關鍵點，減少抖動造成的誤判：

```python
# PoseRuleEngine 支援平滑參數
rule_engine = PoseRuleEngine(
    torso_angle_threshold=60.0,
    enable_smoothing=True,      # 啟用平滑
    smoothing_min_cutoff=1.0,   # 越低越平滑
    smoothing_beta=0.007,       # 越高對快速動作反應越快
)

# 需傳入 timestamp 以計算濾波
is_fallen = rule_engine.is_fallen(skeleton, timestamp=current_time)
```

CLI 使用: `--enable-smoothing` 旗標

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

**Observers:** `EventLogger`, `LineNotifier`, `Pipeline`

### Configuration (src/core/config.py)

載入順序: `config/settings.yaml` → `_substitute_env_vars()` → 強型別 dataclass

**Detection Config Options:**

```yaml
detection:
  use_pose: true # 啟用 Pose 模式（預設 false，使用 BBox）
  enable_smoothing: true # 啟用 Keypoint 平滑（僅 Pose 模式）
  smoothing_min_cutoff: 1.0
  smoothing_beta: 0.007
```

環境變數: `.env` 定義 `LINE_BOT_CHANNEL_ACCESS_TOKEN`, `LINE_BOT_USER_ID`

## Key Data Structures

| 結構               | 位置                            | 用途                         |
| ------------------ | ------------------------------- | ---------------------------- |
| `BBox`             | `src/detection/bbox.py`         | Bounding box + aspect_ratio  |
| `Skeleton`         | `src/detection/skeleton.py`     | 17 keypoints + torso_angle   |
| `FrameData`        | `src/capture/rolling_buffer.py` | 幀資料（含 timestamp, bbox） |
| `FallEvent`        | `src/events/observer.py`        | 跌倒事件 metadata            |
| `OneEuroFilter`    | `src/analysis/smoothing/`       | 自適應低通濾波器             |
| `KeypointSmoother` | `src/analysis/smoothing/`       | 17 關鍵點平滑器              |

## CLI Entry Points

| Command          | Module                         | 用途               |
| ---------------- | ------------------------------ | ------------------ |
| `fds`            | `main:main`                    | 主程式（即時偵測） |
| `fds-test-video` | `scripts.test_with_video:main` | 影片測試           |
| `fds-cleanup`    | `scripts.cleanup_clips:main`   | 清理過期檔案       |

## Important Notes

- **Model files:** 首次執行自動下載 `yolo11n.pt` / `yolo11s-pose.pt`
- **Data directory:** `data/` 由 gitignore，包含 `fds.db`, `clips/`
- **Camera source:** 開發用影片測試，正式環境改 camera index 或 RTSP URL
- **LINE Bot:** 配置缺失時通知失敗但不會 crash Pipeline
- **Cleanup:** `lifecycle.clip_retention_days=7`，使用 `fds-cleanup` 執行

## Output

- 總是使用英文思考, 使用繁體中文進行輸出
