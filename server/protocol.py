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


@dataclass(frozen=True)
class LoginCommand:
    username: str
    password: str


def parse_command(text):
    """Turn one incoming message into a ClickCommand/JumpCommand/
    LoginCommand, or None for anything malformed (invalid JSON,
    missing/wrong-typed fields, an unrecognized "type"). Callers should
    skip a None rather than raise.

    Note: this only checks that "username"/"password" are present and
    string-convertible - it does NOT reject an empty/whitespace-only
    username, and it does NOT check the password against anything (that's
    server/user_store.py's job). Both are login-*validity* questions, not
    parsing-*shape* ones; see server/game_server.py's login gate."""
    try:
        payload = json.loads(text)
        command_type = payload["type"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        logger.warning("Dropping malformed command %r: %s", text, error)
        return None

    if command_type == "login":
        try:
            username = str(payload["username"])
            password = str(payload["password"])
        except (KeyError, TypeError) as error:
            # Never log `text` here - unlike click/jump, it may contain a
            # real password.
            logger.warning("Dropping malformed login command: %s", error)
            return None
        return LoginCommand(username=username, password=password)

    if command_type in ("click", "jump"):
        try:
            x = int(payload["x"])
            y = int(payload["y"])
        except (KeyError, TypeError, ValueError) as error:
            logger.warning("Dropping malformed command %r: %s", text, error)
            return None
        if command_type == "click":
            return ClickCommand(x=x, y=y)
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


def serialize_frame_update(snapshot, moves, jumps, clock, cooldowns, cooldown_remaining):
    """Turn one tick's worth of server-side data into the JSON-serializable
    dict a remote client rebuilds a full FrameState from (see
    view.snapshot.FrameState.from_network_payload) - everything
    GraphicsRenderer needs to draw in-flight moves/jumps and cooldown
    overlays exactly like local play, except history/score (excluded here
    on purpose - see FrameState.from_network_payload's TODO comments,
    those arrive via a separate event channel in a later task).

    Reuses serialize_snapshot for the board-state fields it already
    computes identically, then adds motion/clock/cooldown data on top.
    `cooldowns`/`cooldown_remaining` are dicts keyed by cell tuple (as
    produced by view.snapshot.cooldowns_from_engine) - JSON object keys
    can't be tuples, so each becomes a list of [cell, value] pairs.
    """
    payload = serialize_snapshot(snapshot)
    payload["type"] = "frame_update"
    payload["moves"] = [
        {"piece": move.piece, "start": list(move.start), "end": list(move.end), "arrival": move.arrival}
        for move in moves
    ]
    payload["jumps"] = [
        {"piece": jump.piece, "cell": list(jump.cell), "end_time": jump.end_time}
        for jump in jumps
    ]
    payload["clock"] = clock
    payload["cooldowns"] = [[list(cell), kind] for cell, kind in cooldowns.items()]
    payload["cooldown_remaining"] = [[list(cell), remaining] for cell, remaining in cooldown_remaining.items()]
    return payload


def serialize_score_changed(event):
    """Turn a ScoreChangedEvent into a small, purpose-specific JSON
    message - a distinct "type" from frame_update, so a client can tell
    them apart (see server.event_broadcast_handler.EventBroadcastHandler,
    client_net.remote_event_source.RemoteEventSource for the other end)."""
    return {"type": "score_changed", "player": event.player, "new_score": event.new_score}


def serialize_move_made(event):
    """Turn a MoveMadeEvent into a small, purpose-specific JSON message -
    a distinct "type" from frame_update, so a client can tell them apart."""
    return {
        "type": "move_made",
        "color": event.color,
        "piece": event.piece,
        "start": list(event.start),
        "end": list(event.end),
        "timestamp": event.timestamp,
    }


def serialize_invalid_move(event):
    """Turn an InvalidMoveEvent into a small, purpose-specific JSON
    message - a distinct "type" from frame_update, so a client can tell
    them apart."""
    return {
        "type": "invalid_move",
        "reason": event.reason,
        "start": list(event.start),
        "end": list(event.end),
    }


def serialize_game_started(event):
    """Turn a GameStartedEvent into a small, purpose-specific JSON
    message - a distinct "type" from frame_update, so a client can tell
    them apart."""
    return {"type": "game_started", "white_player": event.white_player, "black_player": event.black_player}


def serialize_game_ended(event):
    """Turn a GameEndedEvent into a small, purpose-specific JSON message -
    a distinct "type" from frame_update, so a client can tell them apart."""
    return {"type": "game_ended", "winner": event.winner, "reason": event.reason}


def serialize_assigned_color(color):
    """Sent once, immediately after a connection is accepted, telling the
    client which color it may play (see server.session_manager.SessionManager
    and server/game_server.py's connection handler)."""
    return {"type": "assigned_color", "color": color}


def serialize_rejected(reason):
    """Sent to a connection SessionManager has no color slot left for (a
    3rd+ concurrent player), immediately before the server closes it.
    Viewer support for these connections is a later task - see
    SessionManager's `# TODO: viewers`."""
    return {"type": "rejected", "reason": reason}


def serialize_login_rejected(reason):
    """Sent to a connection whose very first message wasn't a valid login
    (wrong message type, an empty/whitespace-only username, or a
    "wrong_password" for an existing username - see server/user_store.py)
    - immediately before the server closes it. A distinct "type" from
    "rejected" (which is about the game being full, not about login), so
    a client can tell the two apart and react differently."""
    return {"type": "login_rejected", "reason": reason}


def serialize_login_success(rating, is_new_account):
    """Sent right after a successful login (new account or re-
    authentication) - lets the client show the player their current
    rating and whether they just registered, before color assignment
    even happens (see server/user_store.py, server/game_server.py)."""
    return {"type": "login_success", "rating": rating, "is_new_account": is_new_account}


def serialize_disconnect_countdown(color, seconds_remaining):
    """Broadcast roughly once a second, while a disconnected player's
    grace period counts down, to whoever is still connected (see
    server/disconnect_resign_handler.py) - `color` is the DISCONNECTED
    player's color, not the recipient's, so a client can render "opponent
    reconnecting in Ns"."""
    return {"type": "disconnect_countdown", "color": color, "seconds_remaining": seconds_remaining}
