# FDS Cloud Sync 設計文檔

> **建立日期：** 2025-12-29
> **狀態：** 設計完成，待實作
> **目標：** Phase 2 收尾 - 骨架 JSON 雲端備份

---

## 1. 專案概述

### 目標

實作 Cloud Sync 功能，將本地提取的骨架 JSON 檔案上傳至 GCP Cloud Storage，實現：
- 隱私保護的資料備份（骨架已脫敏，無人臉/身份資訊）
- 長期資料保存（用於未來 ML 訓練、統計分析）
- 本地儲存空間釋放（本地僅保留 30 天，雲端永久保留）

### 使用場景

**開發環境：** 一般 PC（非邊緣裝置）
**網路環境：** 可能不穩定，需要失敗重試機制
**GCP 經驗：** 使用者首次在 GCP 部署，需完整設定文檔

---

## 2. 核心設計決策

### 2.1 上傳時機：手動觸發 + 自動補償

**選擇方案：** Manual + Auto-retry

**運作方式：**
- 預設不自動上傳（`upload_on_extract: false`）
- 提供 CLI 手動觸發：`fds-cloud-sync --upload-pending`
- 上傳失敗時自動記錄到資料庫，可稍後批次重試
- 未來可調整為自動上傳（修改配置 `upload_on_extract: true`）

**理由：**
- 開發階段可靈活控制上傳時機
- 網路故障不影響核心偵測功能
- 可先手動測試 GCP 設定，穩定後再自動化

### 2.2 儲存服務：Cloud Storage

**選擇方案：** GCP Cloud Storage (Object Storage)

**配置：**
- **Bucket 名稱：** `fds-skeletons-{project-id}`
- **區域：** `asia-east1`（台灣）或 `asia-northeast1`（日本）
- **儲存類別：** Standard → Coldline → Archive（生命週期自動轉換）
- **存取控制：** Uniform（統一權限管理）

**理由：**
- 成本最低（Standard: $0.023/GB/month）
- 設定簡單（無需設計 database schema）
- 支援生命週期自動管理（降級但不刪除）
- 未來可輕鬆整合 BigQuery 做資料分析

### 2.3 檔案組織：日期分層結構

**目錄結構：**

```
gs://fds-skeletons-{project-id}/
└── 2025/
    └── 12/
        └── 29/
            ├── evt_1735459200.json
            ├── evt_1735459800.json
            └── evt_1735460400.json
```

**命名規則：**
- 路徑：`YYYY/MM/DD/evt_{timestamp}.json`
- 範例：`2025/12/29/evt_1735459200.json`

**理由：**
- 易於按日期查找和管理
- Lifecycle rules 可以按資料夾套用
- 符合時間序列資料的自然組織方式

### 2.4 上傳狀態追蹤：資料庫欄位

**Schema 變更：**

```sql
-- 新增欄位到 events 表
ALTER TABLE events ADD COLUMN skeleton_cloud_path TEXT;
ALTER TABLE events ADD COLUMN skeleton_upload_status TEXT DEFAULT 'pending';
  -- 狀態: 'pending', 'uploaded', 'failed'
ALTER TABLE events ADD COLUMN skeleton_upload_error TEXT;
  -- 失敗時儲存錯誤訊息
```

**狀態流轉：**

```
骨架提取完成 → pending
   ↓
上傳成功 → uploaded (記錄 cloud_path)
   ↓
上傳失敗 → failed (記錄 error message)
   ↓
手動重試 → uploaded 或 failed
```

**理由：**
- 與現有 `clip_path` 欄位一致
- 可用 SQL 查詢「所有未上傳的骨架」
- Web Dashboard 可顯示「已備份到雲端」標記

### 2.5 失敗重試：佇列機制

**重試策略：**

1. **立即重試（同步）：** 失敗時立即重試 3 次，間隔 5 秒
2. **失敗記錄：** 3 次全部失敗後，標記 `status='failed'` 並記錄錯誤
3. **批次重試（非同步）：** 執行 `fds-cloud-sync --retry-failed` 重試所有失敗項目

**錯誤分類：**

| 錯誤類型 | 立即重試 | 可批次重試 | 需要人工介入 |
|---------|---------|-----------|------------|
| NetworkError | ✅ 3次 | ✅ | ❌ |
| AuthenticationError | ❌ | ❌ | ✅ 修正金鑰 |
| QuotaExceededError | ❌ | ✅ 隔天重試 | ❌ |
| FileNotFoundError | ❌ | ❌ | ✅ 檢查檔案 |

**理由：**
- 不阻塞主流程（失敗後立即放棄，稍後重試）
- 可觀察性高（失敗記錄在資料庫）
- 靈活性高（手動或定時批次重試）

### 2.6 認證方式：User Account (ADC) 【推薦用於開發】

**選擇方案：** Application Default Credentials (ADC) with User Account

**⚠️ 重要：認證方式比較**

根據 Google Cloud 官方建議，針對不同環境選擇合適的認證方式：

| 認證方式 | 適用場景 | 安全性 | 設定複雜度 |
|---------|---------|-------|-----------|
| **User Account (ADC)** ✅ | 本地開發環境 | 中（本地檔案儲存） | 低 |
| **Workload Identity Federation** | CI/CD, 外部 IdP | 高（短期 token） | 高 |
| **Service Account Key** ❌ | 僅測試用 | 低（長期憑證） | 低 |

**PC 開發環境的認證設定：**

**方案 A：User Account (gcloud ADC) - 本專案採用**
```bash
# 1. 安裝 gcloud CLI
# 2. 執行登入
gcloud auth application-default login

# 3. 憑證自動儲存到 ~/.config/gcloud/application_default_credentials.json
# 4. Python SDK 會自動使用此憑證（無需額外設定）
```

**特點：**
- ✅ 適合單機開發環境
- ✅ 無需管理 Service Account Key
- ✅ Google 推薦用於本地開發
- ⚠️ 憑證儲存在本地檔案（需保護檔案權限）
- ❌ 不適用於生產環境或 CI/CD

**方案 B：Workload Identity Federation - 需外部 IdP**
- 適用於：GitHub Actions, AWS, Azure, 自建 OIDC/SAML IdP
- 不適用於：一般 PC 開發環境（除非有外部 IdP）
- 範例：GitHub Actions 使用 OIDC token 交換 GCP access token

**方案 C：Service Account Key - 不推薦**
- ⚠️ **僅限測試或 CI/CD 無法使用 WIF 時**
- 需手動管理金鑰檔案
- 長期憑證，洩漏風險高
- 必須定期輪替（建議 90 天）

**為何不在 PC 使用 Workload Identity Federation？**
- WIF 需要外部身份提供者（GitHub, AWS, Azure, OIDC/SAML）
- 一般 PC 沒有這些 IdP
- 設定過於複雜，不適合開發環境

**本專案採用：方案 A（User Account ADC）**

理由：
- PC 本地開發環境
- 設定簡單（一條命令）
- 無需管理金鑰檔案
- Google 官方推薦用於開發環境

---

## 3. 系統架構

### 3.1 核心元件

```
src/lifecycle/cloud_sync.py
├── CloudStorageUploader     # GCS 上傳核心邏輯
│   ├── upload_skeleton()    # 單檔上傳
│   ├── upload_batch()       # 批次上傳
│   └── retry_failed()       # 重試失敗項目
│
└── UploadQueue              # 上傳佇列管理
    ├── mark_pending()       # 標記待上傳
    ├── mark_uploaded()      # 標記已上傳
    └── get_failed_items()   # 取得失敗清單
```

### 3.2 CLI 工具

**入口點：** `scripts/cloud_sync.py` → CLI 命令 `fds-cloud-sync`

**支援指令：**

```bash
# 上傳所有待上傳的骨架 JSON
fds-cloud-sync --upload-pending

# 重試所有失敗的上傳
fds-cloud-sync --retry-failed

# 上傳指定事件
fds-cloud-sync --event-id evt_1735459200

# 檢查上傳狀態（不執行上傳）
fds-cloud-sync --status

# 乾運行模式（顯示會上傳什麼，但不實際執行）
fds-cloud-sync --upload-pending --dry-run
```

### 3.3 配置檔

**新增到 `config/settings.yaml`：**

```yaml
cloud_sync:
  enabled: true
  gcs_bucket: "fds-skeletons-{your-project-id}"
  upload_on_extract: false  # 未來可改為 true 自動上傳
  retry_attempts: 3
  retry_delay_seconds: 5
```

**環境變數（`.env`）：**

```bash
GOOGLE_APPLICATION_CREDENTIALS=/home/kionc9986/.gcp/fds-cloud-sync.json
GCS_BUCKET_NAME=fds-skeletons-{your-project-id}
```

---

## 4. 錯誤處理

### 4.1 例外類型

```python
class UploadError(Exception):
    """上傳錯誤基類"""
    pass

class NetworkError(UploadError):
    """網路錯誤（可重試）"""
    pass

class AuthenticationError(UploadError):
    """認證錯誤（不可重試，需修正配置）"""
    pass

class QuotaExceededError(UploadError):
    """配額超限（可重試，但需等待）"""
    pass
```

### 4.2 錯誤記錄範例

```
skeleton_upload_error: "NetworkError: [Errno 111] Connection refused (attempt 3/3)"
skeleton_upload_error: "AuthenticationError: Invalid service account key"
skeleton_upload_error: "QuotaExceededError: Daily upload limit exceeded"
```

---

## 5. GCP 設定指南

### 5.1 前置需求

- ✅ GCP 帳號已開通
- ✅ 已有空白 GCP 專案可用
- 📝 記下專案 ID（例如：`my-project-123456`）

### 5.2 啟用 Cloud Storage API

**GCP Console：**
1. 選擇你的專案
2. 左側選單 → "APIs & Services" → "Library"
3. 搜尋 "Cloud Storage API"
4. 點擊 "Enable"

**或用 gcloud CLI：**

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable storage.googleapis.com
```

### 5.3 建立 Cloud Storage Bucket

**Bucket 命名規則：** `fds-skeletons-{your-project-id}`

**GCP Console：**
1. 左側選單 → "Cloud Storage" → "Buckets"
2. 點擊 "Create Bucket"
3. 設定：
   - **名稱：** `fds-skeletons-{your-project-id}`
   - **Location type：** Region
   - **Location：** `asia-east1`（台灣）或 `asia-northeast1`（日本）
   - **Storage class：** Standard
   - **Access control：** Uniform
4. 點擊 "Create"

**或用 gsutil CLI：**

```bash
gsutil mb -c STANDARD -l asia-east1 gs://fds-skeletons-{your-project-id}
```

### 5.4 設定認證（使用 gcloud CLI - 推薦）

**Step 1: 安裝 gcloud CLI**

```bash
# Linux/WSL2
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# macOS（使用 Homebrew）
brew install google-cloud-sdk

# 驗證安裝
gcloud --version
```

**Step 2: 初始化 gcloud 並登入**

```bash
# 初始化配置
gcloud init

# 選擇你的 GCP 專案
gcloud config set project YOUR_PROJECT_ID

# 設定 Application Default Credentials（ADC）
gcloud auth application-default login
```

執行 `gcloud auth application-default login` 後：
1. 瀏覽器會自動開啟 Google 登入頁面
2. 選擇你的 Google 帳號並授權
3. 憑證會自動儲存到 `~/.config/gcloud/application_default_credentials.json`
4. Python SDK 會自動使用此憑證（無需額外設定環境變數）

**Step 3: 授予你的帳號 Storage 權限**

```bash
# 取得你的 Google 帳號 email
gcloud config get-value account

# 授予 Storage Object Creator 角色
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:YOUR_EMAIL@gmail.com" \
    --role="roles/storage.objectCreator"
```

**Step 4: 驗證認證**

```bash
# 驗證 ADC 已設定
gcloud auth application-default print-access-token

# 測試 Cloud Storage 存取
gsutil ls gs://fds-skeletons-{your-project-id}
```

**環境變數（可選）：**

```bash
# .env 檔案（僅需設定 bucket 名稱）
echo 'GCS_BUCKET_NAME=fds-skeletons-{your-project-id}' >> .env

# GOOGLE_APPLICATION_CREDENTIALS 環境變數不需要設定
# gcloud ADC 會自動使用 ~/.config/gcloud/application_default_credentials.json
```

---

### 5.5 備選方案：Service Account（用於 CI/CD 或自動化）

**⚠️ 僅在以下情況使用此方案：**
- CI/CD pipeline（無法使用互動式登入）
- 自動化腳本（無人值守執行）
- 需要精確的最小權限控制

**不推薦用於：** 本地開發環境（請使用 gcloud ADC）

<details>
<summary>點擊展開 Service Account 設定步驟</summary>

**建立 Service Account：**

```bash
# 使用 gcloud CLI 建立
gcloud iam service-accounts create fds-cloud-sync \
    --description="FDS skeleton JSON uploader" \
    --display-name="FDS Cloud Sync"

# 授予權限
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:fds-cloud-sync@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

# 建立並下載金鑰（⚠️ 僅測試用）
gcloud iam service-accounts keys create ~/.gcp/fds-cloud-sync.json \
    --iam-account=fds-cloud-sync@YOUR_PROJECT_ID.iam.gserviceaccount.com

chmod 600 ~/.gcp/fds-cloud-sync.json

# 設定環境變數
echo 'GOOGLE_APPLICATION_CREDENTIALS=/home/kionc9986/.gcp/fds-cloud-sync.json' >> .env
```

**⚠️ 安全提醒：**
- 金鑰檔案絕對不可 commit 到 git
- 定期輪替金鑰（建議 90 天）
- 使用後立即刪除（`gcloud iam service-accounts keys delete`）
- 考慮升級到 Workload Identity Pool

</details>

---

### 5.6 設定 Lifecycle Policy（自動降級儲存）

**建立 `lifecycle.json`：**

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
        "condition": {"age": 30},
        "description": "30 天後轉為 Coldline（降低 80% 成本）"
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
        "condition": {"age": 365},
        "description": "1 年後轉為 Archive（最低成本）"
      }
    ]
  }
}
```

**套用到 Bucket：**

```bash
gsutil lifecycle set lifecycle.json gs://fds-skeletons-{your-project-id}

# 驗證
gsutil lifecycle get gs://fds-skeletons-{your-project-id}
```

---

## 6. 測試策略

### 6.1 本地驗證步驟

```bash
# Step 1: 驗證 GCP 認證
python -c "
from google.cloud import storage
client = storage.Client()
print('✅ GCP 認證成功')
print(f'專案 ID: {client.project}')
"

# Step 2: 驗證 Bucket 存取權限
python -c "
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('fds-skeletons-{your-project-id}')
print(f'✅ Bucket 存在: {bucket.exists()}')
"

# Step 3: 測試上傳單一檔案
fds-cloud-sync --event-id evt_123 --dry-run  # 先乾運行
fds-cloud-sync --event-id evt_123             # 實際上傳

# Step 4: 驗證檔案已上傳
gsutil ls gs://fds-skeletons-{your-project-id}/2025/12/29/

# Step 5: 測試批次上傳
fds-cloud-sync --upload-pending

# Step 6: 測試失敗重試
fds-cloud-sync --retry-failed
```

### 6.2 單元測試

**檔案：** `tests/lifecycle/test_cloud_sync.py`

```python
class TestCloudStorageUploader:
    def test_upload_skeleton_success()         # 成功上傳
    def test_upload_skeleton_network_error()   # 網路錯誤重試
    def test_upload_skeleton_auth_error()      # 認證錯誤不重試
    def test_generate_cloud_path()             # 路徑生成正確
    def test_mark_upload_status()              # 資料庫狀態更新
    def test_get_pending_uploads()             # 查詢待上傳清單
    def test_retry_failed_uploads()            # 重試失敗項目
    def test_dry_run_mode()                    # 乾運行不實際上傳
```

### 6.3 整合測試

1. **完整流程：** 提取骨架 → 上傳 → 驗證雲端檔案 → 確認資料庫狀態
2. **失敗恢復：** Mock 網路錯誤 → 確認標記 failed → 修復網路 → 重試成功
3. **並發上傳：** 批次上傳 10 個檔案 → 驗證全部成功

---

## 7. 成本估算與生命週期管理

### 7.1 費用估算（永久保留）

**假設場景：** 每天 10 個跌倒事件，每個骨架 JSON 約 50KB

```
第一年累積：10 events/day × 365 days × 50KB = 182MB
第五年累積：182MB × 5 = 910MB ≈ 0.91GB

儲存成本（混合儲存類別）：
- 前 30 天（Standard）：0.18GB × $0.023 = $0.004/month
- 30 天-1 年（Coldline）：0.18GB × $0.004 = $0.0007/month
- 1 年以上（Archive）：0.18GB × $0.0012 = $0.0002/month

五年總成本：約 $0.5 ≈ NT$15（幾乎可忽略）
```

### 7.2 儲存類別比較

| 儲存類別 | 使用時機 | 成本（asia-east1） | 存取延遲 |
|---------|---------|------------------|---------|
| **Standard** | 0-30 天 | $0.023/GB/month | 毫秒級 |
| **Coldline** | 30 天-1 年 | $0.004/GB/month | 毫秒級 |
| **Archive** | 1 年以上 | $0.0012/GB/month | 毫秒級 |

### 7.3 完整資料生命週期

**配置（`config/settings.yaml`）：**

```yaml
lifecycle:
  clip_retention_days: 7          # 影片保留 7 天後刪除
  skeleton_retention_days: 30     # 骨架 JSON 本地保留 30 天
  cloud_retention_days: -1        # -1 表示雲端永久保留
```

**時間軸：**

- **Day 0-7：** 本地有影片 + 骨架 JSON + 雲端備份（Standard）
- **Day 7-30：** 本地僅骨架 JSON + 雲端備份（Standard）
- **Day 30-365：** 本地已清空 + 雲端備份（Coldline，成本降低 80%）
- **Day 365+：** 雲端長期歸檔（Archive，成本降低 95%）

**永久保留理由：**
- 骨架 JSON 檔案極小（50KB）
- 已脫敏（無隱私問題）
- 未來用途：ML 模型訓練、跌倒模式分析、長期統計

---

## 8. 實作檢查清單

### 8.1 核心功能

- [ ] 實作 `src/lifecycle/cloud_sync.py`
  - [ ] `CloudStorageUploader` 類別
  - [ ] `upload_skeleton()` 方法
  - [ ] `upload_batch()` 方法
  - [ ] `retry_failed()` 方法
- [ ] 實作 `scripts/cloud_sync.py` CLI 工具
- [ ] 更新資料庫 schema（新增 3 個欄位）
- [ ] 新增配置項目到 `config/settings.yaml`
- [ ] 更新 `pyproject.toml`（新增 CLI 入口點 `fds-cloud-sync`）

### 8.2 測試

- [ ] 單元測試：`tests/lifecycle/test_cloud_sync.py`（8 個測試）
- [ ] 整合測試：完整流程驗證
- [ ] Mock 測試：網路錯誤、認證錯誤、配額超限

### 8.3 文檔

- [ ] GCP 設定步驟文檔（含螢幕截圖）
- [ ] CLI 使用範例
- [ ] 故障排除指南
- [ ] 更新 `CLAUDE.md` 和 `README.md`

### 8.4 依賴

- [ ] 新增 `google-cloud-storage>=2.10.0` 到 `pyproject.toml`
- [ ] 執行 `uv sync` 安裝依賴

---

## 9. 未來擴充

### 9.1 自動化排程

**目標：** 骨架提取完成後自動上傳（不需手動觸發）

**實作方式：**
```yaml
# config/settings.yaml
cloud_sync:
  upload_on_extract: true  # 改為 true
```

**觸發點：** `SkeletonExtractor.extract_and_save()` 完成後呼叫 `CloudStorageUploader.upload_skeleton()`

### 9.2 Web Dashboard 整合

**功能：**
- 事件列表顯示「☁️ 已備份」圖示
- 點擊可從雲端下載骨架 JSON（Signed URL）
- 上傳狀態統計（成功/失敗/待上傳）

### 9.3 BigQuery 整合（資料分析）

**使用場景：** 大量歷史資料的 SQL 查詢和 ML 訓練

**實作方式：**
- Cloud Function 觸發器：GCS 新增檔案 → 自動匯入 BigQuery
- Schema mapping：JSON → BigQuery Table

---

## 10. 參考資料

### GCP 官方文檔

**認證與安全性：**
- [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) - 本專案使用的認證方式
- [Set up ADC for Local Development](https://cloud.google.com/docs/authentication/set-up-adc-local-dev-environment) - 本地開發環境 ADC 設定
- [Authentication Methods at Google](https://cloud.google.com/docs/authentication) - 各種認證方式比較
- [Best Practices for Service Account Keys](https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys) - 為何避免使用 Service Account Keys

**進階認證（非本專案使用）：**
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation) - 用於 CI/CD 和外部 IdP
- [Best Practices for Workload Identity Federation](https://cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation)

**Cloud Storage：**
- [Cloud Storage 快速入門](https://cloud.google.com/storage/docs/quickstart-console)
- [Object Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)
- [Python Client Library](https://cloud.google.com/python/docs/reference/storage/latest)

### Python SDK

- [google-cloud-storage](https://googleapis.dev/python/storage/latest/index.html)
- [google-auth User Guide](https://googleapis.dev/python/google-auth/latest/user-guide.html) - ADC 在 Python 中的使用

---

**文檔版本：** 1.2
**最後更新：** 2025-12-29
**變更歷史：**
- v1.0: 初始設計（使用 Service Account Key）
- v1.1: 更新為 Workload Identity Federation（錯誤）
- v1.2: 更正為 User Account (ADC)，釐清 WIF 適用場景

**下一步：** 建立實作計畫（使用 superpowers:writing-plans）
