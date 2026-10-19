import json

import pytest

from src.sim.runs import load_run, run_dir, run_experiment, seed_band
from src.sim.seeds import CHECK_START, EVAL_START


def test_seed_band():
    assert seed_band(1, 100) == "tuning"
    assert seed_band(CHECK_START, 100) == "check"
    assert seed_band(EVAL_START, 100) == "evaluation"
    assert seed_band(EVAL_START - 50, 100) == "mixed"


def test_run_saves_and_reloads(tmp_path):
    path, res = run_experiment("t", "greedy", "random", pairs=3, start=CHECK_START, workers=1, decision_every=0, root=tmp_path)
    meta, logs, summary = load_run(path)
    assert meta["games"] == len(logs) == 6
    assert meta["seeds"] == [CHECK_START, CHECK_START + 2]
    assert meta["seed_band"] == "check"
    assert meta["a"]["name"] == "greedy" and "vp" in meta["a"]["weights"]
    assert meta["b"] == {"name": "random"}
    assert len(meta["git"]["commit"]) in (40, 7)
    assert summary["a_wins"] == res["a_wins"]
    json.dumps(meta)


def test_runs_never_overwrite(tmp_path):
    first = run_dir("x", tmp_path)
    first.mkdir()
    second = run_dir("x", tmp_path)
    assert second != first and second.name.endswith("_2")


def test_evaluation_runs_need_clean_code(tmp_path, monkeypatch):
    monkeypatch.setattr("src.sim.runs.git_info", lambda: {"commit": "abc1234", "dirty": True})
    with pytest.raises(RuntimeError):
        run_experiment("t", "greedy", "random", pairs=1, start=EVAL_START, workers=1, root=tmp_path)
    path, _ = run_experiment("t", "greedy", "random", pairs=1, start=EVAL_START, workers=1, root=tmp_path, allow_dirty=True)
    assert json.loads((path / "meta.json").read_text())["git"]["dirty"] is True
