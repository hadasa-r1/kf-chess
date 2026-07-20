"""Manual smoke-test client - not wired into main_gui.py.

Connects to a running KungFu Chess server, prints every received
FrameState to stdout, and also wires the score/move-log event channel:
a local EventBus + RemoteEventSource + the existing (unmodified)
ScoreDisplayState/MoveLogDisplayState, so score_changed/move_made
messages can be seen taking effect too - confirms the wire protocol works
end-to-end before any GUI integration.

Run the server first:
    python -m server.game_server
Then, in a second terminal:
    python -m client_net.manual_test_client
"""

import asyncio

from websockets.asyncio.client import connect

from bus.event_bus import EventBus
from bus_handlers.move_log_display_state import MoveLogDisplayState
from bus_handlers.score_display_state import ScoreDisplayState
from client_net.network_client import NetworkClient
from client_net.remote_event_source import RemoteEventSource

SERVER_URI = "ws://localhost:8765"


async def _main():
    local_bus = EventBus()
    remote_event_source = RemoteEventSource(local_bus)
    score_state = ScoreDisplayState(local_bus)
    move_log_state = MoveLogDisplayState(local_bus)

    def on_frame_update(frame_state):
        print(frame_state)
        print("score: w =", score_state.score_for("w"), "b =", score_state.score_for("b"))
        print("moves: w =", len(move_log_state.entries_for("w")), "b =", len(move_log_state.entries_for("b")))

    async with connect(SERVER_URI) as connection:
        client = NetworkClient(
            connection,
            on_frame_update=on_frame_update,
            on_remote_event=remote_event_source.handle_message,
        )
        await client.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
