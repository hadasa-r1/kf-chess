from bus.event_bus import EventBus
from bus.events import GameEndedEvent
from server.rating_update_handler import RatingUpdateHandler
from server.session_manager import SessionManager
from server.user_registry import UserRegistry
from server.user_store import UserStore


def _make_handler(tmp_path):
    bus = EventBus()
    user_store = UserStore(str(tmp_path / "test_users.db"))
    session_manager = SessionManager()
    user_registry = UserRegistry()
    RatingUpdateHandler(bus, user_store, session_manager, user_registry)
    return bus, user_store, session_manager, user_registry


def _seat_players(session_manager, user_registry, white_username, black_username):
    session_manager.assign_color("white-conn", white_username)  # w
    session_manager.assign_color("black-conn", black_username)  # b
    user_registry.login("white-conn", white_username)
    user_registry.login("black-conn", black_username)


def test_game_ended_event_updates_both_ratings_per_elo_math(tmp_path):
    bus, user_store, session_manager, user_registry = _make_handler(tmp_path)
    user_store.register_or_authenticate("alice", "pw")
    user_store.register_or_authenticate("bob", "pw")
    _seat_players(session_manager, user_registry, "alice", "bob")

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))

    # Both start at 1200 (equal expected score of 0.5) - a win/loss with
    # the default K=32 moves each by exactly 16 points.
    assert user_store.rating_for("alice") == 1216
    assert user_store.rating_for("bob") == 1184


def test_winner_gains_more_when_the_loser_was_higher_rated(tmp_path):
    bus, user_store, session_manager, user_registry = _make_handler(tmp_path)
    user_store.register_or_authenticate("alice", "pw")
    user_store.register_or_authenticate("bob", "pw")
    user_store.update_rating("bob", 1400)  # bob is the stronger-rated player
    _seat_players(session_manager, user_registry, "alice", "bob")

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))  # alice (white) upsets bob

    alice_gain = user_store.rating_for("alice") - 1200
    assert alice_gain > 16  # bigger gain than the equal-ratings case above
    assert user_store.rating_for("bob") < 1400  # bob's rating dropped


def test_black_winning_updates_ratings_in_the_opposite_direction(tmp_path):
    bus, user_store, session_manager, user_registry = _make_handler(tmp_path)
    user_store.register_or_authenticate("alice", "pw")
    user_store.register_or_authenticate("bob", "pw")
    _seat_players(session_manager, user_registry, "alice", "bob")

    bus.publish(GameEndedEvent(winner="b", reason="captured_K"))

    assert user_store.rating_for("alice") == 1184
    assert user_store.rating_for("bob") == 1216


def test_a_game_with_only_one_player_seated_is_skipped_without_crashing(tmp_path):
    bus, user_store, session_manager, user_registry = _make_handler(tmp_path)
    user_store.register_or_authenticate("alice", "pw")
    session_manager.assign_color("white-conn", "alice")  # w
    user_registry.login("white-conn", "alice")
    # No black connection/color assigned at all.

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))  # must not raise

    assert user_store.rating_for("alice") == 1200  # left untouched


def test_a_game_ended_event_with_no_players_at_all_is_skipped_without_crashing(tmp_path):
    bus, user_store, session_manager, user_registry = _make_handler(tmp_path)

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))  # must not raise
