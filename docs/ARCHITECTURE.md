# FDS 系統架構文件

> Fall Detection System 開發者學習指南
>
> 透過 C4 Model、Sequence Diagram 與 SA/SD 分析理解系統設計

---

## 目錄

1. [系統架構總覽](#系統架構總覽)
2. [四層架構設計](#四層架構設計)
3. [C4 Model](#c4-model)
4. [Sequence Diagrams](#sequence-diagrams)
5. [SA/SD 分析](#sasd-分析)
6. [設計模式](#設計模式)
7. [學習路徑建議](#學習路徑建議)

---

## 系統架構總覽

FDS 採用 **四層架構設計**，將系統職責清晰分離：

```mermaid
graph TD
    subgraph Input_Layer ["INPUT LAYER"]
        direction TB
        Cam["1. Camera / Video Source<br/>USB/RTSP/File"]
        Ingest["2. Ingest / Capture<br/>接收影像串流"]
        Cam --> Ingest
    end

    subgraph Processing_Layer ["PROCESSING LAYER<br/>Edge Inference"]
        direction TB
        YOLO["3. Person Detection<br/>YOLOv11: BBox & Conf"]
        Tracker["4. Object Tracking<br/>ID Maintenance"]
        FeatBuilder["5. Feature Builder<br/>滑動視窗聚合 30-90 frames"]
        Buffer[("6. Rolling Buffer<br/>環形緩衝區<br/>保留前後 N 秒影像")]

        Ingest ==> YOLO
        YOLO <==> Tracker
        Tracker ==> FeatBuilder
        Ingest -.-> Buffer
    end

    subgraph Analysis_Layer ["ANALYSIS LAYER<br/>Decision & Event"]
        direction TB
        Classifier["7. Temporal Event Classifier<br/>時間窗分類器<br/>Output: P_fall + confidence"]
        StateMachine["8. Decision & State Machine<br/>Delay Confirm / Logic<br/>Normal→Suspected→Confirmed"]

        FeatBuilder ==> Classifier
        Classifier ==> StateMachine
    end

    subgraph Output_Layer ["OUTPUT LAYER<br/>Server Side"]
        direction TB
        Observer["9. Observer / Publisher<br/>事件發布介面"]
        Notifier["10. Notifier<br/>LINE / Email"]
        ClipRec["11. Clip Recorder<br/>MP4 Evidence"]
        APIServer["12. API Server<br/>FastAPI"]
        DB[("13. Database<br/>SQLite<br/>Events/Logs/Settings")]
        Dash["14. Dashboard<br/>Web UI"]

        StateMachine == "Event Confirmed" ==> Observer
        Observer ==> Notifier
        Observer ==> ClipRec
        Observer ==> APIServer
        Buffer -. "Extract N secs" .-> ClipRec
        ClipRec --> DB
        APIServer <--> DB
        Dash <--> APIServer
    end
```

---

## 四層架構設計

### Layer 1: INPUT LAYER

| 元件 | 職責 | 實作 |
|------|------|------|
| **Camera / Video Source** | 提供影像來源 | USB Camera、RTSP、影片檔案 |
| **Ingest / Capture** | 接收並解碼影像串流 | `capture/camera.py` |

### Layer 2: PROCESSING LAYER (Edge Inference)

| 元件 | 職責 | 實作 |
|------|------|------|
| **Person Detection** | YOLO11 偵測人體骨架 | `detection/detector.py` |
| **Object Tracking** | 維護人員 ID 連續性 | `detection/tracker.py` |
| **Feature Builder** | 聚合時間窗特徵 (30-90 frames) | `analysis/feature_builder.py` |
| **Rolling Buffer** | 環形緩衝區，保留事件前後影像 | `capture/rolling_buffer.py` |

### Layer 3: ANALYSIS LAYER (Decision & Event)

| 元件 | 職責 | 實作 |
|------|------|------|
| **Temporal Event Classifier** | 時間序列分類，輸出跌倒機率 | `analysis/classifier.py` |
| **Decision & State Machine** | 狀態機管理 (Normal→Suspected→Confirmed) | `analysis/delay_confirm.py` |

### Layer 4: OUTPUT LAYER (Server Side)

| 元件 | 職責 | 實作 |
|------|------|------|
| **Observer / Publisher** | 事件發布介面，廣播給所有訂閱者 | `events/observer.py` |
| **Notifier** | LINE / Email 通知（直接訂閱 Observer） | `events/notifier.py` |
| **Clip Recorder** | 擷取事件影片存檔（直接訂閱 Observer） | `events/clip_recorder.py` |
| **API Server** | FastAPI HTTP 服務（直接訂閱 Observer） | `web/app.py` |
| **Database** | SQLite 事件儲存 | `data/fds.db` |
| **Dashboard** | Web UI（透過 API Server 存取） | `web/templates/` |

### Observer Pattern 訂閱關係

```
Observer (Publisher)
    ├──► Notifier      ← 發送 LINE/Email 通知
    ├──► ClipRecorder  ← 擷取事件影片
    └──► APIServer     ← 寫入 DB + WebSocket 推播 Dashboard
```

**設計優勢**：
- 三個訂閱者**並行獨立**運作
- API Server **不再負責觸發通知**，只服務 Dashboard
- 即使 API Server 掛掉，通知仍能發送

---

## 雙管線架構（居家監控 App）

> **狀態**：規劃中，待 Phase 3 實作
> **設計文件**：[2026-01-06-home-monitoring-app-draft.md](./plans/2026-01-06-home-monitoring-app-draft.md)

為支援 **24/7 即時影像監控** + **事件偵測通知**，系統將擴展為雙管線架構：

```mermaid
graph TD
    subgraph Input["INPUT LAYER"]
        Camera["Camera"]
        Capture["Capture<br/>(共用)"]
        Camera --> Capture
    end

    subgraph Pipelines["DUAL PIPELINE"]
        subgraph P1["Pipeline 1: 即時串流"]
            StreamServer["Stream Server<br/>MJPEG/WebSocket"]
        end
        
        subgraph P2["Pipeline 2: 事件偵測"]
            YOLO["YOLO Detection"]
            Classifier["Classifier"]
            StateMachine["State Machine"]
            Observer["Observer"]
        end
    end

    subgraph Output["OUTPUT LAYER"]
        API["API Server<br/>FastAPI"]
        Notifier["Notifier"]
        Tunnel["Cloudflare Tunnel"]
        App["📱 Mobile App"]
    end

    Capture --> StreamServer
    Capture --> YOLO
    YOLO --> Classifier
    Classifier --> StateMachine
    StateMachine --> Observer

    StreamServer --> API
    Observer --> Notifier
    Observer --> API
    API --> Tunnel
    Tunnel --> App
```

### 設計原則

| 原則 | 說明 |
|------|------|
| **雙管線分離** | 串流與偵測各自獨立 Pipeline |
| **共用 Capture** | 兩條 Pipeline 透過 Queue 訂閱同一 Capture |
| **計算本地化** | AI 推論在 Edge 端執行 |
| **前後端分離** | App 透過 REST API + WebSocket 通訊 |

### Capture 共用機制

為避免 Frame 競爭，採用 **Broadcaster Pattern**：

```
Camera ──► Capture ──► Broadcaster
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Queue[1]      Queue[2]     Queue[N]
         (串流)        (偵測)       (未來...)
```

詳細設計參考：[Camera Manager 設計草案](./plans/2026-01-06-camera-manager-draft.md)

### 對外暴露：Cloudflare Tunnel

- **Dashboard 遠端存取**：透過 Cloudflare Tunnel 暴露 FastAPI
- **LINE/Email 通知**：直接 POST（不經過 Tunnel）
- **影片不外傳**：MP4 保留本地，僅傳輸 metadata

詳細設計參考：[Cloudflare Tunnel 整合設計](./plans/2026-01-06-cloudflare-tunnel-integration.md)

---

## C4 Model

### Level 1: System Context Diagram

```mermaid
C4Context
    title FDS System Context Diagram

    Person(user, "家屬/照護者", "接收跌倒通知，查看歷史事件")
    Person(elderly, "長者", "被監測對象")

    System(fds, "FDS Fall Detection System", "即時偵測跌倒，發送警報，記錄事件")

    System_Ext(camera, "IP Camera / USB Camera", "提供即時影像串流")
    System_Ext(line, "LINE Notify API", "推播通知服務")

    Rel(camera, fds, "RTSP/USB 影像串流")
    Rel(fds, line, "HTTP POST 通知")
    Rel(fds, user, "LINE 推播 / Web Dashboard")
    Rel(elderly, camera, "被攝影機監測")
```

**解讀重點：**

- FDS 是一個 **邊緣運算系統**，部署在本地設備
- 對外依賴：攝影機（輸入）、LINE API（通知）
- 使用者透過 **LINE 通知** 或 **Web Dashboard** 與系統互動

---

### Level 2: Container Diagram

```mermaid
C4Container
    title FDS Container Diagram

    Person(user, "家屬/照護者")

    Container_Boundary(fds, "FDS System") {
        Container(core, "Core Pipeline", "Python", "主流程協調器，串接所有模組")
        Container(web, "Web Server", "FastAPI", "Dashboard API 與 Web UI")
        ContainerDb(sqlite, "SQLite", "Database", "事件 metadata 儲存")
        Container(clips, "Clip Storage", "File System", "影片片段儲存")
    }

    System_Ext(camera, "Camera")
    System_Ext(line, "LINE Notify")

    Rel(camera, core, "影像擷取")
    Rel(core, sqlite, "讀寫事件")
    Rel(core, clips, "儲存影片")
    Rel(core, line, "發送通知")
    Rel(web, sqlite, "查詢事件")
    Rel(user, web, "存取 Dashboard")
    Rel(user, line, "接收通知")
```

---

### Level 3: Component Diagram

```mermaid
C4Component
    title FDS Core Pipeline Components

    Container_Boundary(core, "Core Pipeline") {
        Component(camera, "Camera", "capture/camera.py", "攝影機串流擷取")
        Component(buffer, "RollingBuffer", "capture/rolling_buffer.py", "N秒環形緩衝區")
        Component(detector, "PoseDetector", "detection/detector.py", "YOLO11 姿態偵測")
        Component(tracker, "Tracker", "detection/tracker.py", "人員追蹤")
        Component(classifier, "Classifier", "analysis/classifier.py", "時間序列分類")
        Component(delay, "DelayConfirm", "analysis/delay_confirm.py", "狀態機")
        Component(observer, "Observer", "events/observer.py", "事件發布")
        Component(logger, "EventLogger", "events/event_logger.py", "SQLite 事件記錄")
        Component(recorder, "ClipRecorder", "events/clip_recorder.py", "MP4 影片儲存")
        Component(notifier, "LineNotifier", "events/notifier.py", "LINE API 通知")
        Component(pipeline, "Pipeline", "core/pipeline.py", "主流程協調器")
    }

    Rel(pipeline, camera, "read()")
    Rel(pipeline, buffer, "push()")
    Rel(pipeline, detector, "detect()")
    Rel(pipeline, classifier, "classify()")
    Rel(pipeline, delay, "update()")
    Rel(delay, observer, "publish()")
    Rel(observer, logger, "on_fall_confirmed()")
    Rel(observer, notifier, "on_fall_confirmed()")
    Rel(observer, recorder, "on_fall_confirmed()")
    Rel(buffer, recorder, "get_clip()")
```

---

## Sequence Diagrams

### 主流程：跌倒偵測

```mermaid
sequenceDiagram
    autonumber
    participant Cam as Camera
    participant Pip as Pipeline
    participant Det as PoseDetector (YOLO11)
    participant Feat as FeatureBuilder
    participant Cls as Classifier
    participant SM as StateMachine
    participant Obs as Observer
    participant Buf as RollingBuffer

    loop Every Frame
        Cam->>Pip: read() → frame
        Pip->>Buf: push(frame)
        Pip->>Det: detect(frame)
        Det-->>Pip: Skeleton[]
        Pip->>Feat: update(skeleton)
        Feat-->>Pip: features (if window ready)
        Pip->>Cls: classify(features)
        Cls-->>Pip: P_fall, confidence
        Pip->>SM: update(P_fall)

        alt P_fall > threshold 且持續 N 秒
            SM->>Obs: publish(FallEvent)
            par Parallel Notification
                Obs->>Notifier: on_fall_confirmed()
            and
                Obs->>ClipRecorder: on_fall_confirmed()
            and
                Obs->>APIServer: on_fall_confirmed()
            end
        end
    end
```

### Observer Pattern 事件通知

```mermaid
sequenceDiagram
    autonumber
    participant SM as StateMachine
    participant Obs as Observer
    participant NT as Notifier
    participant CR as ClipRecorder
    participant API as APIServer
    participant DB as Database
    participant Dash as Dashboard

    SM->>Obs: publish(FallEvent)

    par Observer broadcasts to all subscribers
        Obs->>NT: on_fall_confirmed(event)
        NT->>NT: POST to LINE API
    and
        Obs->>CR: on_fall_confirmed(event)
        CR->>CR: Extract clip from Buffer
        CR->>DB: Save clip path
    and
        Obs->>API: on_fall_confirmed(event)
        API->>DB: INSERT event
        API->>Dash: WebSocket push
    end
```

### Post-Event Recording Flow

> 延遲錄製機制：事件確認後等待 `clip_after_sec` 秒，確保擷取事件後的影像

```mermaid
sequenceDiagram
    autonumber
    participant SM as StateMachine
    participant Obs as Observer
    participant CR as ClipRecorder
    participant Timer as threading.Timer
    participant Buf as RollingBuffer
    participant DB as Database

    SM->>Obs: publish(FallEvent) @ t₀
    Obs->>CR: on_fall_confirmed(event)
    CR->>Timer: schedule(_save_clip, delay=clip_after_sec)
    Note over Timer: 等待 clip_after_sec 秒<br/>（預設 5 秒）

    loop Main Thread 繼續運作
        Note over Buf: push(frame) 持續接收影格
    end

    Timer->>CR: _save_clip(event) @ t₀+clip_after_sec
    CR->>Buf: get_clip(before=5, after=5)
    Buf-->>CR: frames[t₀-5 ~ t₀+5]
    CR->>CR: save() → MP4
    CR->>DB: update_clip_path()
```

**設計重點：**

| 項目 | 說明 |
|------|------|
| **延遲機制** | `threading.Timer` 延遲 `clip_after_sec` 秒後執行錄製 |
| **Buffer 容量** | `buffer_seconds` >= `delay_sec` + `clip_before_sec` + `clip_after_sec` + margin |
| **Thread Safety** | `RollingBuffer` 使用 `threading.Lock` 保護並發存取 |
| **Graceful Shutdown** | `ClipRecorder.shutdown()` 取消所有 pending timers |

---

### State Machine 狀態轉換

```mermaid
stateDiagram-v2
    [*] --> NORMAL

    NORMAL --> SUSPECTED : P_fall > threshold
    SUSPECTED --> NORMAL : P_fall < threshold<br/>(reset)
    SUSPECTED --> CONFIRMED : 持續 N 秒
    CONFIRMED --> NORMAL : P_fall < threshold<br/>(recover)
    CONFIRMED --> CONFIRMED : 每 120 秒<br/>re-notify

    note right of NORMAL : 預設狀態
    note right of SUSPECTED : 延遲確認中<br/>(避免誤報)
    note right of CONFIRMED : Observer.publish()<br/>→ 通知所有訂閱者
```

---

## SA/SD 分析

### Data Flow Diagram

```mermaid
flowchart LR
    subgraph Input
        CAM[🎥 Camera]
    end

    subgraph Processing
        DET[🔍 PoseDetector<br/>YOLO11]
        TRACK[🏃 Tracker]
        FEAT[📊 FeatureBuilder]
    end

    subgraph Analysis
        CLS[🧠 Classifier<br/>Temporal Model]
        SM[⏱️ StateMachine<br/>Delay Confirm]
    end

    subgraph Output
        OBS[📢 Observer]
        DB[(💾 SQLite)]
        CLIP[📹 Clip Storage]
        LINE[📱 LINE Notify]
        DASH[🖥️ Dashboard]
    end

    CAM -->|frame| DET
    DET -->|Skeleton| TRACK
    TRACK -->|tracked| FEAT
    FEAT -->|features| CLS
    CLS -->|P_fall| SM
    SM -->|FallEvent| OBS
    OBS -->|parallel| DB
    OBS -->|parallel| CLIP
    OBS -->|parallel| LINE
    OBS -->|parallel| DASH
```

### 模組職責與邊界

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                         src/                                           │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│   capture/  │  detection/ │  analysis/  │   events/   │    web/     │      core/      │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ Camera      │ Detector    │ Classifier  │ Observer    │ API Server  │ Config          │
│ RollingBuf  │ Tracker     │ StateMachine│ EventLogger │ Dashboard   │ Pipeline        │
│             │             │ FeatureBldr │ Notifier    │ WebSocket   │                 │
│             │             │             │ ClipRecord  │             │                 │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ INPUT       │ PROCESSING  │ ANALYSIS    │ OUTPUT      │ OUTPUT      │ ORCHESTRATION   │
│ LAYER       │ LAYER       │ LAYER       │ LAYER       │ LAYER       │                 │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘

                                 ↓ 依賴方向 ↓

       capture ← detection ← analysis ← events ← web ← core(Pipeline)
```

---

## 設計模式

### 1. Observer Pattern

**位置**：`src/events/observer.py`

```python
class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...
```

**訂閱者**：
- `Notifier` - LINE/Email 通知
- `ClipRecorder` - 影片擷取
- `APIServer` - DB 寫入 + WebSocket 推播

**設計優勢**：
- 新增訂閱者無需修改 Observer
- 各訂閱者獨立運作，互不影響
- 符合開放封閉原則 (OCP)

---

### 2. State Machine Pattern

**位置**：`src/analysis/delay_confirm.py`

```python
class FallState(Enum):
    NORMAL = "normal"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
```

**狀態轉換**：

| 轉換 | 條件 | 動作 |
|------|------|------|
| NORMAL → SUSPECTED | P_fall > threshold | - |
| SUSPECTED → CONFIRMED | 持續 N 秒 | Observer.publish() |
| CONFIRMED → NORMAL | P_fall < threshold | Observer.on_recovered() |

---

### 3. Pipeline Pattern

**位置**：`src/core/pipeline.py`

```python
def process_frame(self, frame, current_time) -> FallState:
    skeletons = self.detector.detect(frame)       # Step 1
    self.tracker.update(skeletons)                # Step 2
    features = self.feature_builder.update()      # Step 3
    p_fall = self.classifier.classify(features)   # Step 4
    state = self.state_machine.update(p_fall)     # Step 5
    return state
```

---

## 學習路徑建議

```mermaid
graph TD
    A[1. 閱讀 README.md] --> B[2. 理解四層架構]
    B --> C[3. 追蹤 Pipeline.run]
    C --> D[4. 深入 StateMachine]
    D --> E[5. 理解 Observer 通知機制]
    E --> F[6. 探索 Web Dashboard]

    style A fill:#e1f5fe
    style F fill:#c8e6c9
```

| 步驟 | 檔案 | 學習重點 |
|------|------|----------|
| 1 | `README.md` | 功能概覽、快速開始 |
| 2 | 本文件 | 四層架構、系統邊界 |
| 3 | `src/core/pipeline.py` | 主流程、元件串接 |
| 4 | `src/analysis/delay_confirm.py` | 狀態機設計 |
| 5 | `src/events/observer.py` | Observer 模式應用 |
| 6 | `src/web/` | FastAPI + Dashboard |

---

_文件更新日期：2026-01-06_
