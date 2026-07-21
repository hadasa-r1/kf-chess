from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.move_history import MoveRecord


class MoveObserver(ABC):
    """Lets GameEngine notify listeners about a started move without
    depending on a concrete collaborator like MoveHistory."""

    @abstractmethod
    def on_move_started(self, record: "MoveRecord") -> None:
        ...
