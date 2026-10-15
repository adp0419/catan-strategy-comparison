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

Confirmed by `tests/test_engine_assumptions.py`. Re-run the suite whenever the pinned engine version changes.

- **2 players work natively.** No inert seats or workaround needed. Games run to completion and setup follows snake order P1, P2, P2, P1, with only the second settlement paying out.
- **No player trading exists in the engine.** The only trade action is `MARITIME_TRADE` (4:1 bank, 3:1 generic, 2:1 resource port, all verified). The wrapper filter is a safety net, not a requirement.
- **Seat order is decided by the seed.** `State` shuffles players with `random.sample`. The wrapper must force seat order explicitly so matched pair seat swaps actually swap.
- **Discards are random, not chosen.** On a 7, the engine offers a single `DISCARD` action with value `None` and picks the discarded cards at random. Neither agent controls discards. This is symmetric, so it does not bias A vs B, but discard strategy is outside the experiment.
- **All randomness shares Python's global `random` stream.** Dice, dev deck shuffle, steals, discards, and any `random` call an agent makes all draw from it. A `ROLL` action can carry explicit dice (`Action(color, ROLL, (d1, d2))` executed with `validate_action=False`), which is how the wrapper will feed each game an independent seeded dice stream.
- **Dev cards can be played on the turn they are bought.** This deviates from the official rule, so `legal_actions` in `src/common/engine.py` removes any Knight, Year of Plenty, Monopoly, or Road Building play unless the player held that card before the turn started. Victory point cards count immediately on purchase. The engine already enforces one dev card play per turn, and allows a Knight before rolling.
- **Road Building requires road money (engine bug).** The Road Building card is only offered when the player can already afford a road (1 wood, 1 brick), and the free road phase ends early if they cannot. Not yet fixed; `tests/test_engine_assumptions.py::test_road_building_requires_road_money` pins the current behavior.
- **Largest army transfers only when strictly exceeded** (3 to take it, 4 to take it from a holder of 3). Longest road likewise needs 5 and transfers only when strictly beaten.
- **The legal action list is cached.** `state.playable_actions` must be regenerated after any direct state edit (tests only; agents never edit state).
- **No strong built-in bot ships in the base package.** Only `RandomPlayer`, `WeightedRandomPlayer`, and `VictoryPointPlayer` (greedy on immediate VP). The stronger AlphaBeta and value bots live in a separate package. Phase 2's "competitive with the engine's built-in bot" target needs a decision.
- **Not yet covered:** longest road recomputation when a road is cut by an enemy settlement. The engine's cut logic reassigns the holder by max length without re-checking the 5 segment minimum, which is a possible bug worth a dedicated test before any agent depends on it.
