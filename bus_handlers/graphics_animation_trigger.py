"""First-pass AnimationTrigger, not a final design.

PieceAnimator/GraphicsRenderer (UI/rendering/piece_animator.py,
UI/graphics_renderer.py) only track per-piece, per-cell animation state
today - there is no full-board start/end animation hook to call into yet,
and building one is a larger rendering-layer change than this step should
force. Until such a hook exists, this simply logs which animation was
requested, so GameStartedEvent/GameEndedEvent -> AnimationTriggerHandler
is wired end-to-end; swapping in a real overlay/flash later only touches
this file, not its callers.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GraphicsAnimationTrigger:
    def trigger(self, animation_id: str) -> None:
        logger.info("GraphicsAnimationTrigger: TODO real animation for %r", animation_id)
