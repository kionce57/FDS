from enum import Enum

from src.events.observer import (
    FallEvent,
    FallEventObserver,
)


class FallState(Enum):
    NORMAL = "normal"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class DelayConfirm:
    def __init__(
        self,
        delay_sec: float = 3.0,
        same_event_window: float = 60.0,
        re_notify_interval: float = 120.0,
    ):
        self.state = FallState.NORMAL
        self.delay_sec = delay_sec
        self.same_event_window = same_event_window
        self.re_notify_interval = re_notify_interval

        self.suspected_since: float | None = None
        self.current_event: FallEvent | None = None
        self.observers: list[FallEventObserver] = []

    def add_observer(self, observer: FallEventObserver) -> None:
        self.observers.append(observer)

    def update(self, is_fallen: bool, current_time: float) -> FallState:
        match self.state:
            case FallState.NORMAL:
                if is_fallen:
                    self.state = FallState.SUSPECTED
                    self.suspected_since = current_time

            case FallState.SUSPECTED:
                if not is_fallen:
                    self._reset()
                elif current_time - self.suspected_since >= self.delay_sec:
                    self._confirm_fall(current_time)

            case FallState.CONFIRMED:
                if not is_fallen:
                    self._recover(current_time)
                else:
                    self._check_re_notify(current_time)

        return self.state

    def _confirm_fall(self, current_time: float) -> None:
        if (
            self.current_event
            and current_time - self.current_event.confirmed_at < self.same_event_window
        ):
            self.state = FallState.CONFIRMED
            return

        self.state = FallState.CONFIRMED
        self.current_event = FallEvent(
            event_id=f"evt_{int(current_time)}",
            confirmed_at=current_time,
            last_notified_at=current_time,
            notification_count=1,
        )
        for observer in self.observers:
            observer.on_fall_confirmed(self.current_event)

    def _check_re_notify(self, current_time: float) -> None:
        if not self.current_event:
            return
        if current_time - self.current_event.last_notified_at >= self.re_notify_interval:
            self.current_event.last_notified_at = current_time
            self.current_event.notification_count += 1
            for observer in self.observers:
                observer.on_fall_confirmed(self.current_event)

    def _recover(self, current_time: float) -> None:
        self.state = FallState.NORMAL
        if self.current_event:
            for observer in self.observers:
                observer.on_fall_recovered(self.current_event)
        self.suspected_since = None

    def _reset(self) -> None:
        self.state = FallState.NORMAL
        self.suspected_since = None
