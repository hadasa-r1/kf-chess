from __future__ import annotations


class ScoreBoard:
    """Running per-color score, tallied from captured-piece values.

    `piece_values` is injected (config.PIECE_VALUES) rather than hardcoded,
    matching the project convention that gameplay constants live only in
    config/settings.py.
    """

    def __init__(self, piece_values):
        self._piece_values = piece_values
        self._scores = {}

    def apply_capture(self, capturing_color, captured_piece):
        value = self._piece_values.get(captured_piece[1], 0)
        self._scores[capturing_color] = self._scores.get(capturing_color, 0) + value

    def score_for(self, color):
        return self._scores.get(color, 0)
