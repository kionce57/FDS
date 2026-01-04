"""
測試腳本：使用影片檔案測試跌倒偵測系統
用法: uv run python -m scripts.test_with_video <video_path>
   或: fds-test-video <video_path>  (安裝後)
"""

import argparse
import logging
import time

import cv2
import numpy as np

from src.analysis.delay_confirm import DelayConfirm, FallState
from src.analysis.rule_engine import RuleEngine
from src.analysis.pose_rule_engine import PoseRuleEngine
from src.capture.rolling_buffer import FrameData, RollingBuffer
from src.detection.detector import Detector, PoseDetector
from src.detection.bbox import BBox
from src.detection.skeleton import Skeleton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def draw_bbox(frame: np.ndarray, bbox: BBox | None, state: FallState) -> np.ndarray:
    """在畫面上繪製 bounding box 和狀態"""
    if bbox is None:
        return frame

    # 根據狀態選擇顏色
    colors = {
        FallState.NORMAL: (0, 255, 0),  # 綠色
        FallState.SUSPECTED: (0, 255, 255),  # 黃色
        FallState.CONFIRMED: (0, 0, 255),  # 紅色
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


def draw_skeleton(frame: np.ndarray, skeleton: Skeleton | None, state: FallState) -> np.ndarray:
    """在畫面上繪製骨架和狀態"""
    if skeleton is None:
        return frame

    colors = {
        FallState.NORMAL: (0, 255, 0),
        FallState.SUSPECTED: (0, 255, 255),
        FallState.CONFIRMED: (0, 0, 255),
    }
    color = colors.get(state, (255, 255, 255))

    # 繪製關鍵點
    for i in range(17):
        x, y, vis = skeleton.keypoints[i]
        if vis > 0.3:
            cv2.circle(frame, (int(x), int(y)), 5, color, -1)

    # 繪製連接線（軀幹）
    connections = [
        (5, 6),  # shoulders
        (5, 11),  # left shoulder to hip
        (6, 12),  # right shoulder to hip
        (11, 12),  # hips
        (11, 13),  # left hip to knee
        (12, 14),  # right hip to knee
        (13, 15),  # left knee to ankle
        (14, 16),  # right knee to ankle
    ]

    for i, j in connections:
        pt1 = skeleton.keypoints[i]
        pt2 = skeleton.keypoints[j]
        if pt1[2] > 0.3 and pt2[2] > 0.3:
            cv2.line(frame, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), color, 2)

    # 顯示狀態和軀幹角度
    text = f"{state.value} (angle: {skeleton.torso_angle:.1f}°)"
    cv2.putText(frame, text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return frame


def test_video(
    video_path: str,
    show_window: bool = True,
    use_pose: bool = False,
    enable_smoothing: bool = False,
) -> int:
    """使用影片測試跌倒偵測"""

    # 開啟影片
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"無法開啟影片: {video_path}")
        return 1

    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    logger.info(f"影片 FPS: {fps}")
    logger.info(f"偵測模式: {'Pose (骨架)' if use_pose else 'BBox (長寬比)'}")
    if use_pose and enable_smoothing:
        logger.info("Keypoint 平滑: 已啟用 (One Euro Filter)")

    # 初始化模組
    if use_pose:
        detector = PoseDetector(model_path="yolo11s-pose.pt", confidence=0.5)
        rule_engine = PoseRuleEngine(
            torso_angle_threshold=60.0,
            enable_smoothing=enable_smoothing,
        )
    else:
        detector = Detector(model_path="yolo11n.pt", confidence=0.5, classes=[0])
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

            # 偵測
            detections = detector.detect(frame)
            detection = detections[0] if detections else None

            # 判斷是否跌倒（Pose 模式需傳入 timestamp 以支援 smoothing）
            if use_pose:
                is_fallen = rule_engine.is_fallen(detection, timestamp=current_time)
            else:
                is_fallen = rule_engine.is_fallen(detection)

            # 更新狀態機
            state = delay_confirm.update(is_fallen=is_fallen, current_time=current_time)

            # 儲存到 buffer
            if use_pose:
                bbox_tuple = None  # Pose mode doesn't track bbox
            else:
                bbox_tuple = (
                    (detection.x, detection.y, detection.width, detection.height)
                    if detection
                    else None
                )

            rolling_buffer.push(
                FrameData(
                    timestamp=current_time,
                    frame=frame.copy(),
                    bbox=bbox_tuple,
                )
            )

            # 記錄狀態變化
            if state == FallState.SUSPECTED:
                if use_pose and detection:
                    logger.warning(
                        f"[{current_time:.1f}s] 疑似跌倒! angle={detection.torso_angle:.1f}°"
                    )
                elif detection:
                    logger.warning(
                        f"[{current_time:.1f}s] 疑似跌倒! ratio={detection.aspect_ratio:.2f}"
                    )
            elif state == FallState.CONFIRMED:
                logger.error(f"[{current_time:.1f}s] ⚠️ 跌倒確認!")

            # 繪製視覺化
            if show_window:
                if use_pose:
                    display_frame = draw_skeleton(frame.copy(), detection, state)
                else:
                    display_frame = draw_bbox(frame.copy(), detection, state)

                # 顯示資訊
                mode_text = "POSE" if use_pose else "BBOX"
                info_text = f"[{mode_text}] Frame: {frame_count} | Time: {current_time:.1f}s | State: {state.value}"
                cv2.putText(
                    display_frame,
                    info_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                cv2.imshow("Fall Detection Test", display_frame)

        # 鍵盤控制
        if show_window:
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("p"):
                paused = not paused
                logger.info("暫停" if paused else "繼續")

    elapsed = time.time() - start_time
    logger.info(f"處理完成: {frame_count} 幀, 耗時 {elapsed:.1f} 秒")

    cap.release()
    if show_window:
        cv2.destroyAllWindows()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="使用影片檔案測試跌倒偵測系統")
    parser.add_argument("video", help="影片檔案路徑")
    parser.add_argument("--no-window", action="store_true", help="不顯示視窗（純 CLI 模式）")
    parser.add_argument(
        "--use-pose", action="store_true", help="使用骨架姿態偵測（預設使用 BBox 長寬比）"
    )
    parser.add_argument(
        "--enable-smoothing",
        action="store_true",
        help="啟用 Keypoint 平滑 (One Euro Filter)，減少抖動 (僅 Pose 模式)",
    )
    args = parser.parse_args()

    return test_video(
        args.video,
        show_window=not args.no_window,
        use_pose=args.use_pose,
        enable_smoothing=args.enable_smoothing,
    )


if __name__ == "__main__":
    exit(main())
