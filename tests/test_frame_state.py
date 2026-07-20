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


def test_from_engine_matches_the_old_direct_engine_calls_for_moves_jumps_and_clock():
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    engine.request_move((0, 0), (0, 2))
    controller = _FakeController(selected=(0, 0))

    frame_state = FrameState.from_engine(engine, controller, score_state, move_log_state)

    assert frame_state.snapshot == engine.snapshot(selected=(0, 0))
    assert frame_state.moves == tuple(engine.active_moves())
    assert frame_state.jumps == tuple(engine.active_jumps())
    assert frame_state.clock == engine.clock


def test_from_engine_sources_history_and_score_from_the_bus_read_models():
    # Deliberately NOT engine.move_history()/engine.score(): main_gui.py's
    # render loop already sources these from the bus-fed read models (see
    # main_gui._run_loop), and from_engine preserves that rather than
    # reintroducing a direct engine dependency for these two fields.
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    engine.request_move((0, 0), (0, 2))
    engine.wait(2 * settings.MOVE_DURATION)  # lands, captures bP
    controller = _FakeController()

    frame_state = FrameState.from_engine(engine, controller, score_state, move_log_state)

    assert frame_state.white_history == move_log_state.entries_for("w")
    assert frame_state.black_history == move_log_state.entries_for("b")
    assert frame_state.white_score == score_state.score_for("w")
    assert frame_state.black_score == score_state.score_for("b")
    assert len(frame_state.white_history) == 1
    assert frame_state.white_score == 1  # pawn value


def test_cooldowns_dict_covers_every_occupied_cell():
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    engine.request_move((0, 0), (0, 2))
    engine.wait(2 * settings.MOVE_DURATION)  # wR lands on (0,2), starts resting
    controller = _FakeController()

    frame_state = FrameState.from_engine(engine, controller, score_state, move_log_state)

    occupied_cells = {
        (row, col)
        for row, cells in enumerate(frame_state.snapshot.cells)
        for col, token in enumerate(cells)
        if token != "."
    }
    assert set(frame_state.cooldowns.keys()) == occupied_cells
    assert set(frame_state.cooldown_remaining.keys()) == occupied_cells
    assert frame_state.cooldowns[(0, 2)] == "move"
    assert frame_state.cooldown_remaining[(0, 2)] == settings.MOVE_COOLDOWN_DURATION


def test_cooldowns_and_remaining_are_none_and_zero_for_a_cell_not_on_cooldown():
    rows = [["wK", ".", "."]]
    engine, board, score_state, move_log_state = _make_engine(rows)
    controller = _FakeController()

    frame_state = FrameState.from_engine(engine, controller, score_state, move_log_state)

    assert frame_state.cooldowns[(0, 0)] is None
    assert frame_state.cooldown_remaining[(0, 0)] == 0
