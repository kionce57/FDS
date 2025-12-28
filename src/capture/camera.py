import cv2
import numpy as np


class CameraError(Exception):
    """Camera-related errors."""


class Camera:
    def __init__(
        self,
        source: int | str = 0,
        fps: int = 15,
        resolution: tuple[int, int] = (640, 480),
        max_retries: int = 3,
    ):
        self.source = source
        self.fps = fps
        self.resolution = resolution
        self.max_retries = max_retries
        self._consecutive_failures = 0

        self._capture = cv2.VideoCapture(source)

        if not self._capture.isOpened():
            raise CameraError(f"Failed to open camera: {source}")

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
        self._capture.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> np.ndarray | None:
        ret, frame = self._capture.read()

        if not ret or frame is None:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.max_retries:
                raise CameraError(
                    f"Camera {self.source} has {self._consecutive_failures} consecutive failures"
                )
            return None

        self._consecutive_failures = 0
        return frame

    def release(self) -> None:
        if self._capture:
            self._capture.release()

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
