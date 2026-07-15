class PieceStateMachine:
    """Picks which sprite folder to draw a cell's piece from: idle, move,
    jump, short_rest, long_rest.

    Purely a rendering concern - it decides visuals only, never whether a
    move is legal (that is GameEngine/RealTimeArbiter's job). It is a pure
    function of facts the caller already read from the engine this frame
    (is the piece moving/jumping right now, and if neither, which rest kind
    - if any - the engine currently attributes to this cell), mirroring the
    asset layout's own state graph (pieces2/<piece>/states/<state>/
    config.json's "next_state_when_finished"):

        move -> long_rest -> idle
        jump -> short_rest -> idle
        idle -> idle (loops until something moves/jumps)

    Deliberately stateless: earlier versions tracked rest-state elapsed time
    per grid cell, but a moved piece's token lives at `move.start` while
    flying and only appears at `move.end` after arrival - two different
    cell keys - so a cell-keyed timer never saw the transition into rest at
    the piece's real destination. Reading `rest_kind` fresh from the engine
    (which correctly keys cooldowns by destination cell) avoids that class
    of bug entirely.
    """

    def state_for(self, is_moving, is_jumping, rest_kind):
        if is_moving:
            return "move"
        if is_jumping:
            return "jump"
        if rest_kind is not None:
            return rest_kind
        return "idle"
