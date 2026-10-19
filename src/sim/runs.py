import argparse
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from src.agents.registry import describe, spec_name
from src.common.engine import TURNS_LIMIT, VPS_TO_WIN
from src.sim.match import DECISION_EVERY, report, run_match, summarize
from src.sim.seeds import CHECK_START, EVAL_START, TUNE_END

RUNS_DIR = Path("data/runs")


def git_info():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": True}
    return {"commit": commit, "dirty": dirty}


def seed_band(start, pairs):
    end = start + pairs - 1
    if end <= TUNE_END:
        return "tuning"
    if start >= EVAL_START:
        return "evaluation"
    if start >= CHECK_START and end < EVAL_START:
        return "check"
    return "mixed"


def run_dir(name, root=RUNS_DIR):
    base = f"{datetime.now().strftime('%Y-%m-%d')}_{name}"
    path = root / base
    n = 2
    while path.exists():
        path = root / f"{base}_{n}"
        n += 1
    return path


def run_experiment(name, a_spec, b_spec, pairs, start=EVAL_START, workers=None, decision_every=DECISION_EVERY, root=RUNS_DIR, allow_dirty=False):
    band = seed_band(start, pairs)
    git = git_info()
    if band in ("evaluation", "mixed") and git["dirty"] and not allow_dirty:
        raise RuntimeError("commit your changes first: evaluation runs must map to an exact code version")
    path = run_dir(name, root)
    path.mkdir(parents=True)
    meta = {
        "name": name,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "a": describe(a_spec),
        "b": describe(b_spec),
        "pairs": pairs,
        "games": pairs * 2,
        "seeds": [start, start + pairs - 1],
        "seed_band": band,
        "decision_every": decision_every,
        "git": git,
        "engine": {"catanatron": version("catanatron"), "vps_to_win": VPS_TO_WIN, "turn_limit": TURNS_LIMIT},
        "python": platform.python_version(),
    }
    (path / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    began = time.time()
    logs = run_match(a_spec, b_spec, pairs, start, workers, decision_every)
    with (path / "games.jsonl").open("w") as f:
        for log in logs:
            f.write(json.dumps(log) + "\n")
    res = summarize(logs)
    res["seconds"] = round(time.time() - began, 1)
    (path / "summary.json").write_text(json.dumps(res, indent=2) + "\n")
    return path, res


def load_run(path):
    path = Path(path)
    meta = json.loads((path / "meta.json").read_text())
    with (path / "games.jsonl").open() as f:
        logs = [json.loads(line) for line in f]
    summary = json.loads((path / "summary.json").read_text())
    return meta, logs, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--pairs", type=int, default=100)
    parser.add_argument("--start", type=int, default=EVAL_START)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--decision-every", type=int, default=DECISION_EVERY)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    path, res = run_experiment(args.name, args.a, args.b, args.pairs, args.start, args.workers, args.decision_every, allow_dirty=args.allow_dirty)
    report(args.a, args.b, res, res["seconds"])
    print(f"saved -> {path}")


if __name__ == "__main__":
    main()
