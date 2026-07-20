from server.session_manager import SessionManager


def test_first_connection_is_assigned_white():
    manager = SessionManager()

    assert manager.assign_color("conn-1") == "w"


def test_second_connection_is_assigned_black():
    manager = SessionManager()
    manager.assign_color("conn-1")

    assert manager.assign_color("conn-2") == "b"


def test_third_connection_gets_no_color():
    manager = SessionManager()
    manager.assign_color("conn-1")
    manager.assign_color("conn-2")

    assert manager.assign_color("conn-3") is None


def test_reassigning_an_already_tracked_connection_keeps_its_color():
    manager = SessionManager()
    manager.assign_color("conn-1")

    # Same connection object asking again must not consume a second slot.
    assert manager.assign_color("conn-1") == "w"


def test_release_frees_the_color_for_a_new_connection():
    manager = SessionManager()
    manager.assign_color("conn-1")  # w
    manager.assign_color("conn-2")  # b

    manager.release("conn-1")

    assert manager.assign_color("conn-3") == "w"


def test_release_of_an_unknown_connection_does_not_raise():
    manager = SessionManager()

    manager.release("never-connected")  # must not raise
