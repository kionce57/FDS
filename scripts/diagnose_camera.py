"""Windows 攝影機診斷工具"""

import cv2
import sys

# 強制使用 UTF-8 輸出（修復 Windows console 編碼問題）
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def test_camera_index(index: int, timeout_ms: int = 5000) -> dict:
    """測試特定攝影機索引"""
    result = {
        "index": index,
        "opened": False,
        "backend": None,
        "resolution": None,
        "fps": None,
        "frame_test": False,
        "error": None,
    }

    try:
        # 嘗試使用 MSMF backend (Windows 預設)
        cap = cv2.VideoCapture(index, cv2.CAP_MSMF)

        # 設定超時（避免長時間卡住）
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)

        if cap.isOpened():
            result["opened"] = True
            result["backend"] = "MSMF"

            # 讀取解析度和 FPS
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            result["resolution"] = f"{width}x{height}"
            result["fps"] = fps

            # 測試讀取一幀
            ret, frame = cap.read()
            if ret and frame is not None:
                result["frame_test"] = True
            else:
                result["error"] = "Can read metadata but failed to grab frame"

            cap.release()
        else:
            # 嘗試使用 DSHOW backend (DirectShow, 備用方案)
            cap_ds = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap_ds.isOpened():
                result["opened"] = True
                result["backend"] = "DSHOW"

                width = int(cap_ds.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap_ds.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap_ds.get(cv2.CAP_PROP_FPS)

                result["resolution"] = f"{width}x{height}"
                result["fps"] = fps

                ret, frame = cap_ds.read()
                result["frame_test"] = ret and frame is not None

                cap_ds.release()
            else:
                result["error"] = "Failed to open with MSMF and DSHOW"

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    print("=== Windows 攝影機診斷工具 ===\n")
    print("正在掃描攝影機（索引 0-2）...\n")

    available_cameras = []

    for i in range(3):
        print(f"[{i}] 測試中... ", end="", flush=True)
        result = test_camera_index(i)

        if result["opened"]:
            print("✓ 可用")
            available_cameras.append(result)
            print(f"    Backend: {result['backend']}")
            print(f"    解析度: {result['resolution']}")
            print(f"    FPS: {result['fps']}")
            print(f"    讀取測試: {'✓ 成功' if result['frame_test'] else '✗ 失敗'}")
        else:
            print("✗ 無法開啟")
            if result["error"]:
                print(f"    錯誤: {result['error']}")
        print()

    print("=== 診斷結果 ===")
    if available_cameras:
        print(f"找到 {len(available_cameras)} 個可用攝影機:\n")
        for cam in available_cameras:
            status = "✓" if cam["frame_test"] else "⚠"
            print(
                f"  {status} index={cam['index']} | {cam['backend']} | {cam['resolution']} @ {cam['fps']} fps"
            )

        print("\n建議:")
        working = [c for c in available_cameras if c["frame_test"]]
        if working:
            best = working[0]
            print(f"  修改 config/settings.yaml 中的 camera.source 為: {best['index']}")
            if best["backend"] == "DSHOW":
                print("  或考慮在程式中強制使用 CAP_DSHOW backend")
        else:
            print("  ⚠ 所有攝影機都無法正常讀取幀，可能被其他程式佔用")
            print("  請關閉可能使用攝影機的程式（Teams, Zoom, Skype, 瀏覽器等）")
    else:
        print("未找到任何可用攝影機")
        print("\n可能原因:")
        print("  1. 攝影機未插入或驅動未安裝")
        print("  2. Windows 隱私設定阻擋攝影機存取")
        print("     -> 設定 > 隱私權 > 相機 > 允許應用程式存取您的相機")
        print("  3. 攝影機被其他程式佔用")

    return 0 if available_cameras else 1


if __name__ == "__main__":
    sys.exit(main())
