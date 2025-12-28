# FDS 專案狀態文檔

> 最後更新：2025-12-28
> 更新者：Claude Sonnet 4.5

本文檔提供完整的專案狀態，供後續開發者快速了解並繼續開發。

---

## 📋 專案概覽

**專案名稱：** FDS (Fall Detection System) - 居家長照跌倒偵測系統

**當前階段：** Phase 2 - Data Lifecycle Management (進行中)

**技術棧：**
- Python 3.12+
- YOLOv8 (Ultralytics) - 物件偵測 & 姿態估計
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

### Phase 2: Data Lifecycle Management (進行中)

**最近 Commits（本次 session）:**
1. `d55247a` - feat: add skeleton extractor with coordinate normalization
2. `40e737a` - feat: add clip cleanup scheduler with retention policy
3. `2a01bf9` - feat: add Docker containerization for edge deployment
4. `cec958b` - docs: add Windows testing guide and quick test scripts

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

---

## 🔄 待辦事項（按優先級）

### Phase 2 剩餘任務

#### Task 18: Cloud Sync (可選，優先級：低)
- **狀態：** 未開始
- **說明：** 骨架 JSON 同步至雲端儲存
- **預計檔案：**
  - `src/lifecycle/cloud_sync.py`
  - `tests/lifecycle/test_cloud_sync.py`
- **技術選項：**
  - AWS S3 / Google Cloud Storage / Azure Blob
  - 僅上傳骨架 JSON（隱私保護）
  - 可選壓縮（gzip）

### Phase 2+ 未來功能

#### 自動化排程（優先級：中）
- **需求：** 整合 Cleanup Scheduler 至主程式
- **選項：**
  1. 定時觸發（APScheduler）
  2. Cron job（推薦）
  3. Systemd timer

#### 骨架特徵擴充（優先級：低）
- MediaPipe33 格式支援（目前僅 COCO17）
- 速度/加速度特徵計算
- 軌跡分析

#### Web 儀表板（優先級：低）
- 事件查詢介面
- 骨架視覺化
- 統計圖表

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
- `test_validator.py` - 28 tests (27 ✅, 1 ⚠️)
- `test_skeleton_extractor.py` - 6 tests ✅
- `test_clip_cleanup.py` - 10 tests ✅

**總計：** 72 tests, 71 passed, 1 known issue

### 整合測試
- 真實影片骨架提取 ✅
- 真實清理場景驗證 ✅
- Docker 配置驗證 ✅

### 未測試項目
- Cloud Sync（未實作）
- 真實 Docker 容器執行（需實際攝影機）

---

## 🔧 開發環境設定

### 當前環境
- **位置：** `/home/kionc9986/Projects/FDS`
- **分支：** `main`
- **Python：** 3.12.3
- **uv 版本：** 最新
- **Docker：** 29.1.3
- **Docker Compose：** v5.0.0

### 快速設定（新開發者）
```bash
# 1. Clone 專案
cd /home/kionc9986/Projects/FDS

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
  clip_retention_days: 7      # 影片保留天數
  skeleton_retention_days: 30  # 骨架 JSON 保留天數（未使用）

camera:
  source: 0                    # 攝影機索引或 RTSP URL
  fps: 15

detection:
  model: "yolov8n.pt"          # BBox 模式
  confidence: 0.5

analysis:
  fall_threshold: 1.3          # 長寬比閾值
  delay_sec: 3.0              # 延遲確認秒數

notification:
  line_token: "${LINE_NOTIFY_TOKEN}"  # 從 .env 讀取
  enabled: true
```

### pyproject.toml - CLI 入口點
```toml
[project.scripts]
fds = "main:main"
fds-test-video = "scripts.test_with_video:main"
fds-cleanup = "scripts.cleanup_clips:main"
```

---

## 🚀 下一步建議

### 立即可執行的任務

1. **修復 Validator 測試**（10 分鐘）
   - 修改 `test_too_many_keypoints_for_coco17` 測試用例
   - 使用標準 keypoint 名稱但超過 17 個

2. **實作自動化清理排程**（30 分鐘）
   - 選項 A：整合 APScheduler 至 main.py
   - 選項 B：提供 crontab 設定範例

3. **Docker 實際測試**（需實體設備）
   - 在樹莓派或 Linux 機器上建構鏡像
   - 測試攝影機訪問
   - 驗證資源使用

### 功能擴充建議

1. **骨架特徵分析**（1-2 天）
   - 速度計算（連續幀位移）
   - 加速度計算（速度變化率）
   - 軌跡平滑（Kalman Filter）

2. **Cloud Sync 實作**（2-3 天）
   - 選擇雲端儲存服務
   - 實作上傳邏輯
   - 失敗重試機制
   - 上傳進度追蹤

3. **監控儀表板**（3-5 天）
   - Flask/FastAPI Web 介面
   - 事件列表與查詢
   - 骨架視覺化（Canvas/D3.js）
   - 系統狀態監控

---

## 📚 重要文檔位置

- **設計文檔：** `docs/plans/2025-12-28-fall-detection-system-design.md`
- **Phase 1 實作：** `docs/plans/2025-12-28-fds-phase1-implementation.md`
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
