"""Combines a network-sourced FrameState (board/moves/jumps/clock/
cooldowns, from FrameState.from_network_payload) with locally bus-fed
score/move-log read models - so GraphicsRenderer keeps seeing one
ordinary FrameState regardless of whether history/score arrived on the
same channel as the board data (local play) or a separate event channel
(networked play; see view.snapshot.FrameState.from_network_payload's
TODO comments for why those fields start out empty/zero).
"""

from __future__ import annotations

from dataclasses import replace


def merge_display_data(network_frame_state, score_state, move_log_state):
    """Returns a NEW FrameState - network_frame_state itself is untouched
    (frozen) - with the same snapshot/moves/jumps/clock/cooldowns/
    cooldown_remaining, but white_history/black_history/white_score/
    black_score replaced by the given read models' current values."""
    return replace(
        network_frame_state,
        white_history=move_log_state.entries_for("w"),
        black_history=move_log_state.entries_for("b"),
        white_score=score_state.score_for("w"),
        black_score=score_state.score_for("b"),
    )
