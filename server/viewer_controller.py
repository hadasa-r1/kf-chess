"""A completely inert stand-in for a Controller, registered for a
connection that's watching a full room rather than playing in it.

Single responsibility: expose the same minimal public surface
PlayerScopedController does (click(x, y), jump(x, y), .selected) so
ConnectionManager/the tick loop can treat a viewer exactly like a player
for registration/broadcast purposes, while guaranteeing click/jump never
do anything at all. A viewer owns no color, so there's no ownership check
to perform - just an unconditional no-op, independent of
SessionManager.is_game_started (that gate is a PlayerScopedController-only
concept; a viewer is never blocked OR unblocked by it, it's simply always
inert). This is the server-side half of a belt-and-suspenders defense -
client_gui.py also refuses to forward clicks/jumps for a viewer - so even
a client that somehow sent one anyway would still hit this no-op.
"""

from __future__ import annotations


class ViewerController:
    @property
    def selected(self):
        return None

    def click(self, x, y):
        pass

    def jump(self, x, y):
        pass
