from client_net.frame_state_merge import merge_display_data
from realtime.models import Move, Jump
from view.snapshot import FrameState, GameSnapshot


class _FakeScoreState:
    def __init__(self, scores):
        self._scores = scores

    def score_for(self, player):
        return self._scores[player]


class _FakeMoveLogState:
    def __init__(self, entries):
        self._entries = entries

    def entries_for(self, player):
        return self._entries[player]


def _make_network_frame_state():
    return FrameState(
        snapshot=GameSnapshot(cells=(("wR", "."), (".", "bK")), width=2, height=2, game_over=False, selected=None),
        moves=(Move(piece="wR", start=(0, 0), end=(0, 1), arrival=1000),),
        jumps=(Jump(piece="bK", cell=(1, 1), end_time=500),),
        white_history=(),  # as produced by FrameState.from_network_payload
        black_history=(),
        white_score=0,
        black_score=0,
        clock=250,
        cooldowns={(0, 0): "move"},
        cooldown_remaining={(0, 0): 1200},
    )


def test_merge_substitutes_score_and_history_from_the_display_states():
    network_frame_state = _make_network_frame_state()
    score_state = _FakeScoreState({"w": 3, "b": 9})
    move_log_state = _FakeMoveLogState({"w": ("w-entry",), "b": ("b-entry-1", "b-entry-2")})

    merged = merge_display_data(network_frame_state, score_state, move_log_state)

    assert merged.white_score == 3
    assert merged.black_score == 9
    assert merged.white_history == ("w-entry",)
    assert merged.black_history == ("b-entry-1", "b-entry-2")


def test_merge_preserves_board_moves_jumps_clock_and_cooldowns_untouched():
    network_frame_state = _make_network_frame_state()
    score_state = _FakeScoreState({"w": 3, "b": 9})
    move_log_state = _FakeMoveLogState({"w": (), "b": ()})

    merged = merge_display_data(network_frame_state, score_state, move_log_state)

    assert merged.snapshot == network_frame_state.snapshot
    assert merged.moves == network_frame_state.moves
    assert merged.jumps == network_frame_state.jumps
    assert merged.clock == network_frame_state.clock
    assert merged.cooldowns == network_frame_state.cooldowns
    assert merged.cooldown_remaining == network_frame_state.cooldown_remaining


def test_merge_does_not_mutate_the_original_frame_state():
    network_frame_state = _make_network_frame_state()
    score_state = _FakeScoreState({"w": 3, "b": 9})
    move_log_state = _FakeMoveLogState({"w": ("w-entry",), "b": ()})

    merge_display_data(network_frame_state, score_state, move_log_state)

    assert network_frame_state.white_score == 0
    assert network_frame_state.black_score == 0
    assert network_frame_state.white_history == ()
