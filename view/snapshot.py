from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GameSnapshot:
    """Read-only view of engine state for rendering.

    The renderer receives this DTO only, never a live Board - so drawing
    code can never accidentally mutate game state. `selected` is carried
    here for a future graphical renderer to highlight the selected piece;
    GameEngine itself always leaves it None since selection is Controller
    state and print-board output never shows it.
    """

    cells: tuple
    width: int
    height: int
    game_over: bool
    selected: Optional[tuple] = None

    @classmethod
    def from_board(cls, board, game_over, selected=None):
        cells = tuple(tuple(row) for row in board.snapshot())
        return cls(
            cells=cells,
            width=board.width,
            height=board.height,
            game_over=game_over,
            selected=selected,
        )
