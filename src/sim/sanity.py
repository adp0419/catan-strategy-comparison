import argparse

from src.analysis.stats import wilson
from src.sim.match import pair_results, run_match, summarize
from src.sim.seeds import CHECK_START

ALT = ("greedy", {"weights": {"dev": 3.0}})


def mirror_check(pairs, start=CHECK_START, workers=None):
    logs = run_match("greedy", "greedy", pairs, start, workers)
    sweeps_a, sweeps_b, splits = pair_results(logs)
    same_board = all(x["board_hash"] == y["board_hash"] for x, y in zip(logs[::2], logs[1::2]))
    ok = sweeps_a == sweeps_b == 0 and splits == pairs and same_board
    return ok, f"{splits}/{pairs} boards split 1-1, {sweeps_a + sweeps_b} swept, same board per pair: {same_board}"


def label_check(pairs, start=CHECK_START, workers=None):
    first = run_match("greedy", ALT, pairs, start, workers)
    second = run_match(ALT, "greedy", pairs, start, workers)
    bad = 0
    for i in range(0, len(first), 2):
        for x, y in ((first[i], second[i + 1]), (first[i + 1], second[i])):
            flipped = {"a": "b", "b": "a", None: None}[y["winner"]]
            if x["winner"] != flipped or x["turns"] != y["turns"] or x["rolls"] != y["rolls"]:
                bad += 1
    ok = bad == 0
    return ok, f"{len(first) - bad}/{len(first)} games identical after swapping labels and colors"


def null_check(pairs, start=CHECK_START, workers=None):
    res = summarize(run_match("random", "random", pairs, start, workers))
    lo, hi = res["a_ci"]
    ok = lo < 0.5 < hi
    return ok, f"random vs random: a wins {res['a_rate']:.3f}, 95% CI [{lo:.3f}, {hi:.3f}] should contain 0.5"


def positive_check(pairs, start=CHECK_START, workers=None):
    res = summarize(run_match("greedy", "random", pairs, start, workers))
    lo, _ = wilson(res["a_wins"], res["finished"])
    ok = lo > 0.9
    return ok, f"greedy vs random: {res['a_rate']:.3f}, CI low {lo:.3f} should exceed 0.9"


CHECKS = {"mirror": mirror_check, "labels": label_check, "null": null_check, "positive": positive_check}


def run_all(pairs, start=CHECK_START, workers=None):
    results = {name: fn(pairs, start, workers) for name, fn in CHECKS.items()}
    for name, (ok, detail) in results.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name:<9} {detail}", flush=True)
    return all(ok for ok, _ in results.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=300)
    parser.add_argument("--start", type=int, default=CHECK_START)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(0 if run_all(args.pairs, args.start, args.workers) else 1)


if __name__ == "__main__":
    main()
