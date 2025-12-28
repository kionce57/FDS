from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        if self.width == 0:
            return 0.0
        return self.height / self.width

    @property
    def center(self) -> tuple[int, int]:
        cx = self.x + self.width // 2
        cy = self.y + self.height // 2
        return cx, cy

    @property
    def area(self) -> int:
        return self.width * self.height
