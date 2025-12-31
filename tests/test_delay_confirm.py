from src.analysis.delay_confirm import DelayConfirm, FallState
from src.events.observer import FallEvent, SuspectedEvent


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


class MockSuspectedObserver:
    def __init__(self):
        self.suspected_events: list[SuspectedEvent] = []
        self.cleared_events: list[SuspectedEvent] = []

    def on_fall_suspected(self, event: SuspectedEvent) -> None:
        self.suspected_events.append(event)

    def on_suspicion_cleared(self, event: SuspectedEvent) -> None:
        self.cleared_events.append(event)


class TestDelayConfirmSuspectedObservers:
    def test_suspected_observer_notified_on_suspected(self):
        observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_suspected_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)

        assert len(observer.suspected_events) == 1
        assert observer.suspected_events[0].suspected_id.startswith("sus_")

    def test_suspected_observer_notified_on_cleared(self):
        observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_suspected_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=False, current_time=1.0)  # 未達 3 秒，疑似取消

        assert len(observer.cleared_events) == 1
        assert observer.cleared_events[0].outcome == "cleared"

    def test_suspected_event_outcome_updated_on_confirmed(self):
        observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_suspected_observer(observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)  # 確認跌倒

        # suspected 事件的 outcome 應該被更新為 confirmed
        assert observer.suspected_events[0].outcome == "confirmed"

    def test_existing_observers_still_work(self):
        """確保原有 observer 不受影響"""
        fall_observer = MockObserver()
        suspected_observer = MockSuspectedObserver()
        dc = DelayConfirm(delay_sec=3.0)
        dc.add_observer(fall_observer)
        dc.add_suspected_observer(suspected_observer)

        dc.update(is_fallen=True, current_time=0.0)
        dc.update(is_fallen=True, current_time=4.0)

        assert fall_observer.confirm_count == 1
        assert len(suspected_observer.suspected_events) == 1
