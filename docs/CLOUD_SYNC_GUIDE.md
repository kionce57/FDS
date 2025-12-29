# Cloud Sync 使用指南

將骨架 JSON 檔案上傳至 GCP Cloud Storage，實現隱私保護的資料備份。

## 前置需求

- GCP 帳號與專案
- 已建立 Cloud Storage Bucket
- 已完成 gcloud CLI 認證

## 快速設定

### 1. GCP 認證

```bash
# 安裝 gcloud CLI（如未安裝）
curl https://sdk.cloud.google.com | bash

# 登入並設定 ADC（WSL2 環境使用 --no-launch-browser）
gcloud auth application-default login --no-launch-browser
```

### 2. 建立 Bucket

```bash
# 將 YOUR_PROJECT_ID 替換為你的專案 ID
gsutil mb -c STANDARD -l asia-east1 gs://fds-skeletons-YOUR_PROJECT_ID
```

### 3. 設定 .env

```bash
cp .env.example .env
```

編輯 `.env`：
```
GCS_BUCKET_NAME=fds-skeletons-YOUR_PROJECT_ID
```

## CLI 指令

| 指令 | 說明 |
|-----|------|
| `fds-cloud-sync --status` | 查看上傳狀態統計 |
| `fds-cloud-sync --upload-pending` | 上傳所有待處理的骨架 |
| `fds-cloud-sync --retry-failed` | 重試所有失敗的上傳 |
| `fds-cloud-sync --event-id evt_123` | 上傳特定事件 |
| `fds-cloud-sync --dry-run --upload-pending` | 乾運行（不實際上傳） |

## 錯誤處理

| 錯誤類型 | 自動重試 | 可批次重試 | 處理方式 |
|---------|---------|-----------|---------|
| NetworkError | ✅ 3次 | ✅ | 等待網路恢復後執行 `--retry-failed` |
| AuthenticationError | ❌ | ❌ | 重新執行 `gcloud auth application-default login` |
| QuotaExceededError | ❌ | ✅ | 隔天再執行 `--retry-failed` |
| FileNotFoundError | ❌ | ❌ | 檢查本地骨架檔案是否存在 |

## 故障排除

### 問題：Bucket names must start and end with a number or letter

**原因：** `.env` 檔案未正確載入或 `GCS_BUCKET_NAME` 未設定

**解決：**
1. 確認 `.env` 檔案存在且格式正確
2. 確認 `GCS_BUCKET_NAME` 不含 `${}` 符號

### 問題：Your default credentials were not found

**原因：** 未設定 GCP Application Default Credentials

**解決：**
```bash
gcloud auth application-default login --no-launch-browser
```

### 問題：Access Denied / 403 Forbidden

**原因：** 帳號沒有 Cloud Storage 寫入權限

**解決：**
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:YOUR_EMAIL@gmail.com" \
    --role="roles/storage.objectCreator"
```

## 驗證上傳

```bash
# 確認檔案已上傳
gsutil ls gs://YOUR_BUCKET_NAME/2025/12/29/
```

## 相關設定

`config/settings.yaml`：
```yaml
cloud_sync:
  enabled: true
  gcs_bucket: "${GCS_BUCKET_NAME}"
  upload_on_extract: false    # 提取後自動上傳（目前為手動）
  retry_attempts: 3
  retry_delay_seconds: 5
```

## 更多資訊

- [GCP 設定詳細指南](docs/plans/2025-12-29-cloud-sync-design.md#5-gcp-設定指南)
- [WSL 環境認證指南](docs/gcloud_wsl_auth_guide.md)
