from board.board import Board
from client_net.remote_controller import RemoteController
from game.board_mapper import BoardMapper


class _FakeNetworkClient:
    def __init__(self):
        self.clicks = []
        self.jumps = []

    def send_click(self, x, y):
        self.clicks.append((x, y))

    def send_jump(self, x, y):
        self.jumps.append((x, y))


def _make_controller():
    board = Board([["wR", ".", "."], [".", ".", "."], [".", ".", "."]])
    mapper = BoardMapper(board, cell_size=100)
    network_client = _FakeNetworkClient()
    return RemoteController(network_client, mapper), network_client


def test_first_click_optimistically_selects_the_cell():
    controller, network_client = _make_controller()

    controller.click(0, 0)  # pixel (0,0) -> cell (0,0)

    assert controller.selected == (0, 0)
    assert network_client.clicks == [(0, 0)]


def test_second_click_sends_the_raw_pixel_click_and_clears_selection():
    # Both clicks are forwarded as raw NetworkClient.send_click(x, y) calls
    # (matching the existing wire protocol exactly) - the server's own
    # per-connection Controller (unmodified) is what actually applies the
    # click-then-move state machine; this class only tracks an optimistic
    # local copy of "selected" for instant UI feedback.
    controller, network_client = _make_controller()

    controller.click(0, 0)  # selects (0,0)
    controller.click(200, 0)  # pixel (200,0) -> cell (0,2)

    assert controller.selected is None
    assert network_client.clicks == [(0, 0), (200, 0)]


def test_click_outside_the_board_is_a_no_op():
    controller, network_client = _make_controller()

    controller.click(-10, -10)

    assert controller.selected is None
    assert network_client.clicks == []


def test_click_outside_the_board_with_a_pending_selection_leaves_it_untouched():
    controller, network_client = _make_controller()
    controller.click(0, 0)  # selects (0,0)

    controller.click(-10, -10)  # outside the board - no-op

    assert controller.selected == (0, 0)
    assert network_client.clicks == [(0, 0)]


def test_jump_clears_selection_and_sends_raw_pixel_coordinates():
    controller, network_client = _make_controller()
    controller.click(0, 0)  # selects (0,0)

    controller.jump(200, 0)  # pixel (200,0) -> cell (0,2)

    assert controller.selected is None
    assert network_client.jumps == [(200, 0)]


def test_jump_outside_the_board_still_clears_selection_but_sends_nothing():
    controller, network_client = _make_controller()
    controller.click(0, 0)  # selects (0,0)

    controller.jump(-10, -10)

    assert controller.selected is None
    assert network_client.jumps == []
