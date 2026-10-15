# 04 Catan Strategy Reference (1v1 adjusted)

This is the knowledge base Agent B draws on. Each archetype has an identity, the board conditions that make it viable, a build order, failure modes, and how 1v1 changes its value relative to a 4 player game.

Important: this file is a reference, not a ruleset. Agent B scores archetypes against the board rather than following a fixed preference order. The relative rankings below are hypotheses the experiment should confirm or refute, and the results section of the project should report which ones held.

## The 1v1 context

Four structural differences from a 4 player game drive everything below.

1. **No player trading.** A strategy that depends on acquiring an off production resource through trade is dead. Ports replace trading as the only flexibility mechanism.
2. **More open board.** Four initial settlements instead of eight. Expansion space is abundant early, so denial is cheap to ignore and expansion is cheap to pursue.
3. **Robber always hits the opponent.** Every 7 and every Knight is a guaranteed tempo hit, which makes Knights better and makes blocking a key resource devastating.
4. **One competitor for the bonus cards.** Longest road and largest army are two player races, so each is worth contesting rather than conceding.

## Archetype 1: Expansion (settlement spam)

**Identity.** Build settlements as fast as possible. Each settlement is 1 VP plus more production, which compounds.

**Board conditions.** Multiple open high pip nodes within 2 to 3 road segments. Strong wood and brick production. Diverse resources.

**Build order.** Road, settlement, road, settlement, then convert to cities once nodes run out.

**Failure modes.** Running out of good spots; wood/brick glut with no wheat or ore to transition to cities; opponent taking the one node the plan depended on.

**1v1 note.** Stronger than in a 4 player game. The open board means expansion rarely gets blocked, and the compounding production advantage is not diluted across three opponents. This is likely the baseline strategy to beat.

## Archetype 2: Ore Wheat Sheep (OWS)

**Identity.** Heavy ore and wheat production feeds city upgrades and a large volume of development cards. Sheep supports dev card purchases. Wins through cities, dev card VPs, and largest army.

**Board conditions.** Strong ore (ideally 6, 8, or two ore hexes), strong wheat, access to sheep or a sheep port. A 2:1 ore or wheat port is a major upgrade.

**Build order.** Settle on ore and wheat, upgrade to cities immediately, buy dev cards continuously, take largest army.

**Failure modes.** Low wood and brick means almost no expansion, so the player is capped at their initial nodes plus whatever a single road reaches. If the city upgrades are slow, the plan never gets off the ground. A robber parked on the key ore tile is close to fatal.

**1v1 note.** Weaker than in a 4 player game and this is the most interesting hypothesis in the project. In 4 player Catan, OWS works partly because the player trades away excess ore and because games run long. In 1v1 there is no trading, the board is open, and an expansion opponent can snowball settlements while the OWS player is still upgrading. Expect OWS to underperform here. Verify it rather than assume it.

## Archetype 3: Longest Road / Road Builder

**Identity.** Wood and brick production funds a long continuous road for 2 VP, with settlements placed along the way.

**Board conditions.** Strong wood and brick, a long open corridor of unclaimed edges, access to additional settlement nodes along that corridor.

**Build order.** Expand along a single corridor so roads serve double duty, claim longest road, settle the nodes the roads unlocked.

**Failure modes.** Roads that do not unlock settlements are pure VP with no economy behind them. Losing longest road late is a 2 VP swing in one move.

**1v1 note.** Much stronger than in a 4 player game, because only one opponent can contest it and they must spend 5 plus segments to take it. The road corridor is also rarely cut, since there is only one player who could cut it. This is probably the most underrated 1v1 archetype.

## Archetype 4: Cities and Roads (hybrid)

**Identity.** The practical default. Expand to 3 to 4 settlements early, then convert the best two into cities, and take whichever bonus card is cheaper.

**Board conditions.** Balanced production with at least moderate ore and wheat.

**Build order.** Settlement, settlement, city, city, opportunistic road or dev cards.

**Failure modes.** Doing everything mediocrely. Without a clear win condition the plan drifts.

**1v1 note.** Likely the strongest general purpose plan and the natural fallback when no specialized archetype scores well on the board. Agent B should default here.

## Archetype 5: Port Play

**Identity.** Over produce one resource and convert it through a 2:1 port into whatever is needed. Replaces trading.

**Board conditions.** A 2:1 port matching a high pip resource the player owns heavily, ideally two hexes of that resource at 5, 6, 8, or 9.

**Build order.** Settle the port node and the matching resource hexes, then convert freely.

**Failure modes.** Port nodes are frequently on low pip coastal hexes, so the port is paid for with weak production. A 3:1 generic port is usually not worth a placement by itself.

**1v1 note.** Substantially stronger than in a 4 player game, because ports are the only substitute for the trading that does not happen. A 2:1 on a high pip resource is close to a trading partner that always says yes.

## Archetype 6: Dev Card / Knight Rush

**Identity.** Buy development cards aggressively for largest army, VP cards, and repeated robber control.

**Board conditions.** Ore, wheat, sheep. Overlaps heavily with OWS but prioritizes dev cards over cities.

**Build order.** Minimal infrastructure, continuous dev card purchases, play Knights to keep the robber on the opponent's best tile permanently.

**Failure modes.** Dev card draws are random, so the plan has high variance. Running out of the deck. Spending heavily for VP cards that never come.

**1v1 note.** Stronger than in a 4 player game because every Knight is a guaranteed hit on the only opponent, and permanent robber control on a single key tile can shut down an opponent's archetype entirely. Largest army is also a 2 player race. The variance is real, so this archetype should show a wide outcome distribution.

## Placement principles (all archetypes)

Placement is believed to decide most Catan games, so this is where Agent B should differ most from Agent A.

- **Pip count is the floor, not the ceiling.** A high pip node with two of the same resource is worse than it looks.
- **Resource diversity matters more without trading.** Being cut off from brick in 1v1 means no roads and no settlements, with no trade to rescue it.
- **Wood and brick early, ore and wheat later.** Early game is expansion, late game is cities. A placement with zero wood or brick cannot execute an opening.
- **The 6 and 8 tiles are the backbone.** Each is 5 pips. Two of them on one node is usually the strongest spot on the board.
- **Second settlement should complement the first,** covering missing resources and missing numbers rather than doubling down.
- **Number spread matters.** Two nodes on the same number means feast or famine. Prefer complementary numbers.
- **Road direction at placement is a commitment.** The starting road should point at the best open node reachable in 1 to 2 segments.
- **In 1v1 snake order (P1, P2, P2, P1), player 2 gets the middle two picks.** Whether this is an advantage is an empirical question the experiment should answer directly, and it is a confound that must be controlled by swapping seats.

## Archetype scoring

Agent B must score each archetype against the board rather than picking one by preference. Each archetype exposes a `viability(state) -> float` computed from the shared primitives: production of the relevant resources, port access, open corridor length, open node count. The highest scoring viable archetype becomes the plan. See `06-agent-b-strategic.md`.
