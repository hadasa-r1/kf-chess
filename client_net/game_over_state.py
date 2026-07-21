"""Read model of the game's outcome, kept in sync by GameEndedEvent -
whether that arrived because the server forwarded a real in-engine
ending (e.g. checkmate) or because server/disconnect_resign_handler.py
resigned a disconnected player; this class doesn't know or care which.
Pure in-memory cache, lock-protected the same way as
bus_handlers/score_display_state.py's ScoreDisplayState - written from an
EventBus callback, polled every frame by the render loop.
"""

from __future__ import annotations

import threading

from bus.event_bus import EventBus
from bus.events import GameEndedEvent


class GameOverState:
    def __init__(self, bus: EventBus):
        self._lock = threading.Lock()
        self._latest = None
        bus.subscribe(GameEndedEvent, self._on_game_ended)

    def _on_game_ended(self, event: GameEndedEvent) -> None:
        with self._lock:
            self._latest = (event.winner, event.reason)

    def latest(self):
        with self._lock:
            return self._latest
