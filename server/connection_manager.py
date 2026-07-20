"""Tracks currently-connected client sockets and broadcasts a JSON-
serializable payload to all of them.

Single responsibility: socket bookkeeping and fan-out. No color
assignment, no player identity, no per-client differentiation - that's a
later step (see server/game_server.py's `# TODO: per-client selected`).
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections = set()

    def register(self, connection):
        self._connections.add(connection)

    def unregister(self, connection):
        self._connections.discard(connection)

    async def broadcast(self, payload):
        """Send the same JSON-serializable `payload` to every registered
        connection. A send failing for one connection (e.g. it just
        disconnected) is caught and logged individually so it never stops
        the broadcast to the rest."""
        message = json.dumps(payload)
        for connection in list(self._connections):
            try:
                await connection.send(message)
            except Exception:
                logger.exception("Failed to send to a connection during broadcast")
