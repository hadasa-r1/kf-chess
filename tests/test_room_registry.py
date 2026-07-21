import asyncio

from server.game_session import GameSession
from server.room_registry import RoomRegistry
from server.user_registry import UserRegistry
from server.user_store import UserStore


def _make_registry(tmp_path):
    user_store = UserStore(str(tmp_path / "test_users.db"))
    user_registry = UserRegistry()
    return RoomRegistry(user_store, user_registry)


def test_create_room_returns_a_game_session_with_a_room_id(tmp_path):
    # GameSession.__init__ schedules its tick loop via asyncio.create_task,
    # so this (like every test below) needs a running event loop - see
    # tests/test_disconnect_resign_handler.py for the same async-wrapper
    # convention used elsewhere in this suite.
    async def scenario():
        registry = _make_registry(tmp_path)

        session = registry.create_room()

        assert isinstance(session, GameSession)
        assert session.room_id

    asyncio.run(scenario())


def test_create_room_generates_a_unique_room_id_each_time(tmp_path):
    async def scenario():
        registry = _make_registry(tmp_path)

        first = registry.create_room()
        second = registry.create_room()

        assert first.room_id != second.room_id

    asyncio.run(scenario())


def test_get_room_finds_a_created_session_by_its_room_id(tmp_path):
    async def scenario():
        registry = _make_registry(tmp_path)
        session = registry.create_room()

        assert registry.get_room(session.room_id) is session

    asyncio.run(scenario())


def test_get_room_with_an_unknown_id_returns_none(tmp_path):
    async def scenario():
        registry = _make_registry(tmp_path)

        assert registry.get_room("no-such-room") is None

    asyncio.run(scenario())


def test_two_created_rooms_have_independent_engines(tmp_path):
    # A move in one room's engine must never affect the other's - the
    # real end-to-end proof of this lives in
    # tests/test_game_server_integration.py; this is the narrower,
    # RoomRegistry-level version of the same guarantee.
    async def scenario():
        registry = _make_registry(tmp_path)

        first = registry.create_room()
        second = registry.create_room()

        assert first.engine is not second.engine
        assert first.board is not second.board
        assert first.connection_manager is not second.connection_manager
        assert first.session_manager is not second.session_manager

    asyncio.run(scenario())
