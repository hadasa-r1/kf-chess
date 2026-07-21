"""Tracks the username each logged-in connection presented at login time.

Single responsibility: connection-to-username bookkeeping - deliberately
separate from server/session_manager.py's SessionManager (which stays
focused purely on live connection-to-color assignment). These are
different kinds of bookkeeping that will evolve independently: this class
will grow real auth/password/rating persistence in a later task, while
SessionManager has nothing to do with any of that.

Runs entirely on server/game_server.py's single asyncio event loop - same
reasoning as SessionManager's own docstring (the tick loop and every
connection handler are asyncio tasks on one loop, there is no threading
anywhere in server/) - so no lock is needed here either.
"""

from __future__ import annotations


class UserRegistry:
    def __init__(self):
        self._usernames_by_connection = {}

    def login(self, connection, username: str) -> None:
        self._usernames_by_connection[connection] = username

    def username_for(self, connection) -> str | None:
        return self._usernames_by_connection.get(connection)

    def logout(self, connection) -> None:
        self._usernames_by_connection.pop(connection, None)
