# FDS - Fall Detection System

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

居家長照跌倒偵測系統，使用 YOLOv8 進行人體偵測，透過長寬比規則判斷跌倒，並發送 LINE 通知。

## 功能特色

- 🎯 **即時跌倒偵測** - 使用 YOLOv8 進行人體偵測與長寬比分析
- ⏱️ **延遲確認機制** - 3 秒延遲減少誤報（如彎腰撿東西）
- 📹 **事件前後錄影** - 自動保存跌倒前後 10 秒影片
- 📱 **LINE 即時通知** - 跌倒確認後立即推播警報
- 💾 **事件記錄** - SQLite 儲存所有事件 metadata
- 🔄 **重複通知** - 持續躺著時每 2 分鐘重複通知

## 系統架構

```
Camera → YOLO 偵測 → 規則判斷 → 延遲確認 → 通知/錄影/記錄
           ↓              ↓           ↓
      Rolling Buffer   長寬比<1.3   狀態機
```

## 快速開始

### 安裝

```bash
# Clone 專案
git clone <repository-url>
cd FDS

# 安裝相依套件（需要 uv）
uv sync --all-extras
```

### 設定

1. 複製環境變數範例：

```bash
cp .env.example .env
```

2. 編輯 `.env` 設定 LINE Notify Token：

```
LINE_NOTIFY_TOKEN=your_token_here
```

3. 調整 `config/settings.yaml` 設定（可選）：

```yaml
camera:
  source: 0 # 攝影機索引或 RTSP URL
  fps: 15
analysis:
  fall_threshold: 1.3 # 長寬比閾值
  delay_sec: 3.0 # 延遲確認秒數
```

### 執行

```bash
# 執行主程式
uv run python main.py

# 按 Ctrl+C 停止
```

## 開發

### 執行測試

```bash
# 執行所有測試
uv run pytest -v

# 執行測試並顯示覆蓋率
uv run pytest -v --cov=src --cov-report=term-missing

# 執行特定模組測試
uv run pytest tests/test_delay_confirm.py -v
```

### 程式碼品質

```bash
# Lint 檢查
uv run ruff check .

# 自動修復 Lint 問題
uv run ruff check . --fix

# 格式化程式碼
uv run ruff format .
```

## 專案結構

```
FDS/
├── main.py                    # 程式進入點
├── config/
│   └── settings.yaml          # 設定檔
├── src/
│   ├── capture/               # 影像擷取
│   │   ├── camera.py          # 攝影機串流
│   │   └── rolling_buffer.py  # 環形緩衝區
│   ├── detection/             # 偵測模組
│   │   ├── bbox.py            # BBox 資料結構
│   │   └── detector.py        # YOLOv8 偵測器
│   ├── analysis/              # 分析模組
│   │   ├── rule_engine.py     # 長寬比規則
│   │   └── delay_confirm.py   # 延遲確認狀態機
│   ├── events/                # 事件處理
│   │   ├── observer.py        # Observer Pattern
│   │   ├── event_logger.py    # SQLite 記錄
│   │   ├── clip_recorder.py   # 影片儲存
│   │   └── notifier.py        # LINE 通知
│   └── core/                  # 核心模組
│       ├── config.py          # 設定載入
│       └── pipeline.py        # 主流程整合
├── tests/                     # 測試檔案
└── data/                      # 執行時資料（gitignore）
    ├── fds.db                 # SQLite 資料庫
    └── clips/                 # 影片片段
```

## 核心參數

| 參數                 | 預設值 | 說明                             |
| -------------------- | ------ | -------------------------------- |
| `fall_threshold`     | 1.3    | 站立時 ratio > 1.3，低於視為跌倒 |
| `delay_sec`          | 3.0    | 延遲確認秒數                     |
| `same_event_window`  | 60.0   | 60 秒內視為同一事件              |
| `re_notify_interval` | 120.0  | 持續躺著時，每 2 分鐘重複通知    |

## 技術棧

- **Python 3.12+**
- **YOLOv8** (Ultralytics) - 物件偵測
- **OpenCV** - 影像處理與錄影
- **SQLite** - 事件記錄
- **LINE Notify API** - 推播通知
- **pytest** - 測試框架
- **ruff** - Linting & Formatting

## 未來規劃 (Phase 2+)

- [ ] MediaPipe 姿態估計提升準確度
- [ ] 多攝影機支援
- [ ] Web 儀表板
- [ ] 骨架特徵化與雲端同步

## License

MIT License
