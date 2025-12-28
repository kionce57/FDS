"""
骨架偵測驗證腳本：將偵測結果儲存為圖片
用法: uv run python -m scripts.save_skeleton_frames <video_path>
"""
import argparse
import logging
from pathlib import Path

import cv2
import numpy as np

from src.detection.detector import PoseDetector
from src.detection.skeleton import Skeleton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 骨架連接線定義
SKELETON_CONNECTIONS = [
    # 臉部
    (0, 1), (0, 2), (1, 3), (2, 4),  # nose-eyes-ears
    # 上半身
    (5, 6),   # shoulder-shoulder
    (5, 7), (7, 9),    # left arm
    (6, 8), (8, 10),   # right arm
    # 軀幹
    (5, 11), (6, 12), (11, 12),  # shoulders-hips
    # 下半身
    (11, 13), (13, 15),  # left leg
    (12, 14), (14, 16),  # right leg
]


def draw_skeleton_on_frame(
    frame: np.ndarray,
    skeleton: Skeleton,
    color: tuple[int, int, int] = (0, 255, 0),
) -> np.ndarray:
    """在畫面上繪製完整骨架"""
    output = frame.copy()
    
    # 繪製關鍵點
    for i in range(17):
        x, y, vis = skeleton.keypoints[i]
        if vis > 0.3:
            cv2.circle(output, (int(x), int(y)), 6, color, -1)
            cv2.circle(output, (int(x), int(y)), 8, (255, 255, 255), 2)
    
    # 繪製連接線
    for i, j in SKELETON_CONNECTIONS:
        pt1 = skeleton.keypoints[i]
        pt2 = skeleton.keypoints[j]
        if pt1[2] > 0.3 and pt2[2] > 0.3:
            cv2.line(
                output,
                (int(pt1[0]), int(pt1[1])),
                (int(pt2[0]), int(pt2[1])),
                color,
                3,
            )
    
    return output


def add_info_overlay(
    frame: np.ndarray,
    skeleton: Skeleton,
    frame_num: int,
    time_sec: float,
) -> np.ndarray:
    """加入資訊說明"""
    output = frame.copy()
    h, w = output.shape[:2]
    
    # 半透明背景
    overlay = output.copy()
    cv2.rectangle(overlay, (10, 10), (400, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, output, 0.4, 0, output)
    
    # 資訊文字
    texts = [
        f"Frame: {frame_num} | Time: {time_sec:.2f}s",
        f"Torso Angle: {skeleton.torso_angle:.1f} degrees",
        f"Status: {'FALLEN' if skeleton.torso_angle > 60 else 'STANDING'}",
    ]
    
    for i, text in enumerate(texts):
        color = (0, 0, 255) if "FALLEN" in text else (255, 255, 255)
        cv2.putText(
            output, text,
            (20, 40 + i * 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2,
        )
    
    return output


def save_skeleton_frames(video_path: str, output_dir: str, every_n_frames: int = 10) -> int:
    """從影片中擷取骨架偵測幀並儲存"""
    
    # 建立輸出目錄
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 開啟影片
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"無法開啟影片: {video_path}")
        return 1
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    logger.info(f"影片: {video_path}")
    logger.info(f"FPS: {fps}, 總幀數: {total_frames}")
    logger.info(f"輸出目錄: {output_path}")
    
    # 初始化偵測器
    detector = PoseDetector(model_path="yolov8n-pose.pt", confidence=0.5)
    
    frame_count = 0
    saved_count = 0
    
    logger.info("開始處理...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # 每 N 幀處理一次
        if frame_count % every_n_frames != 0:
            continue
        
        current_time = frame_count / fps
        
        # 偵測骨架
        skeletons = detector.detect(frame)
        
        if not skeletons:
            continue
        
        skeleton = skeletons[0]
        
        # 根據狀態選擇顏色
        color = (0, 0, 255) if skeleton.torso_angle > 60 else (0, 255, 0)
        
        # 繪製骨架
        output_frame = draw_skeleton_on_frame(frame, skeleton, color)
        output_frame = add_info_overlay(output_frame, skeleton, frame_count, current_time)
        
        # 儲存圖片
        filename = f"frame_{frame_count:04d}_angle_{skeleton.torso_angle:.0f}.jpg"
        filepath = output_path / filename
        cv2.imwrite(str(filepath), output_frame)
        saved_count += 1
        
        status = "FALLEN" if skeleton.torso_angle > 60 else "standing"
        logger.info(f"[{current_time:.1f}s] Saved: {filename} ({status})")
    
    cap.release()
    
    logger.info(f"完成! 共儲存 {saved_count} 張圖片到 {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="骨架偵測驗證 - 儲存骨架偵測結果為圖片")
    parser.add_argument("video", help="影片檔案路徑")
    parser.add_argument(
        "--output", "-o",
        default="output/skeleton_frames",
        help="輸出目錄 (預設: output/skeleton_frames)",
    )
    parser.add_argument(
        "--every", "-n",
        type=int,
        default=10,
        help="每 N 幀擷取一張 (預設: 10)",
    )
    args = parser.parse_args()
    
    return save_skeleton_frames(args.video, args.output, args.every)


if __name__ == "__main__":
    exit(main())
