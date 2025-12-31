from src.events.observer import FallEvent, SuspectedEvent


class MockObserver:
    def __init__(self):
        self.confirmed_events: list[FallEvent] = []
        self.recovered_events: list[FallEvent] = []

    def on_fall_confirmed(self, event: FallEvent) -> None:
        self.confirmed_events.append(event)

    def on_fall_recovered(self, event: FallEvent) -> None:
        self.recovered_events.append(event)


class TestFallEvent:
    def test_create_event(self):
        event = FallEvent(
            event_id="evt_123", confirmed_at=1000.0, last_notified_at=1000.0, notification_count=1
        )
        assert event.event_id == "evt_123"
        assert event.confirmed_at == 1000.0
        assert event.notification_count == 1

    def test_event_is_mutable(self):
        event = FallEvent(
            event_id="evt_123", confirmed_at=1000.0, last_notified_at=1000.0, notification_count=1
        )
        event.notification_count = 2
        event.last_notified_at = 1100.0
        assert event.notification_count == 2
        assert event.last_notified_at == 1100.0


class TestMockObserver:
    def test_observer_receives_confirmed_event(self):
        observer = MockObserver()
        event = FallEvent("evt_1", 100.0, 100.0, 1)
        observer.on_fall_confirmed(event)
        assert len(observer.confirmed_events) == 1
        assert observer.confirmed_events[0].event_id == "evt_1"

    def test_observer_receives_recovered_event(self):
        observer = MockObserver()
        event = FallEvent("evt_1", 100.0, 100.0, 1)
        observer.on_fall_recovered(event)
        assert len(observer.recovered_events) == 1


class TestSuspectedEvent:
    def test_suspected_event_creation(self):
        event = SuspectedEvent(
            suspected_id="sus_1234567890",
            suspected_at=1234567890.0,
        )
        assert event.suspected_id == "sus_1234567890"
        assert event.suspected_at == 1234567890.0
        assert event.outcome == "pending"

    def test_suspected_event_with_outcome(self):
        event = SuspectedEvent(
            suspected_id="sus_1234567890",
            suspected_at=1234567890.0,
            outcome="confirmed",
            outcome_at=1234567893.0,
        )
        assert event.outcome == "confirmed"
        assert event.outcome_at == 1234567893.0
