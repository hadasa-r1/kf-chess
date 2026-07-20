import asyncio

from bus.event_bus import EventBus
from bus.events import GameStartedEvent, MoveMadeEvent, ScoreChangedEvent
from server.event_broadcast_handler import EventBroadcastHandler


class _FakeConnectionManager:
    def __init__(self):
        self.broadcasts = []

    async def broadcast(self, payload):
        self.broadcasts.append(payload)


def _publish_and_let_broadcast_run(event):
    """EventBroadcastHandler schedules ConnectionManager.broadcast as an
    asyncio task (bus.publish() calls subscribers synchronously, but
    broadcast is async) - yielding once lets that scheduled task run
    before we inspect its effect."""
    bus = EventBus()
    connection_manager = _FakeConnectionManager()
    EventBroadcastHandler(bus, connection_manager)

    async def scenario():
        bus.publish(event)
        await asyncio.sleep(0)

    asyncio.run(scenario())
    return connection_manager


def test_score_changed_event_triggers_exactly_one_broadcast():
    connection_manager = _publish_and_let_broadcast_run(ScoreChangedEvent(player="w", new_score=3))

    assert connection_manager.broadcasts == [{"type": "score_changed", "player": "w", "new_score": 3}]


def test_move_made_event_triggers_exactly_one_broadcast():
    event = MoveMadeEvent(color="w", piece="wR", start=(0, 0), end=(0, 2), timestamp=1000)
    connection_manager = _publish_and_let_broadcast_run(event)

    assert connection_manager.broadcasts == [
        {"type": "move_made", "color": "w", "piece": "wR", "start": [0, 0], "end": [0, 2], "timestamp": 1000},
    ]


def test_unrelated_event_does_not_trigger_a_broadcast():
    connection_manager = _publish_and_let_broadcast_run(
        GameStartedEvent(white_player="w", black_player="b"),
    )

    assert connection_manager.broadcasts == []
