"""Thread-safe "latest value wins" cache of the most recently received
FrameState from the network.

Unlike ScoreDisplayState/MoveLogDisplayState (event-driven, accumulating),
this isn't fed by individual events - each frame_update message fully
replaces the previous board/moves/jumps/clock/cooldowns state, so there's
nothing to accumulate. `update` is called from the network thread (see
client_gui.py); `latest` is polled from the render loop on the main
thread - the lock is what makes that safe.
"""

from __future__ import annotations

import threading


class FrameStateCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest = None

    def update(self, frame_state) -> None:
        with self._lock:
            self._latest = frame_state

    def latest(self):
        """Returns the most recently received FrameState, or None if the
        very first frame_update hasn't arrived yet - lets the caller show
        a "connecting..." state instead of crashing on nothing."""
        with self._lock:
            return self._latest
