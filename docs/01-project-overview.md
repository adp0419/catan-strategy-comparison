# 01 Project Overview

## The question

Catan players argue endlessly about whether the game is luck or skill. The usual framing is bad because it conflates two separate things: the variance of dice and board generation, and the value of planning.

This project tests a sharper version of that question:

> Holding the numeric evaluation of the board constant, how much win rate does strategic planning add?

If Agent B beats Agent A by a small margin, the game is dominated by production math and variance. If it beats it by a large margin, planning is where the skill lives.

## Why this framing is defensible

The naive version of this project builds a "luck bot" and a "strategy bot" and compares them. That fails because the two bots would differ in many ways at once, and a win could come from better tuning rather than from strategy.

The control here is that both agents import the same scoring primitives from `src/common/`. Pip counts, production probabilities, port multipliers, and resource scarcity are computed by identical code. The only difference is what each agent does with those numbers:

| | Agent A (Greedy) | Agent B (Strategic) |
|---|---|---|
| Horizon | Current turn | Multi turn plan |
| Objective | Maximize immediate expected value | Advance a chosen archetype toward 10 VP |
| Board reading | Scores individual spots | Scores spots relative to a plan and to the opponent |
| Plan | None | Named archetype, re-evaluated at checkpoints |
| Opponent model | Ignores opponent | Tracks opponent expansion, blocks and robs with intent |

## Hypotheses

**H1.** Agent B beats Agent A at a rate significantly above 50 percent across a large matched sample.

**H2.** The gap is larger on boards with strong archetype potential (a clear ore wheat corner, a good 2:1 port) and smaller on flat boards where no archetype is available.

**H3.** Agent B's advantage comes disproportionately from the settlement placement phase rather than from mid game decisions. Catan is widely believed to be decided at placement, and this is testable here.

**H4 (null worth reporting).** On a meaningful fraction of boards, placement order and dice variance dominate and neither agent's policy matters. Quantifying this fraction is a real result.

## What counts as a result

- Win rate with a confidence interval over a large matched sample
- Elo gap between the two agents and against the baselines
- Win rate split by board archetype potential and by placement order
- Per archetype win rate for Agent B, so "which 1v1 strategies actually work" is an output
- A variance decomposition estimating how much of the outcome is attributable to board and dice versus policy

## Scope boundaries

In scope: 1v1 base game Catan, bank and port trading, robber, development cards, longest road, largest army.

Out of scope for v1: player trading, expansions (Seafarers, Cities and Knights), more than two players, learned value functions, GUI.

Deliberate extensions documented in `08-roadmap.md`: a third and fourth agent archetype, a learned value function trained on the generated logs, and a 3 to 4 player variant where trading comes back.

## Portfolio framing

This reads as an experimental ML and systems project rather than a game bot. The strong framing is: designed a controlled experiment to quantify the contribution of strategic planning versus production math in a stochastic, imperfect information game, with reproducible simulation infrastructure and statistical analysis over thousands of matches.
