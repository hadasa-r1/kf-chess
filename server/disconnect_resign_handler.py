"""Gives a disconnected player a grace period before resigning them,
instead of ending the game the instant their socket drops.

Single responsibility: run this one countdown-then-resign timer and
publish the resulting GameEndedEvent. Does NOT broadcast a game_ended
message or touch ratings itself - server/event_broadcast_handler.py and
server/rating_update_handler.py already subscribe to GameEndedEvent and
handle both of those, so publishing the event here is enough to trigger
the normal flow.

There is no reconnection support anywhere in this project yet: this is a
one-way countdown that always ends in a resignation (or is silently
cancelled if the game already ended some other way, e.g. checkmate,
before the grace period is up) - never a "welcome back" path.

The caller (server/game_server.py's _handle_connection) unregisters the
disconnected connection from ConnectionManager *before* starting this
countdown, so a plain ConnectionManager.broadcast naturally reaches only
the still-connected player(s) - no separate "who's still here" lookup is
needed here.
"""

from __future__ import annotations

import asyncio
import logging

from bus.event_bus import EventBus
from bus.events import GameEndedEvent
from server.connection_manager import ConnectionManager
from server.protocol import serialize_disconnect_countdown

logger = logging.getLogger(__name__)

COUNTDOWN_SECONDS = 20
OTHER_COLOR = {"w": "b", "b": "w"}


class DisconnectResignHandler:
    def __init__(self, bus: EventBus, connection_manager: ConnectionManager, engine,
                 countdown_seconds: int = COUNTDOWN_SECONDS):
        self._bus = bus
        self._connection_manager = connection_manager
        self._engine = engine
        self._countdown_seconds = countdown_seconds

    async def start_countdown(self, disconnected_color: str) -> None:
        """Broadcasts a descending disconnect_countdown message once a
        second for `countdown_seconds` seconds, then resigns
        `disconnected_color` (publishing a real GameEndedEvent) unless
        the game has already ended some other way by then."""
        for seconds_remaining in range(self._countdown_seconds, 0, -1):
            await self._connection_manager.broadcast(
                serialize_disconnect_countdown(disconnected_color, seconds_remaining),
            )
            await asyncio.sleep(1)

        if self._engine.game_over:
            return  # already ended some other way (e.g. checkmate) - nothing to do

        logger.info(
            "Resigning %s after a %ds disconnect grace period", disconnected_color, self._countdown_seconds,
        )
        self._bus.publish(GameEndedEvent(winner=OTHER_COLOR[disconnected_color], reason="disconnect_timeout"))
