from game.score_board import ScoreBoard

PIECE_VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}


def test_apply_capture_accumulates_per_color():
    board = ScoreBoard(PIECE_VALUES)
    board.apply_capture("w", "bP")
    board.apply_capture("w", "bN")

    assert board.score_for("w") == 4
    assert board.score_for("b") == 0


def test_king_capture_scores_zero():
    board = ScoreBoard(PIECE_VALUES)
    board.apply_capture("w", "bK")

    assert board.score_for("w") == 0


def test_score_for_untouched_color_is_zero():
    board = ScoreBoard(PIECE_VALUES)

    assert board.score_for("b") == 0
