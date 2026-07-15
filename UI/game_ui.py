import time

import cv2

from UI.img import Img


class GameUI:
    """Wires an existing (already constructed) GameEngine + Controller to an
    OpenCV window. It owns no game logic - only input translation (mouse ->
    controller) and drawing (snapshot -> pixels).
    """

    WINDOW_NAME = "KungFu Chess"

    # GameEngine.cooldown_kind reports the *cause* ("move"/"jump"); the
    # sprite/rest-duration vocabulary elsewhere is the *state name*
    # ("long_rest"/"short_rest") - this is the one place that translates
    # between them.
    REST_STATE_FOR_CAUSE = {"move": "long_rest", "jump": "short_rest"}

    def __init__(self, engine, controller, sprites, state_machine, animator, position_resolver, rest_durations, board_bg, cell_size, board_width, board_height):
        self._engine = engine
        self._controller = controller
        self._sprites = sprites
        self._state_machine = state_machine
        self._animator = animator
        self._position_resolver = position_resolver
        self._rest_durations = rest_durations
        self._board_bg = board_bg
        self._cell_size = cell_size
        self._board_width = board_width
        self._board_height = board_height

        expected_h = board_height * cell_size
        expected_w = board_width * cell_size
        actual_h, actual_w = board_bg.img.shape[:2]
        if (actual_h, actual_w) != (expected_h, expected_w):
            print(
                f"WARNING: board background image is {actual_w}x{actual_h}px "
                f"but the board expects {expected_w}x{expected_h}px "
                f"({board_width}x{board_height} cells at {cell_size}px); "
                "compensating so pieces still land centered on each square."
            )

        # The background image's actual per-cell pixel size can differ
        # slightly from `cell_size` (e.g. a non-800x800 board.png for an 8x8
        # board). Sprites are still sized/positioned in `cell_size` units
        # elsewhere, so drawing scales that logical grid onto the real image
        # dimensions and centers each sprite within its real cell footprint.
        self._display_cell_w = actual_w / board_width
        self._display_cell_h = actual_h / board_height

    def run(self):
        cv2.namedWindow(self.WINDOW_NAME)
        cv2.setMouseCallback(self.WINDOW_NAME, self._on_mouse)

        last_frame = time.time()
        while True:
            now = time.time()
            elapsed_ms = int((now - last_frame) * 1000)
            last_frame = now

            self._engine.wait(elapsed_ms)
            active_by_start = {move.start: move for move in self._engine.active_moves()}
            snapshot = self._engine.snapshot(selected=self._controller.selected)
            self._animator.advance(elapsed_ms)

            frame = self._draw_frame(snapshot, active_by_start)

            if snapshot.game_over:
                cv2.imshow(self.WINDOW_NAME, frame.img)
                cv2.waitKey(0)
                break

            cv2.imshow(self.WINDOW_NAME, frame.img)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        cv2.destroyAllWindows()

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._controller.click(x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self._controller.jump(x, y)

    def _draw_frame(self, snapshot, active_by_start):
        frame = self._background_frame()

        if snapshot.selected is not None:
            self._draw_selection(frame, snapshot.selected)

        for row, cells in enumerate(snapshot.cells):
            for col, token in enumerate(cells):
                if token == ".":
                    continue
                cell = (row, col)
                is_moving = cell in active_by_start
                is_jumping = not is_moving and self._engine.is_busy(cell)
                cause = None if (is_moving or is_jumping) else self._engine.cooldown_kind(cell)
                rest_kind = self.REST_STATE_FOR_CAUSE.get(cause)
                state = self._state_machine.state_for(is_moving, is_jumping, rest_kind)
                frame_list = self._sprites.get(token, state)
                index = self._animator.current_frame_index(cell, token, state, len(frame_list))

                if is_moving:
                    x, y = self._position_resolver.pixel_position(active_by_start[cell], self._engine.clock)
                else:
                    x, y = col * self._cell_size, row * self._cell_size

                sprite = frame_list[index]
                sprite_h, sprite_w = sprite.img.shape[:2]
                draw_x, draw_y = self._to_display_position(x, y, sprite_w, sprite_h)
                sprite.draw_on(frame, draw_x, draw_y)

                if rest_kind is not None:
                    self._draw_rest_overlay(frame, cell, rest_kind)

        if snapshot.game_over:
            self._draw_game_over(frame)

        return frame

    def _background_frame(self):
        frame = Img()
        frame.img = self._board_bg.img.copy()
        return frame

    def _to_display_point(self, logical_x, logical_y):
        """Scale a point from the logical `cell_size` grid onto the real
        background image's per-cell pixel size."""
        scale_x = self._display_cell_w / self._cell_size
        scale_y = self._display_cell_h / self._cell_size
        return int(logical_x * scale_x), int(logical_y * scale_y)

    def _to_display_position(self, logical_x, logical_y, sprite_w, sprite_h):
        """Like `_to_display_point`, but also centers a sprite of the given
        size within its real cell footprint (which may be a few pixels wider
        or taller than the sprite itself)."""
        x, y = self._to_display_point(logical_x, logical_y)
        x += int((self._display_cell_w - sprite_w) / 2)
        y += int((self._display_cell_h - sprite_h) / 2)
        return x, y

    def _opaque_color(self, frame, bgr):
        """cv2 pads a color tuple shorter than the image's channel count with
        zeros - on a BGRA frame that silently zeroes alpha (fully
        transparent) instead of leaving it opaque. Match the channel count
        explicitly so drawn shapes are actually visible."""
        if frame.img.shape[2] == 4:
            return (*bgr, 255)
        return bgr

    def _draw_rest_overlay(self, frame, cell, rest_kind):
        """Overlay a translucent yellow bar on `cell` that shrinks from the
        full cell height down to nothing as the engine's real cooldown for
        this cell (long_rest after a move, short_rest after a jump) runs out."""
        duration = self._rest_durations.get(rest_kind, 0)
        if duration <= 0:
            return
        remaining = self._engine.cooldown_remaining(cell)
        progress = max(0.0, min(1.0, remaining / duration))
        if progress <= 0:
            return

        row, col = cell
        x1, y1 = self._to_display_point(col * self._cell_size, row * self._cell_size)
        x2, y2 = self._to_display_point((col + 1) * self._cell_size, (row + 1) * self._cell_size)
        bar_y2 = y1 + int((y2 - y1) * progress)
        if bar_y2 <= y1:
            return

        overlay = frame.img.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, bar_y2), self._opaque_color(frame, (0, 255, 255)), thickness=-1)
        alpha = 0.4
        region = frame.img[y1:bar_y2, x1:x2]
        overlay_region = overlay[y1:bar_y2, x1:x2]
        frame.img[y1:bar_y2, x1:x2] = cv2.addWeighted(overlay_region, alpha, region, 1 - alpha, 0)

    def _draw_selection(self, frame, cell):
        row, col = cell
        x1, y1 = self._to_display_point(col * self._cell_size, row * self._cell_size)
        x2, y2 = self._to_display_point((col + 1) * self._cell_size, (row + 1) * self._cell_size)
        cv2.rectangle(
            frame.img,
            (x1, y1),
            (x2, y2),
            self._opaque_color(frame, (0, 255, 255)),
            thickness=3,
        )

    def _draw_game_over(self, frame):
        text = "Game Over"
        font_size = 1.5
        thickness = 2
        board_width_px = self._board_width * self._cell_size
        board_height_px = self._board_height * self._cell_size

        (text_width, text_height), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_size, thickness
        )
        x = max(0, (board_width_px - text_width) // 2)
        y = (board_height_px + text_height) // 2

        frame.put_text(
            text,
            x,
            y,
            font_size=font_size,
            color=(255, 255, 255, 255),
            thickness=thickness,
        )


if __name__ == "__main__":  # pragma: no cover
    from config import settings
    from rules.rule_registry import build_default_registry
    from rules.rule_engine import RuleEngine
    from rules.game_conditions import KingCaptureWinCondition, LastRankPromotion
    from realtime.real_time_arbiter import RealTimeArbiter
    from board.loaders import load_text_board
    from game.board_mapper import BoardMapper
    from game.engine import GameEngine
    from game.controller import Controller
    from UI import ui_config
    from UI.assets.asset_resolver import AssetResolver
    from UI.assets.sprites import PieceSprites
    from UI.rendering.piece_state_machine import PieceStateMachine
    from UI.rendering.piece_animator import PieceAnimator
    from UI.rendering.position_resolver import PositionResolver

    config = settings
    registry = build_default_registry(config)

    with open(ui_config.BOARD_FILE) as f:
        board_lines = [line.rstrip("\n") for line in f]
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

    asset_resolver = AssetResolver(ui_config.PIECES_DIR, ui_config.FOLDER_MAP, ui_config.STATE_MAP)
    sprites = PieceSprites(asset_resolver, config.CELL_SIZE)
    # Read directly by GameUI for the rest-bar overlay - matches the same
    # durations GameEngine actually enforces (engine.cooldown_remaining is
    # the source of truth; this just says how long each kind started at).
    rest_durations = {
        "long_rest": config.MOVE_COOLDOWN_DURATION,
        "short_rest": config.JUMP_COOLDOWN_DURATION,
    }
    state_machine = PieceStateMachine()
    animator = PieceAnimator(ui_config.FRAME_DURATION_MS)
    position_resolver = PositionResolver(config.CELL_SIZE, config.MOVE_DURATION)
    board_bg = Img().read(ui_config.BOARD_IMAGE_PATH)

    ui = GameUI(
        engine=engine,
        controller=controller,
        sprites=sprites,
        state_machine=state_machine,
        animator=animator,
        position_resolver=position_resolver,
        rest_durations=rest_durations,
        board_bg=board_bg,
        cell_size=config.CELL_SIZE,
        board_width=board.width,
        board_height=board.height,
    )
    ui.run()
