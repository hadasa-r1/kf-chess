"""Pairs up waiting players by ELO proximity for the "Play" quick-match
option, instead of them typing/sharing a room id.

Single responsibility: matching only - delegates actual room creation to
the injected RoomRegistry (server/room_registry.py), constructor-injected
the same way server/rating_update_handler.py takes its own collaborators
rather than building them itself. No new bus/events.py event type, and no
periodic background scanning task: a match is only ever checked for at
the exact moment find_match() is called, which immediately resolves the
other (already-waiting) player's pending Future if one now matches.

Runs entirely on server/game_server.py's single asyncio event loop - same
reasoning as server/session_manager.py's own docstring (no threading
anywhere in server/) - so the waiting list needs no lock: every mutation
to it happens with no `await` in between, making it atomic against other
coroutines by construction.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from server.room_registry import RoomRegistry
from server.user_store import STARTING_RATING, UserStore

RATING_RANGE = 100
DEFAULT_WAIT_SECONDS = 60


@dataclass
class _WaitingPlayer:
    username: str
    rating: int
    future: asyncio.Future


class Matchmaker:
    def __init__(self, user_store: UserStore, room_registry: RoomRegistry, wait_seconds: int = DEFAULT_WAIT_SECONDS):
        self._user_store = user_store
        self._room_registry = room_registry
        self._wait_seconds = wait_seconds
        self._waiting: list[_WaitingPlayer] = []

    async def find_match(self, username: str):
        """Looks for any currently-waiting player within +/-RATING_RANGE
        of `username`'s rating. If one exists, both players end up in the
        SAME new GameSession (as if one had "created" and the other
        "joined" it) - returned to this caller directly, and handed to the
        matched player by resolving their own pending Future.

        Otherwise, joins the waiting list and awaits up to `wait_seconds`
        for someone suitable to arrive, returning None (and removing its
        own now-stale waiting entry) if nobody does in time."""
        rating = self._user_store.rating_for(username)
        if rating is None:
            rating = STARTING_RATING  # mirrors UserStore's own default for a brand-new account

        for candidate in self._waiting:
            if candidate.username == username:
                continue  # never match a player against itself
            if abs(candidate.rating - rating) <= RATING_RANGE:
                self._waiting.remove(candidate)
                session = self._room_registry.create_room()
                candidate.future.set_result(session)
                return session

        waiting_player = _WaitingPlayer(username, rating, asyncio.get_event_loop().create_future())
        self._waiting.append(waiting_player)
        try:
            return await asyncio.wait_for(waiting_player.future, timeout=self._wait_seconds)
        except asyncio.TimeoutError:
            try:
                self._waiting.remove(waiting_player)
            except ValueError:
                pass  # already matched (and removed) by someone else - shouldn't happen, but safe
            return None
