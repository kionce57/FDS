import logging
from collections import deque
from datetime import datetime

import requests

from src.events.observer import FallEvent, FallEventObserver

logger = logging.getLogger(__name__)


class LineNotifier(FallEventObserver):
    API_URL = "https://notify-api.line.me/api/notify"

    def __init__(self, token: str, enabled: bool = True):
        self.token = token
        self.enabled = enabled
        self._pending_queue: deque[FallEvent] = deque()

    def on_fall_confirmed(self, event: FallEvent) -> None:
        if not self.enabled:
            return

        timestamp = datetime.fromtimestamp(event.confirmed_at).strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"\n🚨 跌倒警報!\n"
            f"事件 ID: {event.event_id}\n"
            f"時間: {timestamp}\n"
            f"通知次數: {event.notification_count}"
        )
        self._send(event, message)

    def on_fall_recovered(self, event: FallEvent) -> None:
        if not self.enabled:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"\n✅ 已恢復\n事件 ID: {event.event_id}\n恢復時間: {timestamp}"
        self._send(event, message)

    def _send(self, event: FallEvent, message: str) -> bool:
        try:
            response = requests.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.token}"},
                data={"message": message},
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f"Notification sent for {event.event_id}")
                return True
            else:
                logger.warning(f"Notification failed: {response.status_code}")
                self._pending_queue.append(event)
                return False
        except Exception as e:
            logger.error(f"Notification error: {e}")
            self._pending_queue.append(event)
            return False

    def retry_pending(self) -> None:
        while self._pending_queue:
            event = self._pending_queue[0]
            timestamp = datetime.fromtimestamp(event.confirmed_at).strftime("%Y-%m-%d %H:%M:%S")
            message = f"\n🚨 跌倒警報 (重試)!\n事件 ID: {event.event_id}\n時間: {timestamp}"
            try:
                response = requests.post(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {self.token}"},
                    data={"message": message},
                    timeout=10,
                )
                if response.status_code == 200:
                    self._pending_queue.popleft()
                else:
                    break
            except Exception:
                break
