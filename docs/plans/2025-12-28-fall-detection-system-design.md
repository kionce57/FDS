# FDS - Fall Detection System 設計文件

> Phase 1 設計規格書
> 建立日期：2025-12-28

---

## 1. 專案概述與目標

### FDS - Fall Detection System（跌倒偵測系統）

**應用場景**：居家長照，監測獨居長者，偵測跌倒後自動通知家人或照護人員。

**Phase 1 目標**：

- 建立端到端的跌倒偵測流程驗證
- 使用物件偵測 + 規則判斷的輕量方案
- 透過 LINE Notify 完成通知功能
- 所有處理在本地邊緣裝置執行，影像不上傳雲端，保護隱私

### 技術選型

| 項目     | 選擇                                      |
| -------- | ----------------------------------------- |
| 程式語言 | Python 3.12+                              |
| 物件偵測 | YOLOv8/YOLOv11 (nano 版本起步)            |
| 跌倒判斷 | Bounding Box 長寬比規則，後續加入位移速度 |
| 誤報處理 | 延遲確認機制（3 秒）                      |
| 通知平台 | LINE Notify（架構預留擴充其他平台）       |
| 事件紀錄 | SQLite + 事件前後影片片段                 |
| 資料庫   | SQLite（結構化資料），檔案系統（影片）    |

### 未來擴展方向（Phase 2+）

- 升級至姿態估計（MediaPipe）提升準確度
- 多攝影機支援
- 更多通知平台整合

---

## 2. 資料生命週期管理

### 儲存架構

```
/data
├── fds.db                    # SQLite 資料庫（事件 metadata）
原生支援多人骨架偵測
├── clips/                    # 近期影片（7天）
├── snapshots/                # 關鍵截圖（30天）
└── sync_queue/               # 待上傳佇列
```

### 資料保留策略

```
時間軸：
├─ 0-7天    → 完整保留（影片 + log）
├─ 7天後    → 特徵化處理：
│              1. 使用 MediaPipe 提取骨架序列
│              2. 儲存骨架座標時序資料（JSON/Parquet）
│              3. 刪除原始影片
└─ 定期同步  → 骨架特徵 + metadata 上傳雲端
```

### 骨架特徵資料結構（Pose-Based / Skeleton Features）

```json
{
  "event_id": "evt_20251228_143052",
  "timestamp": "2025-12-28T14:30:52Z",
  "duration_sec": 10,
  "fps": 15,
  "skeleton_sequence": [
    {
      "frame": 0,
      "keypoints": {
        "nose": [0.52, 0.15],
        "left_shoulder": [0.45, 0.28],
        "right_shoulder": [0.58, 0.27]
      },
      "bbox": [120, 80, 200, 350]
    }
  ],
  "detection_result": "fall_confirmed",
  "rule_triggered": "aspect_ratio_change"
}
```

### 優勢

| 面向           | 效益                                              |
| -------------- | ------------------------------------------------- |
| **隱私**       | 骨架資料無法還原人臉/身份，可安心上傳             |
| **儲存**       | 10 秒影片 ≈ 5MB → 骨架 JSON ≈ 50KB（壓縮 100 倍） |
| **ML 價值**    | 骨架序列可直接用於訓練 Phase 2 的姿態分類模型     |
| **Phase 銜接** | Phase 1 收集的骨架資料，成為 Phase 2 的訓練素材   |

---

## 3. 系統架構

### 整體架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                        Edge Device                              │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Camera  │───→│ Video Capture │───→│  Fall Detection Core  │  │
│  └──────────┘    └──────────────┘    │  ┌─────────────────┐  │  │
│                                       │  │ YOLOv8 Detector │  │  │
│                                       │  └────────┬────────┘  │  │
│                                       │           ↓           │  │
│                                       │  ┌─────────────────┐  │  │
│                                       │  │  Rule Engine    │  │  │
│                                       │  │ (Aspect Ratio)  │  │  │
│                                       │  └────────┬────────┘  │  │
│                                       │           ↓           │  │
│                                       │  ┌─────────────────┐  │  │
│                                       │  │ Delay Confirm   │  │  │
│                                       │  │ (3 sec)         │  │  │
│                                       │  └─────────────────┘  │  │
│                                       └───────────┬───────────┘  │
│                                                   ↓              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Event Logger │←───│ Clip Recorder │←───│   Notifier   │       │
│  │  (SQLite)    │    │ (FFmpeg/CV2)  │    │ (LINE API)   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         ↓                   ↓                                    │
│  ┌─────────────────────────────────────┐                        │
│  │         Data Lifecycle Manager       │                        │
│  │  • 7天後: MediaPipe 骨架特徵化       │                        │
│  │  • 刪除原始影片                      │                        │
│  │  • 同步特徵至雲端                    │                        │
│  └─────────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    ┌──────────────────────┐
                    │    Cloud (Optional)   │
                    │  • 骨架特徵儲存       │
                    │  • 統計分析儀表板     │
                    └──────────────────────┘
```

### 核心模組說明

| 模組                | 職責                           | 技術                      |
| ------------------- | ------------------------------ | ------------------------- |
| **Video Capture**   | 攝影機串流擷取、幀率控制       | OpenCV                    |
| **Rolling Buffer**  | 環形緩衝區，保留最近 10 秒畫面 | collections.deque         |
| **YOLOv8 Detector** | 偵測畫面中的人體 bbox          | Ultralytics               |
| **Rule Engine**     | 分析 bbox 變化判斷跌倒         | 純 Python                 |
| **Delay Confirm**   | 延遲確認，減少誤報             | 狀態機 + Observer Pattern |
| **Clip Recorder**   | 錄製事件前後影片片段           | OpenCV / FFmpeg           |
| **Event Logger**    | 事件與 metadata 持久化         | SQLite                    |
| **Notifier**        | 發送 LINE 推播通知             | LINE Notify API           |
| **Data Lifecycle**  | 影片特徵化、清理、雲端同步     | MediaPipe + 排程          |

### 資料流摘要

```
Camera Frame
    ↓
Rolling Buffer（持續儲存最近 10 秒）
    ↓
YOLO 偵測人體 bbox
    ↓
Rule Engine 計算長寬比（閾值 1.3）
    ↓ (aspect ratio < 1.3)
啟動 Delay Confirm (3秒倒數)
    ↓ (未站起)
觸發事件 ──→ 從 Rolling Buffer 擷取 t-5 ~ t+5 秒
          ──→ 儲存影片片段至 clips/
          ──→ 寫入 SQLite log
          ──→ 發送 LINE 通知
```

---

## 4. Delay Confirm 核心邏輯

### 狀態機設計

```
         ┌────────────────────────────────────────┐
         │                                        │
         ↓                                        │
    ┌─────────┐   偵測到異常    ┌───────────┐     │ 恢復站立
    │ NORMAL  │ ──────────────→ │ SUSPECTED │ ────┘
    └─────────┘                 └─────┬─────┘
         ↑                            │
         │                            │ 超過延遲時間
         │                            │ 且仍未恢復
         │                            ↓
         │                     ┌─────────────┐
         │  恢復站立           │  CONFIRMED  │ ──→ 觸發通知
         └─────────────────────┴─────────────┘
                                      │
                                      ↓
                               持續監測，定期重複通知
```

### 狀態定義與轉換條件

| 狀態          | 定義             | 進入條件            | 離開條件       |
| ------------- | ---------------- | ------------------- | -------------- |
| **NORMAL**    | 正常監測中       | 初始狀態 / 恢復後   | 偵測到跌倒特徵 |
| **SUSPECTED** | 疑似跌倒，觀察中 | bbox 長寬比 < 1.3   | 恢復 or 超時   |
| **CONFIRMED** | 確認跌倒         | SUSPECTED 超過 3 秒 | 恢復站立       |

### Observer Pattern 實作

```python
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

class FallState(Enum):
    NORMAL = "normal"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"

@dataclass
class FallEvent:
    event_id: str
    confirmed_at: float          # 確認時間戳
    last_notified_at: float      # 上次通知時間
    notification_count: int      # 通知次數

class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...

class DelayConfirm:
    def __init__(self, delay_sec: float = 3.0):
        self.state = FallState.NORMAL
        self.delay_sec = delay_sec
        self.suspected_since: float | None = None
        self.current_event: FallEvent | None = None
        self.observers: list[FallEventObserver] = []

        # 事件合併設定
        self.same_event_window: float = 60.0   # 60秒內算同一事件
        self.re_notify_interval: float = 120.0  # 每2分鐘重複通知

    def add_observer(self, observer: FallEventObserver) -> None:
        self.observers.append(observer)

    def update(self, is_fallen: bool, current_time: float) -> FallState:
        match self.state:
            case FallState.NORMAL:
                if is_fallen:
                    self.state = FallState.SUSPECTED
                    self.suspected_since = current_time

            case FallState.SUSPECTED:
                if not is_fallen:
                    self._reset()
                elif current_time - self.suspected_since >= self.delay_sec:
                    self._confirm_fall(current_time)

            case FallState.CONFIRMED:
                if not is_fallen:
                    self._recover(current_time)
                else:
                    self._check_re_notify(current_time)

        return self.state

    def _confirm_fall(self, current_time: float) -> None:
        if (self.current_event and
            current_time - self.current_event.confirmed_at < self.same_event_window):
            return  # 同一事件，不重複觸發

        self.state = FallState.CONFIRMED
        self.current_event = FallEvent(
            event_id=f"evt_{int(current_time)}",
            confirmed_at=current_time,
            last_notified_at=current_time,
            notification_count=1
        )
        for observer in self.observers:
            observer.on_fall_confirmed(self.current_event)

    def _check_re_notify(self, current_time: float) -> None:
        """持續躺著，定期重複通知"""
        if not self.current_event:
            return
        if current_time - self.current_event.last_notified_at >= self.re_notify_interval:
            self.current_event.last_notified_at = current_time
            self.current_event.notification_count += 1
            for observer in self.observers:
                observer.on_fall_confirmed(self.current_event)

    def _recover(self, current_time: float) -> None:
        self.state = FallState.NORMAL
        if self.current_event:
            for observer in self.observers:
                observer.on_fall_recovered(self.current_event)
        self.suspected_since = None

    def _reset(self) -> None:
        self.state = FallState.NORMAL
        self.suspected_since = None
```

### 關鍵參數

| 參數                 | 值      | 說明                             |
| -------------------- | ------- | -------------------------------- |
| `fall_threshold`     | `1.3`   | 站立時 ratio > 1.3，低於視為跌倒 |
| `delay_sec`          | `3.0`   | 延遲確認秒數（優先減少漏報）     |
| `same_event_window`  | `60.0`  | 60 秒內視為同一事件              |
| `re_notify_interval` | `120.0` | 持續躺著時，每 2 分鐘重複通知    |

---

## 5. Rolling Buffer 設計

### 目的

確保事件發生「前」的畫面也能被錄製，提供完整的事件前後影片。

### 實作

```python
from collections import deque
from dataclasses import dataclass
import numpy as np

@dataclass
class FrameData:
    timestamp: float
    frame: np.ndarray
    bbox: tuple | None

class RollingBuffer:
    def __init__(self, buffer_seconds: float = 10.0, fps: float = 15.0):
        self.max_frames = int(buffer_seconds * fps)
        self.buffer: deque[FrameData] = deque(maxlen=self.max_frames)

    def push(self, frame_data: FrameData) -> None:
        """每幀都推入，自動丟棄最舊的"""
        self.buffer.append(frame_data)

    def get_clip(
        self,
        event_time: float,
        before_sec: float = 5.0,
        after_sec: float = 5.0
    ) -> list[FrameData]:
        """取得事件前後的影片片段"""
        start_time = event_time - before_sec
        end_time = event_time + after_sec
        return [f for f in self.buffer if start_time <= f.timestamp <= end_time]
```

### 運作流程

```
時間軸：
... [t-15] [t-14] [t-13] ... [t-3] [t-2] [t-1] [t=事件] [t+1] [t+2] ...
    ←──── Rolling Buffer 持續儲存 ────→
                                        │
                                        ↓ 事件確認
                              ┌─────────────────────┐
                              │ 取出 t-5 到 t+5 秒   │
                              │ 寫入 clips/ 資料夾   │
                              └─────────────────────┘
```

### 記憶體估算

- 解析度：640x480
- FPS：15
- Buffer：10 秒
- 單幀：640 × 480 × 3 = 921KB
- 總計：921KB × 15 × 10 ≈ **135MB**

---

## 6. 專案結構

```
fds/
├── main.py                     # 程式進入點
├── pyproject.toml
├── config/
│   └── settings.yaml           # 可調參數設定檔
│
├── src/
│   ├── __init__.py
│   │
│   ├── capture/                # 影像擷取層
│   │   ├── __init__.py
│   │   ├── camera.py           # 攝影機串流擷取
│   │   └── rolling_buffer.py   # 環形緩衝區
│   │
│   ├── detection/              # 偵測層
│   │   ├── __init__.py
│   │   ├── detector.py         # YOLOv8 人體偵測
│   │   └── bbox.py             # BBox 資料結構
│   │
│   ├── analysis/               # 分析判斷層
│   │   ├── __init__.py
│   │   ├── rule_engine.py      # 長寬比規則判斷
│   │   └── delay_confirm.py    # 延遲確認狀態機
│   │
│   ├── events/                 # 事件處理層
│   │   ├── __init__.py
│   │   ├── observer.py         # Observer Protocol 定義
│   │   ├── event_logger.py     # SQLite 事件記錄
│   │   ├── clip_recorder.py    # 影片片段儲存
│   │   └── notifier.py         # LINE Notify 通知
│   │
│   ├── lifecycle/              # 資料生命週期管理
│   │   ├── __init__.py
│   │   ├── skeleton_extractor.py  # MediaPipe 骨架特徵化
│   │   ├── cleanup.py          # 過期資料清理
│   │   └── sync.py             # 雲端同步（預留）
│   │
│   └── core/                   # 核心協調
│       ├── __init__.py
│       ├── pipeline.py         # 主處理流程
│       └── config.py           # 設定檔載入
│
├── data/                       # 運行時資料（.gitignore）
│   ├── fds.db
│   ├── clips/
│   └── snapshots/
│
└── tests/
    ├── test_rule_engine.py
    ├── test_delay_confirm.py
    └── fixtures/               # 測試用影片/圖片
```

### 模組職責與介面

| 模組                | 職責               | 主要介面                               |
| ------------------- | ------------------ | -------------------------------------- |
| `camera.py`         | 攝影機連線、幀擷取 | `Camera.read() -> Frame`               |
| `rolling_buffer.py` | 環形緩衝區管理     | `RollingBuffer.push()` / `.get_clip()` |
| `detector.py`       | YOLO 人體偵測      | `Detector.detect(frame) -> list[BBox]` |
| `rule_engine.py`    | bbox 分析判斷      | `RuleEngine.is_fallen(bbox) -> bool`   |
| `delay_confirm.py`  | 狀態機 + Observer  | `DelayConfirm.update() -> FallState`   |
| `event_logger.py`   | SQLite 寫入        | `EventLogger.log(event)`               |
| `clip_recorder.py`  | 影片片段儲存       | `ClipRecorder.save(frames, event_id)`  |
| `notifier.py`       | LINE 通知          | `Notifier.send(event)`                 |
| `pipeline.py`       | 組裝與運行主迴圈   | `Pipeline.run()`                       |

### 依賴關係

```
          ┌─────────┐
          │ main.py │
          └────┬────┘
               │
               ↓
         ┌──────────┐
         │ pipeline │ ←── 載入 config
         └────┬─────┘
              │
    ┌─────────┼─────────┐
    ↓         ↓         ↓
┌────────┐ ┌──────────┐ ┌────────┐
│capture │ │detection │ │analysis│
└────────┘ └──────────┘ └───┬────┘
                            │
                            ↓
                      ┌──────────┐
                      │  events  │ (observers)
                      └──────────┘
                            │
                            ↓
                      ┌───────────┐
                      │ lifecycle │ (排程任務)
                      └───────────┘
```

---

## 7. 設定檔結構

### `config/settings.yaml`

```yaml
# 攝影機設定
camera:
  source: 0 # 攝影機索引或 RTSP URL
  fps: 15
  resolution: [640, 480]

# 偵測設定
detection:
  model: "yolov8n.pt" # 模型檔案
  confidence: 0.5
  classes: [0] # 只偵測 person

# 跌倒判斷
analysis:
  fall_threshold: 1.3 # 長寬比閾值
  delay_sec: 3.0 # 延遲確認秒數
  same_event_window: 60.0 # 同一事件判定窗口
  re_notify_interval: 120.0 # 重複通知間隔

# 影片錄製
recording:
  buffer_seconds: 10 # Rolling buffer 長度
  clip_before_sec: 5 # 事件前錄製
  clip_after_sec: 5 # 事件後錄製

# 通知
notification:
  line_token: "${LINE_NOTIFY_TOKEN}" # 環境變數注入
  enabled: true

# 資料生命週期
lifecycle:
  clip_retention_days: 7 # 原始影片保留天數
  skeleton_retention_days: 30 # 骨架資料保留天數
```

---

## 8. 錯誤處理

### 核心原則

跌倒偵測是安全關鍵系統，錯誤處理必須確保「寧可誤報，不可漏報」。

### 錯誤分類與處理策略

| 錯誤類型       | 範例                       | 處理策略                         |
| -------------- | -------------------------- | -------------------------------- |
| **致命錯誤**   | 攝影機斷線、模型載入失敗   | 立即通知維護者，系統進入安全模式 |
| **可恢復錯誤** | 單幀偵測失敗、網路暫時中斷 | 記錄 log，重試，不中斷主流程     |
| **業務異常**   | 無法發送 LINE 通知         | 降級處理（本地警報），持續重試   |

### 攝影機錯誤處理

```python
class CameraError(Exception):
    """攝影機相關錯誤"""

class Camera:
    def __init__(self, source: int | str, max_retries: int = 3):
        self.source = source
        self.max_retries = max_retries
        self._consecutive_failures = 0

    def read(self) -> Frame | None:
        try:
            frame = self._capture.read()
            self._consecutive_failures = 0
            return frame
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(f"Frame capture failed: {e}")

            if self._consecutive_failures >= self.max_retries:
                raise CameraError("攝影機連續失敗，需要人工介入")
            return None  # 跳過此幀，繼續運作
```

### 通知降級處理

```python
class Notifier(FallEventObserver):
    def __init__(self, config: NotificationConfig):
        self.config = config
        self._pending_queue: deque[FallEvent] = deque()

    def on_fall_confirmed(self, event: FallEvent) -> None:
        try:
            self._send_line_notify(event)
        except NetworkError:
            self._pending_queue.append(event)
            self._trigger_local_alarm()
            logger.error(f"通知發送失敗，已加入重試佇列: {event.event_id}")

    def retry_pending(self) -> None:
        """定期呼叫，重試失敗的通知"""
        while self._pending_queue:
            event = self._pending_queue[0]
            try:
                self._send_line_notify(event, is_retry=True)
                self._pending_queue.popleft()
            except NetworkError:
                break
```

### 系統健康監控

```python
@dataclass
class HealthStatus:
    camera_ok: bool
    detector_ok: bool
    storage_ok: bool
    network_ok: bool
    last_check: float

    @property
    def is_healthy(self) -> bool:
        return all([self.camera_ok, self.detector_ok, self.storage_ok])

    @property
    def can_notify(self) -> bool:
        return self.network_ok
```

健康檢查機制：

- 每 60 秒檢查一次系統狀態
- 攝影機/偵測器異常 → 通知維護者
- 儲存空間 < 1GB → 觸發緊急清理

---

## 9. 測試策略

### 測試金字塔

```
        ╱╲
       ╱  ╲        E2E Tests
      ╱────╲       (手動 + 少量自動化)
     ╱      ╲
    ╱────────╲     Integration Tests
   ╱          ╲    (模組組合測試)
  ╱────────────╲
 ╱              ╲  Unit Tests
╱────────────────╲ (核心邏輯測試)
```

### Unit Tests

```python
# tests/test_delay_confirm.py
import pytest
from src.analysis.delay_confirm import DelayConfirm, FallState

class TestDelayConfirm:
    def test_normal_to_suspected_on_fall(self):
        """偵測到跌倒應進入 SUSPECTED 狀態"""
        dc = DelayConfirm(delay_sec=3.0)
        state = dc.update(is_fallen=True, current_time=0.0)
        assert state == FallState.SUSPECTED

    def test_suspected_to_normal_on_recovery(self):
        """站起來應回到 NORMAL"""
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        state = dc.update(is_fallen=False, current_time=1.0)
        assert state == FallState.NORMAL

    def test_suspected_to_confirmed_after_delay(self):
        """超過延遲時間應確認跌倒"""
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=2.0)
        state = dc.update(is_fallen=True, current_time=3.1)
        assert state == FallState.CONFIRMED

    def test_same_event_window_deduplication(self):
        """同一事件窗口內不應重複觸發"""
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0, same_event_window=60.0)
        dc.add_observer(observer)

        # 第一次跌倒
        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)  # CONFIRMED

        # 短暫站起又跌倒（同一事件窗口內）
        dc.update(is_fallen=False, current_time=10.0)
        dc.update(is_fallen=True, current_time=15.0)
        dc.update(is_fallen=True, current_time=19.0)

        assert observer.confirm_count == 1  # 只觸發一次


# tests/test_rule_engine.py
class TestRuleEngine:
    @pytest.mark.parametrize("width,height,expected", [
        (100, 200, False),   # ratio=2.0，站立
        (100, 130, False),   # ratio=1.3，邊界站立
        (100, 120, True),    # ratio=1.2，跌倒
        (200, 100, True),    # ratio=0.5，明顯跌倒
    ])
    def test_fall_threshold(self, width, height, expected):
        engine = RuleEngine(fall_threshold=1.3)
        bbox = BBox(x=0, y=0, width=width, height=height)
        assert engine.is_fallen(bbox) == expected
```

### Integration Tests

```python
# tests/integration/test_detection_pipeline.py
def test_fall_detection_end_to_end():
    """使用測試影片驗證完整偵測流程"""
    test_video = Path("tests/fixtures/fall_sample.mp4")

    events_captured = []

    pipeline = Pipeline(
        config=test_config,
        observers=[MockObserver(events_captured.append)]
    )
    pipeline.run_on_video(test_video)

    assert len(events_captured) >= 1
    assert events_captured[0].detection_result == "fall_confirmed"
```

### 測試資料

```
tests/fixtures/
├── fall_sample.mp4          # 跌倒場景
├── normal_activity.mp4      # 正常活動（彎腰、坐下）
├── edge_cases/
│   ├── partial_occlusion.mp4
│   ├── multiple_people.mp4
│   └── low_light.mp4
```

---

## 10. Phase 1 實作優先順序

1. **核心偵測流程**

   - Camera + Rolling Buffer
   - YOLOv8 Detector
   - Rule Engine (aspect ratio)
   - Delay Confirm 狀態機

2. **事件處理**

   - Event Logger (SQLite)
   - Clip Recorder

3. **通知整合**

   - LINE Notify

4. **資料生命週期**（可延後）
   - Skeleton Extractor
   - Cleanup
   - Cloud Sync
