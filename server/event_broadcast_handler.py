"""Forwards ScoreChangedEvent/MoveMadeEvent/InvalidMoveEvent/
GameStartedEvent/GameEndedEvent to every connected client as small,
purpose-specific JSON messages, so a remote client's RemoteEventSource
(client_net/remote_event_source.py) can re-publish them on its own local
EventBus and reuse ScoreDisplayState/MoveLogDisplayState/SoundHandler/
AnimationTriggerHandler completely unmodified.
"""

from __future__ import annotations

import asyncio

from bus.event_bus import EventBus
from bus.events import GameEndedEvent, GameStartedEvent, InvalidMoveEvent, MoveMadeEvent, ScoreChangedEvent
from server.connection_manager import ConnectionManager
from server.protocol import (
    serialize_game_ended, serialize_game_started, serialize_invalid_move,
    serialize_move_made, serialize_score_changed,
)


class EventBroadcastHandler:
    def __init__(self, bus: EventBus, connection_manager: ConnectionManager):
        self._connection_manager = connection_manager
        bus.subscribe(ScoreChangedEvent, self._on_score_changed)
        bus.subscribe(MoveMadeEvent, self._on_move_made)
        bus.subscribe(InvalidMoveEvent, self._on_invalid_move)
        bus.subscribe(GameStartedEvent, self._on_game_started)
        bus.subscribe(GameEndedEvent, self._on_game_ended)

    def _on_score_changed(self, event: ScoreChangedEvent) -> None:
        self._broadcast(serialize_score_changed(event))

    def _on_move_made(self, event: MoveMadeEvent) -> None:
        self._broadcast(serialize_move_made(event))

    def _on_invalid_move(self, event: InvalidMoveEvent) -> None:
        self._broadcast(serialize_invalid_move(event))

    def _on_game_started(self, event: GameStartedEvent) -> None:
        self._broadcast(serialize_game_started(event))

    def _on_game_ended(self, event: GameEndedEvent) -> None:
        self._broadcast(serialize_game_ended(event))

    def _broadcast(self, payload: dict) -> None:
        # bus.publish() calls subscribers synchronously, but
        # ConnectionManager.broadcast is async (it awaits each
        # connection's send) - schedule it on the running loop rather
        # than blocking the event publisher on network I/O. Safe because
        # this handler only ever runs inside the server's asyncio loop
        # (see server/game_server.py), which is always active by the time
        # GameEngine can publish anything.
        asyncio.create_task(self._connection_manager.broadcast(payload))
