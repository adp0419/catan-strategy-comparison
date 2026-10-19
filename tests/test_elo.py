import math

import pytest

from src.analysis.elo import fit_strengths, ratings, to_elo


def test_equal_records_give_equal_ratings():
    wins = {("a", "b"): 50, ("b", "a"): 50}
    elo = to_elo(fit_strengths(["a", "b"], wins, prior=0))
    assert elo["a"] == pytest.approx(elo["b"], abs=1e-6)


def test_three_to_one_is_about_191_elo():
    wins = {("a", "b"): 750, ("b", "a"): 250}
    elo = to_elo(fit_strengths(["a", "b"], wins, prior=0), anchor="b")
    assert elo["a"] == pytest.approx(400 * math.log10(3), abs=0.1)


def test_prior_keeps_perfect_record_finite():
    wins = {("a", "b"): 100, ("b", "a"): 0}
    elo = to_elo(fit_strengths(["a", "b"], wins), anchor="b")
    assert 500 < elo["a"] < 1500


def test_transitive_three_agents():
    wins = {("a", "b"): 70, ("b", "a"): 30, ("b", "c"): 70, ("c", "b"): 30, ("a", "c"): 85, ("c", "a"): 15}
    elo = to_elo(fit_strengths(["a", "b", "c"], wins), anchor="c")
    assert elo["a"] > elo["b"] > elo["c"] == 0


def test_ratings_have_standard_errors():
    wins = {("a", "b"): 60, ("b", "a"): 40}
    res = ratings(["a", "b"], wins, anchor="b", n=50)
    assert res["b"][0] == 0
    assert res["a"][1] > 0
