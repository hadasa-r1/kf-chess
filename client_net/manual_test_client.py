"""Manual smoke-test client - not wired into main_gui.py.

Connects to a running KungFu Chess server and prints every received
GameSnapshot to stdout, to confirm the wire protocol works end-to-end
before any GUI integration.

Run the server first:
    python -m server.game_server
Then, in a second terminal:
    python -m client_net.manual_test_client
"""

import asyncio

from websockets.asyncio.client import connect

from client_net.network_client import NetworkClient

SERVER_URI = "ws://localhost:8765"


async def _main():
    async with connect(SERVER_URI) as connection:
        client = NetworkClient(connection, on_snapshot=print)
        await client.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
