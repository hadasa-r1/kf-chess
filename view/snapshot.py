from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameSnapshot:
    """Read-only view of the game state handed to the renderer.

    The renderer never receives the live Board or Piece objects - only this
    immutable snapshot - so the view layer cannot accidentally mutate the
    model. `cells` is the logical board (a tuple of tuples of tokens).

    `selected` is part of the shape (a graphical renderer highlights it) but is
    populated only by whoever owns selection state; the engine leaves it None,
    since `print board` never shows selection.
    """

    cells: tuple
    width: int
    height: int
    game_over: bool
    selected: tuple | None = None
    # Per-color completed-move log (tuple of MoveRecord) and running score,
    # populated only by GameEngine.snapshot - default to empty so every
    # other existing caller of from_board()/GameSnapshot() is unaffected.
    history: dict = field(default_factory=dict)
    score: dict = field(default_factory=dict)

    @classmethod
    def from_board(cls, board, game_over, selected=None, history=None, score=None):
        cells = tuple(tuple(row) for row in board.snapshot())
        return cls(
            cells=cells,
            width=board.width,
            height=board.height,
            game_over=game_over,
            selected=selected,
            history=history if history is not None else {},
            score=score if score is not None else {},
        )
