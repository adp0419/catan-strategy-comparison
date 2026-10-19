# 08 Roadmap

One phase per feature branch. Each phase has a definition of done that must pass before the next starts.

## Phase 0: Engine verification

Branch `phase-0-engine`

- Install `catanatron`, confirm Python 3.11+ environment
- Write `tests/test_engine_assumptions.py` covering every item in `02-engine-and-rules.md`
- Confirm 2 player games run to completion; document the configuration or the workaround
- Build `src/common/engine.py` wrapper: `new_game`, `legal_actions` (player trades filtered), `extract_state`, `play_game`
- Run 100 random vs random games, confirm no crashes and a sane turn count distribution

**Done when:** all assumption tests pass and 100 games complete with logs written.

## Phase 1: Shared primitives

Branch `phase-1-primitives`

- Implement `common/probability.py`, `common/board.py`, `common/economy.py`, `common/scoring.py`, `common/robber.py` per `03-state-representation.md`
- Unit test each against hand computed values on a fixed board fixture
- Verify `expected_production` against empirical production over 1,000 simulated games. If the analytic number and the empirical number disagree, the primitives are wrong

**Done when:** analytic and empirical production match within tolerance.

## Phase 2: Agent A and baselines

Branch `phase-2-agent-a`

- Implement `Random` and `WeightedRandom` baselines
- Implement Agent A per `05-agent-a-greedy.md`
- Tune Agent A weights against the baselines and the engine's built in bot only
- Freeze and record the weights

**Done when:** Agent A beats random above 95 percent and clearly beats Weighted Random and VictoryPoint. The original bar, competitive with the engine's built in bot, was dropped: the base package ships no strong bot, and catanatron's AlphaBeta bots run on a different engine version. **Met:** 1,499 of 1,500 games against the three baselines on reserved seeds; weights frozen in `results/agent_a_weights.json`.

## Phase 3: Simulation infrastructure

Branch `phase-3-sim`

- Matched pair runner with seat swapping and seeded boards
- Parallel execution across cores
- Logging schema from `07-experiment-design.md`, summary records for all games, full decision logs for a sampled subset
- Elo and Wilson confidence interval implementations with unit tests
- Run a 500 pair Agent A versus Agent A sanity check; the win rate must land near 50 percent with seat swapping. If it does not, there is a bug in the runner, not an insight

**Done when:** the runner sanity suite passes (`make sanity`). The original bar, A vs A near 50 percent, was replaced because it cannot fail: Agent A is deterministic, so a seat swapped pair replays the same game mirrored and the rate is exactly 50 percent by construction. **Met** on 300 pairs: mirror 300/300 boards split, labels 600/600 games identical, null 0.472 with CI containing 0.5, positive control CI low 0.994.

## Phase 4: Agent B

Branch `phase-4-agent-b`

- Archetype classes with `viability`, `target_profile`, `next_milestone`, `action_weights`, `is_dead`
- Planner with selection, checkpoints, and switching cost
- Evaluator with plan weighting and milestone bonuses
- Shallow plan-aware lookahead
- Opponent modeling and the Reactor layer
- Ablation variants as separate agent classes

**Done when:** Agent B completes games without plan thrash (switches per game below a set threshold) and beats the random baselines.

## Phase 5: Main experiment

Branch `phase-5-experiment`

- Pilot run, 200 pairs, all matchups
- Power analysis from the pilot effect size
- Main run at the computed sample size
- Full analysis: win rates, Elo, archetype performance, seat advantage, variance decomposition, ablation contributions
- Figures and `results/` csvs

**Done when:** every metric in `07-experiment-design.md` is produced with confidence intervals.

## Phase 6: Write up

Branch `phase-6-writeup`

- README with the question, method, results, and limitations
- The headline chart: win rate with CI, and the variance decomposition
- Honest limitations section

## Extensions (post v1, each its own branch)

**Learned value function.** The Phase 5 run generates tens of thousands of labeled game states. Train a small network (a few hundred thousand parameters, not billions) to predict win probability from the state representation, then use it as the evaluation function for a third agent. Compare against both hand coded agents. This is the natural place for the neural network, once there is data to train it on and two strong baselines to beat.

**MCTS agent.** Catanatron's cheap state copying makes tree search practical. Chance nodes handle dice. This isolates "search" from "strategy" and makes the ablation story complete.

**More archetypes.** Agent C and D exploring other board reading approaches, turning the 2 agent comparison into a ladder.

**3 and 4 player variant.** Reintroduces trading, which is the genuinely hard open problem. Treat as a separate project rather than a feature, since the negotiation agent is a large piece of work on its own.

**Self play RL.** The Gym environment is already there. Realistic only after the hand coded agents define what good looks like.
