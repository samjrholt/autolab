"""Tiny in-process event bus.

The Console (when it exists) and any other subscriber listens on the
event stream — one event per Record write, Resource acquire/release,
and Campaign lifecycle transition. For now this is in-process; a
WebSocket bridge can be slotted on top with no API change.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Event:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """Fan-out async pub/sub. Subscribers get their own queue."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def publish(self, event: Event) -> None:
        for q in self._subscribers:
            q.put_nowait(event)

    async def stream(self) -> AsyncIterator[Event]:
        q = self.subscribe()
        try:
            while True:
                yield await q.get()
        finally:
            self.unsubscribe(q)


__all__ = ["Event", "EventBus"]
