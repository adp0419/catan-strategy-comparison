# 06 Agent B: Strategic / Archetype

## Design philosophy

Agent B uses the same numeric primitives as Agent A but organizes them around a plan. It reads the board, picks an archetype from `04-catan-strategy-reference.md`, and evaluates every action by how much it advances that archetype toward 10 VP. It also tracks the opponent and will deviate from its plan to block or to race.

The hypothesis is that this planning layer is worth a measurable win rate. Agent B must not be given better numbers than Agent A, only better organization of the same numbers.

## Architecture

Three layers:

```
Planner      picks and maintains the archetype
Evaluator    scores actions relative to the active archetype
Reactor      overrides the plan when the opponent threatens to win or the plan dies
```

## Layer 1: Planner

### Archetype interface

Every archetype implements:

```
viability(state) -> float
target_profile() -> dict        desired production mix and port access
next_milestone(state) -> str    e.g. "upgrade_city", "reach_node_17", "buy_knight"
action_weights(state) -> dict   per action type multipliers
is_dead(state) -> bool
```

Archetypes to implement: `Expansion`, `OreWheatSheep`, `LongestRoad`, `CitiesAndRoads`, `PortPlay`, `DevRush`.

### Plan selection

- **At initial placement:** evaluate all archetypes' `viability` against the board, pick the highest. Placement decisions are then made to serve that archetype. This is the single biggest divergence from Agent A and likely the main source of any win rate gap.
- **Re-evaluation checkpoints:** after initial placement completes, every N turns (start with N=5), and on trigger events (losing a target node, robber parked on a key tile for 3 plus turns, opponent reaching 7 VP).
- **Switching cost:** switching plans wastes tempo, so require the new archetype to beat the current one by a margin before switching. Log every switch; plan thrash is a bug signal.

### Viability scoring

Each archetype computes viability from shared primitives only. Examples:

- `Expansion`: count of open nodes within 3 road segments, weighted by pips, times wood/brick production
- `OreWheatSheep`: ore production plus wheat production, times sheep or sheep port access, divided by a penalty for low wood/brick
- `LongestRoad`: longest open edge corridor length, times wood/brick production, times count of settleable nodes along it
- `PortPlay`: best 2:1 port match, measured as port resource production times port accessibility distance

## Layer 2: Evaluator

Same action types as Agent A, but each score is modulated by the plan.

```
score(state, action) = base_score(state, action) * plan_weight(archetype, action)
                     + milestone_bonus(action, next_milestone)
                     + opponent_term(state, action)
```

- `base_score` reuses Agent A's numeric scoring from `common/`, which keeps the control honest
- `plan_weight` comes from `action_weights`. An `OreWheatSheep` plan weights city upgrades and dev cards up and roads down; a `LongestRoad` plan does the opposite
- `milestone_bonus` strongly rewards the specific next step in the plan, so the agent executes a sequence rather than drifting
- `opponent_term` is Agent B's unique layer, described below

### Multi turn lookahead

Agent B evaluates whether an action advances it toward its milestone, not just its immediate value. Implement as a shallow plan-aware search: for the top K candidate actions, simulate the next 2 to 3 turns with expected production (not sampled dice, to keep it deterministic and cheap) and score the resulting position against the archetype target profile.

Keep K small. The point is planning, not raw search depth. If the agent wins purely because it searches deeper, the result is about search, not strategy. Record search depth as an experimental variable and run an ablation with lookahead disabled, so the contribution of planning versus lookahead can be separated.

## Layer 3: Reactor

Overrides the plan under these conditions:

- **Opponent at 8 plus visible VP:** switch to maximum speed to 10, taking the fastest VP regardless of plan. Contest longest road or largest army if either is a one or two move steal.
- **Opponent archetype detected:** infer the opponent's plan from their placements and builds. Target the robber at the resource their plan depends on rather than their highest pip tile. This is a real 1v1 edge, since the robber always hits them.
- **Plan dead:** `is_dead` triggers immediate re-planning.
- **Monopoly timing:** with opponent hand inference, play monopoly when the estimated holding of a resource peaks, rather than immediately.

## Opponent modeling

Agent B maintains:

- Inferred hand distribution from observed production, bank trades, and discards
- Inferred archetype from the opponent's placements and build pattern
- VP trajectory estimate including likely hidden VP cards, inferred from dev card purchase count

All of this is derived from public information only. The wrapper in `common/engine.py` must enforce that hidden state is never readable, so a modeling bug cannot become cheating.

## Required ablations

Agent B has several capabilities Agent A lacks. To attribute the win rate correctly, run these ablations as separate agents in the tournament:

- B minus lookahead (plan but no multi turn simulation)
- B minus opponent modeling (plan and lookahead, no opponent term)
- B minus re-planning (archetype fixed at placement, never switched)
- B placement only (archetype used for placement, then greedy mid game) — this directly tests H3

The ablation table is one of the strongest results this project can produce, because it decomposes "strategy" into components and measures each one.
