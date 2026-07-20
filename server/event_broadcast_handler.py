"""Forwards ScoreChangedEvent/MoveMadeEvent to every connected client as
small, purpose-specific JSON messages, so a remote client's
RemoteEventSource (client_net/remote_event_source.py) can re-publish them
on its own local EventBus and reuse ScoreDisplayState/MoveLogDisplayState
completely unmodified.

Only these two event types are forwarded. GameStartedEvent/GameEndedEvent/
InvalidMoveEvent are NOT - that's a natural follow-up (sound/animation/
error feedback for remote clients), not implemented here since nothing on
the client side needs them yet.
"""

from __future__ import annotations

import asyncio

from bus.event_bus import EventBus
from bus.events import MoveMadeEvent, ScoreChangedEvent
from server.connection_manager import ConnectionManager
from server.protocol import serialize_move_made, serialize_score_changed


class EventBroadcastHandler:
    def __init__(self, bus: EventBus, connection_manager: ConnectionManager):
        self._connection_manager = connection_manager
        bus.subscribe(ScoreChangedEvent, self._on_score_changed)
        bus.subscribe(MoveMadeEvent, self._on_move_made)

    def _on_score_changed(self, event: ScoreChangedEvent) -> None:
        self._broadcast(serialize_score_changed(event))

    def _on_move_made(self, event: MoveMadeEvent) -> None:
        self._broadcast(serialize_move_made(event))

    def _broadcast(self, payload: dict) -> None:
        # bus.publish() calls subscribers synchronously, but
        # ConnectionManager.broadcast is async (it awaits each
        # connection's send) - schedule it on the running loop rather
        # than blocking the event publisher on network I/O. Safe because
        # this handler only ever runs inside the server's asyncio loop
        # (see server/game_server.py), which is always active by the time
        # GameEngine can publish anything.
        asyncio.create_task(self._connection_manager.broadcast(payload))
