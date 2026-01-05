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
uv run pytest -m "not slow"                        # 跳過慢測試
uv run pytest --cov=src --cov-report=term-missing  # 覆蓋率

# 程式碼品質 (line-length=100)
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

| Mode        | Model             | Rule                 | Config                                        |
| ----------- | ----------------- | -------------------- | --------------------------------------------- |
| BBox (預設) | `yolo11n.pt`      | `aspect_ratio < 1.3` | `detection.use_pose: false`                   |
| Pose        | `yolo11s-pose.pt` | `torso_angle < 60°`  | `detection.use_pose: true`                    |
| Pose+平滑   | `yolo11s-pose.pt` | `torso_angle < 60°`  | `detection.use_pose: true, enable_smoothing: true` |

Pose 模式啟用 **One Euro Filter** 可減少關鍵點抖動誤判（`smoothing_min_cutoff` 越低越平滑，`smoothing_beta` 越高對快速動作反應越快）。

### State Machine (src/analysis/delay_confirm.py)

```
NORMAL → is_fallen=True → SUSPECTED
SUSPECTED → is_fallen=False → NORMAL (reset)
SUSPECTED → elapsed >= 3s → CONFIRMED (trigger observers)
CONFIRMED → is_fallen=False → NORMAL (recovery event)
CONFIRMED → is_fallen=True + elapsed >= 120s → re-notify
```

### Observer Pattern (src/events/observer.py)

```python
class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...
```

**內建 Observers:** `EventLogger`, `LineNotifier`, `Pipeline`（負責觸發 ClipRecorder）

### Configuration

載入順序: `config/settings.yaml` → 環境變數替換 `${VAR}` → 強型別 dataclass (`src/core/config.py`)

環境變數: `.env` 定義 `LINE_BOT_CHANNEL_ACCESS_TOKEN`, `LINE_BOT_USER_ID`

## Important Notes

- **Model files:** 首次執行自動下載 `yolo11n.pt` / `yolo11s-pose.pt`
- **Data directory:** `data/` 由 gitignore，包含 `fds.db`, `clips/`
- **Camera source:** 開發用影片測試，正式環境改 camera index 或 RTSP URL
- **LINE Bot:** 配置缺失時通知失敗但不會 crash Pipeline
- **Cleanup:** `lifecycle.clip_retention_days=7`，使用 `fds-cleanup` 執行

## Output

- 總是使用英文思考, 使用繁體中文進行輸出
