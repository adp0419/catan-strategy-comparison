import random

from catanatron.models.enums import ActionType

from src.common.scoring import BONUS_VP, takes_largest_army, takes_longest_road

WEIGHTS = {
    ActionType.BUILD_CITY: 10000,
    ActionType.BUILD_SETTLEMENT: 1000,
    ActionType.BUY_DEVELOPMENT_CARD: 100,
}


class RandomAgent:
    name = "random"

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def decide(self, state, actions):
        return self.rng.choice(actions)


class WeightedRandomAgent:
    name = "weighted_random"

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def decide(self, state, actions):
        weights = [WEIGHTS.get(a.action_type, 1) for a in actions]
        return self.rng.choices(actions, weights=weights)[0]


def vp_gain(state, act):
    kind = act.action_type
    if kind in (ActionType.BUILD_SETTLEMENT, ActionType.BUILD_CITY):
        return 1
    if kind == ActionType.BUILD_ROAD and state["phase"] == "main":
        return BONUS_VP if takes_longest_road(state, act.value) else 0
    if kind == ActionType.PLAY_KNIGHT_CARD:
        return BONUS_VP if takes_largest_army(state) else 0
    return 0


class VictoryPointAgent:
    name = "victory_point"

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def decide(self, state, actions):
        gains = [vp_gain(state, a) for a in actions]
        best = max(gains)
        return self.rng.choice([a for a, g in zip(actions, gains) if g == best])
