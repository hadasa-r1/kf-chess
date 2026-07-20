import json

from server.protocol import ClickCommand, JumpCommand, parse_command, serialize_snapshot
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
