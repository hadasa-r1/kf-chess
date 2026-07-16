from game.models import MoveResult
from game.move_history import MoveRecord
from rules.piece_rules import path_is_clear
from rules.reasons import Reason
from view.snapshot import GameSnapshot


class GameEngine:
    """Application-service coordinator and public command boundary.

    It owns none of the details it coordinates: legality lives in RuleEngine,
    real-time motion in RealTimeArbiter, the win rule in an injected
    WinCondition, and selection/pixel handling in the Controller. The engine
    only sequences them - applying application-level guards (game over, one
    motion at a time), delegating validation, starting validated motions,
    advancing time, and exposing a read-only snapshot.

    All collaborators are injected through the constructor - no module-level
    state, no hidden globals - so the engine is straightforward to unit test
    with fakes/stubs instead of monkeypatching.
    """

    def __init__(self, board, rule_engine, arbiter, win_condition, config, history, score_board):
        self._board = board
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self._win_condition = win_condition
        self._config = config
        self._history = history
        self._score_board = score_board
        self._game_over = False

    @property
    def game_over(self):
        return self._game_over

    @property
    def clock(self):
        return self._arbiter.clock

    def active_moves(self):
        return self._arbiter.active_moves()

    def active_jumps(self):
        return self._arbiter.active_jumps()

    def move_history(self, color):
        return self._history.for_color(color)

    def score(self, color):
        return self._score_board.score_for(color)

    def is_busy(self, cell):
        return self._arbiter.is_moving_from(cell) or self._arbiter.is_jumping_on(cell)

    def cooldown_remaining(self, cell):
        return self._arbiter.cooldown_remaining(cell)

    def cooldown_kind(self, cell):
        return self._arbiter.cooldown_kind(cell)

    def can_select(self, cell):
        """Whether `cell` can be picked as a move source right now."""
        self._apply_events(self._arbiter.resolve())
        if self._game_over:
            return False
        return (
            not self.is_busy(cell)
            and not self._arbiter.is_on_cooldown(cell)
            and not self._board.is_empty(*cell)
        )

    def request_move(self, start, end):
        self._apply_events(self._arbiter.resolve())
        if self._game_over:
            return MoveResult(False, Reason.GAME_OVER)
        if self.is_busy(start):
            return MoveResult(False, Reason.BUSY_SOURCE)
        if self._arbiter.is_on_cooldown(start):
            return MoveResult(False, Reason.ON_COOLDOWN)

        validation = self._rule_engine.validate_move(self._board, start, end)
        if not validation.is_valid:
            return MoveResult(False, validation.reason)

        # Real-time policy: only one move may be in flight at a time, so a
        # second move is rejected while any move is active and the piece that
        # started first wins a contested route. Flip ALLOW_CONCURRENT_MOVES in
        # config to lift this restriction.
        if not self._config.ALLOW_CONCURRENT_MOVES and self._arbiter.has_active_motion():
            return MoveResult(False, Reason.MOTION_IN_PROGRESS)

        piece = self._board.get(*start)

        # Same-color destination contest: resolved proactively here (not
        # retroactively on arrival), so the later mover visibly brakes in
        # real time instead of sliding all the way in and snapping back.
        # The move that started first always keeps its original full
        # destination - this only ever adjusts the second, later-requested
        # same-color move. Opposite-color contests are untouched: the later
        # arrival correctly captures whichever arrived first (see
        # RealTimeArbiter._settle_move).
        if self._arbiter.contested_destination(end, piece[0]) is not None:
            truncated_end = self._truncated_destination(start, end)
            if truncated_end is None:
                return MoveResult(False, Reason.DESTINATION_CONTESTED)
            end = truncated_end

        self._arbiter.start_move(piece, start, end)
        self._history.record(MoveRecord(
            color=piece[0], piece=piece, start=start, end=end,
            timestamp=self._arbiter.clock,
        ))
        return MoveResult(True, Reason.OK)

    def request_jump(self, cell):
        self._apply_events(self._arbiter.resolve())
        if self._game_over:
            return MoveResult(False, Reason.GAME_OVER)
        if self.is_busy(cell):
            return MoveResult(False, Reason.BUSY_CELL)
        if self._arbiter.is_on_cooldown(cell):
            return MoveResult(False, Reason.ON_COOLDOWN)
        if self._board.is_empty(*cell):
            return MoveResult(False, Reason.EMPTY_CELL)

        self._arbiter.start_jump(self._board.get(*cell), cell)
        return MoveResult(True, Reason.OK)

    def wait(self, dt):
        self._apply_events(self._arbiter.advance_time(dt))

    def snapshot(self, selected=None):
        return GameSnapshot.from_board(self._board, self._game_over, selected=selected)

    def render(self, renderer):
        self._apply_events(self._arbiter.resolve())
        return renderer.render(self.snapshot())

    # -- internal helpers -------------------------------------------------

    def _truncated_destination(self, start, end):
        """If `start` -> `end` is a straight/diagonal line of 2+ squares
        (the same shape rules.piece_rules.path_is_clear already assumes for
        Rook/Bishop/Queen) and the square one step short of `end` along
        that line is itself reachable and empty, return that square - the
        contested move stops there instead of the original destination.
        Returns None when there is no such square (an adjacent-square move,
        non-linear movement like a knight, or a blocked intermediate)."""
        sr, sc = start
        er, ec = end
        dr, dc = abs(er - sr), abs(ec - sc)
        straight = (dr == 0) != (dc == 0)
        diagonal = dr == dc and dr != 0
        if not (straight or diagonal) or max(dr, dc) < 2:
            return None

        step_r = (er > sr) - (er < sr)
        step_c = (ec > sc) - (ec < sc)
        intermediate = (er - step_r, ec - step_c)
        if not path_is_clear(self._board, start, intermediate) or not self._board.is_empty(*intermediate):
            return None
        return intermediate

    def _apply_events(self, events):
        """React to arrivals reported by the arbiter. The arbiter reports what
        was captured; the engine owns whether that ends the game."""
        for event in events:
            if event.captured is not None:
                self._score_board.apply_capture(event.piece[0], event.captured)
            if self._win_condition.is_game_over(event.captured):
                self._game_over = True
