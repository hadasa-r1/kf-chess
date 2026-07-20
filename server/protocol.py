"""Wire-format (de)serialization between the server and its clients.

Two directions: raw incoming JSON text -> a typed ClickCommand/JumpCommand
(malformed input is logged and dropped, never raised, so one bad message
never crashes a connection handler), and a GameSnapshot -> a JSON-
serializable dict (tuples become lists - JSON has no tuple type).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClickCommand:
    x: int
    y: int


@dataclass(frozen=True)
class JumpCommand:
    x: int
    y: int


def parse_command(text):
    """Turn one incoming message into a ClickCommand/JumpCommand, or None
    for anything malformed (invalid JSON, missing/wrong-typed fields, an
    unrecognized "type"). Callers should skip a None rather than raise."""
    try:
        payload = json.loads(text)
        command_type = payload["type"]
        x = int(payload["x"])
        y = int(payload["y"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        logger.warning("Dropping malformed command %r: %s", text, error)
        return None

    if command_type == "click":
        return ClickCommand(x=x, y=y)
    if command_type == "jump":
        return JumpCommand(x=x, y=y)

    logger.warning("Dropping command with unknown type %r", command_type)
    return None


def serialize_snapshot(snapshot):
    """Turn a GameSnapshot into a JSON-serializable dict."""
    return {
        "type": "snapshot",
        "cells": [list(row) for row in snapshot.cells],
        "width": snapshot.width,
        "height": snapshot.height,
        "game_over": snapshot.game_over,
        "selected": list(snapshot.selected) if snapshot.selected is not None else None,
    }
