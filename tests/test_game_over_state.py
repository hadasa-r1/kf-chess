from bus.event_bus import EventBus
from bus.events import GameEndedEvent
from client_net.game_over_state import GameOverState


def test_a_fresh_instance_starts_at_none():
    state = GameOverState(EventBus())

    assert state.latest() is None


def test_game_ended_event_is_reflected_by_latest():
    bus = EventBus()
    state = GameOverState(bus)

    bus.publish(GameEndedEvent(winner="w", reason="captured_K"))

    assert state.latest() == ("w", "captured_K")


def test_a_disconnect_timeout_reason_is_captured_the_same_way():
    # GameOverState doesn't care whether the event came from a real
    # in-engine ending or server/disconnect_resign_handler.py's
    # disconnect-timeout resignation - both are just a GameEndedEvent.
    bus = EventBus()
    state = GameOverState(bus)

    bus.publish(GameEndedEvent(winner="b", reason="disconnect_timeout"))

    assert state.latest() == ("b", "disconnect_timeout")
