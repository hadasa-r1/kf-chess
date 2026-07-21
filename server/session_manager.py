"""Tracks connected clients in join order and assigns each a color.

Single responsibility: connection-permission bookkeeping - "who's allowed
to play, and as which color" - layered on top of Controller/GameEngine,
neither of which know anything about color-restricted sessions. Local
hotseat play (main_gui.py) never touches this class at all and keeps its
existing no-color-restriction behavior exactly as before.

Runs entirely on server/game_server.py's single asyncio event loop -
there is no threading anywhere in server/ (confirmed by reading
game_server.py: the tick loop and every connection handler are asyncio
tasks on one loop, same as ConnectionManager's own assumption) - so no
lock is needed here.
"""

from __future__ import annotations

COLORS_IN_JOIN_ORDER = ("w", "b")


class SessionManager:
    def __init__(self):
        self._colors_by_connection = {}
        self._game_started = False

    def assign_color(self, connection) -> str | None:
        """Returns "w" for the 1st connection ever given a slot, "b" for
        the 2nd, and None for the 3rd and beyond. Calling this again for a
        connection that already has a color returns that same color
        without consuming another slot."""
        existing = self._colors_by_connection.get(connection)
        if existing is not None:
            return existing

        taken = set(self._colors_by_connection.values())
        for color in COLORS_IN_JOIN_ORDER:
            if color not in taken:
                self._colors_by_connection[connection] = color
                if len(self._colors_by_connection) == len(COLORS_IN_JOIN_ORDER):
                    # One-way latch: once both colors have ever been handed
                    # out, the game is permanently considered started - a
                    # later release() (e.g. a disconnect) must NEVER flip
                    # this back, since the remaining player must not become
                    # blocked again mid-game (see is_game_started below,
                    # and PlayerScopedController's use of it).
                    self._game_started = True
                return color

        # TODO: viewers. A 3rd+ connection currently gets no color at all;
        # server/game_server.py rejects it outright on a None return. A
        # later task (the "Rooms" slide) should let it spectate instead.
        return None

    def is_game_started(self) -> bool:
        """True forever, once both "w" and "b" have ever been assigned -
        deliberately NOT "are both slots currently occupied" (that would
        re-block the remaining player after any mid-game disconnect)."""
        return self._game_started

    def connection_for(self, color) -> object | None:
        """Reverse lookup: which connection (if any) currently holds
        `color`. Used by server/rating_update_handler.py to combine "who
        is this color" with UserRegistry's "who is this connection" -
        SessionManager itself still knows nothing about usernames."""
        for connection, assigned_color in self._colors_by_connection.items():
            if assigned_color == color:
                return connection
        return None

    def release(self, connection) -> None:
        """Stops tracking `connection`, freeing its color slot.

        Simplification: there is no reconnection/resume-to-same-color
        logic yet, so a disconnected player's color becomes immediately
        available to whoever connects next rather than being reserved for
        them to reclaim - full disconnect/resign handling is a separate,
        later task."""
        self._colors_by_connection.pop(connection, None)
