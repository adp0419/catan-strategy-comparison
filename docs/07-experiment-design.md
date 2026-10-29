# 07 Experiment Design

The experiment is the deliverable. An untested bot is a toy; a controlled comparison with confidence intervals is a result.

## Confounds and controls

| Confound | Control |
|---|---|
| Seat advantage (first vs second placement) | Every board is played twice with seats swapped |
| Board luck | Matched pairs: both agents face the identical board and seed |
| Dice luck | Fixed dice seed per matched pair, so both seat orders see the same roll sequence |
| Tuning bias | Agent A weights frozen before Agent B is written; held out evaluation set never used for tuning |
| Search depth masquerading as strategy | Ablation runs with lookahead disabled |
| Implementation quality | Both agents share `common/` scoring primitives |

## Matched pair protocol

For each seed `s`:

1. Generate board and dice sequence from `s`
2. Game 1: Agent A first, Agent B second
3. Game 2: Agent B first, Agent A second, same board, same dice sequence
4. Record both outcomes as one matched pair

This removes both board variance and seat advantage from the comparison. Report results on pairs, not on individual games.

Note that dice sequence reuse is only approximate, because agents take different actions and the number of rolls diverges. Fix the random stream per game rather than per roll index and document the limitation.

## Sample size

Catan win rates have high variance, so plan for volume.

- Pilot: 200 pairs to shake out bugs and get a rough effect size
- Main run: 2,000 to 5,000 pairs per agent matchup
- Rule of thumb: detecting a 5 percentage point difference from 50 percent at 95 percent confidence needs roughly 1,000 games. A 2 point difference needs roughly 6,000. Compute the actual power from the pilot effect size rather than guessing

Catanatron is fast enough to run thousands of games; parallelize across cores with a per worker seed offset.

## Agents in the tournament

Run a full round robin, not just A versus B. The baselines calibrate whether both agents are any good.

1. `Random` — sanity floor. Both agents should beat this near 100 percent
2. `WeightedRandom` — random weighted by action type, a slightly stronger floor
3. Engine built in bot — external calibration
4. `AgentA` — greedy
5. `AgentB` — strategic
6. `AgentB_noLookahead`
7. `AgentB_noOppModel`
8. `AgentB_noReplan`
9. `AgentB_placementOnly`

If Agent A does not comfortably beat the random baselines, stop and fix Agent A before reading anything into the A vs B result.

## Metrics

**Primary**
- Agent B win rate versus Agent A with a 95 percent confidence interval (Wilson interval, not normal approximation)
- Elo ratings across the full round robin

**Secondary**
- Win rate by seat (first vs second placement) — answers whether 1v1 Catan has a first player advantage
- Agent B win rate by chosen archetype — answers which 1v1 strategies actually work
- Win rate by board archetype potential, bucketed by the max viability score across archetypes — tests H2
- Average game length in turns, by matchup
- Margin of victory (VP difference at game end)
- Plan switch frequency for Agent B

**Variance decomposition**
Estimate how much outcome variance is attributable to board, dice, and policy. A simple approach: for a sample of boards, run each matchup N times with different dice seeds and decompose variance between boards and within boards. The within-board, across-dice variance is irreducible luck; the systematic across-agent difference is skill. This is the most direct quantitative answer to the luck versus strategy question and is the headline result.

## Logging

Every game writes a record:

```
{
  "seed": int, "board_hash": str, "seat_order": [agent, agent],
  "winner": str, "turns": int, "final_vp": {...},
  "agent_b_archetype": str, "archetype_switches": [...],
  "decisions": [{"turn": int, "player": str, "action": ..., "score": float,
                 "alternatives": [...], "plan_state": ...}],
  "production_totals": {...}, "robber_placements": [...], "dev_cards_drawn": [...]
}
```

Full decision logs are large. Log them for a sampled subset (say 1 percent) and log summary records for all games. Store in `data/`, gitignored.

### As implemented (`play_game` in `src/common/engine.py`)

Players are recorded by slot, `"a"` or `"b"`, never by color, so an agent can play itself.

| Field | Contents |
|---|---|
| `seed`, `board_hash`, `agents`, `seat_order` | what was played; `seat_order[0]` placed first |
| `winner`, `turns`, `num_actions` | outcome; `winner` is `None` if the 1,000 turn cap was hit |
| `final_vp`, `final` | per slot VP, settlements, cities, roads, road length, knights, VP cards, bonus card flags |
| `production` | per slot cards received from dice, by resource |
| `robber` | every robber move: turn, mover, hex id, victim, stolen card |
| `dev_cards` | every dev card bought: turn, buyer, card |
| `rolls` | every dice total in order |
| `plans` | only for agents with a `report` method (Agent B): per slot the starting plan, final plan, every switch (turn, from, to, reason), and the number of checkpoints |
| `decisions` | only in sampled games: per decision the turn, player, chosen action, number of options, and for agents with a `scores` method the chosen score and the top 5 alternatives with scores |

`run_match(..., decision_every=100)` records decisions for seeds divisible by 100, so 1 percent of games, chosen by seed so the sample is reproducible. A summary record is about 3 KB; one with decisions is about 25 KB. Agent B's archetype and switches live in `plans`.

### Run folders (`src/sim/runs.py`)

Every experiment run is saved to its own folder, `data/runs/<date>_<name>/`, and is never overwritten (a repeated name gets `_2`, `_3`, ...). Start one with `make run NAME=pilot A=greedy B=random PAIRS=200` or `python -m src.sim.runs`; `load_run(path)` reads one back.

| File | Contents |
|---|---|
| `meta.json` | run name and time; both agents with their full resolved weights; pairs, games, seed range and seed band (`tuning`, `check`, `evaluation`); decision sampling rate; git commit and whether the tree had uncommitted changes; catanatron version, VP target, turn cap; Python version |
| `games.jsonl` | one game record per line, schema above |
| `summary.json` | win rate with Wilson interval, per seat rates, first seat rate, median turns, runtime |

Runs default to the evaluation seeds (1,000,001 onward) and **refuse to start on uncommitted code** there, so every reported number maps to an exact commit. `--allow-dirty` overrides this and the override is recorded in `meta.json`.

### Round robin and Elo (`src/sim/tournament.py`, `src/analysis/elo.py`)

`make tournament NAME=rr AGENTS="greedy victory_point weighted_random random" PAIRS=200` plays every pair of agents on the same seed block, one run folder per matchup inside a tournament folder, and writes `win_rates.csv` (every ordered matchup with games, wins, rate, Wilson interval) and `elo.csv`.

Ratings are a Bradley-Terry maximum likelihood fit, reported on the Elo scale (400 log10) with `random` anchored at 0. Unlike sequential Elo, the fit does not depend on game order. Each matchup gets one prior game split evenly, which keeps ratings finite when one agent wins every game. Standard errors come from 200 bootstrap resamples of each matchup.

**Read perfect records as lower bounds.** When an agent wins every game of a matchup, its rating gap is set by the prior, not by data, and the bootstrap error is too small because every resample is also a sweep. Example from a 150 pair check run: greedy went 900 of 900 and rated +1181, victory_point +98, weighted_random +94. Ratings are informative for competitive matchups such as A vs B.

### Runner sanity checks (`src/sim/sanity.py`, `make sanity`)

Run before every main experiment and after any change to the engine, runner, or agents. Each check can fail, and `tests/test_sanity.py` proves the mirror check catches a planted seat leak.

| Check | Expectation | A failure means |
|---|---|---|
| mirror | greedy vs greedy splits every board 1 to 1, both games on the same board | seat or slot information leaks, or randomness is not controlled |
| labels | greedy vs a reweighted greedy, then the same with slots swapped, gives identical games (winner, turns, dice) with labels flipped | the engine or runner favors slot `a` or a color |
| null | random vs random has a 95 percent interval containing 0.5 | a hidden slot advantage that only shows with stochastic agents |
| positive | greedy vs random has an interval lower bound above 0.9 | the runner cannot detect a real difference |

The null check is statistical, so by design about 1 in 20 seed blocks would fail it by chance. It runs on fixed seeds, so its result is reproducible; rerun on a different `--start` before concluding anything from a single failure.

## Analysis outputs

In `results/`:

- `win_rates.csv` — matchup matrix with CIs
- `elo.csv` — ratings with standard errors
- `archetype_performance.csv` — Agent B archetype win rates and selection frequency
- `seat_advantage.csv`
- `variance_decomposition.csv`
- Figures: win rate with CI by matchup, Elo ladder, archetype win rate bars, win rate versus board archetype potential, ablation contribution chart

## Reporting discipline

- Report the null if it happens. "Strategy added 3 points and most of the outcome was board and dice" is a real finding and a more honest one than a tuned 70 percent
- Report the ablation table so "strategy" is decomposed rather than treated as a black box
- State the limitations explicitly: no player trading, 1v1 only, hand coded evaluators, archetype set chosen by the author
- Do not claim the result generalizes to 4 player Catan. It does not, and saying so is the strongest signal that the experiment was designed carefully
