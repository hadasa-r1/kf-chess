import json

from config import settings
from bus.event_bus import EventBus
from bus_handlers.move_log_display_state import MoveLogDisplayState
from bus_handlers.score_display_state import ScoreDisplayState
from board.board import Board
from rules.rule_registry import build_default_registry
from rules.rule_engine import RuleEngine
from rules.game_conditions import KingCaptureWinCondition, LastRankPromotion
from realtime.real_time_arbiter import RealTimeArbiter
from game.engine import GameEngine
from game.move_history import MoveHistory
from game.score_board import ScoreBoard
from server.protocol import serialize_frame_update
from view.snapshot import FrameState


class _FakeController:
    def __init__(self, selected=None):
        self.selected = selected


def _make_engine(rows):
    bus = EventBus()
    score_state = ScoreDisplayState(bus)
    move_log_state = MoveLogDisplayState(bus)
    registry = build_default_registry(settings)
    board = Board(rows)
    arbiter = RealTimeArbiter(board=board, promotion_rule=LastRankPromotion(settings.PAWN_DIRECTION), config=settings)
    engine = GameEngine(
        board=board,
        rule_engine=RuleEngine(rule_registry=registry, config=settings),
        arbiter=arbiter,
        win_condition=KingCaptureWinCondition(),
        config=settings,
        history=MoveHistory(),
        score_board=ScoreBoard(settings.PIECE_VALUES),
        event_bus=bus,
    )
    return engine, board, score_state, move_log_state


def _round_trip(frame_state):
    payload = serialize_frame_update(
        snapshot=frame_state.snapshot,
        moves=frame_state.moves,
        jumps=frame_state.jumps,
        clock=frame_state.clock,
        cooldowns=frame_state.cooldowns,
        cooldown_remaining=frame_state.cooldown_remaining,
    )
    # Must actually be JSON-serializable (no leftover tuples/dict-with-
    # tuple-keys) - round-trip through real json, not just the dict.
    wire_message = json.dumps(payload)
    return FrameState.from_network_payload(json.loads(wire_message))


def test_round_trip_preserves_moves_jumps_clock_and_cooldowns():
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    engine.request_move((0, 0), (0, 2))
    engine.wait(settings.MOVE_DURATION)  # halfway through the 2-square move

    original = FrameState.from_engine(engine, _FakeController(), score_state, move_log_state)
    reconstructed = _round_trip(original)

    assert reconstructed.snapshot == original.snapshot
    assert reconstructed.moves == original.moves
    assert reconstructed.jumps == original.jumps
    assert reconstructed.clock == original.clock
    assert reconstructed.cooldowns == original.cooldowns
    assert reconstructed.cooldown_remaining == original.cooldown_remaining


def test_round_trip_preserves_a_cooldown_after_a_move_lands():
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    engine.request_move((0, 0), (0, 2))
    engine.wait(2 * settings.MOVE_DURATION)  # lands, captures, starts resting

    original = FrameState.from_engine(engine, _FakeController(), score_state, move_log_state)
    reconstructed = _round_trip(original)

    assert reconstructed.cooldowns[(0, 2)] == "move"
    assert reconstructed.cooldown_remaining[(0, 2)] == settings.MOVE_COOLDOWN_DURATION
    assert reconstructed.cooldowns == original.cooldowns
    assert reconstructed.cooldown_remaining == original.cooldown_remaining


def test_round_trip_deliberately_drops_history_and_score():
    # Documented behavior, not an oversight: history/score are excluded
    # from the wire payload on purpose (they arrive via a separate event
    # channel in a later task) - the original engine-sourced FrameState
    # has real data, the reconstructed one must always be empty/zero.
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    engine.request_move((0, 0), (0, 2))
    engine.wait(2 * settings.MOVE_DURATION)  # lands, captures -> real history/score exist

    original = FrameState.from_engine(engine, _FakeController(), score_state, move_log_state)
    assert original.white_history != ()
    assert original.white_score != 0

    reconstructed = _round_trip(original)

    assert reconstructed.white_history == ()
    assert reconstructed.black_history == ()
    assert reconstructed.white_score == 0
    assert reconstructed.black_score == 0
