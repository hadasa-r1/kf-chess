"""Translates score_changed/move_made network messages back into real
ScoreChangedEvent/MoveMadeEvent instances and publishes them on a local,
client-side EventBus - so the existing ScoreDisplayState/
MoveLogDisplayState (bus_handlers/, completely unmodified) can subscribe
to that bus exactly as they already do server-side. No UI knowledge, no
rendering, no idea these events originated over a network rather than
from a live engine.
"""

from __future__ import annotations

import logging

from bus.event_bus import EventBus
from bus.events import MoveMadeEvent, ScoreChangedEvent

logger = logging.getLogger(__name__)


class RemoteEventSource:
    def __init__(self, bus: EventBus):
        self._bus = bus

    def handle_message(self, payload: dict) -> None:
        """Reconstructs and publishes the event carried by one decoded
        score_changed/move_made message. An unrecognized type or a
        malformed payload is logged and dropped, never raised."""
        message_type = payload.get("type")
        try:
            if message_type == "score_changed":
                event = ScoreChangedEvent(player=payload["player"], new_score=payload["new_score"])
            elif message_type == "move_made":
                event = MoveMadeEvent(
                    color=payload["color"],
                    piece=payload["piece"],
                    start=tuple(payload["start"]),
                    end=tuple(payload["end"]),
                    timestamp=payload["timestamp"],
                )
            else:
                logger.warning("RemoteEventSource: unrecognized message type %r", message_type)
                return
        except (KeyError, TypeError) as error:
            logger.warning("RemoteEventSource: dropping malformed %r message: %s", message_type, error)
            return

        self._bus.publish(event)
