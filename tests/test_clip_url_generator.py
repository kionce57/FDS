# tests/test_clip_url_generator.py
from src.events.clip_url_generator import ClipUrlGenerator


def test_generate_url_from_clip_path():
    generator = ClipUrlGenerator(base_url="https://fds.example.com")
    url = generator.generate("/data/clips/evt_123.mp4")
    assert url == "https://fds.example.com/clips/evt_123.mp4"


def test_generate_url_returns_none_for_none_path():
    generator = ClipUrlGenerator(base_url="https://fds.example.com")
    url = generator.generate(None)
    assert url is None
