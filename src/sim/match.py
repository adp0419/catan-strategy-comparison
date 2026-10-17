import argparse
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor

from src.agents.registry import make_agent, spec_name
from src.analysis.stats import wilson
from src.common.engine import play_game


def play_pair(job):
    a_spec, b_spec, seed = job
    logs = []
    for swap in (False, True):
        a = make_agent(a_spec, seed * 2)
        b = make_agent(b_spec, seed * 2 + 1)
        logs.append(play_game(a, b, seed, swap_order=swap))
    return logs


def run_match(a_spec, b_spec, pairs, start=1, workers=None):
    jobs = [(a_spec, b_spec, seed) for seed in range(start, start + pairs)]
    workers = workers or os.cpu_count()
    if workers == 1:
        results = map(play_pair, jobs)
    else:
        pool = ProcessPoolExecutor(max_workers=workers)
        results = pool.map(play_pair, jobs, chunksize=max(1, pairs // (workers * 4)))
    logs = [log for pair in results for log in pair]
    if workers != 1:
        pool.shutdown()
    return logs


def summarize(logs):
    done = [g for g in logs if g["winner"]]
    wins = sum(g["winner"] == "a" for g in done)
    first = [g for g in done if g["seat_order"][0] == "a"]
    second = [g for g in done if g["seat_order"][0] == "b"]
    lo, hi = wilson(wins, len(done))
    return {
        "games": len(logs),
        "finished": len(done),
        "a_wins": wins,
        "a_rate": wins / len(done) if done else 0.0,
        "a_ci": (lo, hi),
        "a_rate_first": sum(g["winner"] == "a" for g in first) / len(first) if first else 0.0,
        "a_rate_second": sum(g["winner"] == "a" for g in second) / len(second) if second else 0.0,
        "first_seat_rate": sum(g["winner"] == g["seat_order"][0] for g in done) / len(done) if done else 0.0,
        "median_turns": statistics.median(g["turns"] for g in logs) if logs else 0,
    }


def report(a_spec, b_spec, res, secs):
    lo, hi = res["a_ci"]
    print(f"{spec_name(a_spec)} vs {spec_name(b_spec)}: {res['games']} games ({res['finished']} finished) in {secs:.0f}s")
    print(f"  a wins {res['a_wins']}  rate {res['a_rate']:.3f}  95% CI [{lo:.3f}, {hi:.3f}]")
    print(f"  a rate going first {res['a_rate_first']:.3f}, going second {res['a_rate_second']:.3f}")
    print(f"  first seat wins {res['first_seat_rate']:.3f}, median turns {res['median_turns']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--pairs", type=int, default=100)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    start = time.time()
    logs = run_match(args.a, args.b, args.pairs, args.start, args.workers)
    report(args.a, args.b, summarize(logs), time.time() - start)
    if args.out:
        with open(args.out, "w") as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")


if __name__ == "__main__":
    main()
