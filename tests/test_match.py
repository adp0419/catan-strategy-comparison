import pytest

from src.agents.registry import make_agent
from src.analysis.stats import wilson
from src.sim.match import pair_results, play_pair, run_match, summarize


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


def test_pair_results_counts_sweeps_and_splits():
    logs = [{"winner": "a"}, {"winner": "a"}, {"winner": "b"}, {"winner": "b"}, {"winner": "a"}, {"winner": "b"}, {"winner": None}, {"winner": "a"}]
    assert pair_results(logs) == (1, 1, 2)


def test_game_record_fields():
    from src.agents.agent_a import GreedyAgent
    from src.agents.baselines import RandomAgent
    from src.common.engine import play_game

    log = play_game(GreedyAgent(), RandomAgent(1), seed=5)
    assert "decisions" not in log
    winner = log["winner"]
    assert log["final"][winner]["vp"] >= 10
    assert set(log["production"]["a"]) == {"WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"}
    assert all(r["by"] in ("a", "b") and 0 <= r["hex"] < 19 for r in log["robber"])
    assert all(d["card"] in ("KNIGHT", "VICTORY_POINT", "YEAR_OF_PLENTY", "ROAD_BUILDING", "MONOPOLY") for d in log["dev_cards"])
    bought = sum(1 for d in log["dev_cards"] if d["by"] == winner)
    assert log["final"][winner]["vp_cards"] <= bought


def test_decisions_logged_when_asked():
    import json

    from src.agents.agent_a import GreedyAgent
    from src.agents.baselines import RandomAgent
    from src.common.engine import play_game

    log = play_game(GreedyAgent(), RandomAgent(1), seed=5, record_decisions=True)
    assert len(log["decisions"]) == log["num_actions"]
    greedy = [d for d in log["decisions"] if d["player"] == "a" and d["n_options"] > 1]
    assert greedy and all(d["score"] == d["alternatives"][0][1] for d in greedy)
    json.dumps(log)


def test_decision_sampling():
    logs = run_match("greedy", "random", pairs=4, start=99, workers=1, decision_every=100)
    flagged = {g["seed"] for g in logs if "decisions" in g}
    assert flagged == {100}
