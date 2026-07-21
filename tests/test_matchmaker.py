import asyncio

from server.matchmaker import Matchmaker
from server.room_registry import RoomRegistry
from server.user_registry import UserRegistry
from server.user_store import UserStore


def _make_matchmaker(tmp_path, wait_seconds=60):
    user_store = UserStore(str(tmp_path / "test_users.db"))
    room_registry = RoomRegistry(user_store, UserRegistry())
    matchmaker = Matchmaker(user_store, room_registry, wait_seconds=wait_seconds)
    return user_store, matchmaker


def test_two_close_ratings_match_each_other_and_get_the_same_session(tmp_path):
    async def scenario():
        user_store, matchmaker = _make_matchmaker(tmp_path)
        user_store.register_or_authenticate("alice", "pw")
        user_store.register_or_authenticate("bob", "pw")

        alice_session, bob_session = await asyncio.gather(
            matchmaker.find_match("alice"), matchmaker.find_match("bob"),
        )

        assert alice_session is not None
        assert alice_session is bob_session

    asyncio.run(scenario())


def test_a_lone_player_times_out_and_returns_none(tmp_path):
    async def scenario():
        user_store, matchmaker = _make_matchmaker(tmp_path, wait_seconds=0.2)
        user_store.register_or_authenticate("alice", "pw")

        session = await matchmaker.find_match("alice")

        assert session is None

    asyncio.run(scenario())


def test_a_timed_out_players_waiting_entry_is_removed_afterward(tmp_path):
    # Indirect proof: after alice's own find_match times out and returns,
    # a second lone call for a DIFFERENT (close-rated) username must also
    # time out rather than immediately "matching" alice's stale entry.
    async def scenario():
        user_store, matchmaker = _make_matchmaker(tmp_path, wait_seconds=0.2)
        user_store.register_or_authenticate("alice", "pw")
        user_store.register_or_authenticate("bob", "pw")

        assert await matchmaker.find_match("alice") is None
        assert await matchmaker.find_match("bob") is None

    asyncio.run(scenario())


def test_ratings_more_than_100_apart_do_not_match_each_other(tmp_path):
    async def scenario():
        user_store, matchmaker = _make_matchmaker(tmp_path, wait_seconds=0.2)
        user_store.register_or_authenticate("alice", "pw")
        user_store.register_or_authenticate("bob", "pw")
        user_store.update_rating("bob", 1400)  # alice stays at 1200 - a 200-point gap

        alice_result, bob_result = await asyncio.gather(
            matchmaker.find_match("alice"), matchmaker.find_match("bob"),
        )

        assert alice_result is None
        assert bob_result is None

    asyncio.run(scenario())


def test_a_username_never_matches_against_its_own_waiting_entry(tmp_path):
    # A defensive guard against a hypothetical double-call for the same
    # username - the second call must not "match" the first's own entry.
    async def scenario():
        user_store, matchmaker = _make_matchmaker(tmp_path, wait_seconds=0.2)
        user_store.register_or_authenticate("alice", "pw")

        first_result, second_result = await asyncio.gather(
            matchmaker.find_match("alice"), matchmaker.find_match("alice"),
        )

        assert first_result is None
        assert second_result is None

    asyncio.run(scenario())
