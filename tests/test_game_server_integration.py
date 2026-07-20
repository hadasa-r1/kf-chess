import asyncio
import json

from websockets.asyncio.client import connect

from server.game_server import run_server

TEST_HOST = "localhost"
TEST_PORT = 8799


def test_client_receives_a_snapshot_after_sending_a_click():
    async def scenario():
        server_task = asyncio.create_task(run_server(host=TEST_HOST, port=TEST_PORT))
        await asyncio.sleep(0.2)  # let the server finish binding before connecting
        try:
            async with connect(f"ws://{TEST_HOST}:{TEST_PORT}") as connection:
                await connection.send(json.dumps({"type": "click", "x": 0, "y": 0}))
                message = await asyncio.wait_for(connection.recv(), timeout=2)
                payload = json.loads(message)

            assert payload["type"] == "snapshot"
            assert payload["width"] > 0
            assert payload["height"] > 0
            assert isinstance(payload["cells"], list)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())
