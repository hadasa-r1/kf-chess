import numpy as np

from config import settings
from board.board import Board
from rules.rule_registry import build_default_registry
from rules.rule_engine import RuleEngine
from rules.game_conditions import KingCaptureWinCondition, LastRankPromotion
from realtime.real_time_arbiter import RealTimeArbiter
from game.engine import GameEngine
from game.move_history import MoveHistory
from game.score_board import ScoreBoard
from UI.img import Img
from UI.graphics_renderer import GraphicsRenderer
from UI.rendering.piece_state_machine import PieceStateMachine
from UI.rendering.piece_animator import PieceAnimator
from UI.rendering.position_resolver import PositionResolver
from UI.rendering.jump_offset_resolver import JumpOffsetResolver
from UI.rendering.side_panel_renderer import SidePanelRenderer


class _FakeImg:
    def __init__(self):
        self.img = np.zeros((100, 100, 4), dtype=np.uint8)
        self.draw_calls = []

    def draw_on(self, other, x, y):
        self.draw_calls.append((x, y))


class _FakeSprites:
    def __init__(self):
        self.last_sprite = None

    def get(self, token, state):
        sprite = _FakeImg()
        self.last_sprite = sprite
        return [sprite]


def _make_engine(rows):
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
    )
    return engine, board


def test_render_draws_a_mid_flight_piece_from_raw_moves_list():
    engine, board = _make_engine([["wR", ".", "."]])
    engine.request_move((0, 0), (0, 2))  # 2-square move, 2000ms total
    engine.wait(1000)  # halfway

    board_bg = Img()
    board_bg.img = np.full((100, 300, 4), 255, dtype=np.uint8)
    sprites = _FakeSprites()

    renderer = GraphicsRenderer(
        engine=engine,
        sprites=sprites,
        state_machine=PieceStateMachine(),
        animator=PieceAnimator(120),
        position_resolver=PositionResolver(100, settings.MOVE_DURATION),
        jump_offset_resolver=JumpOffsetResolver(100, settings.JUMP_DURATION),
        rest_durations={"long_rest": settings.MOVE_COOLDOWN_DURATION, "short_rest": settings.JUMP_COOLDOWN_DURATION},
        board_bg=board_bg,
        cell_size=100,
        board_width=3,
        board_height=1,
        side_panel_renderer=SidePanelRenderer(50, (30, 30, 30, 255), (255, 255, 255, 255)),
    )

    # Raw lists straight from the engine - not pre-built dicts.
    renderer.render(
        engine.snapshot(), engine.active_moves(), engine.active_jumps(),
        engine.move_history("w"), engine.move_history("b"),
        engine.score("w"), engine.score("b"),
    )

    # Halfway through a 2-square move, the piece should be drawn at the
    # interpolated pixel position (x=100), not its static grid cell (x=0).
    assert sprites.last_sprite.draw_calls == [(100, 0)]


def test_render_does_not_crash_when_a_reoccupied_origin_cell_has_an_unrelated_active_move():
    # wR1 (0,0)->(0,3) takes 3 move-durations to arrive; wR2 (2,0)->(0,0)
    # takes only 2, so wR2 lands on wR1's already-vacated start cell before
    # wR1 itself arrives. (0,0) is then genuinely occupied again while still
    # being an unrelated active move's `start` - GameEngine.is_busy((0,0))
    # is True (it only checks "is this cell some move's start", not whether
    # that move's piece still lives here), which used to be mistaken by the
    # renderer for "this occupied cell is jumping" and crash looking it up
    # in the (empty) active-jumps dict.
    rows = [
        ["wR", ".", ".", "."],
        [".", ".", ".", "."],
        ["wR", ".", ".", "."],
    ]
    engine, board = _make_engine(rows)
    engine.request_move((0, 0), (0, 3))
    engine.request_move((2, 0), (0, 0))
    engine.wait(2 * settings.MOVE_DURATION)  # wR2 arrives at (0,0); wR1 still in flight
    assert board.get(0, 0) == "wR"  # wR2 landed on wR1's vacated start

    board_bg = Img()
    board_bg.img = np.full((300, 400, 4), 255, dtype=np.uint8)
    sprites = _FakeSprites()

    renderer = GraphicsRenderer(
        engine=engine,
        sprites=sprites,
        state_machine=PieceStateMachine(),
        animator=PieceAnimator(120),
        position_resolver=PositionResolver(100, settings.MOVE_DURATION),
        jump_offset_resolver=JumpOffsetResolver(100, settings.JUMP_DURATION),
        rest_durations={"long_rest": settings.MOVE_COOLDOWN_DURATION, "short_rest": settings.JUMP_COOLDOWN_DURATION},
        board_bg=board_bg,
        cell_size=100,
        board_width=4,
        board_height=3,
        side_panel_renderer=SidePanelRenderer(50, (30, 30, 30, 255), (255, 255, 255, 255)),
    )

    # Must not raise KeyError for the reoccupied (0, 0) cell.
    renderer.render(
        engine.snapshot(), engine.active_moves(), engine.active_jumps(),
        engine.move_history("w"), engine.move_history("b"),
        engine.score("w"), engine.score("b"),
    )
