# src/events/clip_url_generator.py
from pathlib import Path


class ClipUrlGenerator:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def generate(self, clip_path: str | None) -> str | None:
        if clip_path is None:
            return None
        filename = Path(clip_path).name
        return f"{self.base_url}/clips/{filename}"
