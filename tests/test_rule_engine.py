import pytest
from src.detection.bbox import BBox
from src.analysis.rule_engine import RuleEngine


class TestRuleEngine:
    @pytest.fixture
    def engine(self):
        return RuleEngine(fall_threshold=1.3)

    def test_standing_not_fallen(self, engine):
        bbox = BBox(x=0, y=0, width=100, height=200)
        assert engine.is_fallen(bbox) is False

    def test_boundary_standing(self, engine):
        bbox = BBox(x=0, y=0, width=100, height=130)
        assert engine.is_fallen(bbox) is False

    def test_just_below_threshold_is_fallen(self, engine):
        bbox = BBox(x=0, y=0, width=100, height=129)
        assert engine.is_fallen(bbox) is True

    def test_clearly_fallen(self, engine):
        bbox = BBox(x=0, y=0, width=200, height=100)
        assert engine.is_fallen(bbox) is True

    def test_none_bbox_returns_false(self, engine):
        assert engine.is_fallen(None) is False

    @pytest.mark.parametrize("width,height,expected", [
        (100, 200, False),
        (100, 130, False),
        (100, 120, True),
        (200, 100, True),
        (100, 100, True),
    ])
    def test_various_ratios(self, engine, width, height, expected):
        bbox = BBox(x=0, y=0, width=width, height=height)
        assert engine.is_fallen(bbox) == expected
