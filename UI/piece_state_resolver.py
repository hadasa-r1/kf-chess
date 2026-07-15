class PieceStateResolver:
    """Maps a board cell to the animation state its piece should render in.

    Kept separate from the render loop so that adding a new visual state
    (e.g. "jump", "capture") means adding a branch only here - the render
    loop always just asks `state_for(cell)` and never inspects the engine
    itself.
    """

    def __init__(self, engine):
        self._engine = engine

    def state_for(self, cell):
        return "move" if self._engine.is_busy(cell) else "idle"
