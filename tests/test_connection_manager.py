import asyncio
import json

from server.connection_manager import ConnectionManager


class _FakeConnection:
    def __init__(self, fail=False):
        self.sent = []
        self._fail = fail

    async def send(self, message):
        if self._fail:
            raise ConnectionError("simulated disconnect")
        self.sent.append(message)


class _FakeController:
    def __init__(self, selected=None):
        self.selected = selected


def test_broadcast_delivers_to_every_registered_connection():
    manager = ConnectionManager()
    a, b = _FakeConnection(), _FakeConnection()
    manager.register(a, _FakeController())
    manager.register(b, _FakeController())

    asyncio.run(manager.broadcast({"type": "snapshot", "width": 1}))

    assert a.sent == [json.dumps({"type": "snapshot", "width": 1})]
    assert b.sent == [json.dumps({"type": "snapshot", "width": 1})]


def test_unregister_stops_delivery():
    manager = ConnectionManager()
    a = _FakeConnection()
    manager.register(a, _FakeController())
    manager.unregister(a)

    asyncio.run(manager.broadcast({"type": "snapshot"}))

    assert a.sent == []


def test_one_failing_send_does_not_block_the_others():
    manager = ConnectionManager()
    good_before = _FakeConnection()
    failing = _FakeConnection(fail=True)
    good_after = _FakeConnection()
    manager.register(good_before, _FakeController())
    manager.register(failing, _FakeController())
    manager.register(good_after, _FakeController())

    asyncio.run(manager.broadcast({"type": "snapshot"}))  # must not raise

    assert good_before.sent == [json.dumps({"type": "snapshot"})]
    assert good_after.sent == [json.dumps({"type": "snapshot"})]


def test_controller_for_returns_the_registered_controller():
    manager = ConnectionManager()
    a = _FakeConnection()
    controller = _FakeController(selected=(1, 2))
    manager.register(a, controller)

    assert manager.controller_for(a) is controller


def test_controller_for_returns_none_for_an_unregistered_connection():
    manager = ConnectionManager()

    assert manager.controller_for(_FakeConnection()) is None


def test_connections_returns_all_registered_connections():
    manager = ConnectionManager()
    a, b = _FakeConnection(), _FakeConnection()
    manager.register(a, _FakeController())
    manager.register(b, _FakeController())

    assert set(manager.connections()) == {a, b}


def test_send_delivers_to_exactly_one_connection():
    manager = ConnectionManager()
    a, b = _FakeConnection(), _FakeConnection()
    manager.register(a, _FakeController())
    manager.register(b, _FakeController())

    asyncio.run(manager.send(a, {"type": "frame_update", "selected": [1, 2]}))

    assert a.sent == [json.dumps({"type": "frame_update", "selected": [1, 2]})]
    assert b.sent == []


def test_send_failure_is_caught_and_logged_not_raised():
    manager = ConnectionManager()
    failing = _FakeConnection(fail=True)
    manager.register(failing, _FakeController())

    asyncio.run(manager.send(failing, {"type": "frame_update"}))  # must not raise
