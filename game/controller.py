class Controller:
    """Translates user clicks/jumps into GameEngine commands and owns the
    selected-cell state. It decides nothing about chess legality - it only
    turns pixels into cells (via BoardMapper) and drives the engine's public
    command path, then updates its selection from the engine's MoveResult.

    Both collaborators are injected. Selection is deliberately kept here (not
    on the engine) so the engine stays a pure application service.
    """

    def __init__(self, engine, board_mapper):
        self._engine = engine
        self._mapper = board_mapper
        self._selected = None

    @property
    def selected(self):
        return self._selected

    def deselect(self):
        """Clears the current selection without going through a click -
        for external callers (e.g. a networked ownership guard) that need
        to cancel a selection Controller itself would otherwise keep."""
        self._selected = None

    def click(self, x, y):
        cell = self._mapper.pixel_to_cell(x, y)
        if cell is None:
            # Outside the board: leave selection untouched (a no-op click).
            return

        if self._selected is None:
            # First click selects a piece if that cell can be a move source.
            # can_select() settles pending arrivals and refuses after game over.
            if self._engine.can_select(cell):
                self._selected = cell
            return

        # Second click: ask the engine to move, then update selection.
        result = self._engine.request_move(self._selected, cell)
        self._resolve_selection(result, cell)

    def jump(self, x, y):
        # A jump always ends any pending selection first (matches the engine's
        # historical order: selection is cleared before the jump is attempted).
        self._selected = None
        cell = self._mapper.pixel_to_cell(x, y)
        if cell is None:
            return
        self._engine.request_jump(cell)

    def _resolve_selection(self, result, cell):
        # This is a real-time game with no turn concept - any color's piece
        # may be selected at any time (GameEngine.can_select performs no
        # color check) - so any rejected second click (friendly destination,
        # illegal move for the selected piece, or anything else) re-selects
        # `cell` immediately if it currently holds a selectable piece,
        # regardless of color. A rejected click on a cell that can't be
        # selected (empty, busy, on cooldown, ...) clears the selection
        # instead, and so does an accepted move (the selected piece is now
        # in flight).
        if not result.is_accepted and self._engine.can_select(cell):
            self._selected = cell
        else:
            self._selected = None
