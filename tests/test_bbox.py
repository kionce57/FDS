import pytest
from src.detection.bbox import BBox


class TestBBox:
    def test_create_bbox(self):
        bbox = BBox(x=10, y=20, width=100, height=200)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 200

    def test_aspect_ratio_standing(self):
        bbox = BBox(x=0, y=0, width=100, height=200)
        assert bbox.aspect_ratio == 2.0

    def test_aspect_ratio_fallen(self):
        bbox = BBox(x=0, y=0, width=200, height=100)
        assert bbox.aspect_ratio == 0.5

    def test_center_point(self):
        bbox = BBox(x=100, y=100, width=50, height=80)
        cx, cy = bbox.center
        assert cx == 125
        assert cy == 140

    def test_area(self):
        bbox = BBox(x=0, y=0, width=100, height=200)
        assert bbox.area == 20000
