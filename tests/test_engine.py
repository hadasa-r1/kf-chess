import pytest

from config import settings
from board.text_board import TextBoardRepresentation
from rules.rule_registry import build_default_registry
from rules.game_conditions import KingCaptureWinCondition, LastRankPromotion, WinCondition, PromotionRule
from game.engine import GameEngine
from game.renderer import BoardRenderer


class NeverEndsWinCondition(WinCondition):
    """Fake collaborator used to test engine behaviour in isolation,
    injected instead of monkeypatching KingCaptureWinCondition."""

    def is_game_over(self, captured_piece):
        return False


class NoPromotion(PromotionRule):
    def promote(self, piece, row, board_height):
        return piece


def make_engine(rows, win_condition=None, promotion_rule=None):
    board = TextBoardRepresentation(rows)
    registry = build_default_registry(settings)
    return GameEngine(
        board=board,
        rule_registry=registry,
        win_condition=win_condition or KingCaptureWinCondition(),
        promotion_rule=promotion_rule or LastRankPromotion(),
        config=settings,
    ), board


def cell_to_pixel(row, col):
    return col * settings.CELL_SIZE, row * settings.CELL_SIZE


def test_click_selects_own_piece():
    engine, board = make_engine([["wK", "."], [".", "."]])
    x, y = cell_to_pixel(0, 0)
    engine.handle_click(x, y)
    assert engine.selected == (0, 0)


def test_click_out_of_bounds_is_ignored():
    engine, board = make_engine([["wK", "."], [".", "."]])
    engine.handle_click(-1, -1)
    assert engine.selected is None


def test_selecting_then_moving_starts_a_move():
    engine, board = make_engine([["wR", ".", "."], [".", ".", "."], [".", ".", "."]])
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 2))

    assert engine.selected is None
    # the piece stays visible at its origin until the move actually arrives
    assert board.get(0, 0) == "wR"
    assert board.is_empty(0, 2)


def test_move_duration_scales_with_distance():
    engine, board = make_engine([["wR", ".", "."], [".", ".", "."], [".", ".", "."]])
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 2))  # 2 cells away

    engine.wait(settings.MOVE_DURATION)  # only enough time for 1 cell
    assert board.get(0, 0) == "wR"  # not arrived yet

    engine.wait(settings.MOVE_DURATION)  # total = 2 cells worth of time
    assert board.get(0, 2) == "wR"
    assert board.is_empty(0, 0)


def test_illegal_move_keeps_selection_and_piece_in_place():
    engine, board = make_engine([["wN", ".", "."], [".", ".", "."], [".", ".", "."]])
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 1))  # not a legal knight move

    assert engine.selected == (0, 0)
    assert board.get(0, 0) == "wN"


def test_king_capture_ends_the_game():
    rows = [["wR", ".", "bK"], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 2))
    engine.wait(settings.MOVE_DURATION * 2)  # 2 cells of distance

    assert engine.game_over is True


def test_injected_win_condition_overrides_default_behaviour():
    rows = [["wR", ".", "bK"], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows, win_condition=NeverEndsWinCondition())
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 2))
    engine.wait(settings.MOVE_DURATION * 2)

    assert engine.game_over is False


def test_jump_intercepts_a_move_of_the_opposite_color():
    rows = [["wR", ".", "bP"], [".", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 2))  # move arrives after 2 cells of time
    engine.handle_jump(*cell_to_pixel(0, 2))

    engine.wait(settings.MOVE_DURATION * 2)
    assert board.get(0, 2) == "bP"  # move was intercepted, target unchanged
    assert board.is_empty(0, 0)  # the intercepted piece is destroyed, not returned


def test_pawn_promotion_on_arrival():
    # white pawn one step from the last rank (row 0)
    rows = [[".", ".", "."], ["wP", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows)

    engine.handle_click(*cell_to_pixel(1, 0))
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.wait(settings.MOVE_DURATION)

    assert board.get(0, 0) == "wQ"


def test_injected_promotion_rule_overrides_default_behaviour():
    rows = [[".", ".", "."], ["wP", ".", "."], [".", ".", "."]]
    engine, board = make_engine(rows, promotion_rule=NoPromotion())

    engine.handle_click(*cell_to_pixel(1, 0))
    engine.handle_click(*cell_to_pixel(0, 0))
    engine.wait(settings.MOVE_DURATION)

    assert board.get(0, 0) == "wP"


def test_render_returns_current_board_text():
    engine, board = make_engine([["wK", "."], [".", "bK"]])
    text = engine.render(BoardRenderer())
    assert text == "wK .\n. bK"

def test_second_move_is_blocked_while_one_is_in_flight():
    rows = [["wR", ".", "."], [".", ".", "."], ["bR", ".", "."]]
    engine, board = make_engine(rows)

    engine.handle_click(*cell_to_pixel(0, 0))
    engine.handle_click(*cell_to_pixel(0, 2))  # white move starts, still in flight

    engine.handle_click(*cell_to_pixel(2, 0))
    engine.handle_click(*cell_to_pixel(2, 2))  # blocked: a move is already active

    engine.wait(settings.MOVE_DURATION * 2)
    assert board.get(0, 2) == "wR"
    assert board.get(2, 0) == "bR"  # never moved
