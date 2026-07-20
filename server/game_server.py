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

No login, no rooms, no matchmaking, no persistence - later steps.
"""

from __future__ import annotations

import asyncio
import logging
import time

from websockets.asyncio.server import serve

from config import settings
from game.board_mapper import BoardMapper
from game.controller import Controller
from main import _build_game
from server.connection_manager import ConnectionManager
from server.protocol import ClickCommand, JumpCommand, parse_command, serialize_snapshot
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
    """Advances the engine's clock and broadcasts a snapshot roughly every
    TICK_INTERVAL_SECONDS, using the actual elapsed wall time (not a fixed
    constant) so event-loop jitter never desyncs the game clock."""
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
        await connection_manager.broadcast(serialize_snapshot(snapshot))


async def _handle_connection(connection, engine, board_mapper, connection_manager):
    controller = Controller(engine=engine, board_mapper=board_mapper)
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


async def run_server(host=HOST, port=PORT):
    engine, _controller, board, _bus = _build_game(_load_board_lines(), settings)
    board_mapper = BoardMapper(board, settings.CELL_SIZE)
    connection_manager = ConnectionManager()

    async def handler(connection):
        await _handle_connection(connection, engine, board_mapper, connection_manager)

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
