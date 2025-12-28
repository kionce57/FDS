from src.detection.bbox import BBox


class RuleEngine:
    def __init__(self, fall_threshold: float = 1.3):
        self.fall_threshold = fall_threshold

    def is_fallen(self, bbox: BBox | None) -> bool:
        if bbox is None:
            return False
        return bbox.aspect_ratio < self.fall_threshold
