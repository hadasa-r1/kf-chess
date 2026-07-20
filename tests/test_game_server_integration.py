import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from server.game_server import run_server

TEST_HOST = "localhost"
TEST_PORT = 8799


async def _next_message_of_type(connection, message_type, attempts=20, timeout=2):
    """Reads incoming messages until one matches `message_type`, skipping
    any others - the connection now interleaves frame_update broadcasts
    with score_changed/move_made broadcasts (see
    server/event_broadcast_handler.py), so a test after a real move must
    not assume the very next message is the type it's after."""
    for _ in range(attempts):
        message = await asyncio.wait_for(connection.recv(), timeout=timeout)
        payload = json.loads(message)
        if payload["type"] == message_type:
            return payload
    raise AssertionError(f"no {message_type!r} message received within {attempts} messages")


def test_client_receives_a_frame_update_after_sending_a_click():
    async def scenario():
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT}") as connection:
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 0}))
                payload = await _next_message_of_type(connection, "frame_update")

            assert payload["type"] == "frame_update"
            assert payload["width"] > 0
            assert payload["height"] > 0
            assert isinstance(payload["cells"], list)
            assert isinstance(payload["moves"], list)
            assert isinstance(payload["jumps"], list)
            assert "clock" in payload
            assert isinstance(payload["cooldowns"], list)
            assert isinstance(payload["cooldown_remaining"], list)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_client_receives_a_frame_update_with_an_in_flight_move():
    async def scenario():
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT + 1))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 1}") as connection:
                # Board's starting position (boards/start.txt) has a white
                # pawn at row 6, col 0 - pixel (0, 600) at CELL_SIZE=100 -
                # moving it two squares forward keeps a move in flight long
                # enough for the very next broadcast to catch it.
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 400}))

                payload = None
                for _ in range(20):
                    payload = await _next_message_of_type(connection, "frame_update")
                    if payload["moves"]:
                        break

                assert payload is not None
                assert payload["moves"], "expected at least one in-flight move to be broadcast"
                move = payload["moves"][0]
                assert set(move.keys()) == {"piece", "start", "end", "arrival"}
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_client_receives_a_move_made_broadcast_distinct_from_frame_update():
    # EventBroadcastHandler forwards MoveMadeEvent as its own "move_made"
    # message, separate from the tick loop's "frame_update" broadcasts -
    # confirms the two channels actually coexist on one real connection.
    async def scenario():
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT + 2))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 2}") as connection:
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 400}))

                payload = await _next_message_of_type(connection, "move_made")

            assert payload["color"] == "w"
            assert payload["piece"] == "wP"
            assert payload["start"] == [6, 0]
            assert payload["end"] == [4, 0]
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_first_two_connections_get_white_and_black_third_gets_rejected():
    async def scenario():
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT + 3))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as first:
                first_payload = await _next_message_of_type(first, "assigned_color")
                assert first_payload["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as second:
                    second_payload = await _next_message_of_type(second, "assigned_color")
                    assert second_payload["color"] == "b"

                    async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as third:
                        third_payload = await _next_message_of_type(third, "rejected")
                        assert third_payload["reason"] == "game_full"

                        # The server closes a rejected connection outright -
                        # nothing further should ever arrive on it.
                        with pytest.raises(Exception):
                            await asyncio.wait_for(third.recv(), timeout=2)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_a_freed_color_slot_is_reassigned_to_the_next_connection():
    async def scenario():
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT + 4))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 4}") as first:
                first_payload = await _next_message_of_type(first, "assigned_color")
                assert first_payload["color"] == "w"

            # `first` is now closed (its `async with` block exited) -
            # SessionManager.release() should have freed "w" for reuse.
            await asyncio.sleep(0.2)

            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 4}") as second:
                second_payload = await _next_message_of_type(second, "assigned_color")
                assert second_payload["color"] == "w"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())
