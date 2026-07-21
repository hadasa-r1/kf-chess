"""Bundles everything one independent room/game needs to run.

Single responsibility: build one room's own engine/board/board_mapper/bus
(via one call to main._build_game - the project's single place that
builds that graph), plus its own ConnectionManager/SessionManager/
EventBroadcastHandler/RatingUpdateHandler/DisconnectResignHandler, and
start that room's tick loop. A GameSession knows nothing about websocket
connections beyond what its own ConnectionManager already tracks, and
nothing about other rooms - server/room_registry.py owns room_id lookup
and is the only thing that constructs a GameSession.

UserRegistry/UserStore are NOT built here: accounts and ratings are
global, independent of which room a game happens in, so they're
constructed once in server/game_server.py's run_server() and passed in
(via server/room_registry.py) to every GameSession's RatingUpdateHandler.

The tick loop (_tick_loop) moved here, unmodified, from server/game_server.py
- now a per-room concern instead of a single global task, since each room
has its own engine/ConnectionManager to advance and broadcast to.
"""

from __future__ import annotations

import asyncio
import time

from config import settings
from game.board_mapper import BoardMapper
from main import _build_game
from server.connection_manager import ConnectionManager
from server.disconnect_resign_handler import COUNTDOWN_SECONDS, DisconnectResignHandler
from server.event_broadcast_handler import EventBroadcastHandler
from server.protocol import serialize_frame_update
from server.rating_update_handler import RatingUpdateHandler
from server.session_manager import SessionManager
from view.snapshot import cooldowns_from_engine
# BOARD_FILE is a plain path constant with no cv2/UI machinery behind it
# (UI/ui_config.py has no imports at all) - reused here rather than
# duplicating the same literal path in a second place.
from UI.ui_config import BOARD_FILE

TICK_INTERVAL_SECONDS = 0.05


def _load_board_lines():
    with open(BOARD_FILE) as f:
        return [line.rstrip("\n") for line in f]


async def _tick_loop(engine, connection_manager):
    """Advances the engine's clock and broadcasts a frame_update roughly
    every TICK_INTERVAL_SECONDS, using the actual elapsed wall time (not a
    fixed constant) so event-loop jitter never desyncs the game clock.

    The broadcast payload carries everything a remote client needs to
    rebuild a full FrameState (moves/jumps/clock/cooldowns) - not just a
    bare snapshot - so networked clients can render in-flight motion and
    cooldown overlays exactly like local play. History/score are excluded
    on purpose (see server.protocol.serialize_frame_update)."""
    last_tick = time.monotonic()
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        now = time.monotonic()
        elapsed_ms = int((now - last_tick) * 1000)
        last_tick = now

        engine.wait(elapsed_ms)
        # `selected=None` here is a placeholder - the per-connection loop
        # below overwrites "selected" with each client's own
        # Controller.selected before sending, since the server has no
        # single shared "selected" concept.
        snapshot = engine.snapshot(selected=None)
        cooldowns, cooldown_remaining = cooldowns_from_engine(engine, snapshot)
        base_payload = serialize_frame_update(
            snapshot=snapshot,
            moves=engine.active_moves(),
            jumps=engine.active_jumps(),
            clock=engine.clock,
            cooldowns=cooldowns,
            cooldown_remaining=cooldown_remaining,
        )
        for connection in connection_manager.connections():
            controller = connection_manager.controller_for(connection)
            if controller is None:
                continue  # disconnected between building the list and this lookup
            personalized_payload = dict(base_payload)
            personalized_payload["selected"] = (
                list(controller.selected) if controller.selected is not None else None
            )
            await connection_manager.send(connection, personalized_payload)


class GameSession:
    def __init__(self, room_id, user_store, user_registry, disconnect_countdown_seconds=None):
        self.room_id = room_id
        self.engine, _controller, self.board, self.bus = _build_game(_load_board_lines(), settings)
        self.board_mapper = BoardMapper(self.board, settings.CELL_SIZE)
        self.connection_manager = ConnectionManager()
        self.session_manager = SessionManager()
        self.event_broadcast_handler = EventBroadcastHandler(self.bus, self.connection_manager)
        self.rating_update_handler = RatingUpdateHandler(
            self.bus, user_store, self.session_manager, user_registry,
        )
        self.disconnect_resign_handler = DisconnectResignHandler(
            self.bus, self.connection_manager, self.engine,
            countdown_seconds=disconnect_countdown_seconds or COUNTDOWN_SECONDS,
        )
        self._tick_task = asyncio.create_task(_tick_loop(self.engine, self.connection_manager))
