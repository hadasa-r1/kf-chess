from __future__ import annotations

import threading
from collections import defaultdict

from bus.event_bus import EventBus
from bus.events import MoveMadeEvent


class MoveLogDisplayState:
    """Read model of each player's move log, kept in sync by MoveMadeEvent.
    Pure in-memory cache - no rendering, no I/O. The event callback only
    appends state; `entries_for` is the synchronous getter a (future)
    render loop polls on its own thread and schedule.

    MoveMadeEvent already carries exactly the fields (timestamp/piece/
    start/end) the display layer needs per entry, so the event itself is
    stored as the display-ready entry - no separate display type.
    """

    def __init__(self, bus: EventBus):
        self._lock = threading.Lock()
        self._entries: dict[str, list[MoveMadeEvent]] = defaultdict(list)
        bus.subscribe(MoveMadeEvent, self._on_move_made)

    def _on_move_made(self, event: MoveMadeEvent) -> None:
        with self._lock:
            self._entries[event.color].append(event)

    def entries_for(self, player: str) -> tuple:
        with self._lock:
            return tuple(self._entries.get(player, ()))
