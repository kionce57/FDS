import numpy as np
from ultralytics import YOLO

from src.detection.bbox import BBox


class Detector:
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        classes: list[int] | None = None,
    ):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.classes = classes if classes is not None else [0]

    def detect(self, frame: np.ndarray) -> list[BBox]:
        results = self.model(frame, conf=self.confidence, verbose=False)

        bboxes = []
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()

            for box, cls, conf in zip(boxes, classes, confs):
                if int(cls) not in self.classes:
                    continue

                x1, y1, x2, y2 = map(int, box)
                bboxes.append(
                    BBox(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    )
                )

        return bboxes
