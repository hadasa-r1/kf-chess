"""Pure ELO rating math - no imports from anywhere else in this project.

Standard formulas (ratings A and B, A's perspective):

    expected_A = 1 / (1 + 10 ** ((rating_B - rating_A) / 400))

    new_rating_A = round(rating_A + K * (actual_A - expected_A))

`actual_A` is 1.0 for a win, 0.0 for a loss, 0.5 for a draw. K controls
how many points can change hands after a single game; 32 is a common
default for club-level/casual play (higher than the ~16-24 used for
established/elite players in real chess federations, but simpler for a
single fixed constant here).
"""

from __future__ import annotations


def expected_score(rating_a: int, rating_b: int) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def updated_rating(rating: int, expected: float, actual_score: float, k: int = 32) -> int:
    return round(rating + k * (actual_score - expected))
