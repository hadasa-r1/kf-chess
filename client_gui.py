"""KungFu Chess - remote graphical entry point.

Run this file directly (`python client_gui.py [ws://host:port]`) to play
over the network against a running `server/game_server.py`. Mirrors
main_gui.py's structure as closely as possible, but there is no local
GameEngine/Board at all: board/move/cooldown state arrives over the wire
as frame_update messages (cached by FrameStateCache), and score/move-log
arrive as separate score_changed/move_made events (re-published on a
local EventBus by RemoteEventSource, then read by the same, unmodified
ScoreDisplayState/MoveLogDisplayState main_gui.py already uses locally).

Out of scope, left as follow-ups: InvalidMoveEvent feedback to the client
(an invalid selection currently just fails silently - see
client_net/remote_controller.py), reconnection handling, and any
login/room UI.
"""

import asyncio
import sys
import threading
import time

import cv2
import numpy as np
from websockets.asyncio.client import connect

from board.board import Board
from bus.event_bus import EventBus
from bus_handlers.animation_trigger_handler import AnimationTriggerHandler
from bus_handlers.audio_sound_player import AudioSoundPlayer
from bus_handlers.graphics_animation_trigger import GraphicsAnimationTrigger
from bus_handlers.move_log_display_state import MoveLogDisplayState
from bus_handlers.score_display_state import ScoreDisplayState
from bus_handlers.sound_handler import SoundHandler
from client_net.frame_state_cache import FrameStateCache
from client_net.frame_state_merge import merge_display_data
from client_net.network_client import NetworkClient
from client_net.remote_controller import RemoteController
from client_net.remote_event_source import RemoteEventSource
from config import settings
from game.board_mapper import BoardMapper
from main_gui import _build_renderer
from UI import ui_config

WINDOW_NAME = "KungFu Chess (remote)"
DEFAULT_SERVER_URI = "ws://localhost:8765"


class _NetworkThread:
    """Runs NetworkClient's asyncio connection loop on a background daemon
    thread, so cv2 keeps the main thread. Exposes thread-safe, synchronous
    send_click(x, y)/send_jump(x, y) - the surface RemoteController expects
    - built on asyncio.run_coroutine_threadsafe, since the real
    NetworkClient.send_click/send_jump are coroutines that must run on
    this thread's own event loop, not the caller's.
    """

    def __init__(self, uri, on_frame_update, on_remote_event, on_assigned_color, on_rejected):
        self._uri = uri
        self._on_frame_update = on_frame_update
        self._on_remote_event = on_remote_event
        self._on_assigned_color = on_assigned_color
        self._on_rejected = on_rejected
        self._loop = None
        self._connection = None
        self._network_client = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        """Starts the background thread and blocks until connected."""
        self._thread.start()
        self._ready.wait()

    def send_click(self, x, y):
        asyncio.run_coroutine_threadsafe(self._network_client.send_click(x, y), self._loop)

    def send_jump(self, x, y):
        asyncio.run_coroutine_threadsafe(self._network_client.send_jump(x, y), self._loop)

    def stop(self):
        """Closes the connection (letting NetworkClient.run()'s receive
        loop end naturally) and waits for the background thread to exit."""
        if self._connection is not None:
            asyncio.run_coroutine_threadsafe(self._connection.close(), self._loop)
        self._thread.join(timeout=2)

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_and_run())

    async def _connect_and_run(self):
        async with connect(self._uri) as connection:
            self._connection = connection
            self._network_client = NetworkClient(
                connection, on_frame_update=self._on_frame_update, on_remote_event=self._on_remote_event,
                on_assigned_color=self._on_assigned_color, on_rejected=self._on_rejected,
            )
            self._ready.set()
            await self._network_client.run()


class _ConnectionState:
    """Shared holder for the two things the network thread learns before
    any board data exists: which color we were assigned, or that the
    server rejected us outright (a 3rd+ connection - see
    server/session_manager.py). Plain attributes, not a lock-protected
    read model like FrameStateCache: each is written at most once, by the
    network thread, and only ever read from the main thread's loop."""

    def __init__(self):
        self.assigned_color = None
        self.rejected_reason = None

    def on_assigned_color(self, color):
        print(f"Assigned color: {color}")
        # TODO: display assigned color in UI more prominently than a
        # window-title update (e.g. a side-panel label) - see _run_loop.
        self.assigned_color = color

    def on_rejected(self, reason):
        print(f"Connection rejected by server: {reason}")
        self.rejected_reason = reason


def _connecting_frame(width=400, height=200):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        frame, "Connecting...", (20, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2,
    )
    return frame


def _rejected_frame(reason, width=400, height=200):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        frame, "Connection rejected:", (20, height // 2 - 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
    )
    cv2.putText(
        frame, str(reason), (20, height // 2 + 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
    )
    return frame


def _on_mouse(controller, board_offset_x, event, x, y, flags, param):
    # Mirrors main_gui.py's _on_mouse exactly: the displayed frame is
    # [white panel | board | black panel], so raw window pixels need the
    # left panel's width subtracted before BoardMapper can turn them into
    # board cells.
    board_x = x - board_offset_x
    if event == cv2.EVENT_LBUTTONDOWN:
        controller.click(board_x, y)
    elif event == cv2.EVENT_RBUTTONDOWN:
        controller.jump(board_x, y)


def _run_loop(network_thread, connection_state, frame_cache, score_state, move_log_state, config):
    """Owns the cv2 window, mouse handling, and the frame-timing loop -
    mirrors main_gui.py's _run_loop, except each frame's data comes from
    merge_display_data(frame_cache.latest(), ...) instead of a live
    engine, and the renderer/controller/mouse callback aren't built until
    the first frame_update arrives (there's no local Board to read
    width/height from before then - meanwhile a simple "Connecting..."
    placeholder is shown, or a "rejected" one if the server turned us
    away as a 3rd+ connection - see server/session_manager.py)."""
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    while frame_cache.latest() is None:
        if connection_state.rejected_reason is not None:
            cv2.imshow(WINDOW_NAME, _rejected_frame(connection_state.rejected_reason))
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            return
        cv2.imshow(WINDOW_NAME, _connecting_frame())
        key = cv2.waitKey(50) & 0xFF
        if key == ord("q"):
            cv2.destroyAllWindows()
            return

    first_snapshot = frame_cache.latest().snapshot
    board_mapper = BoardMapper(Board(first_snapshot.cells), config.CELL_SIZE)
    controller = RemoteController(network_thread, board_mapper)
    renderer = _build_renderer(first_snapshot.width, first_snapshot.height, config)

    if connection_state.assigned_color is not None:
        color_label = "White" if connection_state.assigned_color == "w" else "Black"
        try:
            cv2.setWindowTitle(WINDOW_NAME, f"{WINDOW_NAME} - You are {color_label}")
        except Exception:
            pass  # some OpenCV builds lack setWindowTitle - stdout print already covers it

    cv2.setMouseCallback(
        WINDOW_NAME,
        lambda event, x, y, flags, param: _on_mouse(controller, ui_config.SIDE_PANEL_WIDTH, event, x, y, flags, param),
    )

    last_frame = time.time()
    while True:
        now = time.time()
        elapsed_ms = int((now - last_frame) * 1000)
        last_frame = now

        renderer.advance(elapsed_ms)
        frame_state = merge_display_data(frame_cache.latest(), score_state, move_log_state)
        frame = renderer.render(frame_state)

        if frame_state.snapshot.game_over:
            cv2.imshow(WINDOW_NAME, frame.img)
            cv2.waitKey(0)
            break

        cv2.imshow(WINDOW_NAME, frame.img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cv2.destroyAllWindows()


def main(server_uri=None, config=settings):
    """Connect to a running server and launch the graphical OpenCV front
    end for networked play."""
    uri = server_uri or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER_URI)

    frame_cache = FrameStateCache()
    connection_state = _ConnectionState()
    local_bus = EventBus()
    remote_event_source = RemoteEventSource(local_bus)
    score_state = ScoreDisplayState(local_bus)
    move_log_state = MoveLogDisplayState(local_bus)
    # Kept in a local variable for main()'s whole lifetime (mirroring
    # main_gui.py's _build_bus_handlers) - EventBus.subscribe holds a plain
    # reference to the bound method, but nothing keeps the handler object
    # itself alive without this, and a garbage-collected handler would
    # silently stop reacting to published events.
    sound_handler = SoundHandler(local_bus, AudioSoundPlayer())
    animation_handler = AnimationTriggerHandler(local_bus, GraphicsAnimationTrigger())

    network_thread = _NetworkThread(
        uri, on_frame_update=frame_cache.update, on_remote_event=remote_event_source.handle_message,
        on_assigned_color=connection_state.on_assigned_color, on_rejected=connection_state.on_rejected,
    )
    network_thread.start()

    try:
        _run_loop(network_thread, connection_state, frame_cache, score_state, move_log_state, config)
    finally:
        network_thread.stop()


if __name__ == "__main__":  # pragma: no cover
    main()
