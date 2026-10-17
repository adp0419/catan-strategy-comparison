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

All production figures are **per dice roll**. In 1v1 both players' rolls pay out to everyone, so one full round is two rolls. Every function that reads production takes `robber=True` by default, which excludes the hex the robber currently sits on; pass `robber=False` for the structural value.

- `pips(number) -> int`, `roll_prob(number) -> float`
- `node_pips(board, node) -> int` pips over adjacent producing hexes, desert excluded
- `node_production(board, node, robber_hex=None, mult=1) -> dict[resource, float]` cards per roll a building there would produce, for scoring spots not yet owned
- `expected_production(state, player) -> dict[resource, float]` cards per roll by resource
- `production_variance(state, player, extra=None, resource=None) -> float` variance of total cards per roll, or of one resource with `resource=`. This is the number collision measure: two spots on the same number have the same mean as two spots on different numbers of equal probability, but higher variance. `extra={node: mult}` evaluates a hypothetical settlement or city
- `resource_diversity(state, player) -> int` count of distinct resources produced, ignoring the robber
- `resource_roll_prob(state, player, resource) -> float` chance a single roll pays at least one card of that resource
- `prob_of_resource_within(state, player, resource, rolls) -> float`

- `robber_adjusted_production(state, player, downtime) -> dict[resource, float]` long run production discounted by robber downtime, where `downtime` maps a hex's pip count to the share of rolls the robber sits on it (see `04-catan-strategy-reference.md`). An empty table gives plain production with no robber

**Validation.** `python -m src.sim.validate_production` (or `make validate`) compares `expected_production` against the cards actually paid over 1,000 random games. Result: every resource within 0.44 percent across 344,000 rolls with all z scores under 0.9, and observed over predicted variance of 1.003. A 100 game version runs in `tests/test_production_validation.py`.

**Downtime calibration is pending.** Random agents place the robber uniformly (about 1/19 of rolls per hex at every pip count), so their downtime table is meaningless for real play. Calibrate `downtime` from Agent A self play once Agent A's weights are frozen in Phase 2, and use the same frozen table for both agents.

`src/common/board.py`
- `adjacent_hexes(board, node)`, `adjacent_nodes(board, node)`
- `node_ports(board) -> dict[node, port]` port resource or `"3:1"` for every port node
- `distance_rule_ok(state, node)` the no adjacent settlement rule (takes `state`, since buildings live in `me` / `opp`, not `board`)
- `buildable_nodes(state, player)` and `buildable_edges(state, player)`, where `player` is `"me"` or `"opp"`. Placement rules apply when `state["phase"] == "placement"`. Both are checked against the engine's own legal moves in `tests/test_board.py`
- `road_distances(state, player) -> dict[node, int]` and `road_distance(state, player, node)` minimum new roads needed to reach a node. Own roads are free, opponent roads and buildings block, unreachable is `inf`
- `port_access(state, player) -> dict[resource, ratio]` effective trade ratios including 4:1 default

`src/common/economy.py`
- `COSTS` for `road`, `settlement`, `city`, `dev_card`. Any function taking an `item` also accepts a raw cost dict
- `can_afford(hand, item)`, `missing(hand, item)`, `surplus(hand, item)`
- `can_afford_with_trades(hand, item, ratios)` and `trade_plan(hand, item, ratios) -> list[(give, ratio, get)] | None` the bank and port trades that complete a purchase right now, cheapest ratio first, never spending a card the purchase itself needs. This is what Agent A's "trade only to complete a purchase this turn" rule uses
- `effective_hand_value(hand, ratios)` hand value in free choice cards, each card counted as `1 / ratio` of its resource
- `rolls_to_afford(hand, production, item, ratios)` and `turns_to_afford(state, player, item)` expected **rolls** until the item is affordable, counting trades. Fluid approximation: production accrues at its expected rate, trades happen in whole ratio lots. Returns `inf` when unreachable within 500 rolls. `turns_to_afford` only works for `"me"`, since the opponent's hand is hidden; Agent B can call `rolls_to_afford` with an inferred hand

`src/common/scoring.py`
- `victory_points(state, player)` actual VP including hidden VP cards for `"me"`, visible VP for `"opp"` since theirs are hidden
- `visible_victory_points(state, player)` what the other side can see, used for opponent modeling
- `trail_length(edges, blocked)` and `longest_road_length(state, player, extra=())` longest continuous road; an opponent building can end a road but not sit in the middle of it. `extra` scores hypothetical roads. The engine wrapper uses the same function to award longest road
- `army_size(state, player)`
- `LONGEST_ROAD_MIN`, `LARGEST_ARMY_MIN`, `BONUS_VP`

`src/common/robber.py`
- `hex_yield(state, player, hex)` and `robber_damage(state, target, hex)` cards per roll the target loses while the robber blocks that hex
- `can_steal(state, target, hex)`, `steal_ev(state, target, hex=None)` a steal takes exactly one card, so the value is 1 card when the target has a building on the hex and a nonempty hand, else 0
- `steal_odds(hand)` per resource chance of the stolen card, for a known or inferred hand
- `discard_loss(cards)` and `expected_discard_loss(cards)` cards lost to a 7 per roll at a given hand size, so both agents can price hoarding

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
