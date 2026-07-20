from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class FrameState:
    """Everything GraphicsRenderer needs to draw one frame, precomputed
    once by `from_engine` so the renderer itself never touches a live
    GameEngine - only this plain data bundle (mirrors GameSnapshot's own
    "renderer never sees live Board/Piece objects" principle, extended to
    cover motion/cooldown/clock data too).

    `cooldowns` maps every currently-occupied cell to its cooldown cause
    ("move"/"jump") or None; `cooldown_remaining` maps the same cells to
    however many milliseconds are left on that cooldown (0 if none) - the
    two are kept separate, matching GameEngine's own
    cooldown_kind()/cooldown_remaining() split.
    """

    snapshot: GameSnapshot
    moves: tuple
    jumps: tuple
    white_history: tuple
    black_history: tuple
    white_score: int
    black_score: int
    clock: int
    cooldowns: dict
    cooldown_remaining: dict

    @classmethod
    def from_engine(cls, engine, controller, score_state, move_log_state):
        """The only place (besides tests) allowed to call
        engine.cooldown_kind/cooldown_remaining/clock/active_moves/
        active_jumps for rendering purposes.

        white_history/black_history/white_score/black_score are read from
        `move_log_state`/`score_state` (the bus-fed read models - see
        bus_handlers/), not engine.move_history()/engine.score() directly:
        main_gui.py's render loop already sources those from the bus, by
        deliberate design (see main_gui._run_loop's own docstring), and
        this builder preserves that rather than reintroducing a direct
        engine dependency for the two fields that don't need one.
        """
        snapshot = engine.snapshot(selected=controller.selected)
        occupied_cells = [
            (row, col)
            for row, cells in enumerate(snapshot.cells)
            for col, token in enumerate(cells)
            if token != "."
        ]
        return cls(
            snapshot=snapshot,
            moves=tuple(engine.active_moves()),
            jumps=tuple(engine.active_jumps()),
            white_history=move_log_state.entries_for("w"),
            black_history=move_log_state.entries_for("b"),
            white_score=score_state.score_for("w"),
            black_score=score_state.score_for("b"),
            clock=engine.clock,
            cooldowns={cell: engine.cooldown_kind(cell) for cell in occupied_cells},
            cooldown_remaining={cell: engine.cooldown_remaining(cell) for cell in occupied_cells},
        )
