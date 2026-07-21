from server.session_manager import SessionManager


def test_first_connection_is_assigned_white():
    manager = SessionManager()

    assert manager.assign_color("conn-1", "alice") == "w"


def test_second_connection_is_assigned_black():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")

    assert manager.assign_color("conn-2", "bob") == "b"


def test_third_connection_gets_no_color():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")
    manager.assign_color("conn-2", "bob")

    assert manager.assign_color("conn-3", "carol") is None


def test_reassigning_an_already_tracked_connection_keeps_its_color():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")

    # Same connection object asking again must not consume a second slot.
    assert manager.assign_color("conn-1", "alice") == "w"


def test_release_frees_the_color_for_a_new_connection():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b

    manager.release("conn-1")

    assert manager.assign_color("conn-3", "carol") == "w"


def test_release_of_an_unknown_connection_does_not_raise():
    manager = SessionManager()

    manager.release("never-connected")  # must not raise


def test_connection_for_finds_the_connection_holding_a_color():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b

    assert manager.connection_for("w") == "conn-1"
    assert manager.connection_for("b") == "conn-2"


def test_connection_for_returns_none_when_no_connection_holds_that_color():
    manager = SessionManager()

    assert manager.connection_for("w") is None


def test_connection_for_reflects_a_release():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w

    manager.release("conn-1")

    assert manager.connection_for("w") is None


def test_is_game_started_is_false_right_after_construction():
    manager = SessionManager()

    assert manager.is_game_started() is False


def test_is_game_started_is_false_after_only_one_assign_color_call():
    manager = SessionManager()

    manager.assign_color("conn-1", "alice")  # w

    assert manager.is_game_started() is False


def test_is_game_started_is_true_once_both_colors_have_been_assigned():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w

    manager.assign_color("conn-2", "bob")  # b

    assert manager.is_game_started() is True


def test_is_game_started_stays_true_after_a_later_release():
    # One-way latch: a mid-game disconnect (release()) must never flip
    # this back to False, so the remaining player is never re-blocked.
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b

    manager.release("conn-1")

    assert manager.is_game_started() is True


def test_reconnect_returns_the_color_the_username_previously_held():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b
    manager.release("conn-1")  # alice disconnects - "w" is now vacant

    assert manager.reconnect("conn-3", "alice") == "w"


def test_reconnect_assigns_the_reclaimed_color_to_the_new_connection():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b
    manager.release("conn-1")

    manager.reconnect("conn-3", "alice")

    assert manager.connection_for("w") == "conn-3"


def test_reconnect_returns_none_for_an_unknown_username():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.release("conn-1")

    assert manager.reconnect("conn-2", "someone-who-never-played") is None


def test_reconnect_does_not_steal_a_color_still_held_by_a_live_connection():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b
    # "conn-1" never disconnects - alice's "w" slot is still live.

    assert manager.reconnect("conn-3", "alice") is None


def test_reconnect_does_not_affect_is_game_started():
    manager = SessionManager()
    manager.assign_color("conn-1", "alice")  # w
    manager.assign_color("conn-2", "bob")  # b
    manager.release("conn-1")

    manager.reconnect("conn-3", "alice")

    assert manager.is_game_started() is True
