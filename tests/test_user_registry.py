from server.user_registry import UserRegistry


def test_login_records_the_username_for_a_connection():
    registry = UserRegistry()

    registry.login("conn-1", "alice")

    assert registry.username_for("conn-1") == "alice"


def test_username_for_an_unknown_connection_returns_none():
    registry = UserRegistry()

    assert registry.username_for("never-logged-in") is None


def test_logout_removes_the_username():
    registry = UserRegistry()
    registry.login("conn-1", "alice")

    registry.logout("conn-1")

    assert registry.username_for("conn-1") is None


def test_logout_of_an_unknown_connection_does_not_raise():
    registry = UserRegistry()

    registry.logout("never-logged-in")  # must not raise


def test_two_connections_can_be_tracked_independently():
    registry = UserRegistry()
    registry.login("conn-1", "alice")
    registry.login("conn-2", "bob")

    assert registry.username_for("conn-1") == "alice"
    assert registry.username_for("conn-2") == "bob"

    registry.logout("conn-1")

    assert registry.username_for("conn-1") is None
    assert registry.username_for("conn-2") == "bob"
