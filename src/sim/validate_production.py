import csv
import math
import sys
import time
from collections import Counter
from pathlib import Path

from catanatron.models.enums import ActionType

from src.agents.baselines import RandomAgent
from src.common.board import RESOURCES
from src.common.engine import SEATS, apply, extract_state, legal_actions, new_game
from src.common.probability import expected_production, pips, production_variance


def record_roll(game, choice, tally):
    views = {c: extract_state(game, c) for c in SEATS}
    before = {c: dict(views[c]["me"]["hand"]) for c in SEATS}
    board = views[SEATS[0]]["board"]
    for h in board["hexes"]:
        tally["hex_rolls"][pips(h["number"])] += 1
    tally["robber_rolls"][pips(board["hexes"][views[SEATS[0]]["robber_hex"]]["number"])] += 1
    apply(game, choice)
    for c in SEATS:
        view = views[c]
        exp = expected_production(view, "me")
        after = extract_state(game, c)["me"]["hand"]
        got = {r: after[r] - before[c][r] for r in RESOURCES}
        for r in RESOURCES:
            tally["exp"][r] += exp[r]
            tally["got"][r] += got[r]
            tally["var"][r] += production_variance(view, "me", resource=r)
        tally["sq_dev"] += (sum(got.values()) - sum(exp.values())) ** 2
        tally["var_total"] += production_variance(view, "me")
    tally["rolls"] += 1


def run(games=1000, start=1, turn_limit=1000):
    tally = {
        "exp": Counter(),
        "got": Counter(),
        "var": Counter(),
        "sq_dev": 0.0,
        "var_total": 0.0,
        "rolls": 0,
        "hex_rolls": Counter(),
        "robber_rolls": Counter(),
    }
    for seed in range(start, start + games):
        game = new_game(seed, SEATS if seed % 2 else SEATS[::-1])
        agents = {c: RandomAgent(seed * 13 + i) for i, c in enumerate(SEATS)}
        while game.winning_color() is None and game.state.num_turns < turn_limit:
            color = game.state.current_color()
            choice = agents[color].decide(extract_state(game, color), legal_actions(game))
            if choice.action_type == ActionType.ROLL:
                record_roll(game, choice, tally)
            else:
                apply(game, choice)
    return summarize(tally)


def row(name, exp, got, var):
    return {
        "resource": name,
        "expected": exp,
        "actual": got,
        "diff_pct": 100 * (got - exp) / exp if exp else 0.0,
        "z": (got - exp) / math.sqrt(var) if var else 0.0,
    }


def summarize(tally):
    rows = [row(r, tally["exp"][r], tally["got"][r], tally["var"][r]) for r in RESOURCES]
    rows.append(row("TOTAL", sum(tally["exp"].values()), sum(tally["got"].values()), tally["var_total"]))
    downtime = {p: tally["robber_rolls"][p] / tally["hex_rolls"][p] for p in sorted(tally["hex_rolls"])}
    return {
        "rows": rows,
        "variance_ratio": tally["sq_dev"] / tally["var_total"],
        "rolls": tally["rolls"],
        "downtime": downtime,
    }


def main(games=1000, out="results/production_validation.csv"):
    start = time.time()
    res = run(games)
    path = Path(out)
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(res["rows"][0]))
        writer.writeheader()
        writer.writerows(res["rows"])
    print(f"{games} games, {res['rolls']} rolls, {time.time() - start:.0f}s -> {path}")
    print(f"{'resource':<8} {'expected':>10} {'actual':>8} {'diff %':>7} {'z':>6}")
    for r in res["rows"]:
        print(f"{r['resource']:<8} {r['expected']:>10.1f} {r['actual']:>8} {r['diff_pct']:>7.2f} {r['z']:>6.2f}")
    print(f"variance ratio (observed / predicted): {res['variance_ratio']:.3f}")
    print("robber share of rolls per hex, by pips (random agents):")
    print("  " + "  ".join(f"{p}:{d:.3f}" for p, d in res["downtime"].items()))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
