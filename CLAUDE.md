# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fall Detection System (FDS) - 居家長照跌倒偵測系統。使用 YOLOv8 進行人體/姿態偵測，透過規則引擎判斷跌倒，並觸發 LINE 通知、影片錄製、事件記錄。

**技術棧:** Python 3.12+, uv, YOLOv8 (Ultralytics), OpenCV, SQLite, ruff, pytest

## Development Commands

### 本地開發模式

**依賴管理:**
```bash
uv sync                    # 安裝/同步依賴
uv sync --all-extras       # 包含 dev 依賴
uv add <package>           # 新增依賴
uv remove <package>        # 移除依賴
```

**執行主程式:**
```bash
uv run python main.py      # 執行即時偵測（使用 camera.source）
fds                        # 安裝後可用的 CLI 入口點
```

**Web Dashboard:**
```bash
uv run python -m src.web.app              # 啟動 Web 儀表板
fds-web                                   # 安裝後可用的 CLI 入口點
# 啟動後訪問 http://localhost:8000
```

**影片測試:**
```bash
# BBox 模式（長寬比規則）
uv run python -m scripts.test_with_video <video_path>
fds-test-video <video_path>

# Pose 模式（骨架角度規則）
uv run python -m scripts.test_with_video --use-pose <video_path>

# 無視窗模式（CLI only）
uv run python -m scripts.test_with_video --no-window <video_path>
```

**清理過期檔案:**
```bash
uv run python -m scripts.cleanup_clips    # 刪除過期影片/骨架檔案
fds-cleanup                               # 安裝後可用的 CLI 入口點
```

**測試:**
```bash
uv run pytest                                    # 執行所有測試
uv run pytest -v                                 # verbose 模式
uv run pytest --cov=src --cov-report=term-missing # 覆蓋率報告
uv run pytest tests/test_detector.py -v          # 單一模組
uv run pytest tests/integration/ -v              # 整合測試
```

**程式碼品質:**
```bash
uv run ruff check .         # Lint 檢查
uv run ruff check . --fix   # 自動修復
uv run ruff format .        # 格式化
```

### Docker 部署模式（推薦）

**完整服務啟動:**
```bash
docker compose up -d                      # 啟動全部服務（fds + fds-web）
docker compose up -d fds                  # 只啟動偵測服務
docker compose up -d fds-web              # 只啟動 Web Dashboard
docker compose logs -f fds                # 查看偵測服務日誌
docker compose logs -f fds-web            # 查看 Web 服務日誌
docker compose down                       # 停止全部服務
docker compose restart fds                # 重啟偵測服務
```

**清理與維護:**
```bash
docker compose --profile cleanup run --rm fds-cleanup  # 手動執行清理
docker compose build                                   # 重新建置映像（程式碼改動後）
docker compose build --no-cache                        # 強制完整重建
```

**資料持久化位置:**
- `./data/fds.db` - 事件資料庫
- `./data/clips/` - 影片片段
- `./data/skeletons/` - 骨架序列
- `./logs/` - 應用程式日誌

**切換攝影機來源:**
1. 真實攝影機：取消 `docker-compose.yml` 中 `devices` 註解，並修改 `config/settings.yaml` 的 `camera.source` 為 `0`
2. 測試影片：保持 `devices` 註解，修改 `camera.source` 為容器內路徑（例如：`/app/tests/fixtures/videos/fall-01-cam0.mp4`）

## Core Architecture

### Pipeline Flow (src/core/pipeline.py)

```
Camera → Detector → RuleEngine → DelayConfirm → Observers (EventLogger, LineNotifier, ClipRecorder)
           ↓            ↓              ↓
      YOLO detect   is_fallen?   State Machine
                                (NORMAL → SUSPECTED → CONFIRMED)
```

**關鍵流程:**
1. `Camera.read()` 擷取影像幀
2. `Detector.detect()` 執行 YOLO 推論 → 回傳 BBox 或 Skeleton
3. `RuleEngine.is_fallen()` 套用規則（長寬比 < 1.3 或軀幹角度 < 60°）
4. `DelayConfirm.update()` 狀態機判斷（3 秒延遲確認）
5. 狀態變化時觸發 Observer Pattern 通知所有訂閱者
6. `RollingBuffer` 持續保存 10 秒環形緩衝，跌倒確認時提取前後 5 秒影片

### Detection Modes

**1. BBox Mode (預設):**
- Model: `yolov8n.pt` (物件偵測)
- Rule: `aspect_ratio = height / width < 1.3`
- Classes: `[0]` (person only)
- Output: `BBox(x, y, width, height, confidence, aspect_ratio)`

**2. Pose Mode (Phase 2):**
- Model: `yolov8n-pose.pt` (姿態估計)
- Rule: `torso_angle < 60°` (軀幹相對水平的角度)
- Output: `Skeleton(keypoints[17], torso_angle, confidence)`
- Keypoints: COCO 17-point format (shoulders, hips, knees, ankles, etc.)

在 `scripts/test_with_video.py` 中可透過 `--use-pose` 切換模式。

### State Machine (src/analysis/delay_confirm.py)

**States:**
- `NORMAL`: 正常站立/走動
- `SUSPECTED`: 偵測到疑似跌倒（長寬比 < 1.3 或角度 < 60°）
- `CONFIRMED`: 持續 `delay_sec` (預設 3 秒) 後確認跌倒

**Transitions:**
```
NORMAL → is_fallen=True → SUSPECTED
SUSPECTED → is_fallen=False → NORMAL (reset)
SUSPECTED → elapsed >= 3s → CONFIRMED (trigger observers)
CONFIRMED → is_fallen=False → NORMAL (recovery event)
CONFIRMED → is_fallen=True + elapsed >= 120s → re-notify (重複通知)
```

**Event Window Logic:**
- `same_event_window=60s`: 60 秒內視為同一跌倒事件，不建立新 event_id
- `re_notify_interval=120s`: 持續躺著時每 2 分鐘重複通知

### Observer Pattern (src/events/)

所有事件觸發透過 `FallEventObserver` 介面：

```python
class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...
```

**Observers:**
- `EventLogger`: 寫入 SQLite (`data/fds.db`)，記錄 event_id, timestamp, bbox
- `LineNotifier`: 發送 LINE Notify 推播（含 event_id, notification_count）
- `ClipRecorder`: 從 RollingBuffer 提取影片並存檔至 `data/clips/`
- `Pipeline` 自己也是 Observer，用於更新 clip_path

### Configuration (src/core/config.py)

**載入順序:**
1. 讀取 `config/settings.yaml`
2. 使用 `_substitute_env_vars()` 替換 `${ENV_VAR}` 語法
3. 建立強型別 dataclass (`Config`, `CameraConfig`, ...)

**環境變數處理:**
- `.env` 中定義 `LINE_NOTIFY_TOKEN`
- `settings.yaml` 中使用 `line_token: "${LINE_NOTIFY_TOKEN}"` 引用
- 支援任意深度的嵌套字典替換

**關鍵參數 (config/settings.yaml):**
- `camera.source`: `0` (USB camera) 或 `"rtsp://..."` (IP camera)
- `analysis.fall_threshold`: 1.3 (長寬比閾值)
- `analysis.delay_sec`: 3.0 (延遲確認秒數)
- `recording.buffer_seconds`: 10 (環形緩衝總秒數)
- `recording.clip_before_sec/after_sec`: 各 5 秒（跌倒前後錄影範圍）

## Testing Strategy

**單元測試:** 每個模組獨立測試（detector, rule_engine, delay_confirm, rolling_buffer...）

**整合測試:** `tests/integration/test_full_pipeline.py` 模擬完整流程

**影片測試:** `scripts/test_with_video.py` 使用真實影片驗證，支援視覺化 bbox/skeleton

## Data Structures

**BBox (src/detection/bbox.py):**
```python
@dataclass
class BBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    aspect_ratio: float  # height / width
```

**Skeleton (src/detection/skeleton.py):**
```python
@dataclass
class Skeleton:
    keypoints: np.ndarray  # shape (17, 3) - [x, y, visibility]
    confidence: float
    torso_angle: float     # 軀幹相對水平的角度（計算自 shoulders/hips）
```

**FrameData (src/capture/rolling_buffer.py):**
```python
@dataclass
class FrameData:
    timestamp: float
    frame: np.ndarray
    bbox: tuple[int, int, int, int] | None
```

## Important Notes

- **Camera source:** 開發時使用影片測試，正式環境改為 camera index 或 RTSP URL
- **Model files:** 首次執行會自動下載 `yolov8n.pt` / `yolov8n-pose.pt`
- **Data directory:** `data/` 由 gitignore，包含 `fds.db` (SQLite) 和 `clips/` (影片)
- **Lifecycle:** `lifecycle.clip_retention_days=7` 表示影片保留 7 天（需實作清理邏輯）
- **LINE Token:** 必須在 `.env` 設定 `LINE_NOTIFY_TOKEN`，否則通知會失敗（但不會 crash）

## CLI Entry Points (pyproject.toml)

```toml
[project.scripts]
fds = "main:main"                             # 主程式（即時偵測）
fds-test-video = "scripts.test_with_video:main"  # 影片測試工具
fds-cleanup = "scripts.cleanup_clips:main"      # 清理過期檔案
fds-web = "src.web.app:main"                   # Web Dashboard
```

安裝後可直接執行這些 CLI 指令。

## Web Dashboard Architecture (src/web/)

FDS 提供 FastAPI 網頁儀表板，用於查詢歷史事件和影片播放。

**核心元件:**
- `src/web/app.py` - FastAPI 應用程式進入點
- `src/web/routes/api.py` - RESTful API 路由（`/api/*`）
- `src/web/routes/pages.py` - 頁面路由（Jinja2 模板）
- `src/web/services/event_service.py` - 事件查詢服務（封裝資料庫存取）
- `src/web/static/` - 靜態檔案（CSS, JS）
- `src/web/templates/` - Jinja2 模板

**API 端點:**
- `GET /` - 首頁（事件列表）
- `GET /api/events` - 查詢事件（支援分頁、篩選）
- `GET /api/events/{event_id}` - 取得單一事件詳情
- `GET /api/status` - 健康檢查

**Docker 部署注意事項:**
- Web Dashboard 使用獨立的輕量化 Image (`Dockerfile.web`)
- 預設監聽 port 8000
- 透過 volume 掛載共享 `data/` 目錄存取資料庫和影片


## Output
- 總是使用英文思考, 使用繁體中文進行輸出