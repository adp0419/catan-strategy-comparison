import pytest

from src.agents.registry import make_agent
from src.analysis.stats import wilson
from src.sim.match import play_pair, run_match, summarize


def test_wilson_known_values():
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    lo, hi = wilson(100, 100)
    assert hi == pytest.approx(1.0) and lo == pytest.approx(0.9630, abs=1e-3)
    assert wilson(0, 0) == (0.0, 1.0)


def test_registry():
    assert make_agent("greedy", 1).name == "greedy"
    assert make_agent(("greedy", {"weights": {"vp": 3.0}}), 1).w["vp"] == 3.0
    with pytest.raises(ValueError):
        make_agent("nope", 1)


def test_pair_plays_both_seat_orders():
    logs = play_pair(("random", "random", 5))
    assert [g["seat_order"] for g in logs] == [["a", "b"], ["b", "a"]]
    assert logs[0]["board_hash"] == logs[1]["board_hash"]


def test_parallel_matches_serial():
    serial = run_match("greedy", "random", pairs=6, workers=1)
    parallel = run_match("greedy", "random", pairs=6, workers=3)
    assert serial == parallel


def test_summary():
    logs = run_match("greedy", "random", pairs=5, workers=1)
    res = summarize(logs)
    assert res["games"] == 10
    assert res["a_wins"] == 10
    assert res["a_ci"][0] > 0.6
