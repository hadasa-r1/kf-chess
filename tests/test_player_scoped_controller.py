from config import settings
from bus.event_bus import EventBus
from board.board import Board
from rules.rule_registry import build_default_registry
from rules.rule_engine import RuleEngine
from rules.game_conditions import KingCaptureWinCondition, LastRankPromotion
from realtime.real_time_arbiter import RealTimeArbiter
from game.engine import GameEngine
from game.board_mapper import BoardMapper
from game.controller import Controller
from game.move_history import MoveHistory
from game.score_board import ScoreBoard
from server.player_scoped_controller import PlayerScopedController


class _FakeController:
    """Records calls; `selected` is settable so tests can simulate a
    move-in-progress (second click) without a real engine."""

    def __init__(self):
        self.selected = None
        self.clicks = []
        self.jumps = []

    def click(self, x, y):
        self.clicks.append((x, y))

    def jump(self, x, y):
        self.jumps.append((x, y))


def _make(assigned_color, selected=None):
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    board = Board(rows)
    mapper = BoardMapper(board, cell_size=100)
    controller = _FakeController()
    controller.selected = selected
    scoped = PlayerScopedController(controller, assigned_color, board, mapper)
    return scoped, controller


def test_select_click_on_own_color_piece_is_forwarded():
    scoped, controller = _make("w")

    scoped.click(0, 0)  # pixel (0,0) -> cell (0,0) -> "wR"

    assert controller.clicks == [(0, 0)]
    assert scoped.selected is None  # delegates straight through - fake never sets it


def test_select_click_on_opposite_color_piece_is_not_forwarded():
    scoped, controller = _make("w")

    scoped.click(200, 0)  # pixel (200,0) -> cell (0,2) -> "bP"

    assert controller.clicks == []


def test_select_click_on_empty_cell_is_not_forwarded():
    scoped, controller = _make("w")

    scoped.click(100, 0)  # pixel (100,0) -> cell (0,1) -> "."

    assert controller.clicks == []


def test_select_click_outside_the_board_is_forwarded_unchanged():
    # Controller itself already treats an out-of-bounds click as a no-op
    # (BoardMapper.pixel_to_cell returns None) - PlayerScopedController
    # only rejects clicks it can actually map to an owned/unowned cell, so
    # it defers to the wrapped Controller here rather than guessing.
    scoped, controller = _make("w")

    scoped.click(-10, -10)

    assert controller.clicks == [(-10, -10)]


def test_move_click_is_always_forwarded_regardless_of_destination_owner():
    # A selection is already in progress (selected is not None) - this is
    # the "move" click, not the "select" click - so ownership of the
    # *destination* cell is irrelevant (capturing an enemy piece is the
    # whole point of a move) and it must always be forwarded.
    scoped, controller = _make("w", selected=(0, 0))

    scoped.click(200, 0)  # destination cell (0,2) holds the opposite color

    assert controller.clicks == [(200, 0)]


def test_black_assigned_color_can_select_black_piece_but_not_white():
    scoped, controller = _make("b")

    scoped.click(200, 0)  # (0,2) -> "bP" - owned
    assert controller.clicks == [(200, 0)]

    scoped.click(0, 0)  # (0,0) -> "wR" - not owned
    assert controller.clicks == [(200, 0)]  # unchanged


def test_jump_is_always_forwarded_with_no_ownership_check():
    # TODO parity: GameEngine.request_jump has no color concept at all
    # (see game/engine.py) - PlayerScopedController intentionally applies
    # no ownership check to jump either, for either color.
    scoped, controller = _make("w")

    scoped.jump(200, 0)  # (0,2) holds the opposite color - forwarded anyway

    assert controller.jumps == [(200, 0)]


def test_selected_property_delegates_to_the_wrapped_controller():
    scoped, controller = _make("w")
    controller.selected = (3, 3)

    assert scoped.selected == (3, 3)


def _make_real(rows, assigned_color):
    """Wraps a REAL Controller/GameEngine (not the fake above) - needed to
    reproduce the actual bug: Controller._resolve_selection's color-blind
    re-select (see its docstring in game/controller.py) only exists in the
    real Controller, not in _FakeController's simple call recorder."""
    board = Board(rows)
    registry = build_default_registry(settings)
    engine = GameEngine(
        board=board,
        rule_engine=RuleEngine(rule_registry=registry, config=settings),
        arbiter=RealTimeArbiter(board=board, promotion_rule=LastRankPromotion(settings.PAWN_DIRECTION), config=settings),
        win_condition=KingCaptureWinCondition(),
        config=settings,
        history=MoveHistory(),
        score_board=ScoreBoard(settings.PIECE_VALUES),
        event_bus=EventBus(),
    )
    mapper = BoardMapper(board, settings.CELL_SIZE)
    controller = Controller(engine=engine, board_mapper=mapper)
    scoped = PlayerScopedController(controller, assigned_color, board, mapper)
    return scoped, controller, engine, board


def _cell_pixel(row, col):
    return col * settings.CELL_SIZE, row * settings.CELL_SIZE


def test_illegal_second_click_onto_enemy_piece_deselects_instead_of_taking_it():
    # The reported bug: Controller's own color-blind re-select (see its
    # docstring) would otherwise leave `selected` pointing at the black
    # rook after this rejected knight move - PlayerScopedController must
    # catch that and clear it instead, since this connection is White.
    rows = [["wN", ".", "."], [".", "bR", "."], [".", ".", "."]]
    scoped, controller, engine, board = _make_real(rows, "w")

    scoped.click(*_cell_pixel(0, 0))  # select own knight
    assert scoped.selected == (0, 0)

    scoped.click(*_cell_pixel(1, 1))  # illegal knight move onto the enemy rook

    assert scoped.selected is None
    assert board.get(1, 1) == "bR"  # the enemy piece was never actually taken


def test_illegal_second_click_onto_enemy_piece_deselects_for_black_too():
    # Symmetric case: assigned_color="b" clicking into a white piece.
    rows = [["bN", ".", "."], [".", "wR", "."], [".", ".", "."]]
    scoped, controller, engine, board = _make_real(rows, "b")

    scoped.click(*_cell_pixel(0, 0))  # select own knight
    assert scoped.selected == (0, 0)

    scoped.click(*_cell_pixel(1, 1))  # illegal knight move onto the enemy rook

    assert scoped.selected is None
    assert board.get(1, 1) == "wR"


def test_legitimate_second_click_still_moves_own_piece_normally():
    # Regression guard: a legal move to an empty destination must still
    # work and end with no selection, same as a real Controller's own
    # behavior - the new post-move ownership check must not interfere.
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "."]]
    scoped, controller, engine, board = _make_real(rows, "w")

    scoped.click(*_cell_pixel(0, 0))  # select own rook
    scoped.click(*_cell_pixel(0, 2))  # legal rook move to an empty cell

    assert scoped.selected is None
    assert board.is_empty(0, 0)  # source clears the instant the move starts
