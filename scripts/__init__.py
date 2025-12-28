"""
測試腳本：使用影片檔案測試跌倒偵測系統
用法: uv run python -m scripts.test_with_video <video_path>
   或: fds-test-video <video_path>  (安裝後)
"""
import argparse
import logging
import time

import cv2

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.detection.detector import Detector
from src.detection.bbox import BBox

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def draw_bbox(frame, bbox: BBox | None, state: FallState):
    """在畫面上繪製 bounding box 和狀態"""
    if bbox is None:
        return frame
    
    # 根據狀態選擇顏色
    colors = {
        FallState.NORMAL: (0, 255, 0),      # 綠色
        FallState.SUSPECTED: (0, 255, 255),  # 黃色
        FallState.CONFIRMED: (0, 0, 255),    # 紅色
    }
    color = colors.get(state, (255, 255, 255))
    
    # 繪製 bbox
    cv2.rectangle(
        frame,
        (bbox.x, bbox.y),
        (bbox.x + bbox.width, bbox.y + bbox.height),
        color,
        2,
    )
    
    # 顯示狀態和長寬比
    text = f"{state.value} (ratio: {bbox.aspect_ratio:.2f})"
    cv2.putText(frame, text, (bbox.x, bbox.y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    return frame


def test_video(video_path: str, show_window: bool = True):
    """使用影片測試跌倒偵測"""
    
    # 開啟影片
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"無法開啟影片: {video_path}")
        return 1
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    logger.info(f"影片 FPS: {fps}")
    
    # 初始化模組
    detector = Detector(model_path="yolov8n.pt", confidence=0.5, classes=[0])
    rule_engine = RuleEngine(fall_threshold=1.3)
    delay_confirm = DelayConfirm(delay_sec=3.0)
    rolling_buffer = RollingBuffer(buffer_seconds=10.0, fps=fps)
    
    frame_count = 0
    start_time = time.time()
    
    logger.info("開始處理影片...")
    logger.info("按 'q' 退出, 按 'p' 暫停/繼續")
    
    paused = False
    
    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                logger.info("影片結束")
                break
            
            frame_count += 1
            current_time = frame_count / fps
            
            # 偵測人體
            bboxes = detector.detect(frame)
            bbox = bboxes[0] if bboxes else None
            
            # 判斷是否跌倒
            is_fallen = rule_engine.is_fallen(bbox)
            
            # 更新狀態機
            state = delay_confirm.update(is_fallen=is_fallen, current_time=current_time)
            
            # 儲存到 buffer
            bbox_tuple = (bbox.x, bbox.y, bbox.width, bbox.height) if bbox else None
            rolling_buffer.push(FrameData(
                timestamp=current_time,
                frame=frame.copy(),
                bbox=bbox_tuple,
            ))
            
            # 記錄狀態變化
            if state == FallState.SUSPECTED:
                logger.warning(f"[{current_time:.1f}s] 疑似跌倒! ratio={bbox.aspect_ratio:.2f}" if bbox else "")
            elif state == FallState.CONFIRMED:
                logger.error(f"[{current_time:.1f}s] ⚠️ 跌倒確認!")
            
            # 繪製視覺化
            if show_window:
                display_frame = draw_bbox(frame.copy(), bbox, state)
                
                # 顯示資訊
                info_text = f"Frame: {frame_count} | Time: {current_time:.1f}s | State: {state.value}"
                cv2.putText(display_frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                cv2.imshow("Fall Detection Test", display_frame)
        
        # 鍵盤控制
        if show_window:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('p'):
                paused = not paused
                logger.info("暫停" if paused else "繼續")
    
    elapsed = time.time() - start_time
    logger.info(f"處理完成: {frame_count} 幀, 耗時 {elapsed:.1f} 秒")
    
    cap.release()
    if show_window:
        cv2.destroyAllWindows()
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="使用影片檔案測試跌倒偵測系統")
    parser.add_argument("video", help="影片檔案路徑")
    parser.add_argument("--no-window", action="store_true", help="不顯示視窗（純 CLI 模式）")
    args = parser.parse_args()
    
    return test_video(args.video, show_window=not args.no_window)


if __name__ == "__main__":
    exit(main())
