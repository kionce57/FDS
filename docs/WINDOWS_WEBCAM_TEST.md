# Windows Webcam 驗證步驟

## 前置

1. 安裝 uv: `irm https://astral.sh/uv/install.ps1 | iex`
2. 設定 `.env`（複製 `.env.example`，填入 `LINE_NOTIFY_TOKEN`）

## 執行

```powershell
cd C:\path\to\FDS
uv sync
uv run python main.py
```

## 驗證

1. 視窗出現攝影機畫面 ✓
2. 站在鏡頭前，看到綠色 BBox ✓
3. 躺下 3 秒，觸發通知 ✓
4. 檢查 `data/clips/` 有影片 ✓

## 攝影機問題排除

如果 `source: 0` 找不到攝影機：

```python
# 找出正確的 index
uv run python -c "
import cv2
for i in range(3):
    cap = cv2.VideoCapture(i)
    print(f'{i}: {\"✓\" if cap.isOpened() else \"✗\"}')
    cap.release()
"
```

修改 `config/settings.yaml` 中的 `camera.source` 為正確的 index。
