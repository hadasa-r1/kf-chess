import time

import cv2

from UI.img import Img


class GameUI:
    """Wires an existing (already constructed) GameEngine + Controller to an
    OpenCV window. It owns no game logic - only input translation (mouse ->
    controller) and drawing (snapshot -> pixels).
    """

    WINDOW_NAME = "KungFu Chess"

    def __init__(self, engine, controller, sprites, state_resolver, animator, position_resolver, board_bg, cell_size, board_width, board_height):
        self._engine = engine
        self._controller = controller
        self._sprites = sprites
        self._state_resolver = state_resolver
        self._animator = animator
        self._position_resolver = position_resolver
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
                "pieces may be misaligned."
            )

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
            snapshot = self._engine.snapshot()
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

        selected = self._controller.selected
        if selected is not None:
            self._draw_selection(frame, selected)

        for row, cells in enumerate(snapshot.grid):
            for col, token in enumerate(cells):
                if token == ".":
                    continue
                cell = (row, col)
                state = self._state_resolver.state_for(cell)
                frame_list = self._sprites.get(token, state)
                index = self._animator.current_frame_index(cell, token, state, len(frame_list))

                if cell in active_by_start:
                    x, y = self._position_resolver.pixel_position(active_by_start[cell], self._engine.clock)
                    x, y = int(x), int(y)
                else:
                    x, y = col * self._cell_size, row * self._cell_size

                frame_list[index].draw_on(frame, x, y)

        if snapshot.game_over:
            self._draw_game_over(frame)

        return frame

    def _background_frame(self):
        frame = Img()
        frame.img = self._board_bg.img.copy()
        return frame

    def _draw_selection(self, frame, cell):
        row, col = cell
        x = col * self._cell_size
        y = row * self._cell_size
        cv2.rectangle(
            frame.img,
            (x, y),
            (x + self._cell_size, y + self._cell_size),
            (0, 255, 255),
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
    from UI.asset_resolver import AssetResolver
    from UI.sprites import PieceSprites
    from UI.piece_state_resolver import PieceStateResolver
    from UI.piece_animator import PieceAnimator
    from UI.position_resolver import PositionResolver

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
    state_resolver = PieceStateResolver(engine)
    animator = PieceAnimator(ui_config.FRAME_DURATION_MS)
    position_resolver = PositionResolver(config.CELL_SIZE, config.MOVE_DURATION)
    board_bg = Img().read(ui_config.BOARD_IMAGE_PATH)

    ui = GameUI(
        engine=engine,
        controller=controller,
        sprites=sprites,
        state_resolver=state_resolver,
        animator=animator,
        position_resolver=position_resolver,
        board_bg=board_bg,
        cell_size=config.CELL_SIZE,
        board_width=board.width,
        board_height=board.height,
    )
    ui.run()
