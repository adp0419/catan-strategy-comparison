import argparse
import json
import os
from collections import Counter

from src.sim.match import run_match, summarize
from src.sim.seeds import CHECK_START

BASELINES = ("random", "weighted_random", "victory_point")
BEAT_RANDOM = 0.95
MEAN_SWITCHES = 1.0
MAX_SWITCHES = 4


def check(agent="strategic", pairs=200, start=CHECK_START, workers=None):
    rows = {}
    switches = []
    for opp in BASELINES:
        logs = run_match(agent, opp, pairs, start, workers)
        res = summarize(logs)
        rows[opp] = {"rate": res["a_rate"], "ci": res["a_ci"], "games": res["games"]}
        switches += [len(g["plans"]["a"]["switches"]) for g in logs]
    rows["switches"] = {
        "mean": sum(switches) / len(switches),
        "max": max(switches),
        "spread": dict(sorted(Counter(switches).items())),
    }
    ok = {opp: rows[opp]["ci"][0] > BEAT_RANDOM for opp in ("random", "weighted_random")}
    ok["victory_point"] = rows["victory_point"]["ci"][0] > 0.5
    ok["thrash"] = rows["switches"]["mean"] < MEAN_SWITCHES and rows["switches"]["max"] <= MAX_SWITCHES
    return rows, ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="strategic")
    parser.add_argument("--pairs", type=int, default=200)
    parser.add_argument("--start", type=int, default=CHECK_START)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--out", default="results/agent_b_check.json")
    args = parser.parse_args()
    rows, ok = check(args.agent, args.pairs, args.start, args.workers)
    for opp in BASELINES:
        lo, hi = rows[opp]["ci"]
        print(f"{'PASS' if ok[opp] else 'FAIL'}  vs {opp:<16} {rows[opp]['rate']:.3f}  95% CI [{lo:.3f}, {hi:.3f}]")
    sw = rows["switches"]
    print(f"{'PASS' if ok['thrash'] else 'FAIL'}  plan switches     mean {sw['mean']:.2f}, max {sw['max']}, spread {sw['spread']}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"agent": args.agent, "pairs": args.pairs, "start": args.start, "rows": rows, "ok": ok}, f, indent=2)
    raise SystemExit(0 if all(ok.values()) else 1)


if __name__ == "__main__":
    main()
