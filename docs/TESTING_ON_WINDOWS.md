# Windows 測試指南

本文檔說明如何在 Windows 上測試 FDS 專案的最新更新。

## 測試項目

1. ✅ **Skeleton Extractor** - 骨架提取功能
2. ✅ **Clip Cleanup** - 影片清理排程器
3. ✅ **Docker 配置** - 容器化部署

---

## 方式 1：WSL2 內測試（推薦，最簡單）

### 前提條件
- 已在 WSL2 Ubuntu 環境
- 已安裝 `uv`（當前專案使用）

### 步驟 1：測試 Skeleton Extractor

```bash
# 在 WSL2 終端中執行

# 1. 確認環境
cd /home/kionc9986/Projects/FDS
uv sync

# 2. 執行單元測試
uv run pytest tests/lifecycle/test_skeleton_extractor.py -v

# 3. 測試真實影片提取
uv run python3 -c "
from pathlib import Path
from src.lifecycle.skeleton_extractor import SkeletonExtractor
from src.lifecycle.schema.validator import SkeletonValidator

# 初始化
extractor = SkeletonExtractor(model_path='yolo11s-pose.pt')
output_path = Path('data/test_output.json')
output_path.parent.mkdir(parents=True, exist_ok=True)

# 提取骨架
print('正在提取骨架...')
extractor.extract_and_save(
    'tests/fixtures/videos/fall-01-cam0.mp4',
    output_path,
    event_id='evt_1234567890'
)

# 驗證
validator = SkeletonValidator()
is_valid = validator.validate_file(output_path)
print(f'驗證結果: {\"✓ 通過\" if is_valid else \"✗ 失敗\"}')
"

# 預期結果：✓ 通過
```

### 步驟 2：測試 Clip Cleanup

```bash
# 1. 執行單元測試
uv run pytest tests/lifecycle/test_clip_cleanup.py -v

# 2. 測試清理腳本（乾運行）
uv run python -m scripts.cleanup_clips --dry-run

# 預期結果：10/10 tests passed
```

### 步驟 3：測試 Docker 配置（WSL2 + Docker Desktop）

```bash
# 1. 確認 Docker 可用
docker --version
docker compose version

# 2. 驗證配置語法
docker compose config --dry-run

# 3. 建構鏡像（需時 5-10 分鐘）
docker compose build

# 4. 測試啟動（不使用攝影機）
# 編輯 docker-compose.yml，暫時註解掉 devices: 區塊
# 然後執行：
docker compose up -d

# 5. 查看日誌
docker compose logs fds

# 6. 停止
docker compose down

# 預期結果：容器成功啟動（雖然會因為沒有攝影機而報錯，但這是預期的）
```

---

## 方式 2：Windows PowerShell 本地測試

### 前提條件

1. **安裝 Python 3.12+**
   - 下載：https://www.python.org/downloads/
   - 勾選 "Add Python to PATH"

2. **安裝 uv（Windows）**
   ```powershell
   # 在 PowerShell 中執行
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **安裝 Git for Windows**
   - 下載：https://git-scm.com/download/win

### 步驟 1：Clone 專案到 Windows

```powershell
# 在 PowerShell 中執行

# 1. 切換到 Windows 使用者目錄
cd $HOME\Documents

# 2. Clone 專案（從 WSL2 複製）
# 方式 A：使用 Git
git clone /mnt/c/Users/<你的用戶名>/path/to/FDS

# 方式 B：直接從 WSL2 複製
cp -r /home/kionc9986/Projects/FDS ./FDS-Windows
cd FDS-Windows
```

**或者直接在 Windows 文件系統訪問 WSL2 專案：**

```powershell
# WSL2 專案可從 Windows 訪問
cd \\wsl$\Ubuntu\home\kionc9986\Projects\FDS
```

### 步驟 2：設定環境

```powershell
# 1. 安裝依賴
uv sync

# 2. 設定環境變數
copy .env.example .env
# 編輯 .env 設定 LINE_NOTIFY_TOKEN（用記事本或 VSCode）
```

### 步驟 3：執行測試

```powershell
# 1. 測試 Skeleton Extractor
uv run pytest tests/lifecycle/test_skeleton_extractor.py -v

# 2. 測試 Clip Cleanup
uv run pytest tests/lifecycle/test_clip_cleanup.py -v

# 3. 測試所有 lifecycle 模組
uv run pytest tests/lifecycle/ -v

# 預期結果：大部分測試通過（除了一個已知的 validator 測試問題）
```

### 步驟 4：測試真實骨架提取

```powershell
# 使用 PowerShell 執行 Python 腳本
uv run python -c @"
from pathlib import Path
from src.lifecycle.skeleton_extractor import SkeletonExtractor
from src.lifecycle.schema.validator import SkeletonValidator

extractor = SkeletonExtractor(model_path='yolo11s-pose.pt')
output_path = Path('data/test_skeleton_windows.json')
output_path.parent.mkdir(parents=True, exist_ok=True)

print('正在提取骨架...')
extractor.extract_and_save(
    'tests/fixtures/videos/fall-01-cam0.mp4',
    output_path,
    event_id='evt_9876543210'
)

validator = SkeletonValidator()
is_valid = validator.validate_file(output_path)
print(f'驗證結果: {'通過' if is_valid else '失敗'}')
"@
```

### 步驟 5：即時視覺化骨架提取（推薦）

使用內建測試腳本即時觀看骨架偵測效果：

```powershell
# 使用 Pose 模式（骨架偵測）並顯示即時視窗
uv run python -m scripts.test_with_video tests/fixtures/videos/fall-01-cam0.mp4 --use-pose
```

**視窗功能：**

- 🟢 綠色骨架 = 正常狀態 (NORMAL)
- 🟡 黃色骨架 = 疑似跌倒 (SUSPECTED)
- 🔴 紅色骨架 = 確認跌倒 (CONFIRMED)
- 顯示軀幹角度（angle）

**控制鍵：**

- `q` - 退出
- `p` - 暫停/繼續

**其他模式：**
```powershell
# BBox 長寬比模式（預設）
uv run python -m scripts.test_with_video tests/fixtures/videos/fall-01-cam0.mp4

# 無視窗純 CLI 模式
uv run python -m scripts.test_with_video tests/fixtures/videos/fall-01-cam0.mp4 --use-pose --no-window
```

---

## 方式 3：Docker Desktop on Windows 測試

### 前提條件

1. **安裝 Docker Desktop for Windows**
   - 下載：https://www.docker.com/products/docker-desktop/
   - 啟用 WSL2 整合

2. **在 Docker Desktop 設定中：**
   - Settings → Resources → WSL Integration
   - 啟用你的 WSL2 發行版（Ubuntu）

### 步驟 1：在 WSL2 中建構

```bash
# 在 WSL2 終端執行
cd /home/kionc9986/Projects/FDS

# 1. 建構鏡像
docker compose build

# 2. 檢查鏡像
docker images | grep fds
```

### 步驟 2：測試容器啟動（無攝影機模式）

**編輯 `docker-compose.yml`：**
```yaml
# 暫時註解掉攝影機設備映射
services:
  fds:
    # devices:
    #   - /dev/video0:/dev/video0
```

**啟動測試：**
```bash
# 1. 啟動容器
docker compose up -d

# 2. 查看日誌（會看到 "Camera not found" 錯誤，這是正常的）
docker compose logs -f fds

# 3. 檢查容器狀態
docker compose ps

# 4. 停止
docker compose down
```

### 步驟 3：測試清理服務

```bash
# 執行清理容器（不需要攝影機）
docker compose run --rm fds-cleanup

# 預期輸出：找到 0 個過期影片（因為是新資料庫）
```

---

## 常見問題排除

### Q1: WSL2 找不到測試影片
```bash
# 確認測試影片存在
ls -lh tests/fixtures/videos/

# 如果缺少，可能需要重新下載或從其他來源獲取
```

### Q2: Windows PowerShell 執行 Python 多行腳本失敗
```powershell
# 改用檔案方式
# 建立 test_skeleton.py 檔案，然後執行：
uv run python test_skeleton.py
```

### Q3: Docker Desktop 無法訪問 WSL2 檔案
```bash
# 確保 Docker Desktop 的 WSL2 整合已啟用
# Settings → Resources → WSL Integration → 啟用 Ubuntu
```

### Q4: uv 在 Windows 上找不到
```powershell
# 重新安裝 uv
irm https://astral.sh/uv/install.ps1 | iex

# 或使用 pip
pip install uv
```

---

## 測試檢查清單

完成以下測試項目，確保所有功能正常：

- [ ] **Skeleton Extractor 單元測試通過**
  ```bash
  uv run pytest tests/lifecycle/test_skeleton_extractor.py -v
  # 預期：6/6 passed
  ```

- [ ] **Skeleton Extractor 真實影片測試**
  ```bash
  # 輸出檔案存在且通過 Schema 驗證
  ls data/test_output.json
  ```

- [ ] **Clip Cleanup 單元測試通過**
  ```bash
  uv run pytest tests/lifecycle/test_clip_cleanup.py -v
  # 預期：10/10 passed
  ```

- [ ] **Clip Cleanup 腳本執行**
  ```bash
  uv run python -m scripts.cleanup_clips --dry-run
  # 預期：無錯誤，顯示統計資訊
  ```

- [ ] **Docker 配置語法驗證**
  ```bash
  docker compose config --dry-run
  # 預期：無錯誤（只有 version 警告可忽略）
  ```

- [ ] **Docker 鏡像建構成功**（可選，需時較長）
  ```bash
  docker compose build
  # 預期：Build complete
  ```

---

## 推薦測試流程（5 分鐘快速驗證）

```bash
# 在 WSL2 終端執行以下命令

cd /home/kionc9986/Projects/FDS

# 1. 測試骨架提取（約 2 分鐘）
echo "=== 測試 1: Skeleton Extractor ==="
uv run pytest tests/lifecycle/test_skeleton_extractor.py -v

# 2. 測試清理排程器（約 1 分鐘）
echo "=== 測試 2: Clip Cleanup ==="
uv run pytest tests/lifecycle/test_clip_cleanup.py -v

# 3. 驗證 Docker 配置（約 5 秒）
echo "=== 測試 3: Docker Config ==="
docker compose config --dry-run > /dev/null 2>&1 && echo "✓ Docker 配置正確" || echo "✗ Docker 配置錯誤"

echo "=== 測試完成 ==="
```

---

## 進階：攝影機測試（Windows 原生）

如果你想在 Windows 上測試真實攝影機（不使用 Docker）：

```powershell
# 1. 確認攝影機 ID
uv run python -c "import cv2; print(f'Camera 0: {cv2.VideoCapture(0).isOpened()}')"

# 2. 編輯 config/settings.yaml
# camera:
#   source: 0  # Windows 攝影機索引

# 3. 執行主程式（按 Ctrl+C 停止）
uv run python main.py
```

**注意：** Windows 的攝影機訪問權限需要確認「相機」隱私設定已啟用。

---

## 總結

**最簡單的測試方式（推薦）：**
1. 在 WSL2 中執行單元測試
2. 不需要設定 Windows 環境
3. 5 分鐘內完成所有驗證

**如需在 Windows 原生環境測試：**
1. 安裝 Python 3.12+ 和 uv
2. 從 WSL2 複製專案或直接訪問 `\\wsl$\...`
3. 執行相同的測試命令

**Docker 測試：**
1. 使用 Docker Desktop 的 WSL2 整合
2. 在 WSL2 中建構和測試即可
3. 攝影機映射在 Windows 容器中較複雜，建議在 Linux/WSL2 中測試

有任何問題隨時詢問！
