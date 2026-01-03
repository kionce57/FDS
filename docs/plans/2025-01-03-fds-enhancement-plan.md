# FDS Enhancement Implementation Plan

**建立日期：** 2025-01-03
**狀態：** Phase 1 已完成，Phase 2 請參閱 `2025-01-03-yolo11-pose-integration.md`

---

## 概述

本計畫分兩個主要階段：
1. **Phase 1: LINE 通知影片支援** - ✅ 已完成
2. **Phase 2: 模型升級至 YOLO11-Pose** - 請參閱獨立計畫文件

---

## Phase 1: LINE Notification with Video Support ✅

**目標：** 跌倒警報通知時可附帶事件影片

**狀態：** 已完成

### 已完成的 Commits

```
32e5bcb fix(notifier): use _build_messages in retry_pending for video support
8332ee7 feat(notifier): support video message in LINE notification
a0b3f3c feat(events): add ClipUrlGenerator for video URL generation
1f675d6 feat(observer): add clip_url field to FallEvent
```

### Task 1.1: 擴展 FallEvent 資料結構 ✅

**Files:**
- `src/events/observer.py` - 新增 `clip_url: str | None = None`
- `tests/test_observer.py` - 新增 `TestFallEventClipUrl` 測試類別

**變更：**
```python
@dataclass
class FallEvent:
    event_id: str
    confirmed_at: float
    last_notified_at: float
    notification_count: int
    clip_url: str | None = None  # 新增：影片的公開 URL
```

---

### Task 1.2: 新增影片 URL 生成器 ✅

**Files:**
- `src/events/clip_url_generator.py` - 新建
- `tests/test_clip_url_generator.py` - 新建

**用途：** 將本地檔案路徑轉換為公開 URL

```python
generator = ClipUrlGenerator(base_url="https://fds.example.com")
url = generator.generate("/data/clips/evt_123.mp4")
# 輸出: "https://fds.example.com/clips/evt_123.mp4"
```

---

### Task 1.3: 擴展 LineNotifier 支援影片訊息 ✅

**Files:**
- `src/events/notifier.py` - 新增 `_build_messages()` 方法
- `tests/test_notifier.py` - 新增影片相關測試

**變更：**
- 新增 `_build_messages(event, text)` 方法建構訊息列表
- 當 `event.clip_url` 存在時，自動附加 video message
- 預覽圖 URL 規則：`{clip_url}.mp4` → `{clip_url}_thumb.jpg`
- `retry_pending()` 也已更新使用 `_build_messages()`

**使用方式：**
```python
event = FallEvent(
    event_id="evt_123",
    confirmed_at=time.time(),
    last_notified_at=time.time(),
    notification_count=1,
    clip_url="https://your-server.com/clips/evt_123.mp4"
)
notifier.on_fall_confirmed(event)  # 發送文字 + 影片
```

---

### 後續整合需求（未實作）

以下功能已設計但未實作，若需要完整的影片通知功能需自行補充：

| 項目 | 說明 | 備註 |
|------|------|------|
| 影片託管服務 | LINE API 需要 HTTPS URL | 可用 GCS、S3 或自建 Web 服務 |
| 縮圖生成 | 預覽圖需 ≤1MB | 可用 OpenCV 提取第一幀 |
| Pipeline 整合 | 自動填入 `clip_url` | 需修改 `src/core/pipeline.py` |

---

## Phase 2: 模型升級

**狀態：** 技術選型已完成，實作計畫見獨立文件

### 技術選型過程

#### 初始評估（已否決）

| 模型 | 評估結果 | 否決原因 |
|------|----------|----------|
| **SDES-YOLO** | ❌ 否決 | 無公開程式碼、Benchmark 不可比（不同數據集）、工程風險過高 |
| **YOLOv9-C** | ❌ 不適用 | 無原生 Pose 支援，需自行移植 |

#### 選型決策分析

**問題：原始 SDES-YOLO vs YOLOv9-C 比較存在嚴重方法論錯誤**

| 錯誤類型 | 問題描述 |
|---------|---------|
| **Benchmark Bias** | mAP 來自不同數據集（COCO 80類 vs 跌倒專用 1-2類），無法直接比較 |
| **Dimensional Asymmetry** | SDES (2.9M) vs YOLOv9-C (25.3M)，量級差 10 倍，應比較 YOLOv9-T/S |
| **遮擋處理誤判** | YOLOv9 的 PGI 本身就是為解決資訊丟失（含遮擋）設計 |
| **工程風險低估** | SDES-YOLO 無公開程式碼 = 需自行復現論文 = Debug 成本極高 |

#### 最終決策：YOLO11-Pose

**選擇理由：**

1. **Ultralytics 官方支援** - 開箱即用，持續維護
2. **相同 API** - 與 YOLOv8-Pose 完全相容，改一行即可切換
3. **架構改進** - C3k2 模組，理論上比 v8 更快更準
4. **COCO 17 Keypoint** - 與現有 `Skeleton` 類別完全相容

**推薦配置：**
- 使用 `yolo11s-pose.pt`（Small）而非 Nano，穩定性更好
- 加入時序過濾（One Euro Filter）解決關鍵點抖動

**潛在風險：**

| 風險 | 緩解措施 |
|------|----------|
| 旋轉敏感度（橫躺偵測差） | Fine-tune 時開啟 Rotation Augmentation (degrees=180) |
| 關鍵點抖動 | 加入 One Euro Filter 時序過濾 |

---

### 實作計畫

詳見 **`docs/plans/2025-01-03-yolo11-pose-integration.md`**

| Phase | 內容 | Tasks |
|-------|------|-------|
| A | 配置化 + 切換至 YOLO11 | 6 tasks |
| B | KeypointSmoother 時序過濾 | 5 tasks |

---

## 相關文件

- `docs/plans/2025-01-03-yolo11-pose-integration.md` - YOLO11-Pose 詳細實作計畫
- `CLAUDE.md` - 專案架構說明
- `src/events/notifier.py` - LINE 通知實作
- `src/events/clip_url_generator.py` - URL 生成器

---

## Sources

- [LINE Messaging API - Video Message](https://developers.line.biz/en/reference/messaging-api/)
- [LINE Bot SDK Python](https://github.com/line/line-bot-sdk-python)
- [Ultralytics YOLO11 Pose](https://docs.ultralytics.com/tasks/pose/)
- [One Euro Filter](https://gery.casiez.net/1euro/)
