from concurrent.futures import ThreadPoolExecutor

from bus.event_bus import EventBus
from bus.events import MoveMadeEvent
from bus_handlers.move_log_display_state import MoveLogDisplayState


def _move(color="w", piece="wR", start=(0, 0), end=(0, 1), timestamp=0):
    return MoveMadeEvent(color=color, piece=piece, start=start, end=end, timestamp=timestamp)


def test_entries_for_reflects_latest_published_events_in_order():
    bus = EventBus()
    state = MoveLogDisplayState(bus)

    first = _move(timestamp=0, end=(0, 1))
    second = _move(timestamp=1000, start=(0, 1), end=(0, 2))
    bus.publish(first)
    bus.publish(second)

    assert state.entries_for("w") == (first, second)


def test_different_players_are_tracked_independently():
    bus = EventBus()
    state = MoveLogDisplayState(bus)

    white_move = _move(color="w", piece="wR")
    black_move = _move(color="b", piece="bR")
    bus.publish(white_move)
    bus.publish(black_move)

    assert state.entries_for("w") == (white_move,)
    assert state.entries_for("b") == (black_move,)


def test_entries_for_untouched_player_is_empty():
    bus = EventBus()
    state = MoveLogDisplayState(bus)

    assert state.entries_for("w") == ()


def test_concurrent_publish_and_read_does_not_crash():
    bus = EventBus()
    state = MoveLogDisplayState(bus)

    def publish_move(i):
        bus.publish(_move(timestamp=i))
        return state.entries_for("w")

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(publish_move, range(200)))

    assert len(results) == 200
    assert len(state.entries_for("w")) == 200
