import argparse
import csv
import itertools
import json
from pathlib import Path

from src.agents.registry import spec_name
from src.analysis.elo import ratings
from src.sim.match import DECISION_EVERY
from src.sim.runs import RUNS_DIR, run_dir, run_experiment
from src.sim.seeds import EVAL_START

ANCHOR = "random"


def win_counts(results):
    wins = {}
    for (a, b), res in results.items():
        wins[(a, b)] = res["a_wins"]
        wins[(b, a)] = res["finished"] - res["a_wins"]
    return wins


def round_robin(name, specs, pairs, start=EVAL_START, workers=None, decision_every=DECISION_EVERY, root=RUNS_DIR, allow_dirty=False):
    path = run_dir(name, root)
    path.mkdir(parents=True)
    names = [spec_name(s) for s in specs]
    results = {}
    for a, b in itertools.combinations(specs, 2):
        key = (spec_name(a), spec_name(b))
        _, res = run_experiment(f"{key[0]}_vs_{key[1]}", a, b, pairs, start, workers, decision_every, root=path, allow_dirty=allow_dirty)
        results[key] = res
        print(f"  {key[0]} vs {key[1]}: {res['a_wins']}/{res['finished']}", flush=True)
    anchor = ANCHOR if ANCHOR in names else None
    elo = ratings(names, win_counts(results), anchor)
    write_tables(path, names, results, elo)
    (path / "tournament.json").write_text(json.dumps({"agents": names, "pairs": pairs, "start": start, "anchor": anchor}, indent=2) + "\n")
    return path, results, elo


def write_tables(path, names, results, elo):
    with (path / "win_rates.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["agent", "opponent", "games", "wins", "rate", "ci_low", "ci_high"])
        for (a, b), res in results.items():
            lo, hi = res["a_ci"]
            n, w = res["finished"], res["a_wins"]
            writer.writerow([a, b, n, w, round(w / n, 4), round(lo, 4), round(hi, 4)])
            writer.writerow([b, a, n, n - w, round((n - w) / n, 4), round(1 - hi, 4), round(1 - lo, 4)])
    with (path / "elo.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["agent", "elo", "se"])
        for k in sorted(names, key=lambda k: -elo[k][0]):
            writer.writerow([k, round(elo[k][0], 1), round(elo[k][1], 1)])


def matrix(names, results):
    rate = {}
    for (a, b), res in results.items():
        rate[(a, b)] = res["a_rate"]
        rate[(b, a)] = 1 - res["a_rate"]
    width = max(len(n) for n in names) + 2
    lines = [" " * width + "".join(f"{n[:8]:>9}" for n in names)]
    for a in names:
        cells = "".join(f"{'-':>9}" if a == b else f"{rate[(a, b)]:>9.3f}" for b in names)
        lines.append(f"{a:<{width}}" + cells)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("agents", nargs="+")
    parser.add_argument("--pairs", type=int, default=100)
    parser.add_argument("--start", type=int, default=EVAL_START)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    path, results, elo = round_robin(args.name, args.agents, args.pairs, args.start, args.workers, allow_dirty=args.allow_dirty)
    print("\nwin rate of row agent against column agent:")
    print(matrix(args.agents, results))
    print("\nelo (random = 0):")
    for k in sorted(args.agents, key=lambda k: -elo[k][0]):
        print(f"  {k:<16} {elo[k][0]:>8.1f}  +/- {elo[k][1]:.1f}")
    print(f"saved -> {path}")


if __name__ == "__main__":
    main()
