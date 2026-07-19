from __future__ import annotations

from dataclasses import dataclass

from game.move_observer import MoveObserver


@dataclass(frozen=True)
class MoveRecord:
    """One completed move. Plain primitives only (str/tuple/int) so this can
    be serialized (e.g. to JSON for a future networked client) with no
    dependency on the UI/formatting layer. `timestamp` is the arbiter's
    simulated clock, not wall time, so it stays deterministic in tests.
    """

    color: str
    piece: str
    start: tuple
    end: tuple
    timestamp: int


class MoveHistory(MoveObserver):
    """Append-only log of every accepted move, in order.

    Owns nothing about display - GameEngine writes to it, callers read from
    it via `for_color`. Kept as its own object (like RealTimeArbiter owns
    motion state) so it can be tested in isolation from the engine.
    """

    def __init__(self):
        self._entries = []

    def record(self, move_record):
        self._entries.append(move_record)

    def on_move_started(self, record: MoveRecord) -> None:
        self.record(record)

    def for_color(self, color):
        return tuple(e for e in self._entries if e.color == color)
