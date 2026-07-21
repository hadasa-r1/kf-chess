"""Read model of the latest disconnect-countdown info from the server
(see server/protocol.py's serialize_disconnect_countdown), kept in sync
by NetworkClient's on_disconnect_countdown callback. Pure in-memory
cache, lock-protected the same way as bus_handlers/score_display_state.py's
ScoreDisplayState - written from the network thread, polled every frame
by the render loop.

No cancellation message exists server-side: `latest()` simply reflects
whatever the most recent disconnect_countdown tick said. Once a
GameEndedEvent arrives (see client_net/game_over_state.py), the render
loop's game-over screen takes over the loop entirely regardless of
whatever is still cached here.
"""

from __future__ import annotations

import threading


class DisconnectCountdownState:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = None

    def update(self, color: str, seconds_remaining: int) -> None:
        with self._lock:
            self._latest = (color, seconds_remaining)

    def latest(self):
        with self._lock:
            return self._latest
