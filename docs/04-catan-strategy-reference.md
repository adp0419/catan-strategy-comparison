# 04 Catan Strategy Reference (1v1 adjusted)

This is the knowledge base Agent B draws on. Each archetype has an identity, the board conditions that make it viable, a build order, failure modes, and how 1v1 changes its value relative to a 4 player game.

Important: this file is a reference, not a ruleset. Agent B scores archetypes against the board rather than following a fixed preference order. The relative rankings below are hypotheses the experiment should confirm or refute, and the results section of the project should report which ones held.

## Archetypes are priority orderings, not scripts

An archetype never prescribes a fixed sequence of builds. Catan does not allow one, because what you can build is determined by what the dice gave you. An agent that insists on four settlements before its first city will sit on three ore and two wheat doing nothing, which is strictly worse than upgrading.

So every archetype below specifies a **priority ordering over affordable options**, not a build order. On each turn the agent enumerates what it can actually afford right now and picks the highest priority one. The archetype only changes the ranking.

Concretely, an `Expansion` agent that can afford a city and nothing else builds the city. It does not wait. The difference between `Expansion` and `OreWheatSheep` is not which buildings they construct, it is what they place toward, what they spend surplus on, and which option wins when two are affordable on the same turn.

This also means every archetype needs a tiebreak rule for the common case where nothing in its preferred category is affordable. The default is: take the highest value affordable action available, falling back to a dev card if there is surplus, falling back to banking resources toward the next milestone. Never pass a turn with an affordable useful purchase unspent.

## The 1v1 context

Four structural differences from a 4 player game drive everything below.

1. **No player trading.** A strategy that depends on acquiring an off production resource through trade is dead. Ports replace trading as the only flexibility mechanism.
2. **More open board.** Four initial settlements instead of eight. Expansion space is abundant early, so denial is cheap to ignore and expansion is cheap to pursue.
3. **Robber always hits the opponent.** Every 7 and every Knight is a guaranteed tempo hit, which makes Knights better and makes blocking a key resource devastating.
4. **One competitor for the bonus cards.** Longest road and largest army are two player races, so each is worth contesting rather than conceding.

## Archetype 1: Expansion (settlement spam)

**Identity.** Build settlements as fast as possible. Each settlement is 1 VP plus more production, which compounds.

**Board conditions.** Multiple open high pip nodes within 2 to 3 road segments. Strong wood and brick production. Diverse resources.

**Priority ordering.** Settlement if one is affordable and a good node is reachable. Otherwise road, if that road meaningfully shortens the path to a target node. Otherwise city, if affordable. Otherwise dev card on surplus. The agent expands whenever it can and upgrades whenever it can, it simply breaks ties toward expansion.

The weighting shifts over the game rather than switching phases: as open nodes are claimed, the value of a road falls and the value of a city rises automatically, because road scoring is a function of the value of what it unlocks. No explicit "now switch to cities" rule is needed, and adding one would be a bug.

**Failure modes.** Running out of good spots; wood/brick glut with no wheat or ore to transition to cities; opponent taking the one node the plan depended on; building roads toward nodes that are no longer worth settling.

**1v1 note.** Stronger than in a 4 player game. The open board means expansion rarely gets blocked, and the compounding production advantage is not diluted across three opponents. This is likely the baseline strategy to beat.

## Archetype 2: Ore Wheat Sheep (OWS)

**Identity.** Heavy ore and wheat production feeds city upgrades and a large volume of development cards. Sheep supports dev card purchases. Wins through cities, dev card VPs, and largest army.

**Board conditions.** Strong ore (ideally 6, 8, or two ore hexes), strong wheat, access to sheep or a sheep port. A 2:1 ore or wheat port is a major upgrade.

**Priority ordering.** City if affordable. Otherwise dev card. Otherwise settlement if a node is reachable and adds ore or wheat. Otherwise road only if it reaches such a node. The agent still takes a cheap settlement when one is sitting there; it just does not spend roads chasing one.

**Failure modes.** Low wood and brick means almost no expansion, so the player is capped at their initial nodes plus whatever a single road reaches. If the city upgrades are slow, the plan never gets off the ground. A robber parked on the key ore tile is close to fatal.

**1v1 note.** Weaker than in a 4 player game and this is the most interesting hypothesis in the project. In 4 player Catan, OWS works partly because the player trades away excess ore and because games run long. In 1v1 there is no trading, the board is open, and an expansion opponent can snowball settlements while the OWS player is still upgrading. Expect OWS to underperform here. Verify it rather than assume it.

## Archetype 3: Longest Road / Road Builder

**Identity.** Wood and brick production funds a long continuous road for 2 VP, with settlements placed along the way.

**Board conditions.** Strong wood and brick, a long open corridor of unclaimed edges, access to additional settlement nodes along that corridor.

**Priority ordering.** Settlement if affordable and on the corridor. Otherwise road along the corridor, weighted up when longest road is within reach or contested. Otherwise city. Otherwise dev card on surplus. Roads are weighted higher here than in any other archetype, but a free settlement or an affordable city is still taken.

**Failure modes.** Roads that do not unlock settlements are pure VP with no economy behind them. Losing longest road late is a 2 VP swing in one move.

**1v1 note.** Much stronger than in a 4 player game, because only one opponent can contest it and they must spend 5 plus segments to take it. The road corridor is also rarely cut, since there is only one player who could cut it. This is probably the most underrated 1v1 archetype.

## Archetype 4: Cities and Roads (hybrid)

**Identity.** The practical default. Expand to 3 to 4 settlements early, then convert the best two into cities, and take whichever bonus card is cheaper.

**Board conditions.** Balanced production with at least moderate ore and wheat.

**Priority ordering.** Whatever is affordable, ranked by raw expected value, with a mild tilt toward settlements early and cities late. This is close to Agent A's behavior by construction, which makes it the right fallback when no archetype scores well, and a useful internal control: if Agent B wins mostly while running `CitiesAndRoads`, the archetype layer is adding little.

**Failure modes.** Doing everything mediocrely. Without a clear win condition the plan drifts.

**1v1 note.** Likely the strongest general purpose plan and the natural fallback when no specialized archetype scores well on the board. Agent B should default here.

## Archetype 5: Port Play

**Identity.** Over produce one resource and convert it through a 2:1 port into whatever is needed. Replaces trading.

**Board conditions.** A 2:1 port matching a high pip resource the player owns heavily, ideally two hexes of that resource at 5, 6, 8, or 9.

**Priority ordering.** Standard value ranking, but with the port's trade ratio folded into affordability, so "can I afford this" is evaluated through the 2:1 rather than the 4:1. The archetype mostly changes placement and what counts as affordable, not what gets built.

**Failure modes.** Port nodes are frequently on low pip coastal hexes, so the port is paid for with weak production. A 3:1 generic port is usually not worth a placement by itself.

**1v1 note.** Substantially stronger than in a 4 player game, because ports are the only substitute for the trading that does not happen. A 2:1 on a high pip resource is close to a trading partner that always says yes.

## Archetype 6: Dev Card / Knight Rush

**Identity.** Buy development cards aggressively for largest army, VP cards, and repeated robber control.

**Board conditions.** Ore, wheat, sheep. Overlaps heavily with OWS but prioritizes dev cards over cities.

**Priority ordering.** Dev card whenever affordable. Otherwise city. Otherwise settlement. Roads lowest. Knights played on sight when the robber is not already on the opponent's key tile.

**Failure modes.** Dev card draws are random, so the plan has high variance. Running out of the deck. Spending heavily for VP cards that never come.

**1v1 note.** Stronger than in a 4 player game because every Knight is a guaranteed hit on the only opponent, and permanent robber control on a single key tile can shut down an opponent's archetype entirely. Largest army is also a 2 player race. The variance is real, so this archetype should show a wide outcome distribution.

## General play principles (all archetypes)

These are cross-cutting tactics that apply regardless of which archetype is active. Most belong in Agent B's evaluator or Reactor; a few are shared primitives that Agent A gets too, and those are marked.

### Win-scenario reasoning

Most games are decided by longest road or largest army, since each is 2 VP and neither requires new settlements. The practical rule: if one of the two is clearly out of reach, the other becomes a priority rather than an afterthought.

For Agent B this is a Reactor function. Each turn, estimate the cheapest remaining path to 10 VP for both itself and the opponent, in expected turns. A plan that is slower than the opponent's fastest path is a losing plan, and the agent should switch rather than ride it out.

Longest road is the more stealable of the two, because it can flip in a single turn with Road Building or with banked wood and brick, especially when the holder is sitting at exactly 5 segments. Agent B should track whether the opponent's longest road is "insulated" (long enough that a one turn steal is impossible) and should insulate its own.

### The VP leader is not always the player who is winning

Current VP is a lagging indicator. Production strength, open expansion nodes, and city potential predict the next several turns better than the scoreboard does.

This directly changes robber targeting. A naive agent blocks whoever has the most points; a better one blocks whoever has the strongest long-term position, which early in the game is usually a production lead rather than a VP lead. Implement as: target by projected VP at a horizon of N turns, not by current VP.

### Atomic cut-offs

In the main phase, claiming open settlement nodes is usually more valuable than upgrading, because a new node adds both production and resource and number diversity, while a city only doubles what you already have.

The implementable insight for contested nodes: build every road needed to reach a contested node **in one turn**, not incrementally. Partial roads telegraph the destination and let the opponent race there first, which converts the spend into a road to nowhere. So the rule is: if the agent cannot complete the full path this turn, it should not start it unless the path has value on its own.

This is a real 1v1 tactic and a good test of whether planning beats greed, since Agent A will happily build the first road of a path it can never finish. Make this an explicit logged decision so the ablation can measure it.

The flip side is defensive: track whether the opponent is accumulating enough wood and brick to reach a node you want, and treat an unspent opponent dev card as possibly Road Building when assessing that risk.

### Number diversity, and why it is not just about pips

Two nodes on the same number is worse than two nodes on different numbers of equal probability, even though expected production is identical. Concentrated production means feast or famine: large hands that get caught by a 7, alternating with stretches of nothing.

So the evaluation should penalize number collision on variance grounds, not just count pips. This belongs in `common/` and applies to both agents.

A useful corollary for the primitives: two mid-probability hexes can match one high-probability hex in expected production, so a node's quality is the aggregate, not its best single number.

### Low-probability numbers are better than they look for expansion

The 3 and 11 each come up about 5.6 percent of the time, which is not nothing. They make poor opening placements but reasonable expansion nodes, and they have a hidden advantage: the robber almost never goes on them.

That suggests a real feature worth implementing: **robber-adjusted expected production**. Raw pips overstate the value of a 6 or 8 hex, because those tiles absorb most of the robber's attention over a game. Estimate each hex's expected downtime under robbing and discount accordingly. In 1v1 this effect is amplified, since every robber placement is aimed at the single opponent, so high pip tiles are blocked far more often than in a 4 player game.

This is a shared primitive. Give it to both agents, and consider running it as its own ablation, since it is a numeric refinement rather than a strategic one and would otherwise muddy the attribution.

### Development card timing

Rules concrete enough to implement:

- **Road Building** is worth holding rather than spending immediately. Its highest value uses are completing a cut-off in one turn, or taking longest road unexpectedly. Spend it on plain expansion only when wood and brick production is weak enough that roads are otherwise slow.
- **Year of Plenty** should supply resources the agent produces least. Using it for a resource the agent reliably rolls is wasted value, since that resource arrives on its own.
- **Monopoly** gets stronger as the game progresses, because total production rises as cities come online. Playing it early for a small haul is usually a waste. Combined with hand inference, the rule is: play when estimated opponent holdings of the target resource peak, and bias later rather than earlier.
- **Knight** can be played simply to break a stuck hand, when the agent needs one card to act and the robber is not already well placed. It does not have to be saved for a perfect moment.

### Hand tracking

The article's card-tracking method maps directly onto Agent B's opponent model and is worth copying as the implementation approach: reconstruct the opponent's hand from the recent roll history plus their board position, then subtract what they have visibly spent and what they discarded on a 7.

A rolling window of recent rolls is enough; perfect tracking is not required and not achievable. Note that in 1v1 this is strictly easier than in a 4 player game, since there are no player trades moving cards invisibly between opponents. Agent B's hand inference should therefore be unusually accurate here, which makes Monopoly timing and robber targeting better than they would be at a full table.

### What does not transfer

Worth recording explicitly, since the source material is mostly 4 player and much of its advice is social:

- Bluffing, table presence, negotiation framing, and reading opponents' faces have no analogue with two deterministic agents
- "Avoid being the obvious leader" is a coalition dynamic. With one opponent there is no coalition to provoke, so the usual reason to hide a lead disappears. Hidden VP cards still matter for the opponent's modeling of you, but the political argument does not apply
- Talking opponents out of trades, or steering their opening placements, both presume dialogue that does not exist here

The fact that so much elite Catan advice is social is itself worth a sentence in the write-up: this project measures only the mechanical component of skill, which is a real limitation on how far the results generalize to human play.

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

## On sources for this file

There is no canonical, rigorous writeup of Catan strategy. What exists is three tiers, and only one of them is usable here.

**Tier 1, usable: empirical bot weights.** Catanatron's strongest bots (`AlphaBetaPlayer`, `ValueFunction`) use a hand-crafted value function whose weights were tuned by running large numbers of 1v1 games. That is the closest thing to an evidence-based statement of what matters in two player Catan, and it was derived under exactly the conditions this project runs under. Read that value function before finalizing the feature set in `common/`. Treat it as a reference for which features matter, not as something to copy, since beating a tuned evaluator is partly the point.

**Tier 2, usable with translation: academic work.** There is a small literature on learning Catan strategy, including reinforcement learning of strategy selection and neural network approaches to board evaluation. These are useful for state representation and for how other people decomposed "strategy" into selectable archetypes, which is the same move Agent B makes.

**Tier 2.5, partially usable: competitive player guides.** Tournament-level writeups are more rigorous than general guides, but skew heavily toward the social game: negotiation, bluffing, table presence, and reading opponents. Mine them for the mechanical tactics (robber targeting, dev card timing, cut-off execution, number variance, win-scenario reasoning) and discard the rest. The General play principles section above is drawn from this tier, principally Noah Miller's advanced tactics guide.

**Tier 3, mostly not usable: human strategy guides.** Community guides, wikis, and forum threads are abundant and largely agree on the fundamentals: prioritize wheat and ore, get all five resources, count pips, point your opening road at the best node you can still reach, use a 2:1 port to fix a resource gap. That consensus is already reflected above.

The problem is that essentially all of it assumes three or four players **with trading**, and the advice is frequently downstream of that assumption. "Trade for ore before you hit 5 VP, since opponents stop dealing after that" is sound 4 player advice and meaningless in 1v1. "Don't run the same strategy as someone else at the table" presumes a table. Guides that rank OWS highly are partly ranking its ability to dump surplus ore through trades. Copying a 4 player guide into Agent B would import exactly the assumptions this project is built to test.

So: use human guides for the universal primitives (pip counting, resource diversity, wheat and ore matter, port math) and derive everything 1v1-specific from the simulations instead. The output of this project is closer to being the missing 1v1 writeup than any existing guide is.

## Archetype scoring

Agent B must score each archetype against the board rather than picking one by preference. Each archetype exposes a `viability(state) -> float` computed from the shared primitives: production of the relevant resources, port access, open corridor length, open node count. The highest scoring viable archetype becomes the plan. See `06-agent-b-strategic.md`.