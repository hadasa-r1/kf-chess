import asyncio
from dataclasses import dataclass

from bus.event_bus import EventBus
from bus.events import Event, GameEndedEvent, GameStartedEvent, InvalidMoveEvent, MoveMadeEvent, ScoreChangedEvent
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


def test_invalid_move_event_triggers_exactly_one_broadcast():
    event = InvalidMoveEvent(reason="on_cooldown", start=(0, 0), end=(0, 1))
    connection_manager = _publish_and_let_broadcast_run(event)

    assert connection_manager.broadcasts == [
        {"type": "invalid_move", "reason": "on_cooldown", "start": [0, 0], "end": [0, 1]},
    ]


def test_game_started_event_triggers_exactly_one_broadcast():
    event = GameStartedEvent(white_player="w", black_player="b")
    connection_manager = _publish_and_let_broadcast_run(event)

    assert connection_manager.broadcasts == [{"type": "game_started", "white_player": "w", "black_player": "b"}]


def test_game_ended_event_triggers_exactly_one_broadcast():
    event = GameEndedEvent(winner="w", reason="king_captured")
    connection_manager = _publish_and_let_broadcast_run(event)

    assert connection_manager.broadcasts == [{"type": "game_ended", "winner": "w", "reason": "king_captured"}]


def test_unrelated_event_does_not_trigger_a_broadcast():
    @dataclass(frozen=True)
    class _SomeOtherEvent(Event):
        value: int

    connection_manager = _publish_and_let_broadcast_run(_SomeOtherEvent(value=1))

    assert connection_manager.broadcasts == []
