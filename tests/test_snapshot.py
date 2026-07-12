from board.text_board import TextBoardRepresentation
from view.snapshot import GameSnapshot
from view.renderer import BoardRenderer


def test_from_board_carries_cells_dimensions_and_game_over():
    board = TextBoardRepresentation([["wK", "."], [".", "bK"]])
    snapshot = GameSnapshot.from_board(board, game_over=True)

    assert snapshot.cells == (("wK", "."), (".", "bK"))
    assert snapshot.width == 2
    assert snapshot.height == 2
    assert snapshot.game_over is True
    assert snapshot.selected is None


def test_from_board_carries_selected_when_given():
    board = TextBoardRepresentation([["wK"]])
    snapshot = GameSnapshot.from_board(board, game_over=False, selected=(0, 0))
    assert snapshot.selected == (0, 0)


def test_snapshot_is_independent_of_later_board_mutation():
    board = TextBoardRepresentation([["wK", "."]])
    snapshot = GameSnapshot.from_board(board, game_over=False)
    board.set(0, 0, ".")
    board.set(0, 1, "wK")

    assert snapshot.cells == (("wK", "."),)  # unaffected by the mutation above


def test_renderer_reads_cells_from_snapshot():
    board = TextBoardRepresentation([["wK", "."], [".", "bK"]])
    snapshot = GameSnapshot.from_board(board, game_over=False)
    text = BoardRenderer().render(snapshot)
    assert text == "wK .\n. bK"
