from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

Handler = Callable[[Any], None]


@dataclass
class EventBus:

    _subscribers: dict[str, list[Handler]] = field(default_factory=lambda: defaultdict(list))

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: Any = None) -> None:
        for handler in self._subscribers[event_type]:
            handler(payload)

    def subscriber_count(self, event_type: str) -> int:
        return len(self._subscribers[event_type])


def simulate_timer_ticks(bus: EventBus, count: int) -> None:
    for i in range(count):
        bus.publish("tick", i)


def make_logging_handler(log: list[str], label: str) -> Handler:

    def handler(payload: Any) -> None:
        log.append(f"[{label}] {payload}")

    return handler
