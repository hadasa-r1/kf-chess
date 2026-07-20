"""Thin websockets client wrapper.

Two responsibilities: sending click/jump commands to the server, and
receiving incoming snapshot messages and handing each decoded
GameSnapshot to an injected callback so the caller (the render loop)
decides what to do with it. No rendering, no cv2, nothing UI-specific -
and kept in its own package (never imports from server/), since a client
process must not depend on the server's internals.
"""

from __future__ import annotations

import json
import logging

from view.snapshot import GameSnapshot

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
    def __init__(self, connection, on_snapshot):
        self._connection = connection
        self._on_snapshot = on_snapshot

    async def send_click(self, x, y):
        await self._connection.send(json.dumps({"type": "click", "x": x, "y": y}))

    async def send_jump(self, x, y):
        await self._connection.send(json.dumps({"type": "jump", "x": x, "y": y}))

    async def run(self):
        """Receives snapshot messages until the connection closes, handing
        each one to the injected on_snapshot callback. A malformed message
        is logged and skipped, never raised."""
        async for message in self._connection:
            try:
                payload = json.loads(message)
                snapshot = deserialize_snapshot(payload)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                logger.warning("Dropping malformed snapshot message %r: %s", message, error)
                continue
            self._on_snapshot(snapshot)
