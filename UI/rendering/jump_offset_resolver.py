class JumpOffsetResolver:
    """Computes a jumping piece's vertical hop offset from the engine clock.

    Pure function/class - depends only on a Jump's public fields (piece,
    cell, end_time) and a clock value passed in, never on cv2, Img,
    GameEngine, or RealTimeArbiter internals. A jump doesn't travel between
    cells like a Move does (see realtime/models.py's Jump), so there is no
    horizontal component here - only a vertical rise-and-fall arc layered on
    top of the piece's fixed cell position.
    """

    def __init__(self, cell_size, jump_duration):
        self._cell_size = cell_size
        self._jump_duration = jump_duration

    def vertical_offset(self, jump, current_clock):
        """Given a Jump (piece, cell, end_time) and the engine's current
        clock, return the number of pixels to rise by: 0 at the start and
        end of the jump, cell_size/2 at its midpoint, following a parabolic
        arc. Progress is clamped to [0, 1]."""
        started_at = jump.end_time - self._jump_duration
        elapsed = current_clock - started_at
        progress = 0.0 if self._jump_duration == 0 else max(0.0, min(1.0, elapsed / self._jump_duration))

        peak = self._cell_size / 2
        return 4 * peak * progress * (1 - progress)
