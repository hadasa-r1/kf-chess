"""Updates persisted ELO ratings when a game ends.

The only place that combines server/elo.py's pure math with
server/user_store.py's persistence and the EventBus - subscribes to
GameEndedEvent (bus/events.py), figures out which two usernames were
playing by combining SessionManager's connection->color mapping with
UserRegistry's connection->username mapping, and persists both new
ratings. game/engine.py and bus/events.py stay completely unaware that
"rating" exists.

As of this task, GameEngine only ever publishes GameEndedEvent with
`winner` set to the capturing piece's color ("w"/"b" - see
game/engine.py's _apply_events and rules/game_conditions.py's
KingCaptureWinCondition, the only win condition wired up) - there is no
draw/abort case implemented anywhere yet. This handler treats any
`winner` value other than "w"/"b" as a draw (both players score 0.5) so
it degrades sensibly if/when one is ever introduced, rather than
special-casing "no draws exist yet".

Rating updates are best-effort: any case where a player's username can't
be resolved (e.g. a connection dropped before both color slots were even
filled) is logged and skipped rather than raised - a missed rating update
must never crash the server.
"""

from __future__ import annotations

import logging

from bus.event_bus import EventBus
from bus.events import GameEndedEvent
from server import elo
from server.session_manager import SessionManager
from server.user_registry import UserRegistry
from server.user_store import UserStore

logger = logging.getLogger(__name__)


class RatingUpdateHandler:
    def __init__(self, bus: EventBus, user_store: UserStore, session_manager: SessionManager,
                 user_registry: UserRegistry):
        self._user_store = user_store
        self._session_manager = session_manager
        self._user_registry = user_registry
        bus.subscribe(GameEndedEvent, self._on_game_ended)

    def _on_game_ended(self, event: GameEndedEvent) -> None:
        white_username = self._username_for_color("w")
        black_username = self._username_for_color("b")
        if white_username is None or black_username is None:
            logger.info(
                "Skipping rating update - could not resolve both usernames "
                "(white=%r, black=%r) for a game that ended with reason=%r",
                white_username, black_username, event.reason,
            )
            return

        white_rating = self._user_store.rating_for(white_username)
        black_rating = self._user_store.rating_for(black_username)
        if white_rating is None or black_rating is None:
            logger.info(
                "Skipping rating update - no persisted rating for %r/%r",
                white_username, black_username,
            )
            return

        white_actual, black_actual = self._actual_scores(event.winner)
        white_expected = elo.expected_score(white_rating, black_rating)
        black_expected = elo.expected_score(black_rating, white_rating)

        self._user_store.update_rating(
            white_username, elo.updated_rating(white_rating, white_expected, white_actual),
        )
        self._user_store.update_rating(
            black_username, elo.updated_rating(black_rating, black_expected, black_actual),
        )

    def _username_for_color(self, color):
        connection = self._session_manager.connection_for(color)
        if connection is None:
            return None
        return self._user_registry.username_for(connection)

    @staticmethod
    def _actual_scores(winner):
        if winner == "w":
            return 1.0, 0.0
        if winner == "b":
            return 0.0, 1.0
        return 0.5, 0.5  # a draw, or any other non-color winner value
