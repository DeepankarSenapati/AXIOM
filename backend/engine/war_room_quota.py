"""Small in-process guardrail for optional paid reviews; not a billing limit."""

from threading import Lock

from backend.engine.war_room_models import WarRoomError


class WarRoomQuota:
    """Reserve a whole review before the first model call, including failures."""

    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("War Room review limit must not be negative")
        self.limit = limit
        self._used = 0
        self._lock = Lock()

    def reserve(self) -> None:
        with self._lock:
            if self._used >= self.limit:
                raise WarRoomError(429, "This local server has reached its Claude review limit. Restart the demo to reset it.")
            self._used += 1

    def remaining(self) -> int:
        with self._lock:
            return self.limit - self._used
