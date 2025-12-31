import pytest
from unittest.mock import patch
from src.events.notifier import LineNotifier
from src.events.observer import FallEvent


class TestLineNotifier:
    @pytest.fixture
    def notifier(self):
        return LineNotifier(
            channel_access_token="test_channel_access_token",
            user_id="U1234567890abcdefghijklmnopqrstuvw",
            enabled=True,
        )

    @pytest.fixture
    def sample_event(self):
        return FallEvent(
            event_id="evt_123",
            confirmed_at=1000.0,
            last_notified_at=1000.0,
            notification_count=1,
        )

    def test_notifier_disabled(self, sample_event):
        notifier = LineNotifier(channel_access_token="test", user_id="U123", enabled=False)
        with patch("requests.post") as mock_post:
            notifier.on_fall_confirmed(sample_event)
            mock_post.assert_not_called()

    def test_send_notification_success(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.on_fall_confirmed(sample_event)
            mock_post.assert_called_once()

    def test_notification_message_format(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.on_fall_confirmed(sample_event)

            call_args = mock_post.call_args
            json_body = call_args.kwargs.get("json", {})

            # 驗證 JSON 結構
            assert json_body["to"] == "U1234567890abcdefghijklmnopqrstuvw"
            assert isinstance(json_body["messages"], list)
            assert json_body["messages"][0]["type"] == "text"
            assert "跌倒" in json_body["messages"][0]["text"]

    def test_notification_failure_adds_to_queue(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network error")
            notifier.on_fall_confirmed(sample_event)

            assert len(notifier._pending_queue) == 1

    def test_retry_pending_success(self, notifier, sample_event):
        notifier._pending_queue.append(sample_event)

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.retry_pending()

            assert len(notifier._pending_queue) == 0

    def test_recovery_notification(self, notifier, sample_event):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            notifier.on_fall_recovered(sample_event)

            call_args = mock_post.call_args
            json_body = call_args.kwargs.get("json", {})

            # 驗證 JSON 結構
            assert json_body["to"] == "U1234567890abcdefghijklmnopqrstuvw"
            assert isinstance(json_body["messages"], list)
            message_text = json_body["messages"][0]["text"]
            assert "恢復" in message_text or "recovered" in message_text.lower()
