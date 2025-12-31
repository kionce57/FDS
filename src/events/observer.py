from dataclasses import dataclass
from typing import Protocol, Literal


@dataclass
class FallEvent:
    event_id: str
    confirmed_at: float
    last_notified_at: float
    notification_count: int


@dataclass
class SuspectedEvent:
    """疑似跌倒事件，用於骨架收集"""

    suspected_id: str
    suspected_at: float
    outcome: Literal["pending", "confirmed", "cleared"] = "pending"
    outcome_at: float | None = None


class FallEventObserver(Protocol):
    def on_fall_confirmed(self, event: FallEvent) -> None: ...
    def on_fall_recovered(self, event: FallEvent) -> None: ...


class SuspectedEventObserver(Protocol):
    """擴展 Observer，支援 SUSPECTED 階段通知"""

    def on_fall_suspected(self, event: SuspectedEvent) -> None: ...
    def on_suspicion_cleared(self, event: SuspectedEvent) -> None: ...
