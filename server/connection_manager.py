"""Tracks currently-connected client sockets (and each one's own
Controller) and sends JSON-serializable payloads to them, either all at
once (`broadcast`) or one at a time (`send`).

Single responsibility: socket bookkeeping and fan-out. No color
assignment, no player identity - that's server/session_manager.py. The
per-connection Controller is stored here only so server/game_server.py's
tick loop can look it up to read that connection's own `.selected` for a
personalized frame_update (see `controller_for`); ConnectionManager itself
never calls anything on it.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._controllers_by_connection = {}

    def register(self, connection, controller):
        self._controllers_by_connection[connection] = controller

    def unregister(self, connection):
        self._controllers_by_connection.pop(connection, None)

    def connections(self):
        """A snapshot list of currently registered connections - safe to
        iterate even if a connection registers/unregisters while the
        caller is still iterating (mirrors the existing `list(...)`
        pattern already used inside `broadcast`)."""
        return list(self._controllers_by_connection)

    def controller_for(self, connection):
        """The Controller registered for `connection`, or None if it's not
        (or no longer) registered - e.g. it disconnected between the
        caller building a connections list and this lookup. Callers must
        treat None as "skip this connection", never raise."""
        return self._controllers_by_connection.get(connection)

    async def broadcast(self, payload):
        """Send the same JSON-serializable `payload` to every registered
        connection. A send failing for one connection (e.g. it just
        disconnected) is caught and logged individually so it never stops
        the broadcast to the rest."""
        message = json.dumps(payload)
        for connection in self.connections():
            try:
                await connection.send(message)
            except Exception:
                logger.exception("Failed to send to a connection during broadcast")

    async def send(self, connection, payload):
        """Send a JSON-serializable `payload` to exactly one connection.
        A send failure is caught and logged, never raised - same handling
        as one failing connection inside `broadcast`."""
        message = json.dumps(payload)
        try:
            await connection.send(message)
        except Exception:
            logger.exception("Failed to send to a connection")
