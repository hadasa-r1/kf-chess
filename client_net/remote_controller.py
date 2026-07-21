"""Client-side counterpart to game/controller.py's Controller, for
networked play: same public surface (click/jump/selected), but drives a
network client instead of a live GameEngine.

There is no local engine to validate a selection against, so the first
click of a pair is accepted optimistically (no can_select check) purely
for instant local UI feedback - this is an intentional simplification.
The server's own per-connection Controller (game/controller.py, unchanged
- see server/game_server.py) is what actually applies the real
click-then-move state machine against the live engine. An invalid
selection therefore currently fails silently from this client's point of
view (the server just won't complete the move); forwarding server-side
rejection feedback (InvalidMoveEvent) to the client is a natural
follow-up, not implemented here.

Both clicks of a pair - the "select" click and the "move" click - are
forwarded to the server as raw NetworkClient.send_click(x, y) calls,
exactly like a local player's mouse click, deliberately NOT a new
combined "move" wire command: the server's existing per-connection
Controller already implements the same two-click select-then-move
sequencing this class mirrors locally, so no server/ change is needed at
all. `network_client` here is anything exposing plain, synchronous
send_click(x, y)/send_jump(x, y) methods - client_gui.py supplies a
thread-safe wrapper around the real (async) NetworkClient, since this
class is driven from cv2's synchronous main-thread loop.

Must not import anything from game/ or server/ - only client_net/ and
BoardMapper (confirmed stateless: it only reads its injected board's
in_bounds(), holds no per-call mutable state of its own).
"""

from __future__ import annotations


class RemoteController:
    def __init__(self, network_client, board_mapper):
        self._network_client = network_client
        self._mapper = board_mapper
        self._selected = None

    @property
    def selected(self):
        return self._selected

    def click(self, x, y):
        cell = self._mapper.pixel_to_cell(x, y)
        if cell is None:
            # Outside the board: leave selection untouched (a no-op click),
            # matching Controller's own behavior - and don't bother the
            # server with a click that can't possibly land on a cell.
            return

        if self._selected is None:
            # First click: optimistic local selection only (no validity
            # check - see class docstring) - still forwarded to the
            # server so its own Controller starts tracking the same
            # selection.
            self._selected = cell
        else:
            # Second click: the server's Controller will see this as
            # "something is already selected" and attempt the move itself.
            self._selected = None
        self._network_client.send_click(x, y)

    def jump(self, x, y):
        # A jump always ends any pending selection first (matches
        # Controller's existing order).
        self._selected = None
        cell = self._mapper.pixel_to_cell(x, y)
        if cell is None:
            return
        self._network_client.send_jump(x, y)
