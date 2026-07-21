from game.move_history import MoveHistory, MoveRecord


def test_record_and_for_color_filters_by_color_preserving_order():
    history = MoveHistory()
    first = MoveRecord(color="w", piece="wR", start=(0, 0), end=(0, 2), timestamp=0)
    second = MoveRecord(color="b", piece="bP", start=(1, 0), end=(2, 0), timestamp=100)
    third = MoveRecord(color="w", piece="wP", start=(1, 1), end=(2, 1), timestamp=200)

    history.record(first)
    history.record(second)
    history.record(third)

    assert history.for_color("w") == (first, third)
    assert history.for_color("b") == (second,)


def test_for_color_with_no_matching_entries_is_empty():
    history = MoveHistory()
    history.record(MoveRecord(color="w", piece="wR", start=(0, 0), end=(0, 1), timestamp=0))

    assert history.for_color("b") == ()
