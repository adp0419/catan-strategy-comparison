import random


class RandomAgent:
    name = "random"

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def decide(self, state, actions):
        return self.rng.choice(actions)
