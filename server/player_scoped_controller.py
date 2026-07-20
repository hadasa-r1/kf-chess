"""Wraps a Controller with a per-connection color restriction.

click() only forwards a "select" click (the wrapped Controller currently
has no selection) if the clicked cell holds a piece of `assigned_color` -
an invalid-ownership click is silently dropped, never forwarded to the
real Controller/engine. A "move" click (a selection is already in
progress) is always forwarded unchanged: Controller/GameEngine already
handle a bad destination themselves (friendly destination, illegal move,
...), and re-checking ownership of the *destination* cell here would be
wrong anyway (capturing an enemy piece is the whole point of a move).

However, Controller._resolve_selection re-selects a rejected move-click's
destination cell "regardless of color" by design (see its docstring) -
correct for local hotseat play, where either color is fair game at any
time, but wrong here: it can leave this connection's Controller "holding"
a selection on the opponent's piece. So after forwarding a move-click,
this wrapper re-checks the resulting selection and deselects it if it
landed on a cell the connection doesn't own.

This is a connection-permission concern layered on top of Controller, not
baked into it - local hotseat play (main_gui.py) uses a plain Controller
with no such restriction, exactly as before.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PlayerScopedController:
    def __init__(self, controller, assigned_color, board, board_mapper):
        self._controller = controller
        self._assigned_color = assigned_color
        self._board = board
        self._mapper = board_mapper

    @property
    def selected(self):
        return self._controller.selected

    def click(self, x, y):
        if self._controller.selected is None:
            cell = self._mapper.pixel_to_cell(x, y)
            if cell is not None and not self._owns_piece_at(cell):
                logger.debug(
                    "PlayerScopedController: rejecting select click at %s - not %s's piece",
                    cell, self._assigned_color,
                )
                return
            self._controller.click(x, y)
            return

        # Move-click: forward unchanged, then check what Controller left
        # selected - a rejected move can re-select the clicked cell
        # regardless of color (Controller._resolve_selection's documented,
        # intentional behavior for local hotseat play), so this connection
        # must never end up holding a selection it doesn't own.
        self._controller.click(x, y)
        selected = self._controller.selected
        if selected is not None and not self._owns_piece_at(selected):
            logger.debug(
                "PlayerScopedController: clearing selection at %s left by Controller's "
                "color-blind re-select - not %s's piece",
                selected, self._assigned_color,
            )
            self._controller.deselect()

    def jump(self, x, y):
        # TODO: verify jump needs the same ownership check. GameEngine.
        # request_jump has no color concept at all (it only checks
        # busy/on-cooldown/empty - see game/engine.py) - forwarding
        # unchanged for now rather than guessing at intended behavior.
        self._controller.jump(x, y)

    def _owns_piece_at(self, cell):
        if self._board.is_empty(*cell):
            return False
        return self._board.get(*cell)[0] == self._assigned_color
