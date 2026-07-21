import cv2
import numpy as np

from UI.img import Img


class GraphicsRenderer:
    """Turns a FrameState into a drawn frame. Owns only drawing - no cv2
    window, no mouse handling, no game loop (see main_gui.py's _run_loop
    for those), and no GameEngine dependency at all: every value it needs
    per frame arrives pre-computed on the FrameState passed to render()
    (see view/snapshot.py's FrameState.from_engine).
    """

    # The cooldown cause ("move"/"jump") on FrameState.cooldowns; the
    # sprite/rest-duration vocabulary elsewhere is the *state name*
    # ("long_rest"/"short_rest") - this is the one place that translates
    # between them.
    REST_STATE_FOR_CAUSE = {"move": "long_rest", "jump": "short_rest"}

    def __init__(self, sprites, state_machine, animator, position_resolver,
                 jump_offset_resolver, rest_durations, board_bg, cell_size,
                 board_width, board_height, side_panel_renderer):
        self._sprites = sprites
        self._state_machine = state_machine
        self._animator = animator
        self._position_resolver = position_resolver
        self._jump_offset_resolver = jump_offset_resolver
        self._rest_durations = rest_durations
        self._board_bg = board_bg
        self._cell_size = cell_size
        self._board_width = board_width
        self._board_height = board_height
        self._side_panel_renderer = side_panel_renderer

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

    def advance(self, elapsed_ms):
        self._animator.advance(elapsed_ms)

    def render(self, frame_state):
        snapshot = frame_state.snapshot
        active_by_start = {move.start: move for move in frame_state.moves}
        active_by_cell = {jump.cell: jump for jump in frame_state.jumps}
        frame = self._background_frame()

        if snapshot.selected is not None:
            self._draw_selection(frame, snapshot.selected)

        # A mid-flight piece's source cell is cleared on the board the
        # instant its move starts (RealTimeArbiter.start_move), so it no
        # longer shows up as an occupied cell in snapshot.cells - it must be
        # drawn from the Move itself (move.piece/move.start) instead. Cells
        # that aren't mid-flight are unaffected and still read from the
        # board snapshot as before.
        for row, cells in enumerate(snapshot.cells):
            for col, token in enumerate(cells):
                if token == ".":
                    continue
                self._draw_piece(frame, (row, col), token, False, active_by_start, active_by_cell, frame_state)

        for cell, move in active_by_start.items():
            self._draw_piece(frame, cell, move.piece, True, active_by_start, active_by_cell, frame_state)

        if snapshot.game_over:
            self._draw_game_over(frame)

        return self._with_side_panels(
            frame, frame_state.white_history, frame_state.black_history,
            frame_state.white_score, frame_state.black_score,
        )

    def _with_side_panels(self, frame, white_history, black_history, white_score, black_score):
        channels = frame.img.shape[2]
        height = frame.img.shape[0]
        white_panel = self._side_panel_renderer.render(
            height, channels, "White", white_score, white_history,
        )
        black_panel = self._side_panel_renderer.render(
            height, channels, "Black", black_score, black_history,
        )
        composed = Img()
        composed.img = np.hstack([white_panel.img, frame.img, black_panel.img])
        return composed

    def _draw_piece(self, frame, cell, token, is_moving, active_by_start, active_by_cell, frame_state):
        row, col = cell
        # `cell in active_by_cell` (built from the real jumps list, not
        # GameEngine.is_busy) is the only reliable "is this cell jumping"
        # check: is_busy(cell) also returns True when `cell` is merely the
        # *origin* of an unrelated in-flight move elsewhere - which can
        # happen while this same cell has already been reoccupied by a
        # different piece that isn't jumping at all.
        is_jumping = not is_moving and cell in active_by_cell
        cause = None if (is_moving or is_jumping) else frame_state.cooldowns.get(cell)
        rest_kind = self.REST_STATE_FOR_CAUSE.get(cause)
        state = self._state_machine.state_for(is_moving, is_jumping, rest_kind)
        frame_list = self._sprites.get(token, state)
        index = self._animator.current_frame_index(cell, token, state, len(frame_list))

        if is_moving:
            x, y = self._position_resolver.pixel_position(active_by_start[cell], frame_state.clock)
        else:
            x, y = col * self._cell_size, row * self._cell_size

        if is_jumping:
            offset = self._jump_offset_resolver.vertical_offset(active_by_cell[cell], frame_state.clock)
            y -= offset

        sprite = frame_list[index]
        sprite_h, sprite_w = sprite.img.shape[:2]
        draw_x, draw_y = self._to_display_position(x, y, sprite_w, sprite_h)
        sprite.draw_on(frame, draw_x, draw_y)

        if rest_kind is not None:
            self._draw_rest_overlay(frame, cell, rest_kind, frame_state)

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

    def _draw_rest_overlay(self, frame, cell, rest_kind, frame_state):
        """Overlay a translucent yellow bar on `cell` that shrinks from the
        full cell height down to nothing as the real cooldown for this cell
        (long_rest after a move, short_rest after a jump) runs out."""
        duration = self._rest_durations.get(rest_kind, 0)
        if duration <= 0:
            return
        remaining = frame_state.cooldown_remaining.get(cell, 0)
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
