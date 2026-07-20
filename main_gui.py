"""KungFu Chess - graphical entry point.

Run this file directly (`python main_gui.py`) to launch the OpenCV
graphical UI. See main.py for the text/stdin command-script entry point.
"""
import time

import cv2

from bus.event_bus import EventBus
from bus_handlers.animation_trigger_handler import AnimationTriggerHandler
from bus_handlers.audio_sound_player import AudioSoundPlayer
from bus_handlers.graphics_animation_trigger import GraphicsAnimationTrigger
from bus_handlers.move_log_display_state import MoveLogDisplayState
from bus_handlers.score_display_state import ScoreDisplayState
from bus_handlers.sound_handler import SoundHandler
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
from UI.rendering.side_panel_renderer import SidePanelRenderer
from view.snapshot import FrameState

WINDOW_NAME = "KungFu Chess"


def _build_renderer(board, config):
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
    side_panel_renderer = SidePanelRenderer(
        ui_config.SIDE_PANEL_WIDTH, ui_config.SIDE_PANEL_BACKGROUND_COLOR, ui_config.SIDE_PANEL_TEXT_COLOR,
    )

    return GraphicsRenderer(
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
        side_panel_renderer=side_panel_renderer,
    )


def _build_bus_handlers(bus):
    """Builds the four bus-driven subscribers (score/move-log read models,
    sound, animation) and subscribes them to `bus`.

    Must be called - and its handlers subscribed - *before* `_build_game`
    constructs GameEngine: GameEngine publishes GameStartedEvent
    synchronously from its own __init__, so a subscriber wired only after
    that call returns would silently miss the very first game's start.
    """
    score_state = ScoreDisplayState(bus)
    move_log_state = MoveLogDisplayState(bus)
    sound_handler = SoundHandler(bus, AudioSoundPlayer())
    animation_handler = AnimationTriggerHandler(bus, GraphicsAnimationTrigger())
    return score_state, move_log_state, sound_handler, animation_handler


def _on_mouse(controller, board_offset_x, event, x, y, flags, param):
    # The displayed frame is [white panel | board | black panel] (see
    # GraphicsRenderer._with_side_panels), so raw window pixels need the
    # left panel's width subtracted before BoardMapper can turn them into
    # board cells - otherwise every click/jump maps to the wrong column.
    board_x = x - board_offset_x
    if event == cv2.EVENT_LBUTTONDOWN:
        controller.click(board_x, y)
    elif event == cv2.EVENT_RBUTTONDOWN:
        controller.jump(board_x, y)


def _run_loop(engine, controller, renderer, score_state, move_log_state):
    """Owns the cv2 window, mouse handling, and the frame-timing loop.
    Drawing itself is delegated to `renderer` (a GraphicsRenderer), which
    takes no engine dependency at all - each frame's FrameState is built
    here (the boundary between live engine state and pure render data) via
    FrameState.from_engine, sourcing score/move-log from the bus-fed read
    models (score_state/move_log_state) rather than the engine's own
    score()/move_history(), which remain the engine's internal source of
    truth and are still used elsewhere (e.g. tests)."""
    #cv2.namedWindow(WINDOW_NAME)
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(
        WINDOW_NAME,
        lambda event, x, y, flags, param: _on_mouse(controller, ui_config.SIDE_PANEL_WIDTH, event, x, y, flags, param),
    )

    last_frame = time.time()
    while True:
        now = time.time()
        elapsed_ms = int((now - last_frame) * 1000)
        last_frame = now

        engine.wait(elapsed_ms)
        renderer.advance(elapsed_ms)

        frame_state = FrameState.from_engine(engine, controller, score_state, move_log_state)
        frame = renderer.render(frame_state)

        if frame_state.snapshot.game_over:
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

    bus = EventBus()
    score_state, move_log_state, sound_handler, animation_handler = _build_bus_handlers(bus)
    engine, controller, board, bus = _build_game(board_lines, config, bus=bus)

    renderer = _build_renderer(board, config)
    _run_loop(engine, controller, renderer, score_state, move_log_state)


if __name__ == "__main__":  # pragma: no cover
    main()
