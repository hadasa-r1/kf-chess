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


def test_broadcast_delivers_to_every_registered_connection():
    manager = ConnectionManager()
    a, b = _FakeConnection(), _FakeConnection()
    manager.register(a)
    manager.register(b)

    asyncio.run(manager.broadcast({"type": "snapshot", "width": 1}))

    assert a.sent == [json.dumps({"type": "snapshot", "width": 1})]
    assert b.sent == [json.dumps({"type": "snapshot", "width": 1})]


def test_unregister_stops_delivery():
    manager = ConnectionManager()
    a = _FakeConnection()
    manager.register(a)
    manager.unregister(a)

    asyncio.run(manager.broadcast({"type": "snapshot"}))

    assert a.sent == []


def test_one_failing_send_does_not_block_the_others():
    manager = ConnectionManager()
    good_before = _FakeConnection()
    failing = _FakeConnection(fail=True)
    good_after = _FakeConnection()
    manager.register(good_before)
    manager.register(failing)
    manager.register(good_after)

    asyncio.run(manager.broadcast({"type": "snapshot"}))  # must not raise

    assert good_before.sent == [json.dumps({"type": "snapshot"})]
    assert good_after.sent == [json.dumps({"type": "snapshot"})]
