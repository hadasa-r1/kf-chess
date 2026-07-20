import asyncio
import json

from client_net.network_client import NetworkClient


class _FakeConnection:
    """A minimal async-iterable stand-in for a websockets connection:
    yields each of `messages` in turn, then stops (mirroring what
    `async for message in connection` sees when the socket closes)."""

    def __init__(self, messages):
        self._messages = list(messages)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for message in self._messages:
            yield message


def _run_client(messages, on_frame_update, on_remote_event=None):
    connection = _FakeConnection(messages)
    client = NetworkClient(connection, on_frame_update=on_frame_update, on_remote_event=on_remote_event)
    asyncio.run(client.run())


def test_frame_update_messages_are_still_routed_to_on_frame_update():
    received = []
    message = json.dumps({
        "type": "frame_update", "cells": [["."]], "width": 1, "height": 1, "game_over": False,
        "selected": None, "moves": [], "jumps": [], "clock": 0, "cooldowns": [], "cooldown_remaining": [],
    })

    _run_client([message], on_frame_update=received.append)

    assert len(received) == 1
    assert received[0].clock == 0


def test_score_changed_message_is_routed_to_on_remote_event_not_on_frame_update():
    frame_updates = []
    remote_events = []
    message = json.dumps({"type": "score_changed", "player": "w", "new_score": 3})

    _run_client([message], on_frame_update=frame_updates.append, on_remote_event=remote_events.append)

    assert frame_updates == []
    assert remote_events == [{"type": "score_changed", "player": "w", "new_score": 3}]


def test_move_made_message_is_routed_to_on_remote_event_not_on_frame_update():
    frame_updates = []
    remote_events = []
    message = json.dumps({
        "type": "move_made", "color": "w", "piece": "wR",
        "start": [0, 0], "end": [0, 2], "timestamp": 1000,
    })

    _run_client([message], on_frame_update=frame_updates.append, on_remote_event=remote_events.append)

    assert frame_updates == []
    assert len(remote_events) == 1
    assert remote_events[0]["color"] == "w"


def test_remote_event_without_a_callback_is_silently_ignored():
    frame_updates = []
    message = json.dumps({"type": "score_changed", "player": "w", "new_score": 3})

    _run_client([message], on_frame_update=frame_updates.append)  # no on_remote_event - must not raise

    assert frame_updates == []


def test_unrecognized_message_type_is_dropped_without_raising():
    frame_updates = []
    remote_events = []
    message = json.dumps({"type": "mystery"})

    _run_client([message], on_frame_update=frame_updates.append, on_remote_event=remote_events.append)

    assert frame_updates == []
    assert remote_events == []


def test_malformed_json_is_dropped_without_raising():
    frame_updates = []

    _run_client(["not json {"], on_frame_update=frame_updates.append)  # must not raise

    assert frame_updates == []
