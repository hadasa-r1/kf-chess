from concurrent.futures import ThreadPoolExecutor

from bus.event_bus import EventBus
from bus.events import Event, GameStartedEvent, MoveMadeEvent, ScoreChangedEvent


def test_publish_delivers_to_subscribed_handler():
    bus = EventBus()
    received = []
    bus.subscribe(MoveMadeEvent, received.append)

    event = MoveMadeEvent(color="w", piece="wP", start=(6, 0), end=(4, 0), timestamp=0)
    bus.publish(event)

    assert received == [event]


def test_multiple_subscribers_all_receive_the_event():
    bus = EventBus()
    received_a = []
    received_b = []
    bus.subscribe(ScoreChangedEvent, received_a.append)
    bus.subscribe(ScoreChangedEvent, received_b.append)

    event = ScoreChangedEvent(player="white", new_score=9)
    bus.publish(event)

    assert received_a == [event]
    assert received_b == [event]


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []
    subscription = bus.subscribe(MoveMadeEvent, received.append)
    bus.unsubscribe(subscription)

    bus.publish(MoveMadeEvent(color="w", piece="wP", start=(6, 0), end=(4, 0), timestamp=0))

    assert received == []


def test_wrong_type_events_are_not_delivered():
    bus = EventBus()
    received = []
    bus.subscribe(MoveMadeEvent, received.append)

    bus.publish(GameStartedEvent(white_player="alice", black_player="bob"))

    assert received == []


def test_subscribing_to_base_type_receives_subclass_events():
    bus = EventBus()
    received = []
    bus.subscribe(Event, received.append)

    event = MoveMadeEvent(color="w", piece="wP", start=(6, 0), end=(4, 0), timestamp=0)
    bus.publish(event)

    assert received == [event]


def test_handler_exception_does_not_stop_other_handlers_or_propagate():
    bus = EventBus()
    received = []

    def bad_handler(event):
        raise ValueError("boom")

    bus.subscribe(MoveMadeEvent, bad_handler)
    bus.subscribe(MoveMadeEvent, received.append)

    event = MoveMadeEvent(color="w", piece="wP", start=(6, 0), end=(4, 0), timestamp=0)
    bus.publish(event)  # must not raise

    assert received == [event]


def test_concurrent_subscribe_and_publish_does_not_crash_or_deadlock():
    bus = EventBus()
    counts = []

    def subscribe_and_publish(i):
        received = []
        subscription = bus.subscribe(MoveMadeEvent, received.append)
        bus.publish(MoveMadeEvent(color="w", piece="wP", start=(0, 0), end=(1, 1), timestamp=i))
        bus.unsubscribe(subscription)
        counts.append(len(received))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(subscribe_and_publish, range(200)))

    assert len(counts) == 200
