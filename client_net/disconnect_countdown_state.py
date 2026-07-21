"""Read model of the latest disconnect-countdown info from the server
(see server/protocol.py's serialize_disconnect_countdown), kept in sync
by NetworkClient's on_disconnect_countdown callback. Pure in-memory
cache, lock-protected the same way as bus_handlers/score_display_state.py's
ScoreDisplayState - written from the network thread, polled every frame
by the render loop.

If the disconnected player reconnects in time, the server broadcasts a
disconnect_countdown_cancelled message instead (see
server/disconnect_resign_handler.py's cancel_countdown) - NetworkClient's
on_disconnect_countdown_cancelled callback is wired to this class's
clear() method, resetting `latest()` back to None so both the countdown
overlay and the mouse-input lock (client_gui.py's _on_mouse, which keys
off `latest() is not None`) drop away on the very next frame.
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

    def clear(self) -> None:
        with self._lock:
            self._latest = None

    def latest(self):
        with self._lock:
            return self._latest
