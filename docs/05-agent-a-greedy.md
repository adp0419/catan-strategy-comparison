# 05 Agent A: Greedy / Numbers

## Design philosophy

Agent A plays the best move available right now, measured in expected resource value and immediate victory points. It has no plan, no archetype, and no model of the opponent. It is not a weak bot. A well tuned greedy evaluator in Catan is genuinely strong, because production compounds and greedy production maximization is a decent proxy for winning.

This matters: if Agent A is a strawman, the experiment proves nothing. The result is only interesting if Agent A is a competent player and Agent B still beats it.

## Decision procedure

```
decide(state, actions):
    return max(actions, key=lambda a: score(state, a))
```

One function, no search, no plan state. Ties broken by a fixed deterministic ordering so games are reproducible.

## Scoring by action type

### Settlement placement (initial and main phase)

```
score = w1 * node_pips
      + w2 * resource_diversity_gain
      + w3 * port_bonus
      - w4 * number_collision_penalty
```

- `node_pips` from `common.probability.node_pips`
- `resource_diversity_gain` counts new resource types this node adds to the player's production
- `port_bonus` nonzero only if the node is a port node, scaled by whether the player produces the matching resource
- `number_collision_penalty` penalizes stacking the same number across owned nodes

Agent A does not consider whether the node fits a plan, whether it blocks the opponent, or what it enables two settlements from now.

### City upgrade

```
score = w5 * expected_production_gain(node)
```

Upgrading doubles production on that node, so the gain is exactly the node's pip value converted to cards per turn, plus 1 VP valued at a fixed constant.

### Road

```
score = w6 * best_reachable_node_value(new_edge) / road_distance
      + w7 * longest_road_progress_if_leading_or_close
```

Agent A builds roads only toward immediate settlement value. It pursues longest road only when it is already at or near the lead, since it has no multi turn plan to build toward it.

### Development card

Fixed expected value constant, tuned so Agent A buys dev cards when it has surplus ore, wheat, and sheep but no affordable building. This prevents the degenerate behavior of hoarding.

### Bank / port trade

Trade only when it completes a purchase this turn. Score equals the score of the purchase it unlocks, minus the value of the resources given up computed through `effective_hand_value`.

### Robber placement

```
score = robber_damage(state, opponent, hex) + steal_ev(state, opponent)
```

Highest pip opponent tile, with a steal expectation bonus. Agent A never considers which resource the opponent's plan depends on, only raw volume.

### Dev card play

- Knight: play when robber is on own territory, or when largest army is within reach
- Road building: play when two roads unlock a settlement
- Year of plenty: play when it completes a purchase this turn
- Monopoly: play on the resource with the highest estimated opponent holding, estimated from the opponent's production only

## Weight tuning

Weights `w1..w7` live in a single config dict. Tune them by running Agent A against the baselines in `07-experiment-design.md`, specifically against random and against the engine's built in bots. Tune Agent A **before** Agent B exists, so the tuning cannot be biased toward making Agent B look good. Freeze the weights and record them in the results.

If weight tuning is doing too much work, consider a small grid search or a simple evolutionary tune over self play, and document it. Do not hand tune against Agent B.

## Explicit non capabilities

These are the design boundary. Agent A must not have:

- Any persistent plan or archetype state between turns
- Any lookahead beyond evaluating the immediate action
- Any opponent hand inference
- Any blocking or denial logic beyond the robber
- Any awareness of the opponent's victory point trajectory

If any of these creep in, Agent A stops being the control and the experiment is invalid.


## Implementation (`src/agents/agent_a.py`)

`GreedyAgent(weights=None)` scores every legal action and returns the highest. Ties go to the first action in `legal_actions` order, which is sorted, so play is deterministic. The agent stores only its weight dict; anything computed during a decision lives in a per call cache and is discarded, which `tests/test_agent_a.py` enforces.

**One currency.** Every score is in pips, where 36 pips is one card per roll. Production gains are converted with `PIPS_PER_CARD`; a VP is worth `vp` pips. This keeps the weights comparable across action types.

**How each action is scored**, all from `common/`:

| Action | Score |
|---|---|
| Settlement | pips of the node, plus `diversity` per new resource, plus a port bonus (`port_generic` for 3:1, `port_match` times matching production for 2:1), minus `collision` times the number collision covariance; plus `vp` in the main phase |
| City | `city` times the node's production gain, plus `vp` |
| Road | `road_reach` times the improvement in best reachable settlement value (node value divided by 1 + roads needed, within `reach_depth`); plus `2 * vp` if it takes longest road, or `road_progress` if it extends a road that is at least 3 and close to the opponent's |
| Dev card | flat `dev` |
| Bank or port trade | only nonzero when the trade makes a not yet affordable item affordable this turn without selling a card that item needs; then the item's value minus `trade_cost` times the drop in `effective_hand_value` |
| Robber | damage to the opponent, minus damage to self, plus `steal` if the move steals |
| Knight | `knight_relief` times the robber's damage to self, plus `2 * vp` if it takes largest army |
| Road Building | `road_building` times the best settlement reachable within 2 roads |
| Year of Plenty | `plenty` times the best item it makes affordable |
| Monopoly | `monopoly` times the estimated opponent holding (hand size times their production share), only above `monopoly_min` |
| Roll, end turn, discard | `pass`, a small positive constant, so zero value actions never beat passing |

**Additions beyond the original spec.** Robber placement subtracts damage to self, so A never parks the robber on its own hex. Number collision is measured as the covariance between existing production and the new node (`probability.number_collision`), which is positive exactly when they share numbers. Both are shared numeric primitives, not planning.

**Untuned baseline result.** With the starting weights, A won 100 of 100 against Random, Weighted Random, and VictoryPoint (seat swapped every other game), with a median game of 68 turns. In self play over 100 games the winner's VP came from settlements 3.0, cities 2.8, VP cards 1.7, largest army 1.4, longest road 1.2. A buys about 13 dev cards per game and builds under 2 cities, which tuning should look at.


## Tuning and freeze (Phase 2 result)

**Method.** Coordinate ascent by self play (`src/sim/tune.py`). Each trial doubles or halves one weight and plays the changed agent against the current one on 600 fresh boards from the tuning range (seeds 1 to 900,000), both seat orders per board. Most boards split 1 to 1 because two nearly identical deterministic agents mirror each other, so a trial is judged only on boards one side won in both seats: a change is kept when it wins more such boards and the Wilson lower bound of its share is above 0.5. Every trial is in `results/tuning_log.csv`.

**Result.** One full sweep of 40 trials, 24,000 games, kept no change, so the starting weights are a local optimum under doubling and halving and were frozen as is. Changes to `pips`, `diversity`, `dev`, `trade_cost`, and `collision` moved dozens of boards, always in the incumbent's favor. Changes to `city`, `steal`, `knight_relief`, `road_building`, `plenty`, and `monopoly` changed no decisions at all at these values, because another rule always outranks them where they would apply.

**Frozen weights** are recorded in `results/agent_a_weights.json`. `tests/test_agent_a.py::test_weights_are_frozen` fails if `WEIGHTS` in `agent_a.py` ever diverges from that file. Agent B did not exist when they were frozen.

**Check on reserved seeds** (900,001 onward, never used for tuning), 500 games each with seats swapped: 500 / 500 against Random, 499 / 500 against Weighted Random, 500 / 500 against VictoryPoint.
