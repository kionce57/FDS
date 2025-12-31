#!/usr/bin/env python3
"""
攝影機偵測腳本

掃描系統可用的攝影機設備，用於確認 USB Webcam 的 index。

使用方式:
    uv run python scripts/detect_camera.py
"""

import cv2


def detect_cameras(max_index: int = 5) -> list[dict]:
    """掃描可用的攝影機設備

    Args:
        max_index: 最大掃描 index

    Returns:
        可用攝影機資訊列表
    """
    cameras = []

    print(f"掃描攝影機 index 0-{max_index - 1}...\n")

    for i in range(max_index):
        cap = cv2.VideoCapture(i)

        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))

            info = {
                "index": i,
                "width": width,
                "height": height,
                "fps": fps,
            }
            cameras.append(info)

            print(f"  Index {i}: ✅ 可用 ({width}x{height} @ {fps}fps)")
            cap.release()
        else:
            print(f"  Index {i}: ❌ 不可用")

    return cameras


def preview_camera(index: int, duration_sec: int = 5) -> None:
    """預覽指定攝影機

    Args:
        index: 攝影機 index
        duration_sec: 預覽秒數
    """
    cap = cv2.VideoCapture(index)

    if not cap.isOpened():
        print(f"無法開啟攝影機 index {index}")
        return

    print(f"\n預覽攝影機 index {index}（{duration_sec} 秒後自動關閉，或按 'q' 退出）")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_count = int(fps * duration_sec)

    for _ in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow(f"Camera {index} Preview", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def main() -> None:
    cameras = detect_cameras()

    if not cameras:
        print("\n❌ 未偵測到任何攝影機")
        print("\n可能原因:")
        print("  1. 沒有連接攝影機")
        print("  2. 攝影機被其他程式佔用（Teams, Zoom, OBS 等）")
        print("  3. 驅動程式問題")
        return

    print(f"\n✅ 偵測到 {len(cameras)} 個攝影機")
    print("\n建議設定 config/settings.yaml:")
    print("  camera:")
    print(f"    source: {cameras[0]['index']}")

    # 詢問是否預覽
    try:
        choice = input(f"\n是否預覽 index {cameras[0]['index']}? [y/N]: ").strip().lower()
        if choice == "y":
            preview_camera(cameras[0]["index"])
    except KeyboardInterrupt:
        print("\n已取消")


if __name__ == "__main__":
    main()
