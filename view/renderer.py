class BoardRenderer:
    """Turns a GameSnapshot into printable text.

    Takes a read-only GameSnapshot rather than a live Board, so rendering
    can never mutate game state. Kept separate from GameEngine so rendering
    format can change (or the engine can be tested) without either one
    depending on the other.
    """

    def render(self, snapshot):
        return "\n".join(" ".join(row) for row in snapshot.cells)
