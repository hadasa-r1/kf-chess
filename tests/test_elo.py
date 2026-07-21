from server.elo import expected_score, updated_rating


def test_expected_score_is_half_for_equal_ratings():
    assert expected_score(1200, 1200) == 0.5


def test_expected_score_favors_the_higher_rated_player():
    # A 200-point-higher-rated player is expected to score more than half.
    higher = expected_score(1400, 1200)
    lower = expected_score(1200, 1400)

    assert higher > 0.5
    assert lower < 0.5
    # The two perspectives on the same matchup must sum to exactly 1.
    assert higher + lower == 1.0


def test_expected_score_matches_a_known_reference_value():
    # A 400-point gap is the textbook example: the underdog's expected
    # score is 1 / (1 + 10^1) = 1/11 ~= 0.0909.
    assert round(expected_score(1000, 1400), 4) == 0.0909
    assert round(expected_score(1400, 1000), 4) == 0.9091


def test_updated_rating_increases_on_a_win_against_an_equal_opponent():
    new_rating = updated_rating(1200, expected=0.5, actual_score=1.0)

    assert new_rating == 1216  # 1200 + 32 * (1 - 0.5)


def test_updated_rating_decreases_on_a_loss_against_an_equal_opponent():
    new_rating = updated_rating(1200, expected=0.5, actual_score=0.0)

    assert new_rating == 1184  # 1200 + 32 * (0 - 0.5)


def test_updated_rating_is_unchanged_on_a_draw_against_an_equal_opponent():
    new_rating = updated_rating(1200, expected=0.5, actual_score=0.5)

    assert new_rating == 1200


def test_a_win_against_a_higher_rated_opponent_gains_more_than_against_a_lower_rated_one():
    rating = 1200
    expected_vs_stronger = expected_score(rating, 1400)
    expected_vs_weaker = expected_score(rating, 1000)

    gain_vs_stronger = updated_rating(rating, expected_vs_stronger, actual_score=1.0) - rating
    gain_vs_weaker = updated_rating(rating, expected_vs_weaker, actual_score=1.0) - rating

    assert gain_vs_stronger > gain_vs_weaker


def test_updated_rating_respects_a_custom_k_factor():
    new_rating = updated_rating(1200, expected=0.5, actual_score=1.0, k=16)

    assert new_rating == 1208  # 1200 + 16 * (1 - 0.5)
