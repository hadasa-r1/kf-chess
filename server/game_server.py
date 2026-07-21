"""Composition root for the KungFu Chess server process.

Each room is an independent GameSession (server/game_session.py): its own
engine/board/board_mapper/bus, its own ConnectionManager/SessionManager/
EventBroadcastHandler/RatingUpdateHandler/DisconnectResignHandler, and its
own tick loop - a move in one room never affects another. RoomRegistry
(server/room_registry.py) creates/looks up sessions by a short room_id.

Every connection must log in with a username+password as its very first
message before anything else happens: a UserStore (server/user_store.py)
persists accounts (salted/hashed passwords, an ELO rating starting at
1200) in a small SQLite file, independent of any connection/EventBus/room
knowledge; a UserRegistry then caches connection->username for the
lifetime of that connection (in-memory only). Both are global, shared
across every room - accounts and ratings don't belong to any one room.

Once logged in, a connection's NEXT message must be a room command -
either {"type": "room", "action": "create"} (starts a brand new
GameSession) or {"type": "room", "action": "join", "room_name": <id>}
(joins an existing one, or gets room_not_found + closed if that id
doesn't exist). Only once a GameSession is resolved does the existing
color-assignment/Controller-wrapping flow proceed, entirely against that
session's own SessionManager/ConnectionManager/engine/board/board_mapper.

A mid-game disconnect doesn't resign the player immediately: their color
slot/Controller registration (within their room's own SessionManager/
ConnectionManager) are freed right away, but _handle_connection then
kicks off that room's DisconnectResignHandler as a background task,
giving them a 20-second grace period before publishing a real
GameEndedEvent on that room's own bus - reusing that room's
EventBroadcastHandler/RatingUpdateHandler rather than a separate resign
path. There is no reconnection support yet.

A 3rd+ connection to an already-full room becomes a viewer instead of
being turned away: it's registered with an inert ViewerController (see
server/viewer_controller.py) so it still receives tick-loop frame_update
broadcasts, but its click/jump commands never do anything - no
promotion-to-player if a real player later disconnects, and no room
listing/deletion - later steps.
"""

from __future__ import annotations

import asyncio
import json
import logging

from websockets.asyncio.server import serve

from config import settings
from game.controller import Controller
from server.player_scoped_controller import PlayerScopedController
from server.protocol import (
    ClickCommand, JumpCommand, LoginCommand, RoomCommand, parse_command, serialize_assigned_color,
    serialize_login_rejected, serialize_login_success, serialize_rejected, serialize_room_created,
    serialize_room_joined, serialize_room_not_found, serialize_viewer_assigned,
)
from server.room_registry import RoomRegistry
from server.user_registry import UserRegistry
from server.user_store import AuthOutcome, UserStore
from server.viewer_controller import ViewerController

logger = logging.getLogger(__name__)

HOST = "localhost"
PORT = 8765


async def _forward_commands(messages, controller):
    """Reads click/jump commands off `messages` until the connection
    closes, forwarding each to `controller` - shared by both the real-
    player and viewer paths below, which differ only in what `controller`
    is and what happens on disconnect (see their respective `finally`
    blocks), not in how commands get forwarded."""
    async for message in messages:
        command = parse_command(message)
        if isinstance(command, ClickCommand):
            controller.click(command.x, command.y)
        elif isinstance(command, JumpCommand):
            controller.jump(command.x, command.y)


async def _handle_connection(connection, room_registry, user_registry, user_store):
    # A connection's very first message must be a login - checked here,
    # before anything else, by pulling one message off the same async
    # iterator the rest of the handler uses below (so nothing sent after
    # login is skipped or double-read).
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
    try:
        await connection.send(json.dumps(serialize_login_success(
            rating=auth_result.rating, is_new_account=auth_result.outcome is AuthOutcome.NEW_ACCOUNT_CREATED,
        )))

        # The next message must be a room command - same one-message-off-
        # the-iterator pattern as the login step above.
        try:
            room_message = await messages.__anext__()
        except StopAsyncIteration:
            return

        room_command = parse_command(room_message)
        session = None
        if isinstance(room_command, RoomCommand) and room_command.action == "create":
            session = room_registry.create_room()
            await connection.send(json.dumps(serialize_room_created(session.room_id)))
        elif isinstance(room_command, RoomCommand) and room_command.action == "join" and room_command.room_name:
            session = room_registry.get_room(room_command.room_name)
            if session is None:
                await connection.send(json.dumps(serialize_room_not_found(room_command.room_name)))
                await connection.close()
                return
            await connection.send(json.dumps(serialize_room_joined(session.room_id)))
        else:
            await connection.send(json.dumps(serialize_rejected("invalid_room_command")))
            await connection.close()
            return

        session_manager = session.session_manager
        connection_manager = session.connection_manager

        color = session_manager.assign_color(connection)
        if color is None:
            # The room already has both "w" and "b" - this connection
            # becomes a viewer instead of being turned away: an inert
            # ViewerController (server/viewer_controller.py), registered
            # just like a real player's so it still receives tick-loop
            # frame_update broadcasts, but whose click/jump never do
            # anything. Deliberately NOT gated by
            # session_manager.is_game_started - that's a
            # PlayerScopedController-only concept; a viewer is always
            # inert, unconditionally.
            await connection.send(json.dumps(serialize_viewer_assigned()))
            controller = ViewerController()
            connection_manager.register(connection, controller)
            try:
                await _forward_commands(messages, controller)
            finally:
                # No color slot was ever assigned, so nothing to release,
                # and a viewer leaving never resigns anyone - no
                # disconnect-resign countdown either.
                connection_manager.unregister(connection)
            return

        await connection.send(json.dumps(serialize_assigned_color(color)))
        controller = PlayerScopedController(
            Controller(engine=session.engine, board_mapper=session.board_mapper),
            color, session.board, session.board_mapper, session_manager.is_game_started,
        )
        connection_manager.register(connection, controller)
        try:
            await _forward_commands(messages, controller)
        finally:
            # Slot/registration are freed immediately, exactly as before -
            # only the game-end decision is delayed, via a background
            # task started *after* unregistering, so its broadcast
            # naturally reaches only whoever's still connected in this
            # room (see server/disconnect_resign_handler.py).
            connection_manager.unregister(connection)
            session_manager.release(connection)
            asyncio.create_task(session.disconnect_resign_handler.start_countdown(color))
    finally:
        user_registry.logout(connection)


async def run_server(host=HOST, port=PORT, user_db_path=None, disconnect_countdown_seconds=None):
    # `user_db_path`/`disconnect_countdown_seconds` are overridable (rather
    # than always settings.USER_DB_PATH / the 20s default) so tests can use
    # a throwaway file and a short countdown instead of ever touching the
    # real database or waiting 20 real seconds - see
    # tests/test_game_server_integration.py. Both flow down into every
    # GameSession a room command creates, via RoomRegistry.
    user_registry = UserRegistry()
    user_store = UserStore(user_db_path or settings.USER_DB_PATH)
    room_registry = RoomRegistry(
        user_store, user_registry, disconnect_countdown_seconds=disconnect_countdown_seconds,
    )

    async def handler(connection):
        await _handle_connection(connection, room_registry, user_registry, user_store)

    async with serve(handler, host, port):
        await asyncio.Future()  # run until cancelled (Ctrl+C, or a test)


def main():
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
