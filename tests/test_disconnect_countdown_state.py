from client_net.disconnect_countdown_state import DisconnectCountdownState


def test_a_fresh_instance_starts_at_none():
    state = DisconnectCountdownState()

    assert state.latest() is None


def test_update_is_reflected_by_latest():
    state = DisconnectCountdownState()

    state.update("w", 17)

    assert state.latest() == ("w", 17)


def test_a_later_update_overwrites_the_previous_one():
    state = DisconnectCountdownState()
    state.update("w", 17)

    state.update("w", 16)

    assert state.latest() == ("w", 16)


def test_clear_resets_latest_to_none():
    state = DisconnectCountdownState()
    state.update("w", 17)

    state.clear()

    assert state.latest() is None


def test_clear_on_a_fresh_instance_does_not_raise():
    state = DisconnectCountdownState()

    state.clear()  # must not raise

    assert state.latest() is None
