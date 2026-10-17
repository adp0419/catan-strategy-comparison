import pytest

from src.sim.validate_production import run


@pytest.fixture(scope="module")
def res():
    return run(games=100)


def test_expected_production_matches_simulation(res):
    for r in res["rows"]:
        assert abs(r["diff_pct"]) < 3, r
        assert abs(r["z"]) < 3.5, r


def test_production_variance_matches_simulation(res):
    assert 0.95 < res["variance_ratio"] < 1.05


def test_random_robber_spreads_evenly(res):
    shares = [d for p, d in res["downtime"].items() if p > 0]
    assert max(shares) - min(shares) < 0.02
