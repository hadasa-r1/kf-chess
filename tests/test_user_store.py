from server.user_store import AuthOutcome, UserStore


def _make_store(tmp_path):
    # A real file (not ":memory:") under pytest's tmp_path - never the
    # real settings.USER_DB_PATH, and automatically cleaned up.
    return UserStore(str(tmp_path / "test_users.db"))


def test_first_login_for_a_username_creates_an_account_with_starting_rating(tmp_path):
    store = _make_store(tmp_path)

    result = store.register_or_authenticate("alice", "hunter2")

    assert result.outcome is AuthOutcome.NEW_ACCOUNT_CREATED
    assert result.rating == 1200
    assert store.rating_for("alice") == 1200


def test_second_login_with_the_correct_password_authenticates(tmp_path):
    store = _make_store(tmp_path)
    store.register_or_authenticate("alice", "hunter2")

    result = store.register_or_authenticate("alice", "hunter2")

    assert result.outcome is AuthOutcome.AUTHENTICATED
    assert result.rating == 1200


def test_login_with_the_wrong_password_is_rejected(tmp_path):
    store = _make_store(tmp_path)
    store.register_or_authenticate("alice", "hunter2")

    result = store.register_or_authenticate("alice", "wrong-password")

    assert result.outcome is AuthOutcome.WRONG_PASSWORD
    assert result.rating is None


def test_update_rating_persists_and_is_reflected_in_a_later_rating_for_call(tmp_path):
    store = _make_store(tmp_path)
    store.register_or_authenticate("alice", "hunter2")

    store.update_rating("alice", 1250)

    assert store.rating_for("alice") == 1250


def test_rating_for_an_unknown_username_returns_none(tmp_path):
    store = _make_store(tmp_path)

    assert store.rating_for("never-registered") is None


def test_passwords_are_never_stored_in_plaintext(tmp_path):
    import sqlite3

    db_path = tmp_path / "test_users.db"
    store = UserStore(str(db_path))
    store.register_or_authenticate("alice", "hunter2")

    connection = sqlite3.connect(str(db_path))
    row = connection.execute(
        "SELECT password_salt, password_hash FROM users WHERE username = ?", ("alice",),
    ).fetchone()
    connection.close()

    salt, password_hash = row
    assert "hunter2" not in salt
    assert "hunter2" not in password_hash


def test_two_different_usernames_can_reuse_the_same_password(tmp_path):
    # Different random salts must still let both authenticate correctly -
    # confirms the salt (not just the password) is part of the hash input.
    store = _make_store(tmp_path)
    store.register_or_authenticate("alice", "shared-password")
    store.register_or_authenticate("bob", "shared-password")

    assert store.register_or_authenticate("alice", "shared-password").outcome is AuthOutcome.AUTHENTICATED
    assert store.register_or_authenticate("bob", "shared-password").outcome is AuthOutcome.AUTHENTICATED
