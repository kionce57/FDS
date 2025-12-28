from dataclasses import dataclass
from typing import Protocol


@dataclass
class FallEvent:
    event_id: str
    confirmed_at: float
    last_notified_at: float
    notification_count: int


class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...
