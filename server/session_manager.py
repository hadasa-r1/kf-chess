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
        self._username_by_color = {}
        self._game_started = False

    def assign_color(self, connection, username) -> str | None:
        """Returns "w" for the 1st connection ever given a slot, "b" for
        the 2nd, and None for the 3rd and beyond (server/game_server.py
        turns that 3rd+ connection into a viewer instead). Calling this
        again for a connection that already has a color returns that same
        color without consuming another slot or re-recording `username`."""
        existing = self._colors_by_connection.get(connection)
        if existing is not None:
            return existing

        taken = set(self._colors_by_connection.values())
        for color in COLORS_IN_JOIN_ORDER:
            if color not in taken:
                self._colors_by_connection[connection] = color
                # Recorded even though release() never clears it - this is
                # what lets reconnect() reclaim the color later, after the
                # connection that just got it disconnects.
                self._username_by_color[color] = username
                if len(self._colors_by_connection) == len(COLORS_IN_JOIN_ORDER):
                    # One-way latch: once both colors have ever been handed
                    # out, the game is permanently considered started - a
                    # later release() (e.g. a disconnect) must NEVER flip
                    # this back, since the remaining player must not become
                    # blocked again mid-game (see is_game_started below,
                    # and PlayerScopedController's use of it).
                    self._game_started = True
                return color

        return None

    def reconnect(self, connection, username) -> str | None:
        """Reclaims a color for a returning player: finds a color whose
        most recent occupant (per `_username_by_color`, which release()
        never clears) was `username`, AND whose slot is currently vacant -
        i.e. not held by any live connection right now. Returns that color
        (after assigning it to `connection`, exactly like assign_color
        would), or None if no such vacant, matching slot exists.

        Never "steals" a color from a connection that's still actively
        connected: a color already present as a value in
        `_colors_by_connection` is never returned here, live or not."""
        taken = set(self._colors_by_connection.values())
        for color, recorded_username in self._username_by_color.items():
            if recorded_username == username and color not in taken:
                self._colors_by_connection[connection] = color
                return color
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
        """Stops tracking `connection`, freeing its color slot for
        assign_color to hand to a brand-new connection.

        Deliberately does NOT clear `_username_by_color` - that's what
        lets reconnect() reclaim the freed slot for the same username
        later, within server/disconnect_resign_handler.py's grace period.
        The slot stays reclaimable via reconnect() (and only via
        reconnect() - assign_color never consults `_username_by_color`)
        until someone takes it via a fresh assign_color() call, at which
        point the recorded username for that color is overwritten."""
        self._colors_by_connection.pop(connection, None)
