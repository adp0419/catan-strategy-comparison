# CLAUDE.md

Project context for Claude Code. Read this first, then the relevant file in `docs/`.

## What this project is

An experiment that tests whether Settlers of Catan is primarily a numbers game or a strategy game.

Two bots play thousands of 1v1 games against each other:

- **Agent A (Greedy)** evaluates every legal action by immediate expected resource value and probability. No plan, no archetype, no lookahead beyond one turn.
- **Agent B (Strategic)** uses the same numeric primitives but commits to a named Catan strategy archetype, evaluates actions by how well they advance that plan, and re-plans when the board changes.

The result is a win rate, an Elo gap, and a breakdown of which archetypes Agent B wins with. That is the deliverable, not a leaderboard bot.

## Core design constraints

1. **1v1 only.** Two players. This is deliberate: it removes player trading, which is the hardest part of Catan AI and almost never happens in heads-up play since any trade helps your only opponent.
2. **Bank trading only.** 4:1 bank, 3:1 generic ports, 2:1 resource ports. No player-to-player trades. Agents must reject any trade offer action if the engine surfaces one.
3. **Both agents share the same primitives.** Pip counting, probability tables, port values, and the production model live in one shared module. If Agent B wins, it must be because of planning, not because it got better math. This is the main experimental control.
4. **No neural network required for v1.** Both agents are deterministic evaluators over hand-written features. A learned value function is a Phase 5 extension, not the starting point.
5. **Everything is seeded and logged.** Every game records its seed, board layout, both agents' decisions, and the final state. The experiment is worthless if it is not reproducible.

## Stack

- Python 3.11+
- `catanatron` for the game engine (pip installable, pure Python, `Player.decide(game, playable_actions)` interface)
- `numpy`, `pandas` for analysis
- `pytest` for engine assumption tests
- `matplotlib` for result plots
- Local Jupyter notebooks for exploratory analysis, not for the agent code

## Repo layout

```
catan-ai/
  CLAUDE.md
  docs/
    01-project-overview.md
    02-engine-and-rules.md
    03-state-representation.md
    04-catan-strategy-reference.md
    05-agent-a-greedy.md
    06-agent-b-strategic.md
    07-experiment-design.md
    08-roadmap.md
  src/
    common/        shared primitives both agents use
    agents/        agent_a.py, agent_b.py, baselines.py
    sim/           tournament runner, logging, seeding
    analysis/      stats, elo, plots
  tests/
  data/            game logs, not committed
  results/         aggregated csvs and figures
```

## Working conventions

- Simple practical variable names. `res` not `result` unless clarity demands it.
- No comments in agent code. The docs carry the explanation.
- Build piece by piece. When adding to a module, show the full accumulated file.
- Feature branches per phase. Do not work on multiple phases in one branch.
- Any claim about Catan rules or Catanatron behavior gets a test in `tests/` before an agent depends on it.

## What not to do

- Do not implement player to player trading.
- Do not give Agent B extra evaluation features that Agent A lacks unless the feature is inherently strategic. Shared numeric features go in `common/`.
- Do not tune Agent B against Agent A and then report the win rate from the same games used for tuning. Hold out a clean evaluation set.
- Do not reach for a neural network to fix a weak agent. Fix the features or the plan logic first.
