from __future__ import annotations

from dataclasses import dataclass

from realtime.models import Move, Jump


@dataclass(frozen=True)
class ArrivalEvent:
    """What the arbiter reports back when a moving piece arrives.

    The arbiter mutates the board itself, but it does not decide the win
    condition - it only reports which token (if any) was captured, so the
    GameEngine can apply its injected WinCondition. `piece` is the token as
    placed at the destination (already promoted if a promotion applied).
    """

    piece: str
    destination: tuple
    captured: str | None


class RealTimeArbiter:
    """Owns all real-time motion: active Moves/Jumps, the simulated clock,
    arrival timing, and arrival/interception resolution.

    Kept separate from GameEngine so the real-time model can be tested in
    isolation, and so Board keeps representing only logical occupancy while
    in-flight motion state lives here. Time never advances from the wall
    clock: it only moves when `advance_time` is called with a delta.

    Promotion happens on arrival, so the promotion rule is injected here
    (into the layer that owns arrival), not into the engine.
    """

    def __init__(self, board, promotion_rule, config):
        self._board = board
        self._promotion_rule = promotion_rule
        self._config = config
        self._clock = 0
        self._active_moves = []
        self._active_jumps = []
        self._cooldown_until = {}  # cell -> clock time its cooldown ends
        self._cooldown_kind = {}  # cell -> "move" or "jump", whichever caused the cooldown

    @property
    def clock(self):
        return self._clock

    def active_moves(self):
        return list(self._active_moves)

    def active_jumps(self):
        return list(self._active_jumps)

    def has_active_motion(self):
        return bool(self._active_moves)

    def is_moving_from(self, cell):
        return any(move.start == cell for move in self._active_moves)

    def is_jumping_on(self, cell):
        return any(jump.cell == cell for jump in self._active_jumps)

    def is_on_cooldown(self, cell):
        return self._clock < self._cooldown_until.get(cell, -1)

    def cooldown_remaining(self, cell):
        return max(0, self._cooldown_until.get(cell, self._clock) - self._clock)

    def cooldown_kind(self, cell):
        return self._cooldown_kind.get(cell) if self.is_on_cooldown(cell) else None

    def contested_destination(self, end, color):
        """The earliest-started active move (if any) of `color` already
        heading to `end`. Used by GameEngine to resolve a same-color
        destination contest proactively - before a second same-color mover
        to the same cell is even allowed to start - by truncating or
        rejecting it. `active_moves()` preserves start order, so the first
        match is the earliest-started contender."""
        for move in self.active_moves():
            if move.end == end and move.piece[0] == color:
                return move
        return None

    def start_move(self, piece, start, end):
        # The source leaves the board the instant the move starts, not on
        # arrival: otherwise it stays "occupied" for the whole flight,
        # wrongly blocking other pieces from moving into it early and
        # blocking sliding pieces' path_is_clear checks through it.
        self._board.set(*start, self._config.EMPTY_CELL)
        self._active_moves.append(Move(piece, start, end, self._arrival_clock(start, end)))

    def start_jump(self, piece, cell):
        self._active_jumps.append(Jump(piece, cell, self._clock + self._config.JUMP_DURATION))

    def advance_time(self, dt):
        """Advance simulated time and resolve whatever became due."""
        self._clock += dt
        return self.resolve()

    def resolve(self):
        """Settle any moves whose arrival time has been reached, without
        advancing the clock. Returns the arrival events produced."""
        remaining = []
        events = []
        for move in self._active_moves:
            if self._clock < move.arrival:
                remaining.append(move)
                continue
            event = self._settle_move(move)
            if event is not None:
                events.append(event)
        self._active_moves = remaining
        self._resolve_jumps()
        return events

    # -- internal helpers -------------------------------------------------

    def _arrival_clock(self, start, end):
        """A move takes MOVE_DURATION per square travelled; distance is the
        number of squares on a straight/diagonal path (Chebyshev metric)."""
        distance = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        return self._clock + distance * self._config.MOVE_DURATION

    def _settle_move(self, move):
        if self._is_intercepted(move):
            # The moving piece is captured mid-flight by the jumping piece,
            # so it is removed from its source rather than surviving there.
            self._board.set(*move.start, self._config.EMPTY_CELL)
            return None

        r, c = move.end
        target = self._board.get(r, c)
        if target != self._config.EMPTY_CELL and target[0] == move.piece[0]:
            # Defensive safety net: GameEngine.request_move already resolves
            # a same-color destination contest proactively (see
            # contested_destination), truncating or rejecting the second
            # mover before it ever starts - so this should only fire on a
            # rare same-tick race the proactive check couldn't see coming
            # (two same-color moves both settling in the same resolve()
            # call). The piece must never simply vanish. Its source was
            # cleared the moment its move started, so that cell is normally
            # free and is used; if a third piece has since taken it too,
            # the nearest empty neighbouring cell is used instead, and if
            # even that whole neighbourhood is full, the start cell is
            # reused anyway (overwriting) as an absolute last resort -
            # never discarding the piece.
            self._board.set(*self._safe_fallback_cell(move.start), move.piece)
            return None

        captured = None if target == self._config.EMPTY_CELL else target
        piece = self._promotion_rule.promote(move.piece, r, self._board.height)
        self._board.set(r, c, piece)
        self._cooldown_until[(r, c)] = move.arrival + self._config.MOVE_COOLDOWN_DURATION
        self._cooldown_kind[(r, c)] = "move"
        return ArrivalEvent(piece=piece, destination=(r, c), captured=captured)

    def _safe_fallback_cell(self, start):
        """Where to land a piece whose destination is blocked at settle
        time (see _settle_move). Prefers `start` (almost always free, since
        it was cleared the instant the move began); falls back to the
        nearest empty neighbour, and to `start` itself (overwriting) if
        even the whole neighbourhood is occupied."""
        if self._board.is_empty(*start):
            return start
        r, c = start
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if self._board.in_bounds(nr, nc) and self._board.is_empty(nr, nc):
                    return (nr, nc)
        return start

    def _is_intercepted(self, move):
        r, c = move.end
        return any(
            jump.cell == (r, c) and jump.piece[0] != move.piece[0]
            for jump in self._active_jumps
        )

    def _resolve_jumps(self):
        remaining = []
        for jump in self._active_jumps:
            if self._clock < jump.end_time:
                remaining.append(jump)
            else:
                self._cooldown_until[jump.cell] = jump.end_time + self._config.JUMP_COOLDOWN_DURATION
                self._cooldown_kind[jump.cell] = "jump"
        self._active_jumps = remaining
