"""Tracks room_id -> GameSession, and creates new ones on demand.

Single responsibility: room bookkeeping only - the actual engine/board/
ConnectionManager/etc. graph for a room lives entirely inside GameSession
(server/game_session.py); this class just generates room ids and looks
sessions up by them. UserStore/UserRegistry are global (not per-room -
see server/game_session.py's docstring), so this class holds onto them
only to hand them to each new GameSession it creates.

Runs entirely on server/game_server.py's single asyncio event loop - same
reasoning as server/session_manager.py's own docstring (the tick loop(s)
and every connection handler are asyncio tasks on one loop, there is no
threading anywhere in server/) - so no lock is needed here either.
"""

from __future__ import annotations

import secrets

from server.game_session import GameSession

ROOM_ID_BYTES = 4


class RoomRegistry:
    def __init__(self, user_store, user_registry, disconnect_countdown_seconds=None):
        self._sessions_by_room_id = {}
        self._user_store = user_store
        self._user_registry = user_registry
        self._disconnect_countdown_seconds = disconnect_countdown_seconds

    def create_room(self) -> GameSession:
        room_id = secrets.token_hex(ROOM_ID_BYTES)
        while room_id in self._sessions_by_room_id:  # astronomically unlikely, but never silently collide
            room_id = secrets.token_hex(ROOM_ID_BYTES)

        session = GameSession(
            room_id, self._user_store, self._user_registry,
            disconnect_countdown_seconds=self._disconnect_countdown_seconds,
        )
        self._sessions_by_room_id[room_id] = session
        return session

    def get_room(self, room_id) -> GameSession | None:
        return self._sessions_by_room_id.get(room_id)
