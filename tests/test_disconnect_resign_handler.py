import asyncio

from bus.event_bus import EventBus
from bus.events import GameEndedEvent
from server.disconnect_resign_handler import DisconnectResignHandler
from server.protocol import serialize_disconnect_countdown


class _FakeConnectionManager:
    """Records every broadcast payload - stands in for the real
    ConnectionManager, whose actual fan-out is already covered by
    tests/test_connection_manager.py."""

    def __init__(self):
        self.broadcasts = []

    async def broadcast(self, payload):
        self.broadcasts.append(payload)


class _FakeEngine:
    """A settable `game_over` property - the only thing
    DisconnectResignHandler reads from the real GameEngine (GameEngine.
    game_over is a @property, not a method - see game/engine.py)."""

    def __init__(self, game_over=False):
        self.game_over = game_over


def test_countdown_broadcasts_descending_seconds_remaining_to_whoever_is_left():
    connection_manager = _FakeConnectionManager()
    handler = DisconnectResignHandler(EventBus(), connection_manager, _FakeEngine(), countdown_seconds=3)

    asyncio.run(handler.start_countdown("w"))

    assert connection_manager.broadcasts == [
        serialize_disconnect_countdown("w", 3),
        serialize_disconnect_countdown("w", 2),
        serialize_disconnect_countdown("w", 1),
    ]


def test_no_game_ended_event_if_the_game_already_ended_before_the_countdown_finishes():
    # Simulates the game ending some other way (e.g. checkmate) during the
    # grace period - engine.game_over is already True by the time the
    # countdown finishes, so this handler must not also resign anyone.
    bus = EventBus()
    received = []
    bus.subscribe(GameEndedEvent, received.append)
    handler = DisconnectResignHandler(
        bus, _FakeConnectionManager(), _FakeEngine(game_over=True), countdown_seconds=1,
    )

    asyncio.run(handler.start_countdown("w"))

    assert received == []


def test_disconnecting_white_resigns_to_black_when_the_countdown_elapses_and_the_game_is_still_active():
    bus = EventBus()
    received = []
    bus.subscribe(GameEndedEvent, received.append)
    handler = DisconnectResignHandler(
        bus, _FakeConnectionManager(), _FakeEngine(game_over=False), countdown_seconds=1,
    )

    asyncio.run(handler.start_countdown("w"))

    assert received == [GameEndedEvent(winner="b", reason="disconnect_timeout")]


def test_disconnecting_black_resigns_to_white_when_the_countdown_elapses_and_the_game_is_still_active():
    bus = EventBus()
    received = []
    bus.subscribe(GameEndedEvent, received.append)
    handler = DisconnectResignHandler(
        bus, _FakeConnectionManager(), _FakeEngine(game_over=False), countdown_seconds=1,
    )

    asyncio.run(handler.start_countdown("b"))

    assert received == [GameEndedEvent(winner="w", reason="disconnect_timeout")]
