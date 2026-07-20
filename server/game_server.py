"""Composition root for the KungFu Chess server process.

Builds one shared GameEngine (via main._build_game, reused as-is - the
project's single place that constructs the registry/board/arbiter/engine
graph), gives each connected client its own Controller against that
shared engine and a shared, stateless BoardMapper, and runs two
concurrent pieces:

- a tick loop that keeps the engine's real-time clock advancing and
  broadcasts a snapshot to every connected client, regardless of whether
  any client has sent a command recently (cooldowns/motion are
  time-based, not turn-based);
- the websockets per-connection handler that turns incoming click/jump
  commands into calls on that connection's own Controller.

Also constructs an EventBroadcastHandler on the engine's bus, so
ScoreChangedEvent/MoveMadeEvent reach connected clients as small JSON
messages too (see server/event_broadcast_handler.py) - a separate channel
from the tick loop's frame_update broadcasts.

A SessionManager assigns the 1st connection "w" and the 2nd "b" (a 3rd+
is rejected outright - see session_manager.py's `# TODO: viewers`); each
connection's real Controller is wrapped in a PlayerScopedController that
enforces "you may only select your own color's pieces" on top of it,
without game/controller.py itself knowing anything about color
restriction (local hotseat play needs none).

No login, no rooms, no matchmaking, no persistence - later steps.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from websockets.asyncio.server import serve

from config import settings
from game.board_mapper import BoardMapper
from game.controller import Controller
from main import _build_game
from server.connection_manager import ConnectionManager
from server.event_broadcast_handler import EventBroadcastHandler
from server.player_scoped_controller import PlayerScopedController
from server.protocol import (
    ClickCommand, JumpCommand, parse_command, serialize_assigned_color,
    serialize_frame_update, serialize_rejected,
)
from server.session_manager import SessionManager
from view.snapshot import cooldowns_from_engine
# BOARD_FILE is a plain path constant with no cv2/UI machinery behind it
# (UI/ui_config.py has no imports at all) - reused here rather than
# duplicating the same literal path in a second place.
from UI.ui_config import BOARD_FILE

logger = logging.getLogger(__name__)

HOST = "localhost"
PORT = 8765
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
        # TODO: per-client selected. The server has no single "selected"
        # concept - each client has its own Controller.selected - so every
        # client currently gets the same snapshot with no highlight.
        # Broadcasting a per-client-selected view needs per-client
        # differentiated broadcasting, out of scope for this step.
        snapshot = engine.snapshot(selected=None)
        cooldowns, cooldown_remaining = cooldowns_from_engine(engine, snapshot)
        payload = serialize_frame_update(
            snapshot=snapshot,
            moves=engine.active_moves(),
            jumps=engine.active_jumps(),
            clock=engine.clock,
            cooldowns=cooldowns,
            cooldown_remaining=cooldown_remaining,
        )
        await connection_manager.broadcast(payload)


async def _handle_connection(connection, engine, board, board_mapper, connection_manager, session_manager):
    color = session_manager.assign_color(connection)
    if color is None:
        # TODO: viewers. Reject cleanly instead of letting a 3rd+
        # connection spectate - that's a later task (the "Rooms" slide).
        await connection.send(json.dumps(serialize_rejected("game_full")))
        await connection.close()
        return

    await connection.send(json.dumps(serialize_assigned_color(color)))
    controller = PlayerScopedController(
        Controller(engine=engine, board_mapper=board_mapper), color, board, board_mapper,
    )
    connection_manager.register(connection)
    try:
        async for message in connection:
            command = parse_command(message)
            if isinstance(command, ClickCommand):
                controller.click(command.x, command.y)
            elif isinstance(command, JumpCommand):
                controller.jump(command.x, command.y)
    finally:
        connection_manager.unregister(connection)
        session_manager.release(connection)


async def run_server(host=HOST, port=PORT):
    engine, _controller, board, bus = _build_game(_load_board_lines(), settings)
    board_mapper = BoardMapper(board, settings.CELL_SIZE)
    connection_manager = ConnectionManager()
    session_manager = SessionManager()
    event_broadcast_handler = EventBroadcastHandler(bus, connection_manager)

    async def handler(connection):
        await _handle_connection(connection, engine, board, board_mapper, connection_manager, session_manager)

    tick_task = asyncio.create_task(_tick_loop(engine, connection_manager))
    try:
        async with serve(handler, host, port):
            await asyncio.Future()  # run until cancelled (Ctrl+C, or a test)
    finally:
        tick_task.cancel()
        try:
            await tick_task
        except asyncio.CancelledError:
            pass


def main():
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
