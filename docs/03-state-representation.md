# 03 State Representation and Shared Primitives

Everything in this file lives in `src/common/`. Both agents import from here. This module is the experimental control, so changes to it affect both agents equally and must be noted in the changelog.

## Board model

The Catan board is a graph, not a grid. Represent it as:

- **Hexes:** 19 tiles, each with a resource type (brick, wood, sheep, wheat, ore, desert) and a number token (2 to 12, no 7)
- **Nodes (intersections):** 54 vertices, each adjacent to 1 to 3 hexes. Settlements and cities sit here
- **Edges:** 72 connections between nodes. Roads sit here
- **Ports:** 9, attached to specific node pairs. 4 generic 3:1, 5 resource specific 2:1

The board layout is randomized per game, so no agent may hardcode node indices or assume a fixed layout. All evaluation must be computed from the graph.

## Probability primitives

```
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
```

Probability of a number on one roll is `PIPS[n] / 36`.

**Node pip value:** sum of `PIPS[n]` over adjacent producing hexes. A settlement produces 1 card per pip event, a city produces 2.

**Expected cards per turn** for a player is the sum over owned nodes of `multiplier * PIPS[hex] / 36` across adjacent hexes, where multiplier is 1 for settlement and 2 for city. This is the single most important number in the project and both agents use the identical implementation.

## Required shared functions

`src/common/probability.py`
- `pips(number) -> int`
- `node_pips(board, node) -> int`
- `expected_production(state, player) -> dict[resource, float]` cards per turn by resource
- `resource_diversity(state, player) -> int` count of distinct resources produced
- `prob_of_resource_within(state, player, resource, turns) -> float`

`src/common/board.py`
- `adjacent_hexes(board, node)`
- `adjacent_nodes(board, node)`
- `distance_rule_ok(board, node)` the no adjacent settlement rule
- `buildable_nodes(state, player)`
- `buildable_edges(state, player)`
- `road_distance(state, player, node)` minimum roads needed to reach a node
- `port_access(state, player) -> dict[resource, ratio]` effective trade ratios including 4:1 default

`src/common/economy.py`
- `COSTS` for road, settlement, city, dev card
- `can_afford(hand, item)`
- `turns_to_afford(state, player, item) -> float` expected turns given current production and port ratios
- `effective_hand_value(hand, ratios)` hand value normalized through best available trade ratios

`src/common/scoring.py`
- `victory_points(state, player)` including hidden VP cards for self only
- `visible_victory_points(state, player)` what the opponent can see, used for opponent modeling
- `longest_road_length(state, player)`
- `army_size(state, player)`

`src/common/robber.py`
- `robber_damage(state, target, hex)` expected cards per turn denied by blocking a hex
- `steal_ev(state, target)` expected value of a steal given the target's hand size

## Project state dict

`extract_state(game)` returns a plain dict so agents never depend on engine internals:

```
{
  "turn": int,
  "phase": "placement" | "main",
  "board": {"hexes": [...], "nodes": [...], "edges": [...], "ports": [...]},
  "robber_hex": int,
  "me": {"hand": {...}, "settlements": [...], "cities": [...], "roads": [...],
         "dev_cards": {...}, "knights_played": int, "vp": int, "ports": [...]},
  "opp": {"hand_size": int, "settlements": [...], "cities": [...], "roads": [...],
          "dev_cards_count": int, "knights_played": int, "visible_vp": int, "ports": [...]},
  "bank": {...},
  "dev_deck_remaining": int,
  "longest_road_holder": str | None,
  "largest_army_holder": str | None
}
```

Note the asymmetry on `opp`: the opponent's hand contents and unplayed dev cards are hidden. Agents may track an inferred distribution over the opponent's hand, but must not read the true values. Enforce this in the wrapper, not by convention, so a bug cannot leak information.

## Opponent hand inference (optional, Agent B only)

Agent B may maintain a belief over the opponent's hand by tracking production events, known bank trades, and discards. This is strategic reasoning rather than a numeric primitive, so it lives in the agent, not in `common/`. Document it clearly as a capability Agent A lacks by design, since it is inherently a planning feature.
