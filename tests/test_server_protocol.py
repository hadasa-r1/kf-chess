import json

from realtime.models import Move, Jump
from server.protocol import ClickCommand, JumpCommand, parse_command, serialize_frame_update, serialize_snapshot
from view.snapshot import GameSnapshot


def test_parse_command_recognizes_a_click():
    command = parse_command(json.dumps({"type": "click", "x": 12, "y": 34}))
    assert command == ClickCommand(x=12, y=34)


def test_parse_command_recognizes_a_jump():
    command = parse_command(json.dumps({"type": "jump", "x": 5, "y": 6}))
    assert command == JumpCommand(x=5, y=6)


def test_parse_command_returns_none_for_invalid_json():
    assert parse_command("not json at all {") is None


def test_parse_command_returns_none_for_unknown_type():
    assert parse_command(json.dumps({"type": "teleport", "x": 1, "y": 2})) is None


def test_parse_command_returns_none_for_missing_fields():
    assert parse_command(json.dumps({"type": "click", "x": 1})) is None


def test_parse_command_returns_none_for_non_numeric_coordinates():
    assert parse_command(json.dumps({"type": "click", "x": "abc", "y": 2})) is None


def test_parse_command_returns_none_for_non_dict_json():
    assert parse_command(json.dumps([1, 2, 3])) is None


def test_serialize_snapshot_converts_tuples_to_lists():
    snapshot = GameSnapshot(
        cells=(("wR", "."), (".", "bK")),
        width=2,
        height=2,
        game_over=False,
        selected=(0, 0),
    )

    payload = serialize_snapshot(snapshot)

    assert payload == {
        "type": "snapshot",
        "cells": [["wR", "."], [".", "bK"]],
        "width": 2,
        "height": 2,
        "game_over": False,
        "selected": [0, 0],
    }
    # Every value must actually be JSON-serializable (no leftover tuples).
    json.dumps(payload)


def test_serialize_snapshot_handles_no_selection():
    snapshot = GameSnapshot(cells=((".",),), width=1, height=1, game_over=True, selected=None)

    payload = serialize_snapshot(snapshot)

    assert payload["selected"] is None
    assert payload["game_over"] is True


def test_serialize_frame_update_has_the_frame_update_type_and_board_fields():
    snapshot = GameSnapshot(cells=(("wR", "."), (".", "bK")), width=2, height=2, game_over=False, selected=(0, 0))

    payload = serialize_frame_update(
        snapshot=snapshot, moves=(), jumps=(), clock=0, cooldowns={}, cooldown_remaining={},
    )

    assert payload["type"] == "frame_update"
    assert payload["cells"] == [["wR", "."], [".", "bK"]]
    assert payload["width"] == 2
    assert payload["height"] == 2
    assert payload["game_over"] is False
    assert payload["selected"] == [0, 0]


def test_serialize_frame_update_converts_moves_and_jumps_to_dicts():
    snapshot = GameSnapshot(cells=((".",),), width=1, height=1, game_over=False)
    move = Move(piece="wR", start=(0, 0), end=(0, 2), arrival=2000)
    jump = Jump(piece="bP", cell=(1, 1), end_time=1500)

    payload = serialize_frame_update(
        snapshot=snapshot, moves=(move,), jumps=(jump,), clock=500, cooldowns={}, cooldown_remaining={},
    )

    assert payload["moves"] == [{"piece": "wR", "start": [0, 0], "end": [0, 2], "arrival": 2000}]
    assert payload["jumps"] == [{"piece": "bP", "cell": [1, 1], "end_time": 1500}]
    assert payload["clock"] == 500
    # Every value must actually be JSON-serializable (no leftover tuples).
    json.dumps(payload)


def test_serialize_frame_update_converts_cooldown_dicts_to_pair_lists():
    snapshot = GameSnapshot(cells=((".",),), width=1, height=1, game_over=False)

    payload = serialize_frame_update(
        snapshot=snapshot, moves=(), jumps=(), clock=0,
        cooldowns={(0, 1): "move", (1, 0): None},
        cooldown_remaining={(0, 1): 1800, (1, 0): 0},
    )

    assert payload["cooldowns"] == [[[0, 1], "move"], [[1, 0], None]]
    assert payload["cooldown_remaining"] == [[[0, 1], 1800], [[1, 0], 0]]
    # JSON object keys can't be tuples - confirm the pair-list shape survives
    # a real round-trip through json, not just the in-memory dict.
    json.dumps(payload)
