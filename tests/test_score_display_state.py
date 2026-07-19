from concurrent.futures import ThreadPoolExecutor

from bus.event_bus import EventBus
from bus.events import ScoreChangedEvent
from bus_handlers.score_display_state import ScoreDisplayState


def test_score_for_reflects_latest_published_event():
    bus = EventBus()
    state = ScoreDisplayState(bus)

    bus.publish(ScoreChangedEvent(player="w", new_score=1))
    bus.publish(ScoreChangedEvent(player="w", new_score=4))

    assert state.score_for("w") == 4


def test_different_players_are_tracked_independently():
    bus = EventBus()
    state = ScoreDisplayState(bus)

    bus.publish(ScoreChangedEvent(player="w", new_score=3))
    bus.publish(ScoreChangedEvent(player="b", new_score=9))

    assert state.score_for("w") == 3
    assert state.score_for("b") == 9


def test_score_for_untouched_player_is_zero():
    bus = EventBus()
    state = ScoreDisplayState(bus)

    assert state.score_for("w") == 0


def test_concurrent_publish_and_read_does_not_crash():
    bus = EventBus()
    state = ScoreDisplayState(bus)

    def publish_score(i):
        bus.publish(ScoreChangedEvent(player="w", new_score=i))
        return state.score_for("w")

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(publish_score, range(200)))

    assert len(results) == 200
    assert state.score_for("w") in range(200)
