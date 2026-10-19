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
| `decisions` | only in sampled games: per decision the turn, player, chosen action, number of options, and for agents with a `scores` method the chosen score and the top 5 alternatives with scores |

`run_match(..., decision_every=100)` records decisions for seeds divisible by 100, so 1 percent of games, chosen by seed so the sample is reproducible. A summary record is about 3 KB; one with decisions is about 25 KB. `agent_b_archetype` and `archetype_switches` arrive with Agent B.

### Run folders (`src/sim/runs.py`)

Every experiment run is saved to its own folder, `data/runs/<date>_<name>/`, and is never overwritten (a repeated name gets `_2`, `_3`, ...). Start one with `make run NAME=pilot A=greedy B=random PAIRS=200` or `python -m src.sim.runs`; `load_run(path)` reads one back.

| File | Contents |
|---|---|
| `meta.json` | run name and time; both agents with their full resolved weights; pairs, games, seed range and seed band (`tuning`, `check`, `evaluation`); decision sampling rate; git commit and whether the tree had uncommitted changes; catanatron version, VP target, turn cap; Python version |
| `games.jsonl` | one game record per line, schema above |
| `summary.json` | win rate with Wilson interval, per seat rates, first seat rate, median turns, runtime |

Runs default to the evaluation seeds (1,000,001 onward) and **refuse to start on uncommitted code** there, so every reported number maps to an exact commit. `--allow-dirty` overrides this and the override is recorded in `meta.json`.

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
