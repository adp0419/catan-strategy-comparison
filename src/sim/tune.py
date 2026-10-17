import argparse
import csv
import json
import os
import time
from pathlib import Path

from src.agents.agent_a import WEIGHTS
from src.analysis.stats import wilson
from src.sim.match import pair_results, run_match
from src.sim.seeds import TUNE_END, TUNE_START

FIXED = {"pass"}
INT_KEYS = {"reach_depth": (1, 4)}
FACTOR = 2.0
DEFAULT_WORKERS = max(1, (os.cpu_count() or 2) // 2)
NICENESS = 10


def variants(key, val):
    if key in INT_KEYS:
        lo, hi = INT_KEYS[key]
        return [v for v in (val - 1, val + 1) if lo <= v <= hi]
    return [round(val * FACTOR, 4), round(val / FACTOR, 4)]


class SeedBlocks:
    def __init__(self, pairs, start=TUNE_START):
        self.pairs = pairs
        self.next = start

    def take(self):
        start = self.next
        self.next += self.pairs
        if self.next > TUNE_END:
            raise RuntimeError("tuning seed range exhausted")
        return start


def challenge(incumbent, challenger, pairs, start, workers):
    logs = run_match(("greedy", {"weights": challenger}), ("greedy", {"weights": incumbent}), pairs, start, workers)
    wins, losses, splits = pair_results(logs)
    lo, _ = wilson(wins, wins + losses)
    return wins, losses, splits, lo


def save_best(out, best, rows):
    Path(out).write_text(json.dumps({"weights": best, "start": WEIGHTS, "trials": len(rows)}, indent=2) + "\n")


def tune(pairs=300, sweeps=3, workers=DEFAULT_WORKERS, log_path="results/tuning_log.csv", out="results/agent_a_weights.json"):
    best = dict(WEIGHTS)
    blocks = SeedBlocks(pairs)
    rows = []
    path = Path(log_path)
    path.parent.mkdir(exist_ok=True)
    for sweep in range(1, sweeps + 1):
        improved = False
        for key in [k for k in WEIGHTS if k not in FIXED]:
            for val in variants(key, best[key]):
                start = blocks.take()
                cand = dict(best, **{key: val})
                t = time.time()
                wins, losses, splits, lo = challenge(best, cand, pairs, start, workers)
                keep = wins > losses and lo > 0.5
                rows.append({"sweep": sweep, "key": key, "old": best[key], "new": val, "seeds_from": start, "boards_won": wins, "boards_lost": losses, "splits": splits, "ci_low": round(lo, 4), "kept": keep})
                print(f"sweep {sweep} {key}: {best[key]} -> {val}  boards won {wins} lost {losses} split {splits}  low {lo:.3f}  {'KEEP' if keep else '-'}  {time.time() - t:.0f}s", flush=True)
                write_log(path, rows)
                save_best(out, cand if keep else best, rows)
                if keep:
                    best = cand
                    improved = True
                    break
        if not improved:
            break
    return best, rows


def write_log(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=300)
    parser.add_argument("--sweeps", type=int, default=3)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--out", default="results/agent_a_weights.json")
    args = parser.parse_args()
    os.nice(NICENESS)
    start = time.time()
    best, rows = tune(args.pairs, args.sweeps, args.workers, out=args.out)
    save_best(args.out, best, rows)
    print(f"done in {(time.time() - start) / 60:.1f} min, {sum(r['kept'] for r in rows)} changes kept -> {args.out}")
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
