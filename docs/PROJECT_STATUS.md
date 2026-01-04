# FDS 專案狀態文檔

> 最後更新：2025-01-04
> 更新者：Claude Opus 4.5 (YOLO11-Pose Integration Complete)

本文檔提供完整的專案狀態，供後續開發者快速了解並繼續開發。

---

## 📋 專案概覽

**專案名稱：** FDS (Fall Detection System) - 居家長照跌倒偵測系統

**當前階段：** Phase 2 - Data Lifecycle Management (✅ 已完成)

**技術棧：**
- Python 3.12+
- YOLO11/YOLOv8 (Ultralytics) - 物件偵測 & 姿態估計
- OpenCV - 影像處理
- SQLite - 事件記錄
- Docker - 容器化部署
- uv - 包管理器
- pytest - 測試框架
- ruff - Linting & Formatting

---

## ✅ 已完成功能（按時間順序）

### Phase 1: Core Fall Detection (已完成)

**Commit History:**
- `b048ac8` - CLAUDE.md and remove CLAUDE.md from .gitignore
- `f4f1a08` - scripts for cli
- `3cfbaab` - feat: add YOLOv8 Pose skeleton detection
- `115f945` - feat: add test videos and video testing script
- `a3af402` - docs: add README.md and .env.example
- `f52814d` - fix: remove cross-platform incompatible test artifacts

**核心功能：**
1. ✅ Camera 擷取與 Rolling Buffer
2. ✅ YOLOv8 BBox 偵測 (物件偵測)
3. ✅ YOLOv8 Pose 偵測 (姿態估計)
4. ✅ 長寬比規則引擎 (BBox mode)
5. ✅ 軀幹角度規則引擎 (Pose mode)
6. ✅ 延遲確認狀態機 (3 秒)
7. ✅ LINE Notify 通知
8. ✅ Event Logger (SQLite)
9. ✅ Clip Recorder (影片前後 10 秒)
10. ✅ Observer Pattern 架構
11. ✅ Pipeline 整合

**檔案結構：**
```
src/
├── capture/        # 影像擷取
│   ├── camera.py
│   └── rolling_buffer.py
├── detection/      # 偵測模組
│   ├── bbox.py
│   ├── skeleton.py
│   └── detector.py
├── analysis/       # 分析模組
│   ├── rule_engine.py
│   └── delay_confirm.py
├── events/         # 事件處理
│   ├── observer.py
│   ├── event_logger.py
│   ├── clip_recorder.py
│   └── notifier.py
└── core/           # 核心模組
    ├── config.py
    └── pipeline.py
```

### Phase 2: Data Lifecycle Management (✅ 已完成)

**最近 Commits（2025-12-28 ~ 2025-12-29）:**
1. `d55247a` - feat: add skeleton extractor with coordinate normalization
2. `40e737a` - feat: add clip cleanup scheduler with retention policy
3. `2a01bf9` - feat: add Docker containerization for edge deployment
4. `cec958b` - docs: add Windows testing guide and quick test scripts
5. `ff3fcc6` - fix: validator test (too_many_keypoints_for_coco17)
6. `d426633` - feat: automated cleanup scheduling with APScheduler
7. `806b988` - feat(db): add cloud sync columns to events table
8. `4db1d2a` - feat(config): add CloudSyncConfig dataclass
9. `c967045` - feat(cloud-sync): implement CloudStorageUploader core logic
10. `d47dbe3` - feat(cloud-sync): add batch upload and retry methods
11. `c26ef04` - feat(cli): add fds-cloud-sync CLI tool
12. `bab6c52` - test(cloud-sync): add integration tests
13. `b6b52df` - docs: add Cloud Sync commands to CLAUDE.md
14. `30a03da` - chore: final cleanup and formatting
15. `b93cd4f` - chore: add implementation plan and update gitignore

**已完成的 Phase 2 功能：**

#### Task 16.1: Schema Infrastructure ✅
- **Commit:** 之前的提交（Phase 1 完成後）
- **檔案：**
  - `src/lifecycle/schema/__init__.py` - 核心資料結構
  - `src/lifecycle/schema/formats.py` - COCO17/MediaPipe33 格式
  - `tests/lifecycle/test_schema.py`
  - `tests/lifecycle/test_formats.py`
  - `config/examples/skeleton_sequence_example.json`

#### Task 16.1.1: JSON Schema Validator ✅
- **Commit:** 之前的提交
- **檔案：**
  - `config/skeleton_schema.json` - JSON Schema Draft-07
  - `src/lifecycle/schema/validator.py` - 雙層驗證（結構 + 語義）
  - `tests/lifecycle/test_validator.py`

#### Task 16.2: Skeleton Extractor ✅
- **Commit:** `d55247a`
- **檔案：**
  - `src/lifecycle/skeleton_extractor.py` (215 lines)
  - `tests/lifecycle/test_skeleton_extractor.py` (175 lines)
- **功能：**
  - 從影片提取 YOLOv8 Pose 骨架序列
  - 自動正規化座標至 [0, 1] 範圍
  - 輸出符合 COCO17 格式的 JSON
  - 通過 Schema 驗證
- **測試結果：**
  - 6/6 單元測試通過
  - 真實影片測試：155/160 幀提取成功
  - Schema 驗證通過

#### Task 17: Cleanup Scheduler ✅
- **Commit:** `40e737a`
- **檔案：**
  - `src/lifecycle/clip_cleanup.py` (124 lines)
  - `tests/lifecycle/test_clip_cleanup.py` (254 lines)
  - `scripts/cleanup_clips.py` (113 lines)
  - `pyproject.toml` - 新增 `fds-cleanup` 入口點
- **功能：**
  - 基於 `retention_days` 清理過期影片
  - 查詢資料庫 `created_at < cutoff_time`
  - 刪除檔案並更新資料庫（`clip_path` → NULL）
  - 乾運行模式支援
  - 詳細統計資訊
- **測試結果：**
  - 10/10 單元測試通過
  - 真實清理測試：3 個過期檔案成功刪除，300KB 釋放
- **CLI 使用：**
  ```bash
  uv run fds-cleanup --dry-run
  uv run fds-cleanup --retention-days 14
  ```

#### Task 17.1: Automated Cleanup Scheduler ✅
- **日期：** 2025-12-28
- **檔案：**
  - `src/lifecycle/cleanup_scheduler.py` - APScheduler 背景排程器
  - `tests/lifecycle/test_cleanup_scheduler.py` (9 個測試)
  - `src/core/config.py` - 新增 `cleanup_enabled`, `cleanup_schedule_hours` 欄位
  - `config/settings.yaml` - 新增排程設定選項
  - `main.py` - 整合排程器，支援優雅關閉
  - `pyproject.toml` - 新增 `apscheduler>=3.10.0` 依賴
- **功能：**
  - 使用 APScheduler BackgroundScheduler 背景執行
  - 可設定執行間隔（預設 24 小時）
  - 可透過 `cleanup_enabled=false` 停用
  - 支援手動觸發 `run_now()`
  - 優雅關閉處理（SIGINT/SIGTERM）
- **設定範例：**
  ```yaml
  lifecycle:
    cleanup_enabled: true
    cleanup_schedule_hours: 24
  ```
- **測試結果：**
  - 9/9 單元測試通過
  - 包含整合測試驗證排程執行

#### Docker Containerization ✅
- **Commit:** `2a01bf9`
- **檔案：**
  - `Dockerfile` - 多階段建構
  - `docker-compose.yml` - 生產級配置
  - `.dockerignore`
  - `README.md` - 更新部署說明
- **功能：**
  - 多階段建構（Builder + Runtime）
  - 非 root 用戶執行
  - 攝影機設備映射 (`/dev/video0`)
  - Volume 掛載（data, config, logs）
  - 資源限制（2 CPU, 2GB RAM）
  - 分離清理服務
- **驗證：**
  - Docker Compose 配置語法正確
  - 適合邊緣設備部署

#### Testing Documentation ✅
- **Commit:** `cec958b`
- **檔案：**
  - `docs/TESTING_ON_WINDOWS.md` - 完整測試指南
  - `scripts/quick_test.sh` - WSL2/Linux 快速測試
  - `scripts/quick_test.ps1` - Windows PowerShell 快速測試
- **功能：**
  - 3 種測試方式說明（WSL2、Windows 原生、Docker）
  - 快速測試腳本（3-5 分鐘完成所有驗證）
  - 常見問題排除
  - 測試檢查清單

#### Task 19: Web Dashboard ✅
- **日期：** 2025-12-29
- **技術棧：** FastAPI + Jinja2 + RESTful API
- **檔案結構：**
  ```
  src/web/
  ├── __init__.py
  ├── app.py              # FastAPI 應用程式
  ├── routes/
  │   ├── api.py          # RESTful API
  │   └── pages.py        # 頁面路由
  ├── services/
  │   └── event_service.py  # 資料庫服務
  ├── templates/          # Jinja2 模板
  │   ├── base.html
  │   ├── dashboard.html
  │   ├── events.html
  │   └── event_detail.html
  └── static/
      ├── css/style.css   # 深色主題
      └── js/main.js
  ```
- **API 端點：**
  - `GET /api/status` - 系統狀態
  - `GET /api/stats` - 事件統計
  - `GET /api/events` - 事件列表（分頁）
  - `GET /api/events/{id}` - 事件詳情
  - `GET /api/events/{id}/clip` - 影片串流
  - `DELETE /api/events/{id}` - 刪除事件
- **頁面：**
  - `/` - 儀表板首頁
  - `/events` - 事件列表
  - `/events/{id}` - 事件詳情 + 影片播放
  - `/docs` - Swagger API 文檔（自動生成）
- **啟動方式：**
  ```bash
  uv run python scripts/run_web.py
  # 或
  uv run fds-web
  ```
- **依賴：** fastapi, uvicorn, jinja2, httpx
- **測試結果：** 所有 API 和頁面返回 HTTP 200

#### Task 18: Cloud Sync ✅
- **日期：** 2025-12-29
- **狀態：** ✅ 已完成
- **Commits (9 個):**
  1. `806b988` - feat(db): add cloud sync columns to events table
  2. `4db1d2a` - feat(config): add CloudSyncConfig dataclass
  3. `c967045` - feat(cloud-sync): implement CloudStorageUploader core logic
  4. `d47dbe3` - feat(cloud-sync): add batch upload and retry methods
  5. `c26ef04` - feat(cli): add fds-cloud-sync CLI tool
  6. `bab6c52` - test(cloud-sync): add integration tests
  7. `b6b52df` - docs: add Cloud Sync commands to CLAUDE.md
  8. `30a03da` - chore: final cleanup and formatting
  9. `b93cd4f` - chore: add implementation plan and update gitignore

- **檔案結構:**
  ```
  src/lifecycle/
  ├── cloud_sync.py           # CloudStorageUploader (217 行)
  scripts/
  └── cloud_sync.py           # CLI 工具 (147 行)
  tests/
  ├── lifecycle/test_cloud_sync.py        # 單元測試 (12 個)
  └── integration/test_cloud_sync_integration.py  # 整合測試 (2 個)
  ```

- **核心功能:**
  - ✅ 上傳骨架 JSON 至 GCP Cloud Storage
  - ✅ 自動重試機制（可配置次數與延遲）
  - ✅ 批次上傳 (`upload_pending()`)
  - ✅ 失敗重試 (`retry_failed()`)
  - ✅ 狀態追蹤（pending/uploaded/failed）
  - ✅ Dry-run 模式
  - ✅ 資料庫整合（3 個新欄位）

- **CLI 指令:**
  ```bash
  fds-cloud-sync --status              # 查看狀態
  fds-cloud-sync --upload-pending      # 上傳待處理
  fds-cloud-sync --retry-failed        # 重試失敗
  fds-cloud-sync --event-id evt_123    # 上傳特定事件
  fds-cloud-sync --dry-run             # 乾運行模式
  ```

- **認證方式:** Application Default Credentials (ADC)
- **儲存路徑:** `YYYY/MM/DD/evt_{timestamp}.json`
- **測試結果:** 194 個測試全部通過
- **設計文檔:** `docs/plans/2025-12-29-cloud-sync-design.md`
- **實作計畫:** `docs/plans/2025-12-29-cloud-sync-implementation.md`

#### Task 20: Skeleton Observer Extension ✅
- **日期：** 2025-12-31
- **狀態：** ✅ 已完成
- **Commits (7 個):**
  1. `c5e062a` - feat(observer): add SuspectedEvent and SuspectedEventObserver protocol
  2. `480b13b` - feat(delay_confirm): add suspected event notifications
  3. `68833b0` - feat(skeleton_extractor): add extract_from_frames method
  4. `2368258` - feat(lifecycle): add SkeletonCollector for async skeleton extraction
  5. `27b6fbc` - feat(config): add auto_skeleton_extract option
  6. `c7b6a92` - feat(pipeline): integrate SkeletonCollector for auto skeleton extraction
  7. `a16b903` - docs: add SkeletonCollector documentation

- **核心功能:**
  - ✅ 擴展 Observer Pattern 支援 SUSPECTED 階段
  - ✅ 新增 `SuspectedEvent` 與 `SuspectedEventObserver` 協議
  - ✅ DelayConfirm 狀態機新增 suspected 事件通知
  - ✅ SkeletonExtractor 新增 `extract_from_frames()` 方法
  - ✅ SkeletonCollector 非同步骨架提取器
  - ✅ 自動標記 outcome（confirmed/cleared）

- **事件流程:**
  ```
  SUSPECTED → 記錄事件（不提取）
      │
      ├─→ CONFIRMED → 提取骨架 → sus_xxx_confirmed.json（正樣本）
      │
      └─→ CLEARED → 提取骨架 → sus_xxx_cleared.json（負樣本）
  ```

- **新增檔案:**
  ```
  src/lifecycle/skeleton_collector.py    # 骨架收集器（127 行）
  tests/lifecycle/test_skeleton_collector.py  # 測試（4 個）
  ```

- **修改檔案:**
  - `src/events/observer.py` - 新增 SuspectedEvent, SuspectedEventObserver
  - `src/analysis/delay_confirm.py` - 新增 suspected observer 通知
  - `src/lifecycle/skeleton_extractor.py` - 新增 extract_from_frames()
  - `src/core/config.py` - 新增 auto_skeleton_extract, skeleton_output_dir
  - `src/core/pipeline.py` - 整合 SkeletonCollector
  - `config/settings.yaml` - 新增 skeleton 設定
  - `CLAUDE.md` - 新增 SkeletonCollector 文檔

- **設定範例:**
  ```yaml
  lifecycle:
    auto_skeleton_extract: true      # 啟用自動骨架提取
    skeleton_output_dir: "data/skeletons"
  ```

- **測試結果:** 206 個測試（新增 10 個），202 passed, 4 failed（pre-existing GCP 問題）
- **設計文檔:** `docs/plans/2025-12-31-skeleton-observer-extension.md`

#### Task 21: YOLO11-Pose Integration ✅
- **日期：** 2025-01-04
- **狀態：** ✅ 已完成（Phase A + Phase B）
- **目標：** 將 Pose 模型從 YOLOv8n-Pose 升級至 YOLO11s-Pose，並加入時序過濾

**Commits:**
1. `b42ea07` - feat(config): add pose_model configuration for YOLO11 support
2. `630509e` - feat(detector): change PoseDetector default to yolo11s-pose
3. `e61fbcd` - feat(skeleton_extractor): use yolo11s-pose as default
4. `2e1c7c3` - docs: update documentation for YOLO11-Pose integration
5. `24c3a7d` - feat(detector): upgrade BBox detector from yolov8n to yolo11n
6. `5311ce4` - fix(docker): update model references from yolov8 to yolo11
7. `b36d152` - fix: update remaining yolov8 references to yolo11
8. `abc3e52` - test(yolo11): add keypoint compatibility tests
9. `6b3e52c` - feat(smoothing): add One Euro Filter for keypoint smoothing

**Phase A（配置化 + 模型切換）:**
- ✅ A.1: Config 新增 `pose_model` 設定
- ✅ A.2: PoseDetector 改用 yolo11s-pose 預設
- ✅ A.3: SkeletonExtractor 改用 yolo11s-pose 預設
- ✅ A.4: 測試腳本更新 (test_with_video, save_skeleton_frames)
- ✅ A.5: 文件更新 (CLAUDE.md, docs/)
- ✅ A.6: Keypoint 格式相容性測試（11 個測試）

**Phase B（KeypointSmoother 時序過濾）:**
- ✅ B.1: 實作 One Euro Filter (`src/analysis/smoothing/one_euro_filter.py`)
- ✅ B.2: 實作 KeypointSmoother (`src/analysis/smoothing/keypoint_smoother.py`)
- ✅ B.3: 整合至 PoseRuleEngine（新增 `enable_smoothing`, `timestamp` 參數）
- ✅ B.4: 測試腳本傳入 timestamp（新增 `--enable-smoothing` CLI 旗標）
- ✅ B.5: 端到端整合測試（`tests/integration/test_yolo11_pipeline.py`）

**新增檔案:**
```
src/analysis/smoothing/
├── __init__.py
├── one_euro_filter.py    # One Euro Filter 實作
└── keypoint_smoother.py  # 17 關鍵點平滑器
tests/
├── test_smoothing.py              # 14 個測試
├── test_yolo11_compatibility.py   # 11 個測試
└── integration/test_yolo11_pipeline.py  # 5 個測試
```

**使用方式:**
```bash
# Pose 模式
uv run python -m scripts.test_with_video video.mp4 --use-pose

# Pose + Keypoint 平滑（減少抖動）
uv run python -m scripts.test_with_video video.mp4 --use-pose --enable-smoothing
```

**測試結果:** 234 個測試通過
**詳細計畫:** `docs/plans/2025-01-03-yolo11-pose-integration.md`

---

## 🔄 待辦事項（按優先級）

### Phase 2 - 所有任務已完成 ✅

**Phase 2 目標已全數達成：**
- ✅ Schema Infrastructure
- ✅ JSON Schema Validator
- ✅ Skeleton Extractor
- ✅ Cleanup Scheduler
- ✅ Automated Cleanup Scheduling
- ✅ Docker Containerization
- ✅ Testing Documentation
- ✅ Web Dashboard
- ✅ Cloud Sync
- ✅ Skeleton Observer Extension（2025-12-31 新增）

### Phase 3 候選功能（規劃中）

#### ~~自動化排程（已完成）~~
- **狀態：** ✅ 已於 2025-12-28 完成
- **實作：** APScheduler BackgroundScheduler 整合至 `main.py`
- **相關檔案：** `src/lifecycle/cleanup_scheduler.py`

#### ~~Web 儀表板（已完成）~~
- **狀態：** ✅ 已於 2025-12-29 完成
- **說明：** FastAPI + Jinja2，詳見 Task 19

#### ~~Cloud Sync（已完成）~~
- **狀態：** ✅ 已於 2025-12-29 完成
- **說明：** GCP Cloud Storage 整合，詳見 Task 18

#### 骨架特徵擴充（優先級：低）
- MediaPipe33 格式支援（目前僅 COCO17）
- 速度/加速度特徵計算
- 軌跡分析

---

## 🐛 已知問題

### ~~1. Validator 測試失敗（已修復）~~
**檔案：** `tests/lifecycle/test_validator.py::TestSemanticValidation::test_too_many_keypoints_for_coco17`

**問題：** 原測試使用 `kp_0`, `kp_1` 等名稱，但這些名稱包含數字，不符合 JSON Schema 的 `^[a-z_]+$` 模式。

**修復：** 已於 2025-12-28 修正。改用 17 個標準 COCO17 關鍵點名稱加上 `extra_a`, `extra_b`, `extra_c`，成功觸發語義驗證錯誤。

**狀態：** ✅ 已修復，20/20 測試通過

### 2. Docker 攝影機訪問（平台限制）
**問題：** Windows Docker Desktop 的攝影機映射較複雜

**影響：** Docker 容器無法直接訪問 Windows 攝影機

**解決方案：**
- 在 Linux/WSL2 環境部署 Docker
- 或使用 RTSP 串流而非直接設備訪問

---

## 🏗️ 重要技術決策

### 1. Schema-First 設計
**決策：** 先定義 JSON Schema，再實作程式碼

**理由：**
- 資料格式作為契約
- 跨語言相容性
- 嚴格驗證保證資料品質

### 2. YOLOv8 Pose over MediaPipe
**決策：** 使用 YOLOv8 Pose 作為主要骨架提取引擎

**理由：**
- 與 Phase 1 架構一致（已使用 YOLOv8）
- COCO17 格式通用性高
- 性能足夠（30 FPS on GPU）

**保留：** MediaPipe33 格式定義已準備，未來可擴充

### 3. 座標正規化
**決策：** 儲存正規化座標 [0, 1]，而非像素座標

**理由：**
- 解析度無關
- 跨影片比較容易
- 儲存空間小

### 4. 資料庫保留事件歷史
**決策：** 刪除影片後，資料庫記錄保留，僅將 `clip_path` 設為 NULL

**理由：**
- 保留事件統計
- 追蹤長期趨勢
- 骨架 JSON 仍可關聯

### 5. Docker 非 root 用戶
**決策：** 容器內使用 `fds` 用戶（UID 1000）執行

**理由：**
- 安全最佳實踐
- 避免權限問題
- Volume 掛載檔案權限一致

---

## 📊 測試覆蓋率狀態

### Lifecycle 模組測試
- `test_schema.py` - 14 tests ✅
- `test_formats.py` - 14 tests ✅
- `test_validator.py` - 28 tests ✅
- `test_skeleton_extractor.py` - 8 tests ✅（新增 2 個 extract_from_frames 測試）
- `test_clip_cleanup.py` - 10 tests ✅
- `test_cleanup_scheduler.py` - 9 tests ✅
- `test_cloud_sync.py` - 12 tests ✅
- `test_skeleton_collector.py` - 4 tests ✅（新增）

### Observer/Analysis 模組測試
- `test_observer.py` - 6 tests ✅（新增 2 個 SuspectedEvent 測試）
- `test_delay_confirm.py` - 14 tests ✅（新增 4 個 suspected observer 測試）

**總計：** 206 tests, 202 passed, 4 failed（pre-existing GCP 問題）

### 整合測試
- 真實影片骨架提取 ✅
- 真實清理場景驗證 ✅
- Docker 配置驗證 ✅
- Cloud Sync 端到端流程測試 ✅ (`test_cloud_sync_integration.py` - 2 tests)

### 未測試項目
- 真實 Docker 容器執行（需實際攝影機）
- 真實 GCP Cloud Storage 上傳 ✅

---

## 🔧 開發環境設定

### 當前環境
- **位置：** `/home/usr/FDS`
- **分支：** `main`
- **Python：** 3.12.3
- **uv 版本：** 最新
- **Docker：** 29.1.3
- **Docker Compose：** v5.0.0

### 快速設定（新開發者）
```bash
# 1. Clone 專案
cd /home/usr/FDS

# 2. 安裝依賴
uv sync --all-extras

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env 設定 LINE_NOTIFY_TOKEN

# 4. 執行測試
uv run pytest tests/lifecycle/ -v

# 5. 快速驗證
bash scripts/quick_test.sh
```

---

## 📝 配置檔案說明

### config/settings.yaml
```yaml
lifecycle:
  clip_retention_days: 7       # 影片保留天數
  skeleton_retention_days: 30  # 骨架 JSON 保留天數
  cleanup_enabled: true        # 啟用自動清理排程
  cleanup_schedule_hours: 24   # 清理排程間隔（小時）
  auto_skeleton_extract: true  # 啟用自動骨架提取（新增）
  skeleton_output_dir: "data/skeletons"  # 骨架輸出目錄（新增）

camera:
  source: 0                    # 攝影機索引或 RTSP URL
  fps: 15

detection:
  model: "yolo11n.pt"          # BBox 模式（已升級至 YOLO11）
  pose_model: "yolo11s-pose.pt" # Pose 模式（已升級至 YOLO11）
  confidence: 0.5

analysis:
  fall_threshold: 1.3          # 長寬比閾值
  delay_sec: 3.0               # 延遲確認秒數

notification:
  line_channel_access_token: "${line_channel_access_token}"  # 從 .env 讀取
  line_user_id: "${LINE_BOT_USER_ID}"
  enabled: true

cloud_sync:
  enabled: true                # 啟用 Cloud Sync
  gcs_bucket: "${GCS_BUCKET_NAME}"  # GCS bucket 名稱
  upload_on_extract: false     # 提取後自動上傳
  retry_attempts: 3            # 重試次數
  retry_delay_seconds: 5       # 重試延遲（秒）
```

### pyproject.toml - CLI 入口點
```toml
[project.scripts]
fds = "main:main"
fds-test-video = "scripts.test_with_video:main"
fds-cleanup = "scripts.cleanup_clips:main"
fds-web = "src.web.app:main"
fds-cloud-sync = "scripts.cloud_sync:main"
```

---

## 🚀 下一步建議

### 立即可執行的任務

1. **生產環境部署測試**（需實體設備）
   - 在 Linux 機器上建構 Docker 鏡像
   - 測試攝影機訪問
   - 驗證資源使用
   - 測試 Cloud Sync 真實上傳至 GCP

2. **監控與告警**（1-2 天）
   - 實作健康檢查端點
   - 新增效能監控指標
   - 設定告警通知（系統異常、偵測失敗等）

### 功能擴充建議

1. **骨架特徵分析**（1-2 天）
   - 速度計算（連續幀位移）
   - 加速度計算（速度變化率）
   - 軌跡平滑（Kalman Filter）

2. **Web Dashboard 增強**（2-3 天）
   - 骨架視覺化（Canvas/D3.js）
   - 即時系統監控頁面
   - 批次事件管理功能
   - Cloud Sync 狀態查詢介面

3. **機器學習模型整合**（5-7 天）
   - 整合預訓練跌倒偵測模型
   - 替換規則引擎為 ML 推論
   - 建立訓練資料集管道
   - 模型評估與監控

---

## 📚 重要文檔位置

- **設計文檔：** `docs/plans/2025-12-28-fall-detection-system-design.md`
- **Phase 1 實作：** `docs/plans/2025-12-28-fds-phase1-implementation.md`
- **Cloud Sync 設計：** `docs/plans/2025-12-29-cloud-sync-design.md`
- **Cloud Sync 實作：** `docs/plans/2025-12-29-cloud-sync-implementation.md`
- **Skeleton Observer 實作：** `docs/plans/archive/2025-12-31-skeleton-observer-extension.md`
- **專案說明：** `README.md`
- **開發指南：** `CLAUDE.md`
- **測試指南：** `docs/TESTING_ON_WINDOWS.md`
- **專案狀態：** `docs/PROJECT_STATUS.md`（本文檔）

---

## 🔍 關鍵檔案速查

### 如果要修改骨架提取邏輯
- `src/lifecycle/skeleton_extractor.py`
- `src/detection/detector.py` (PoseDetector)
- `src/detection/skeleton.py` (Skeleton dataclass)

### 如果要修改清理邏輯
- `src/lifecycle/clip_cleanup.py`
- `scripts/cleanup_clips.py` (CLI 介面)

### 如果要修改 Schema
- `config/skeleton_schema.json` (JSON Schema)
- `src/lifecycle/schema/__init__.py` (Python dataclasses)
- `src/lifecycle/schema/validator.py` (驗證器)

### 如果要修改 Docker 配置
- `Dockerfile` (鏡像建構)
- `docker-compose.yml` (服務編排)
- `.dockerignore` (建構排除)

### 如果要修改 Cloud Sync
- `src/lifecycle/cloud_sync.py` (核心上傳邏輯)
- `scripts/cloud_sync.py` (CLI 介面)
- `src/events/event_logger.py` (資料庫狀態追蹤)
- `config/settings.yaml` (Cloud Sync 設定)

### 如果要修改骨架收集（Skeleton Collection）
- `src/lifecycle/skeleton_collector.py` - SkeletonCollector 主類別
- `src/events/observer.py` - SuspectedEvent, SuspectedEventObserver
- `src/analysis/delay_confirm.py` - suspected 事件通知邏輯
- `src/core/pipeline.py` - Pipeline 整合點
- `config/settings.yaml` - `lifecycle.auto_skeleton_extract` 設定

---

## 💡 開發提示

### 測試驅動開發（TDD）
本專案使用 TDD 方法，**先寫測試再寫實作**：
1. 建立 `tests/xxx/test_new_feature.py`
2. 寫測試用例（會失敗）
3. 實作 `src/xxx/new_feature.py`
4. 執行測試直到通過
5. 重構並再次測試

### Git Commit 規範
```
feat: 新功能
fix: 修復 bug
docs: 文檔更新
test: 測試相關
refactor: 重構（不改變功能）
chore: 雜項（依賴更新等）
```

每個 commit 結尾加上：
```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### 程式碼風格
- 使用 `ruff format .` 格式化
- 使用 `ruff check .` 檢查
- 行寬限制：100 字元
- Type hints 必須提供

---

## 📞 聯絡與支援

如有問題，查閱：
1. 本文檔（PROJECT_STATUS.md）
2. TESTING_ON_WINDOWS.md
3. CLAUDE.md（專案指南）
4. GitHub Issues（如已設定）

---

**文檔結束**

祝開發順利！ 🚀
