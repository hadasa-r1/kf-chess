"""Thin websockets client wrapper.

Three responsibilities: sending a login command (username+password, must
be the very first outgoing message - see server/game_server.py's login
gate) and click/jump commands to the server, and receiving incoming
messages and dispatching each by its "type": a frame_update is decoded
into a FrameState and handed to on_frame_update; a score_changed/
move_made/invalid_move/game_started/game_ended is handed, undecoded, to
on_remote_event (whose job - see client_net/remote_event_source.py - is
turning it back into a real bus event; RemoteEventSource already handles
all five, this class just has to actually call it for all five); an
assigned_color's color string is handed to on_assigned_color; a
rejected's reason string is handed to on_rejected (see
server/session_manager.py for what assigns/rejects a connection); a
login_rejected's reason string (e.g. "wrong_password" - see
server/user_store.py) is handed to on_login_rejected, distinct from
on_rejected since a bad login and a full game are different failures a
client may want to react to differently; a login_success's rating/
is_new_account is handed to on_login_success; a disconnect_countdown's
color/seconds_remaining (see server/disconnect_resign_handler.py) is
handed to on_disconnect_countdown; a disconnect_countdown_cancelled's
color is handed to on_disconnect_countdown_cancelled (see
server/disconnect_resign_handler.py's cancel_countdown, fired when the
disconnected player reconnects in time - server/session_manager.py's
reconnect()); a room_created/room_joined's room_id
is handed to on_room_created/on_room_joined, and a room_not_found calls
on_room_not_found() with no arguments (see server/room_registry.py,
server/game_session.py for what creates/finds a room); a viewer_assigned
calls on_viewer_assigned() with no arguments (see
server/viewer_controller.py). No rendering, no cv2, nothing UI-specific -
and kept in its own package (never imports from server/), since a client
process must not depend on the server's internals. Never logs a raw
password - only ever sends it onward.
"""

from __future__ import annotations

import json
import logging

from view.snapshot import FrameState, GameSnapshot

logger = logging.getLogger(__name__)


def deserialize_snapshot(payload):
    """Mirrors server.protocol.serialize_snapshot: turns a decoded JSON
    dict back into a GameSnapshot (lists -> tuples)."""
    selected = payload["selected"]
    return GameSnapshot(
        cells=tuple(tuple(row) for row in payload["cells"]),
        width=payload["width"],
        height=payload["height"],
        game_over=payload["game_over"],
        selected=tuple(selected) if selected is not None else None,
    )


class NetworkClient:
    def __init__(self, connection, on_frame_update, on_remote_event=None,
                 on_assigned_color=None, on_rejected=None, on_login_rejected=None, on_login_success=None,
                 on_disconnect_countdown=None, on_disconnect_countdown_cancelled=None, on_room_created=None,
                 on_room_joined=None, on_room_not_found=None, on_viewer_assigned=None):
        self._connection = connection
        self._on_frame_update = on_frame_update
        self._on_remote_event = on_remote_event
        self._on_assigned_color = on_assigned_color
        self._on_rejected = on_rejected
        self._on_login_rejected = on_login_rejected
        self._on_login_success = on_login_success
        self._on_disconnect_countdown = on_disconnect_countdown
        self._on_disconnect_countdown_cancelled = on_disconnect_countdown_cancelled
        self._on_room_created = on_room_created
        self._on_room_joined = on_room_joined
        self._on_room_not_found = on_room_not_found
        self._on_viewer_assigned = on_viewer_assigned

    async def send_login(self, username, password):
        await self._connection.send(json.dumps({"type": "login", "username": username, "password": password}))

    async def send_room_create(self):
        await self._connection.send(json.dumps({"type": "room", "action": "create"}))

    async def send_room_join(self, room_name):
        await self._connection.send(json.dumps({"type": "room", "action": "join", "room_name": room_name}))

    async def send_room_play(self):
        await self._connection.send(json.dumps({"type": "room", "action": "play"}))

    async def send_click(self, x, y):
        await self._connection.send(json.dumps({"type": "click", "x": x, "y": y}))

    async def send_jump(self, x, y):
        await self._connection.send(json.dumps({"type": "jump", "x": x, "y": y}))

    async def run(self):
        """Receives messages until the connection closes, dispatching each
        by its "type". A malformed or unrecognized message is logged and
        skipped, never raised."""
        async for message in self._connection:
            try:
                payload = json.loads(message)
                message_type = payload["type"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                logger.warning("Dropping malformed message %r: %s", message, error)
                continue

            if message_type == "frame_update":
                try:
                    frame_state = FrameState.from_network_payload(payload)
                except (KeyError, TypeError, ValueError) as error:
                    logger.warning("Dropping malformed frame_update message %r: %s", message, error)
                    continue
                self._on_frame_update(frame_state)
            elif message_type in ("score_changed", "move_made", "invalid_move", "game_started", "game_ended"):
                if self._on_remote_event is not None:
                    self._on_remote_event(payload)
            elif message_type == "assigned_color":
                if self._on_assigned_color is not None:
                    try:
                        self._on_assigned_color(payload["color"])
                    except KeyError as error:
                        logger.warning("Dropping malformed assigned_color message %r: %s", message, error)
            elif message_type == "rejected":
                if self._on_rejected is not None:
                    self._on_rejected(payload.get("reason"))
            elif message_type == "login_rejected":
                if self._on_login_rejected is not None:
                    self._on_login_rejected(payload.get("reason"))
            elif message_type == "login_success":
                if self._on_login_success is not None:
                    try:
                        self._on_login_success(payload["rating"], payload["is_new_account"])
                    except KeyError as error:
                        logger.warning("Dropping malformed login_success message %r: %s", message, error)
            elif message_type == "disconnect_countdown":
                if self._on_disconnect_countdown is not None:
                    try:
                        self._on_disconnect_countdown(payload["color"], payload["seconds_remaining"])
                    except KeyError as error:
                        logger.warning("Dropping malformed disconnect_countdown message %r: %s", message, error)
            elif message_type == "disconnect_countdown_cancelled":
                if self._on_disconnect_countdown_cancelled is not None:
                    try:
                        self._on_disconnect_countdown_cancelled(payload["color"])
                    except KeyError as error:
                        logger.warning(
                            "Dropping malformed disconnect_countdown_cancelled message %r: %s", message, error,
                        )
            elif message_type == "room_created":
                if self._on_room_created is not None:
                    try:
                        self._on_room_created(payload["room_id"])
                    except KeyError as error:
                        logger.warning("Dropping malformed room_created message %r: %s", message, error)
            elif message_type == "room_joined":
                if self._on_room_joined is not None:
                    try:
                        self._on_room_joined(payload["room_id"])
                    except KeyError as error:
                        logger.warning("Dropping malformed room_joined message %r: %s", message, error)
            elif message_type == "room_not_found":
                if self._on_room_not_found is not None:
                    self._on_room_not_found()
            elif message_type == "viewer_assigned":
                if self._on_viewer_assigned is not None:
                    self._on_viewer_assigned()
            else:
                logger.warning("Dropping message with unrecognized type %r", message_type)
