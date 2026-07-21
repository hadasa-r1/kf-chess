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


async def _create_room(connection):
    # Every connection must, immediately after logging in, either create
    # or join a room (server/room_registry.py's GameSession) before any
    # color assignment/click/jump handling happens.
    await connection.send(json.dumps({"type": "room", "action": "create"}))
    payload = await _next_message_of_type(connection, "room_created")
    return payload["room_id"]


async def _join_room(connection, room_id):
    await connection.send(json.dumps({"type": "room", "action": "join", "room_name": room_id}))


async def _login_and_create_room(connection, username="tester", password="hunter2"):
    await _login(connection, username, password)
    await _next_message_of_type(connection, "login_success")
    return await _create_room(connection)


async def _login_and_join_room(connection, room_id, username="tester", password="hunter2"):
    await _login(connection, username, password)
    await _next_message_of_type(connection, "login_success")
    await _join_room(connection, room_id)
    await _next_message_of_type(connection, "room_joined")


def test_client_receives_a_frame_update_after_sending_a_click(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT}") as connection:
                await _login_and_create_room(connection)
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
                room_id = await _login_and_create_room(connection)
                # A second player must join before any move is allowed
                # (PlayerScopedController's is_game_started gate) - see
                # tests/test_player_scoped_controller.py /
                # test_session_manager.py for that behavior in isolation.
                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 1}") as opponent:
                    await _login_and_join_room(opponent, room_id, "opponent")

                    # Board's starting position (boards/start.txt) has a
                    # white pawn at row 6, col 0 - pixel (0, 600) at
                    # CELL_SIZE=100 - moving it two squares forward keeps a
                    # move in flight long enough for the next broadcast to
                    # catch it.
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
                room_id = await _login_and_create_room(connection)
                # A second player must join before any move is allowed
                # (PlayerScopedController's is_game_started gate).
                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 2}") as opponent:
                    await _login_and_join_room(opponent, room_id, "opponent")

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


def test_first_two_connections_get_white_and_black_third_becomes_a_viewer(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 3, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as first:
                room_id = await _login_and_create_room(first, "alice")
                first_payload = await _next_message_of_type(first, "assigned_color")
                assert first_payload["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as second:
                    await _login_and_join_room(second, room_id, "bob")
                    second_payload = await _next_message_of_type(second, "assigned_color")
                    assert second_payload["color"] == "b"

                    async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 3}") as third:
                        await _login_and_join_room(third, room_id, "carol")

                        # A 3rd+ connection becomes a viewer instead of
                        # being rejected - see
                        # test_a_third_connection_becomes_a_viewer_instead_of_being_rejected
                        # for the fuller proof (still registered, inert
                        # clicks, doesn't affect the real players' game).
                        third_payload = await _next_message_of_type(third, "viewer_assigned")
                        assert third_payload == {"type": "viewer_assigned"}
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
    # null, even though both share one broadcast engine snapshot.
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 5, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 5}") as first:
                room_id = await _login_and_create_room(first, "alice")
                first_assigned = await _next_message_of_type(first, "assigned_color")
                assert first_assigned["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 5}") as second:
                    await _login_and_join_room(second, room_id, "bob")
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
                room_id = await _login_and_create_room(first, "alice")
                first_payload = await _next_message_of_type(first, "assigned_color")
                assert first_payload["color"] == "w"

            # `first` is now closed (its `async with` block exited) -
            # SessionManager.release() should have freed "w" for reuse -
            # so the second connection joins the SAME room to reclaim it.
            await asyncio.sleep(0.2)

            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 4}") as second:
                await _login_and_join_room(second, room_id, "bob")
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
                await _login_and_create_room(connection, "dave")
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


def test_a_mid_game_disconnect_counts_down_then_resigns_to_the_other_player(tmp_path):
    # Real end-to-end proof of the disconnect grace period: white
    # disconnects, black should see descending disconnect_countdown
    # broadcasts, then - once the (here, shortened) grace period elapses
    # with the game still active - a real game_ended broadcast (produced
    # by the existing EventBroadcastHandler reacting to the
    # DisconnectResignHandler's GameEndedEvent, not a separate path).
    async def scenario():
        server_task = asyncio.create_task(run_server(
            host=TEST_HOST, port=TEST_PORT + 12, user_db_path=str(tmp_path / "users.db"),
            disconnect_countdown_seconds=1,
        ))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 12}") as white:
                room_id = await _login_and_create_room(white, "alice")
                await _next_message_of_type(white, "assigned_color")

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 12}") as black:
                    await _login_and_join_room(black, room_id, "bob")
                    await _next_message_of_type(black, "assigned_color")

                    await white.close()  # white disconnects mid-game

                    countdown_payload = await _next_message_of_type(black, "disconnect_countdown")
                    assert countdown_payload["color"] == "w"
                    assert countdown_payload["seconds_remaining"] == 1

                    game_ended_payload = await _next_message_of_type(black, "game_ended", attempts=40)
                    assert game_ended_payload["winner"] == "b"
                    assert game_ended_payload["reason"] == "disconnect_timeout"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_two_created_rooms_are_independent_games(tmp_path):
    # A move in one room's GameSession must never affect the other's -
    # confirms each "room"/"create" gets its own engine/board, not a
    # shared global one.
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 13, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 13}") as first:
                first_room_id = await _login_and_create_room(first, "alice")
                await _next_message_of_type(first, "assigned_color")

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 13}") as second:
                    second_room_id = await _login_and_create_room(second, "bob")
                    await _next_message_of_type(second, "assigned_color")

                    assert first_room_id != second_room_id

                    # A second player must join the FIRST room before any
                    # move is allowed there (PlayerScopedController's
                    # is_game_started gate) - the second room stays alone,
                    # which is fine since nothing ever moves in it.
                    async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 13}") as first_opponent:
                        await _login_and_join_room(first_opponent, first_room_id, "carol")

                        # Move white's pawn in the FIRST room only.
                        await first.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                        await first.send(json.dumps({"type": "click", "x": 0, "y": 400}))
                        move_payload = await _next_message_of_type(first, "move_made")
                        assert move_payload["start"] == [6, 0]

                    # The SECOND room's own frame_update must still show
                    # its own starting position untouched - (6, 0) still
                    # holds a white pawn there, not moved/emptied.
                    second_frame = await _next_message_of_type(second, "frame_update")
                    assert second_frame["cells"][6][0] == "wP"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_joining_a_created_room_puts_both_connections_in_the_same_session(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 14, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 14}") as first:
                room_id = await _login_and_create_room(first, "alice")
                first_assigned = await _next_message_of_type(first, "assigned_color")
                assert first_assigned["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 14}") as second:
                    await _login_and_join_room(second, room_id, "bob")
                    second_assigned = await _next_message_of_type(second, "assigned_color")
                    assert second_assigned["color"] == "b"

                    # A move made by white in this shared session must be
                    # visible to black too, over the SAME session's bus.
                    await first.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                    await first.send(json.dumps({"type": "click", "x": 0, "y": 400}))
                    move_payload = await _next_message_of_type(second, "move_made")
                    assert move_payload["color"] == "w"
                    assert move_payload["piece"] == "wP"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_joining_an_unknown_room_gets_room_not_found_and_is_disconnected(tmp_path):
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 15, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 15}") as connection:
                await _login(connection, "erin", "correct-horse")
                await _next_message_of_type(connection, "login_success")

                await _join_room(connection, "no-such-room")
                payload = await _next_message_of_type(connection, "room_not_found")
                assert payload["room_name"] == "no-such-room"

                # The server closes a room_not_found connection outright -
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


def test_a_lone_first_player_cannot_move_until_a_second_player_joins(tmp_path):
    # Real end-to-end proof of PlayerScopedController's is_game_started
    # gate (backed by SessionManager's one-way latch): alone in a room, a
    # click/move sequence must be silently dropped; once a second player
    # joins that same room, the identical sequence must succeed normally.
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 16, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 16}") as first:
                room_id = await _login_and_create_room(first, "alice")
                first_assigned = await _next_message_of_type(first, "assigned_color")
                assert first_assigned["color"] == "w"

                # Alone in the room - white pawn at row 6, col 0 -> pixel
                # (0, 600); this select+move sequence must be dropped
                # entirely, so the pawn never actually moves.
                await first.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                await first.send(json.dumps({"type": "click", "x": 0, "y": 400}))

                frame_payload = await _next_message_of_type(first, "frame_update")
                assert frame_payload["selected"] is None
                assert frame_payload["cells"][6][0] == "wP"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 16}") as second:
                    await _login_and_join_room(second, room_id, "bob")
                    second_assigned = await _next_message_of_type(second, "assigned_color")
                    assert second_assigned["color"] == "b"

                    # Now that both players are present, the SAME sequence
                    # from connection 1 must succeed.
                    await first.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                    await first.send(json.dumps({"type": "click", "x": 0, "y": 400}))

                    move_payload = await _next_message_of_type(first, "move_made")
                    assert move_payload["color"] == "w"
                    assert move_payload["piece"] == "wP"
                    assert move_payload["start"] == [6, 0]
                    assert move_payload["end"] == [4, 0]
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_a_third_connection_becomes_a_viewer_instead_of_being_rejected(tmp_path):
    # Real end-to-end proof: a 3rd connection to an already-full room gets
    # viewer_assigned (not rejected/game_full), is still registered with
    # ConnectionManager (proven by it receiving a real tick-loop
    # frame_update), and any click/jump it sends never affects the board -
    # the two real players' game continues completely unaffected.
    async def scenario():
        server_task = asyncio.create_task(
            run_server(host=TEST_HOST, port=TEST_PORT + 17, user_db_path=str(tmp_path / "users.db")),
        )
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 17}") as first:
                room_id = await _login_and_create_room(first, "alice")
                first_assigned = await _next_message_of_type(first, "assigned_color")
                assert first_assigned["color"] == "w"

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 17}") as second:
                    await _login_and_join_room(second, room_id, "bob")
                    second_assigned = await _next_message_of_type(second, "assigned_color")
                    assert second_assigned["color"] == "b"

                    async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 17}") as third:
                        await _login(third, "carol")
                        await _next_message_of_type(third, "login_success")
                        await _join_room(third, room_id)

                        viewer_payload = await _next_message_of_type(third, "viewer_assigned")
                        assert viewer_payload == {"type": "viewer_assigned"}

                        # Still registered - proven by a real tick-loop
                        # broadcast actually reaching it.
                        third_frame = await _next_message_of_type(third, "frame_update")
                        assert third_frame["cells"][6][0] == "wP"

                        # A click/jump from the viewer must never affect
                        # the board - white pawn at row 6, col 0 -> pixel
                        # (0, 600).
                        await third.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                        await third.send(json.dumps({"type": "click", "x": 0, "y": 400}))
                        await third.send(json.dumps({"type": "jump", "x": 0, "y": 600}))

                        # The two real players' game is unaffected: white
                        # can still make its own real move normally.
                        await first.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                        await first.send(json.dumps({"type": "click", "x": 0, "y": 400}))
                        move_payload = await _next_message_of_type(first, "move_made")
                        assert move_payload["color"] == "w"
                        assert move_payload["start"] == [6, 0]
                        assert move_payload["end"] == [4, 0]
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_reconnecting_with_the_same_username_within_the_grace_period_resumes_the_original_color(tmp_path):
    # Real end-to-end proof of reconnection: white disconnects, black sees
    # the disconnect_countdown start, white reconnects (same username, same
    # room) well before the grace period elapses and gets "w" back via a
    # normal assigned_color message (not a new message type), black sees a
    # disconnect_countdown_cancelled, the game keeps going (a real move
    # still works), and no game_ended ever fires for this disconnect - even
    # after the original grace period would have elapsed.
    async def scenario():
        server_task = asyncio.create_task(run_server(
            host=TEST_HOST, port=TEST_PORT + 18, user_db_path=str(tmp_path / "users.db"),
            disconnect_countdown_seconds=1,
        ))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 18}") as white:
                room_id = await _login_and_create_room(white, "alice")
                await _next_message_of_type(white, "assigned_color")

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 18}") as black:
                    await _login_and_join_room(black, room_id, "bob")
                    await _next_message_of_type(black, "assigned_color")

                    await white.close()  # white disconnects mid-game

                    countdown_payload = await _next_message_of_type(black, "disconnect_countdown")
                    assert countdown_payload["color"] == "w"

                    async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 18}") as reconnected_white:
                        await _login_and_join_room(reconnected_white, room_id, "alice")

                        reassigned_payload = await _next_message_of_type(reconnected_white, "assigned_color")
                        assert reassigned_payload["color"] == "w"

                        cancelled_payload = await _next_message_of_type(black, "disconnect_countdown_cancelled")
                        assert cancelled_payload["color"] == "w"

                        # The game truly continues: the reconnected
                        # connection's own PlayerScopedController can still
                        # move white's pieces.
                        await reconnected_white.send(json.dumps({"type": "click", "x": 0, "y": 600}))
                        await reconnected_white.send(json.dumps({"type": "click", "x": 0, "y": 400}))
                        move_payload = await _next_message_of_type(reconnected_white, "move_made")
                        assert move_payload["color"] == "w"
                        assert move_payload["start"] == [6, 0]

                        # No resignation ever fires for this disconnect,
                        # even well past what the original 1s grace period
                        # would have allowed - the countdown was genuinely
                        # cancelled, not just still pending.
                        with pytest.raises(AssertionError):
                            await _next_message_of_type(black, "game_ended", attempts=60, timeout=1)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_disconnecting_without_reconnecting_still_resigns_after_the_grace_period(tmp_path):
    # Confirms the pre-existing disconnect-timeout resign behavior (see
    # test_a_mid_game_disconnect_counts_down_then_resigns_to_the_other_player)
    # is unaffected by adding reconnection support: with nobody ever
    # reconnecting as "alice", the countdown must still run out and resign
    # white to black exactly as before.
    async def scenario():
        server_task = asyncio.create_task(run_server(
            host=TEST_HOST, port=TEST_PORT + 19, user_db_path=str(tmp_path / "users.db"),
            disconnect_countdown_seconds=1,
        ))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 19}") as white:
                room_id = await _login_and_create_room(white, "alice")
                await _next_message_of_type(white, "assigned_color")

                async with connect(f"ws://{TEST_HOST}:{TEST_PORT + 19}") as black:
                    await _login_and_join_room(black, room_id, "bob")
                    await _next_message_of_type(black, "assigned_color")

                    await white.close()  # white disconnects mid-game, and never reconnects

                    countdown_payload = await _next_message_of_type(black, "disconnect_countdown")
                    assert countdown_payload["color"] == "w"

                    game_ended_payload = await _next_message_of_type(black, "game_ended", attempts=40)
                    assert game_ended_payload["winner"] == "b"
                    assert game_ended_payload["reason"] == "disconnect_timeout"
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())
