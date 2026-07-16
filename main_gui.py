"""KungFu Chess - graphical entry point.

Run this file directly (`python main_gui.py`) to launch the OpenCV
graphical UI. See main.py for the text/stdin command-script entry point.
"""
import time

import cv2

from config import settings
from main import _build_game
from UI import ui_config
from UI.graphics_renderer import GraphicsRenderer
from UI.img import Img
from UI.assets.asset_resolver import AssetResolver
from UI.assets.sprites import PieceSprites
from UI.rendering.piece_state_machine import PieceStateMachine
from UI.rendering.piece_animator import PieceAnimator
from UI.rendering.position_resolver import PositionResolver
from UI.rendering.jump_offset_resolver import JumpOffsetResolver

WINDOW_NAME = "KungFu Chess"


def _build_renderer(engine, board, config):
    """Builds the GraphicsRenderer and everything drawing-related it needs
    (sprites, state machine, animator, position/jump resolvers, board
    background)."""
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

    return GraphicsRenderer(
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


def _on_mouse(controller, event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        controller.click(x, y)
    elif event == cv2.EVENT_RBUTTONDOWN:
        controller.jump(x, y)


def _run_loop(engine, controller, renderer):
    """Owns the cv2 window, mouse handling, and the frame-timing loop.
    Drawing itself is delegated to `renderer` (a GraphicsRenderer)."""
    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(
        WINDOW_NAME,
        lambda event, x, y, flags, param: _on_mouse(controller, event, x, y, flags, param),
    )

    last_frame = time.time()
    while True:
        now = time.time()
        elapsed_ms = int((now - last_frame) * 1000)
        last_frame = now

        engine.wait(elapsed_ms)
        snapshot = engine.snapshot(selected=controller.selected)
        renderer.advance(elapsed_ms)

        frame = renderer.render(snapshot, engine.active_moves(), engine.active_jumps())

        if snapshot.game_over:
            cv2.imshow(WINDOW_NAME, frame.img)
            cv2.waitKey(0)
            break

        cv2.imshow(WINDOW_NAME, frame.img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cv2.destroyAllWindows()


def main(config=settings):
    """Build the game from ui_config.BOARD_FILE and launch the graphical
    OpenCV front end."""
    with open(ui_config.BOARD_FILE) as f:
        board_lines = [line.rstrip("\n") for line in f]
    engine, controller, board = _build_game(board_lines, config)

    renderer = _build_renderer(engine, board, config)
    _run_loop(engine, controller, renderer)


if __name__ == "__main__":  # pragma: no cover
    main()
