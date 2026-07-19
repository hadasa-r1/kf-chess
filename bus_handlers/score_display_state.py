from __future__ import annotations

import threading

from bus.event_bus import EventBus
from bus.events import ScoreChangedEvent


class ScoreDisplayState:
    """Read model of the latest score per player, kept in sync by
    ScoreChangedEvent. Pure in-memory cache - no rendering, no I/O. The
    event callback only writes state; `score_for` is the synchronous
    getter a (future) render loop polls on its own thread and schedule.
    """

    def __init__(self, bus: EventBus):
        self._lock = threading.Lock()
        self._scores: dict[str, int] = {}
        bus.subscribe(ScoreChangedEvent, self._on_score_changed)

    def _on_score_changed(self, event: ScoreChangedEvent) -> None:
        with self._lock:
            self._scores[event.player] = event.new_score

    def score_for(self, player: str) -> int:
        with self._lock:
            return self._scores.get(player, 0)
