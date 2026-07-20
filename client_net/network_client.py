"""Thin websockets client wrapper.

Two responsibilities: sending click/jump commands to the server, and
receiving incoming messages and dispatching each by its "type": a
frame_update is decoded into a FrameState and handed to on_frame_update;
a score_changed/move_made is handed, undecoded, to on_remote_event (whose
job - see client_net/remote_event_source.py - is turning it back into a
real bus event). No rendering, no cv2, nothing UI-specific - and kept in
its own package (never imports from server/), since a client process must
not depend on the server's internals.
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
    def __init__(self, connection, on_frame_update, on_remote_event=None):
        self._connection = connection
        self._on_frame_update = on_frame_update
        self._on_remote_event = on_remote_event

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
            elif message_type in ("score_changed", "move_made"):
                if self._on_remote_event is not None:
                    self._on_remote_event(payload)
            else:
                logger.warning("Dropping message with unrecognized type %r", message_type)
