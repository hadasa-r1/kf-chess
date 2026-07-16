"""KungFu Chess - entry point.

Repository: https://github.com/hadasa-r1/kf-chess
"""
import sys

from config import settings
from rules.rule_registry import build_default_registry
from rules.rule_engine import RuleEngine
from rules.game_conditions import KingCaptureWinCondition, LastRankPromotion
from realtime.real_time_arbiter import RealTimeArbiter
from game.parser import parse_input
from board.loaders import load_text_board, BoardParseError
from game.board_mapper import BoardMapper
from game.engine import GameEngine
from game.controller import Controller
from view.renderer import BoardRenderer


def _build_game(board_lines, config):
    """Constructs the registry/board/arbiter/engine/controller graph shared
    by the text CLI and the graphical UI. The only place in the project
    that builds this graph, so a change to any constructor's arguments
    only needs to be made here.
    """
    registry = build_default_registry(config)
    board = load_text_board(board_lines, registry, config)

    arbiter = RealTimeArbiter(
        board=board,
        promotion_rule=LastRankPromotion(config.PAWN_DIRECTION),
        config=config,
    )
    engine = GameEngine(
        board=board,
        rule_engine=RuleEngine(rule_registry=registry, config=config),
        arbiter=arbiter,
        win_condition=KingCaptureWinCondition(),
        config=config,
    )
    controller = Controller(
        engine=engine,
        board_mapper=BoardMapper(board, config.CELL_SIZE),
    )
    return engine, controller, board


def run(input_lines, config=settings):
    """Parse input and execute all commands. `config` is injectable so
    tests (or custom variants) can supply alternate settings without
    monkeypatching the settings module.
    """
    board_lines, commands = parse_input(input_lines)

    try:
        engine, controller, board = _build_game(board_lines, config)
    except BoardParseError as error:
        print("ERROR", error)
        return

    renderer = BoardRenderer()

    for command in commands:
        _dispatch(command, engine, controller, renderer)


def _dispatch(command, engine, controller, renderer):
    parts = command.split()
    if not parts:
        return

    action = parts[0]
    if action == "click":
        controller.click(int(parts[1]), int(parts[2]))
    elif action == "jump":
        controller.jump(int(parts[1]), int(parts[2]))
    elif action == "wait":
        engine.wait(int(parts[1]))
    elif action == "print":
        print(engine.render(renderer))


def run_gui(config=settings):
    """Build the game from ui_config.BOARD_FILE and launch the graphical
    OpenCV front end. Split out from main() so tests can verify --gui
    routes here without actually opening a window. UI-specific imports
    (cv2 and everything that pulls it in) are kept local to this function
    so plain CLI usage never needs them importable.
    """
    from UI import ui_config
    from UI.game_ui import run_gui as run_gui_loop
    from UI.graphics_renderer import GraphicsRenderer
    from UI.img import Img
    from UI.assets.asset_resolver import AssetResolver
    from UI.assets.sprites import PieceSprites
    from UI.rendering.piece_state_machine import PieceStateMachine
    from UI.rendering.piece_animator import PieceAnimator
    from UI.rendering.position_resolver import PositionResolver
    from UI.rendering.jump_offset_resolver import JumpOffsetResolver

    with open(ui_config.BOARD_FILE) as f:
        board_lines = [line.rstrip("\n") for line in f]
    engine, controller, board = _build_game(board_lines, config)

    asset_resolver = AssetResolver(ui_config.PIECES_DIR, ui_config.FOLDER_MAP, ui_config.STATE_MAP)
    sprites = PieceSprites(asset_resolver, config.CELL_SIZE)
    # Matches the same durations GameEngine actually enforces
    # (engine.cooldown_remaining is the source of truth; this just says how
    # long each kind started at).
    rest_durations = {
        "long_rest": config.MOVE_COOLDOWN_DURATION,
        "short_rest": config.JUMP_COOLDOWN_DURATION,
    }
    state_machine = PieceStateMachine()
    animator = PieceAnimator(ui_config.FRAME_DURATION_MS)
    position_resolver = PositionResolver(config.CELL_SIZE, config.MOVE_DURATION)
    jump_offset_resolver = JumpOffsetResolver(config.CELL_SIZE, config.JUMP_DURATION)
    board_bg = Img().read(ui_config.BOARD_IMAGE_PATH)

    renderer = GraphicsRenderer(
        engine=engine,
        sprites=sprites,
        state_machine=state_machine,
        animator=animator,
        position_resolver=position_resolver,
        jump_offset_resolver=jump_offset_resolver,
        rest_durations=rest_durations,
        board_bg=board_bg,
        cell_size=config.CELL_SIZE,
        board_width=board.width,
        board_height=board.height,
    )
    run_gui_loop(engine, controller, renderer)


def main(input_stream=None, argv=None):
    """Entry point: runs the text command loop by default, or launches the
    graphical UI if invoked with --gui. `input_stream`/`argv` are
    injectable so tests can supply alternatives instead of monkeypatching
    sys.stdin/sys.argv; they default to real stdin / sys.argv[1:].
    """
    args = sys.argv[1:] if argv is None else argv
    if "--gui" in args:
        run_gui()
        return

    stream = sys.stdin if input_stream is None else input_stream
    lines = [line.strip() for line in stream]
    run(lines)


if __name__ == "__main__":  # pragma: no cover
    main()
