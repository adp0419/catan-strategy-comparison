# 02 Engine and Rules

## Engine choice

Use `catanatron` (bcollazo). Reasons:

- Pure Python implementation of base game Catan logic, pip installable
- Bot interface is a single method: subclass `Player` and implement `decide(self, game, playable_actions)` returning one of the supplied actions
- State is a flat data container rather than a deep object graph, which makes copying cheap for any future search based agent
- Ships a CLI (`catanatron-play`) for bulk simulation with JSON and CSV output, which is exactly the logging path this experiment needs
- Ships a Gymnasium environment, which keeps the Phase 5 learned agent cheap to add

Do not write a Catan engine from scratch. The rules surface is large (robber on 7, discard over 7, longest road recomputation, dev card timing) and bugs there silently corrupt every result.

## Required verification before any agent work

Catanatron is built around 4 player games. Two player support must be confirmed, not assumed. Phase 0 must produce `tests/test_engine_assumptions.py` asserting each of the following, with the test failing loudly if the engine disagrees:

1. A two player game runs to completion and returns a winner
2. Initial placement follows snake order: P1, P2, P2, P1, with the second settlement granting starting resources
3. Bank trading at 4:1 is available; 3:1 and 2:1 ports apply when the player owns the port
4. Rolling a 7 moves the robber and steals; players over 7 cards discard half
5. Longest road requires 5 segments and transfers correctly when broken
6. Largest army requires 3 knights and transfers on 4
7. The development card deck composition matches the base game
8. Victory at 10 points is detected immediately on the triggering action

If the engine does not support 2 players cleanly, the fallback is a 2 player game with 2 inert `RandomPlayer` seats removed from scoring. Prefer fixing the player count properly; document whichever path is taken.

## 1v1 house rules for this project

Standard base game rules with these fixed decisions:

- **Players:** 2
- **Victory condition:** 10 VP (keep standard; do not shorten to 8, since the archetypes under test differ in how fast they reach 10)
- **Player trading:** disabled. If the engine surfaces a trade offer action, both agents must never select it, and the tournament runner must assert that zero player trades occurred per game
- **Bank and ports:** fully enabled. 4:1 bank, 3:1 generic, 2:1 resource
- **Robber:** standard. Note that in 1v1 the robber is strictly more punishing than in a 4 player game, because there is only one target and the blocked tile is always the opponent's best tile
- **Board:** standard 19 hex base board. Randomized layout and number placement per game, seeded
- **Dev cards:** standard deck

## Rule consequences specific to 1v1

These matter for agent design and should be reflected in both evaluators.

- **The robber is a weapon, not a tax.** Every robber placement hits the opponent. A greedy agent that places the robber on the highest pip tile it does not own is already playing near optimally; a strategic agent should consider blocking the opponent's archetype resource instead of their highest pip tile.
- **Longest road is cheap and contested.** With only two players there is one competitor for it. Five road segments is 5 wood and 5 brick, which is often a faster 2 VP than a city.
- **Blocking placement matters more.** With four initial settlements on the board instead of eight, there is far more open space, so denial placements are usually worse than greedy value placements. This is a hypothesis Agent B should be able to test, not an assumption to hardcode.
- **Resource scarcity is sharper.** With no player trading, a player cut off from a resource must rely on ports or dev cards. Monopoly on a resource type is therefore much stronger in 1v1 than in a 4 player game.
- **Development cards are relatively stronger.** They are the only source of resources outside production and bank trades, and the Knight race for largest army is a 2 VP swing with only one opponent contesting it.

## Interfaces the project must own

Even though the engine is external, wrap it. `src/common/engine.py` exposes:

- `new_game(seed) -> Game` with the 1v1 configuration applied
- `legal_actions(game) -> list[Action]` filtered to remove player trade actions
- `extract_state(game) -> dict` producing the project's own state representation (see `03-state-representation.md`)
- `play_game(agent_a, agent_b, seed, swap_order) -> GameLog`

Agents must never touch `catanatron` internals directly. If the engine changes or is replaced, only this wrapper changes.

## Verified engine behavior (catanatron 3.2.1)

Raw engine behavior is pinned in `tests/test_engine_assumptions.py`. The wrapper's corrections are pinned in `tests/test_engine.py`. Re-run both whenever the pinned engine version changes.

### Correct as shipped

- **2 players work natively.** Games run to completion. Setup is snake order P1, P2, P2, P1 and only the second settlement pays out.
- **No player trading exists in the engine.** The only trade action is `MARITIME_TRADE`: 4:1 bank, 3:1 generic, 2:1 resource port, all verified. `legal_actions` also whitelists action types as a safety net.
- **Robber and discards.** A 7 makes every player over 7 cards discard half, then the roller moves the robber and may steal.
- **Bonus cards.** Longest road needs 5 and transfers only when strictly beaten. Largest army needs 3 knights and transfers only when strictly beaten.
- **Dev deck** is the base game 14 / 5 / 2 / 2 / 2. **Victory** at 10 is detected on the triggering action.
- **One dev card play per turn**, and a Knight may be played before rolling.

### Fixed in the wrapper (`src/common/engine.py`)

- **Seat order.** The engine shuffles seats from the seed. `new_game(seed, order)` forces the order after setup, and the board and dev deck depend only on the seed, so a seat swap keeps the identical board.
- **Dev cards played on the turn bought.** `legal_actions` removes Knight, Year of Plenty, Monopoly, and Road Building plays unless the card was held before the turn started. Victory point cards still count immediately.
- **Road Building required road money.** The engine only offered the card when the player could already afford a road, and ended the free road phase early without wood and brick. The wrapper offers the card whenever a free road can be placed and grants both free roads, stopping early only when no road can be placed.
- **Longest road is computed by the wrapper.** The engine had two longest road bugs. After a cut it reassigned the card to the longest remaining road even below 5 and did not remove the 2 VP. It also dropped the last segment of a road built up to an opponent's settlement, and its stored per player road length was never set during placement. After every road or settlement the wrapper now recomputes both players' lengths with `scoring.trail_length` (the same function the agents use) and applies the award rules in `next_road_holder`: the holder keeps the card on ties; anyone else needs a unique longest road of 5 or more; if the holder's own road shrinks, the card goes to a unique leader of 5 or more, otherwise it is set aside.
- **Short bank with one claimant.** When the bank cannot cover everyone owed a resource, the engine pays nobody. The official rule pays a lone claimant whatever the bank has left, which is common in 1v1. The wrapper applies that remainder after each roll.
- **Randomness.** The engine uses Python's global `random` for everything. The wrapper resolves dice from a per game `dice_rng` and steals and discards from a per game `event_rng`, both seeded from the game seed. Agent randomness can no longer shift the dice, so matched pairs see the same roll sequence by roll index.
- **Action order depended on Python's hash seed.** The engine builds several action lists from sets (trades, robber targets, Year of Plenty), so their order changed between processes and the same seed played a different game in every run. `legal_actions` now returns actions sorted by type and value, and `tests/test_engine.py` replays a game under two `PYTHONHASHSEED` values and requires identical logs.
- **Seed 0.** `Game(seed=0)` treats 0 as no seed. `new_game` seeds the global stream first so every seed, including 0, is reproducible.

### Known deviations kept

- **Discards are random, not chosen.** The engine offers one `DISCARD` action and the wrapper picks the cards from `event_rng`. Symmetric for both agents, so it does not bias A vs B.
- **Non knight dev cards can only be played after rolling.** The official rules allow any dev card before the roll. Symmetric; revisit only if it matters.
- **The legal action list is cached** in `state.playable_actions`. Agents only ever see `legal_actions(game)`, and tests that edit state directly must regenerate it.
- **No strong built-in bot ships in the base package.** Only `RandomPlayer`, `WeightedRandomPlayer`, and `VictoryPointPlayer`. The stronger AlphaBeta and value bots live in a separate package. Phase 2's "competitive with the engine's built-in bot" target needs a decision.

## Agent interface

Agents never see a `Game`. Each agent has a `name` and implements `decide(state, actions) -> action`, where `state` is `extract_state(game, color)` and `actions` is `legal_actions(game)`. `play_game(agent_a, agent_b, seed, swap_order)` drives the loop, rejects any action not in the legal list, and returns a log dict with `seed`, `board_hash`, `agents`, `seat_order`, `winner`, `turns`, `final_vp`, `rolls`, and `num_actions`. Slots are `"a"` and `"b"` so an agent can play itself.
