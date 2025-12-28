from src.analysis.delay_confirm import DelayConfirm, FallState
from src.events.observer import FallEvent


class MockObserver:
    def __init__(self):
        self.confirmed_events: list[FallEvent] = []
        self.recovered_events: list[FallEvent] = []

    def on_fall_confirmed(self, event: FallEvent) -> None:
        self.confirmed_events.append(event)

    def on_fall_recovered(self, event: FallEvent) -> None:
        self.recovered_events.append(event)

    @property
    def confirm_count(self) -> int:
        return len(self.confirmed_events)


class TestDelayConfirmStates:
    def test_initial_state_is_normal(self):
        dc = DelayConfirm(delay_sec=3.0)
        assert dc.state == FallState.NORMAL

    def test_normal_to_suspected_on_fall(self):
        dc = DelayConfirm(delay_sec=3.0)
        state = dc.update(is_fallen=True, current_time=0.0)
        assert state == FallState.SUSPECTED

    def test_suspected_to_normal_on_recovery(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        state = dc.update(is_fallen=False, current_time=1.0)
        assert state == FallState.NORMAL

    def test_suspected_stays_before_delay(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        state = dc.update(is_fallen=True, current_time=2.9)
        assert state == FallState.SUSPECTED

    def test_suspected_to_confirmed_after_delay(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=2.0)
        state = dc.update(is_fallen=True, current_time=3.1)
        assert state == FallState.CONFIRMED

    def test_confirmed_to_normal_on_recovery(self):
        dc = DelayConfirm(delay_sec=3.0)
        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        state = dc.update(is_fallen=False, current_time=5.0)
        assert state == FallState.NORMAL


class TestDelayConfirmObservers:
    def test_observer_notified_on_confirm(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)

        assert observer.confirm_count == 1

    def test_observer_notified_on_recovery(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        dc.update(is_fallen=False, current_time=5.0)

        assert len(observer.recovered_events) == 1

    def test_same_event_window_deduplication(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0, same_event_window=60.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        dc.update(is_fallen=False, current_time=10.0)
        dc.update(is_fallen=True, current_time=15.0)
        dc.update(is_fallen=True, current_time=19.0)

        assert observer.confirm_count == 1

    def test_re_notify_after_interval(self):
        observer = MockObserver()
        dc = DelayConfirm(delay_sec=3.0, re_notify_interval=120.0)
        dc.add_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)
        dc.update(is_fallen=True, current_time=125.0)

        assert observer.confirm_count == 2
