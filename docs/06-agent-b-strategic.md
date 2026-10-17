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

### Failure detection

A plan rarely dies cleanly. It degrades, and the agent needs to notice before it has spent ten turns on something that stopped working. `is_dead` is the hard stop; these are the soft signals that should drive re-evaluation earlier.

Each archetype declares the conditions it depends on, and the Planner monitors them:

- **Target node lost.** The opponent settled a node the plan was routed toward. Severity scales with whether an alternative node of similar value is still reachable.
- **Production choked.** The robber has sat on a key hex for several consecutive turns, or the archetype's core resource is arriving well below its analytic expectation. Compare realized production against `expected_production` over a rolling window; a sustained shortfall means the plan's assumptions no longer hold, whether from robbing or ordinary variance.
- **Milestone stalled.** The agent has not advanced `next_milestone` in N turns. This is the most general signal and catches failures the specific checks miss.
- **Tempo lost.** The opponent's estimated turns-to-10 is now shorter than the agent's. A plan that is on track but slower than the opponent's plan is still a losing plan.
- **Resource dead end.** The plan requires a resource the agent neither produces nor can obtain through an accessible port. Without player trading this is terminal rather than inconvenient, which is why it deserves its own check in 1v1.

Each signal contributes to a degradation score rather than firing independently. One bad signal is noise; a rising score across several is a dying plan. Re-evaluate when the score crosses a threshold, not on every twitch.

### Pivoting

The naive version re-runs `viability` across all archetypes and takes the winner. That is wrong, because viability measures fit to the board and ignores what the agent has already built. A pivot has to be evaluated from the current position, not from scratch.

**Pivot cost.** Score each candidate archetype by its viability minus the cost of getting there from here: assets that become dead weight (roads that lead nowhere under the new plan, nodes placed for production the new plan does not use), plus the expected turns to reach the new plan's first milestone. An archetype that scores highest in the abstract can easily be the worst pivot target.

**Prefer adjacent pivots.** Archetypes that share infrastructure are cheap to move between; ones that do not are close to starting over.

- `Expansion` → `LongestRoad` is nearly free. The roads are already built and already connected; the agent just starts valuing length directly.
- `Expansion` → `CitiesAndRoads` is free. It is a change of emphasis on the same assets.
- `OreWheatSheep` → `DevRush` is cheap. Same production profile, different sink.
- `Expansion` → `OreWheatSheep` is expensive and usually wrong. It needs ore and wheat production the agent did not place for and cannot trade for.
- Anything → `PortPlay` requires a specific port node, so it is only available as a pivot if that node is still reachable.

Encode this as a pivot cost matrix the Planner consults, rather than letting it rediscover the structure every time.

**Partial pivots.** Full archetype switches are not the only option and often not the best one. Usually the right move is to keep the plan and change the win condition: an `OreWheatSheep` agent whose ore is permanently robbed does not need to become an expansion agent, it needs to stop targeting cities and start targeting largest army with what it still produces. Let archetypes expose more than one route to 10 VP and switch route before switching archetype.

**Salvage first.** Before abandoning a plan, check whether a single action repairs it: a Knight to clear a parked robber, Year of Plenty to break a resource dead end, one road to reach a replacement node. A plan that is one action from healthy should be repaired, not replaced. This check runs before pivot evaluation and will usually be the correct answer early in the game.

**Terminal pivots.** Late in the game, with the opponent at 8 or more VP, pivot evaluation stops being about plan quality and becomes a search for the fastest remaining path to 10, accepting a worse position in exchange for speed. The Reactor owns this case; the Planner should hand off rather than keep optimizing.

### Measuring whether pivoting helps

Pivoting is a capability, so it needs its own attribution. `AgentB_noReplan` (archetype fixed at placement) is already in the ablation set and isolates the whole mechanism. Add two logged diagnostics:

- **Pivot outcome rate.** Win rate in games where a pivot occurred versus games where the initial plan held. If pivoting agents lose more, the agent is either pivoting too eagerly or pivoting to the wrong targets, and the degradation threshold or the cost matrix is where to look.
- **Pivot timing.** Turn number of each pivot. Early pivots are usually cheap and correct; late pivots usually mean the failure was detected too slowly, which points back at the detection signals rather than at pivoting itself.

Hold the MVP position: ship the fixed-archetype Planner first, confirm the agent plays sensibly, then layer detection and pivoting on top. Building pivot logic before the base planner works makes it impossible to tell which layer is responsible for bad play.

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