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
