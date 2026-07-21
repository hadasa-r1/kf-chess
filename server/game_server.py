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

Every connection must log in with a username+password as its very first
message before anything else happens: a UserStore (server/user_store.py)
persists accounts (salted/hashed passwords, an ELO rating starting at
1200) in a small SQLite file, independent of any connection/EventBus
knowledge; a UserRegistry then caches connection->username for the
lifetime of that connection (in-memory only). A RatingUpdateHandler
(server/rating_update_handler.py) separately reacts to GameEndedEvent to
update both players' persisted ratings via server/elo.py's pure ELO math.
A SessionManager assigns the 1st logged-in connection "w" and the 2nd "b"
(a 3rd+ is rejected outright - see session_manager.py's `# TODO: viewers`);
each connection's real Controller is wrapped in a PlayerScopedController
that enforces "you may only select your own color's pieces" on top of
it, without game/controller.py itself knowing anything about color
restriction (local hotseat play needs none).

No rooms, no matchmaking - later steps.
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
    ClickCommand, JumpCommand, LoginCommand, parse_command, serialize_assigned_color,
    serialize_frame_update, serialize_login_rejected, serialize_login_success, serialize_rejected,
)
from server.rating_update_handler import RatingUpdateHandler
from server.session_manager import SessionManager
from server.user_registry import UserRegistry
from server.user_store import AuthOutcome, UserStore
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


async def _handle_connection(connection, engine, board, board_mapper, connection_manager, session_manager,
                              user_registry, user_store):
    # A connection's very first message must be a login - checked here,
    # before color assignment or any click/jump handling, by pulling one
    # message off the same async iterator the rest of the handler uses
    # below (so nothing sent after login is skipped or double-read).
    messages = connection.__aiter__()
    try:
        first_message = await messages.__anext__()
    except StopAsyncIteration:
        return  # closed before ever sending anything

    login_command = parse_command(first_message)
    username = login_command.username.strip() if isinstance(login_command, LoginCommand) else ""
    if not username:
        await connection.send(json.dumps(serialize_login_rejected("invalid_username")))
        await connection.close()
        return

    auth_result = user_store.register_or_authenticate(username, login_command.password)
    if auth_result.outcome is AuthOutcome.WRONG_PASSWORD:
        await connection.send(json.dumps(serialize_login_rejected("wrong_password")))
        await connection.close()
        return

    user_registry.login(connection, username)
    await connection.send(json.dumps(serialize_login_success(
        rating=auth_result.rating, is_new_account=auth_result.outcome is AuthOutcome.NEW_ACCOUNT_CREATED,
    )))
    try:
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
        connection_manager.register(connection, controller)
        try:
            async for message in messages:
                command = parse_command(message)
                if isinstance(command, ClickCommand):
                    controller.click(command.x, command.y)
                elif isinstance(command, JumpCommand):
                    controller.jump(command.x, command.y)
        finally:
            connection_manager.unregister(connection)
            session_manager.release(connection)
    finally:
        user_registry.logout(connection)


async def run_server(host=HOST, port=PORT, user_db_path=None):
    # `user_db_path` is overridable (rather than always settings.USER_DB_PATH)
    # so tests can point it at a throwaway file instead of ever touching the
    # real one - see tests/test_game_server_integration.py.
    engine, _controller, board, bus = _build_game(_load_board_lines(), settings)
    board_mapper = BoardMapper(board, settings.CELL_SIZE)
    connection_manager = ConnectionManager()
    session_manager = SessionManager()
    user_registry = UserRegistry()
    user_store = UserStore(user_db_path or settings.USER_DB_PATH)
    event_broadcast_handler = EventBroadcastHandler(bus, connection_manager)
    rating_update_handler = RatingUpdateHandler(bus, user_store, session_manager, user_registry)

    async def handler(connection):
        await _handle_connection(
            connection, engine, board, board_mapper, connection_manager, session_manager,
            user_registry, user_store,
        )

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
