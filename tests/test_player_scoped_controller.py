from board.board import Board
from game.board_mapper import BoardMapper
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
