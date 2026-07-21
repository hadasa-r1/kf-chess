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


async def _login(connection, username="tester", password="hunter2"):
    # Every connection must log in before anything else is allowed - see
    # server/game_server.py's login gate - so every scenario below sends
    # this as its very first message.
    await connection.send(json.dumps({"type": "login", "username": username, "password": password}))


def test_client_receives_a_frame_update_after_sending_a_click(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT}") as connection:
                await _login(connection)
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


def test_client_receives_a_frame_update_with_an_in_flight_move(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 1, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 1}") as connection:
                await _login(connection)
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


def test_client_receives_a_move_made_broadcast_distinct_from_frame_update(tmp_path):
    # EventBroadcastHandler forwards MoveMadeEvent as its own "move_made"
    # message, separate from the tick loop's "frame_update" broadcasts -
    # confirms the two channels actually coexist on one real connection.
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 2, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 2}") as connection:
                await _login(connection)
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


def test_first_two_connections_get_white_and_black_third_gets_rejected(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 3, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as first:
                await _login(first, "alice")
                first_payload = await _next_message_of_type(first, "assigned_color")
                assert first_payload["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as second:
                    await _login(second, "bob")
                    second_payload = await _next_message_of_type(second, "assigned_color")
                    assert second_payload["color"] == "b"

                    async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as third:
                        await _login(third, "carol")
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


def test_each_connection_receives_its_own_selected_cell_in_frame_update(tmp_path):
    # Two connections each select a different one of their own pieces -
    # confirms the tick loop's per-connection "selected" personalization
    # (server/connection_manager.py's controller_for/send) actually gives
    # each client its own Controller.selected, not the other's and not
    # null, even though both share one broadcast engine snapshot. Also a
    # regression check for an earlier register() bugfix - registering a
    # connection with its controller used to raise a TypeError before
    # every connection attempt, which would have made this scenario fail
    # outright rather than merely assert wrong values.
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 5, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 5}") as first:
                await _login(first, "alice")
                first_assigned = await _next_message_of_type(first, "assigned_color")
                assert first_assigned["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 5}") as second:
                    await _login(second, "bob")
                    second_assigned = await _next_message_of_type(second, "assigned_color")
                    assert second_assigned["color"] == "b"

                    # White pawn at row 6, col 0 -> pixel (0, 600).
                    await first.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                    # Black pawn at row 1, col 0 -> pixel (0, 100).
                    await second.send(json.dumps({"type": "click", "x": 0, "y": 100}))

                    first_payload = None
                    for _ in range(20):
                        first_payload = await _next_message_of_type(first, "frame_update")
                        if first_payload["selected"] is not None:
                            break

                    second_payload = None
                    for _ in range(20):
                        second_payload = await _next_message_of_type(second, "frame_update")
                        if second_payload["selected"] is not None:
                            break

                    assert first_payload["selected"] == [6, 0]
                    assert second_payload["selected"] == [1, 0]
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_a_freed_color_slot_is_reassigned_to_the_next_connection(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 4, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 4}") as first:
                await _login(first, "alice")
                first_payload = await _next_message_of_type(first, "assigned_color")
                assert first_payload["color"] == "w"

            # `first` is now closed (its `async with` block exited) -
            # SessionManager.release() should have freed "w" for reuse.
            await asyncio.sleep(0.2)

            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 4}") as second:
                await _login(second, "bob")
                second_payload = await _next_message_of_type(second, "assigned_color")
                assert second_payload["color"] == "w"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_a_valid_login_gets_the_normal_assigned_color_flow(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 6, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 6}") as connection:
                await _login(connection, "dave")
                payload = await _next_message_of_type(connection, "assigned_color")
                assert payload["color"] == "w"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_a_non_login_first_message_is_rejected_without_ever_being_assigned_a_color(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 7, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 7}") as connection:
                # A click as the very first message instead of a login.
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 0}))

                payload = await _next_message_of_type(connection, "login_rejected")
                assert payload["reason"]

                # The server closes a login-rejected connection outright -
                # it must never receive an assigned_color.
                with pytest.raises(Exception):
                    await asyncio.wait_for(connection.recv(), timeout=2)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_an_empty_username_login_is_rejected(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 8, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 8}") as connection:
                await connection.send(json.dumps({"type": "login", "username": "   ", "password": "hunter2"}))

                payload = await _next_message_of_type(connection, "login_rejected")
                assert payload["reason"]
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_registering_a_brand_new_username_gets_login_success_with_starting_rating(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 9, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 9}") as connection:
                await _login(connection, "erin", "correct-horse")
                payload = await _next_message_of_type(connection, "login_success")

                assert payload["rating"] == 1200
                assert payload["is_new_account"] is True
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_reconnecting_with_the_same_credentials_authenticates_instead_of_reregistering(tmp_path):
    async def scenario():
        db_path = str(tmp_path / "users.db")
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT + 10, user_db_path=db_path))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 10}") as first:
                await _login(first, "erin", "correct-horse")
                first_payload = await _next_message_of_type(first, "login_success")
                assert first_payload["is_new_account"] is True
                assert first_payload["rating"] == 1200

            await asyncio.sleep(0.2)  # let the first connection's disconnect be processed

            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 10}") as second:
                await _login(second, "erin", "correct-horse")
                second_payload = await _next_message_of_type(second, "login_success")

                assert second_payload["is_new_account"] is False
                assert second_payload["rating"] == 1200
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_reconnecting_with_the_wrong_password_is_rejected(tmp_path):
    async def scenario():
        db_path = str(tmp_path / "users.db")
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT + 11, user_db_path=db_path))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 11}") as first:
                await _login(first, "erin", "correct-horse")
                await _next_message_of_type(first, "login_success")

            await asyncio.sleep(0.2)  # let the first connection's disconnect be processed

            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 11}") as second:
                await _login(second, "erin", "totally-wrong-password")
                payload = await _next_message_of_type(second, "login_rejected")

                assert payload["reason"] == "wrong_password"

                # The server closes a login-rejected connection outright -
                # it must never receive an assigned_color.
                with pytest.raises(Exception):
                    await asyncio.wait_for(second.recv(), timeout=2)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())
