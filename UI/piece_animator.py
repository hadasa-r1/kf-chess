class PieceAnimator:
    """Tracks per-cell animation timing.

    Deliberately has no knowledge of cv2, Img, or GameEngine - it only deals
    in cell keys, token/state strings, and integer milliseconds, so it can be
    unit tested and reused independent of how frames are actually drawn.
    """

    def __init__(self, frame_duration_ms):
        self._frame_duration_ms = frame_duration_ms
        self._clocks = {}  # key: (row, col) -> {"token": str, "state": str, "elapsed": int}

    def current_frame_index(self, cell, token, state, num_frames):
        entry = self._clocks.get(cell)
        if entry is None or entry["token"] != token or entry["state"] != state:
            entry = {"token": token, "state": state, "elapsed": 0}
            self._clocks[cell] = entry
        return (entry["elapsed"] // self._frame_duration_ms) % num_frames

    def advance(self, dt_ms):
        for entry in self._clocks.values():
            entry["elapsed"] += dt_ms
