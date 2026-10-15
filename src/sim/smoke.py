import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from src.agents.baselines import RandomAgent
from src.common.engine import play_game


def main(n=100, out="data/smoke_games.jsonl"):
    path = Path(out)
    path.parent.mkdir(exist_ok=True)
    logs = []
    start = time.time()
    with path.open("w") as f:
        for seed in range(1, n + 1):
            log = play_game(RandomAgent(seed), RandomAgent(seed + 10**6), seed, swap_order=seed % 2 == 0)
            f.write(json.dumps(log) + "\n")
            logs.append(log)
    done = [g for g in logs if g["winner"]]
    seats = Counter(g["seat_order"].index(g["winner"]) for g in done)
    turns = [g["turns"] for g in logs]
    print(f"{n} games in {time.time() - start:.1f}s -> {path}")
    print(f"finished {len(done)}/{n}, first seat wins {seats[0]}, second seat wins {seats[1]}")
    print(f"turns median {statistics.median(turns)}, min {min(turns)}, max {max(turns)}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
