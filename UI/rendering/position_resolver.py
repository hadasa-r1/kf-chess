class PositionResolver:
    """Interpolates a Move's in-flight pixel position from the engine clock.

    Pure function/class - depends only on a Move's public fields (piece,
    start, end, arrival) and a clock value passed in, never on cv2, Img,
    GameEngine, or RealTimeArbiter internals. Row maps to Y, col maps to X,
    matching BoardMapper's convention used elsewhere in the UI.
    """

    def __init__(self, cell_size, move_duration):
        self._cell_size = cell_size
        self._move_duration = move_duration

    def pixel_position(self, move, current_clock):
        """Given a Move (piece, start, end, arrival) and the engine's current
        clock, return (x, y) pixel coordinates interpolated between start and
        end cells. Progress is clamped to [0, 1]."""
        distance = max(abs(move.end[0] - move.start[0]), abs(move.end[1] - move.start[1]))
        total_duration = distance * self._move_duration
        started_at = move.arrival - total_duration
        elapsed = current_clock - started_at
        progress = 0.0 if total_duration == 0 else max(0.0, min(1.0, elapsed / total_duration))

        start_x = move.start[1] * self._cell_size
        start_y = move.start[0] * self._cell_size
        end_x = move.end[1] * self._cell_size
        end_y = move.end[0] * self._cell_size

        x = start_x + (end_x - start_x) * progress
        y = start_y + (end_y - start_y) * progress
        return (x, y)
