from src.agents.agent_a import WEIGHTS, GreedyAgent
from src.agents.baselines import RandomAgent, VictoryPointAgent, WeightedRandomAgent

AGENTS = {
    "random": lambda seed, **kw: RandomAgent(seed),
    "weighted_random": lambda seed, **kw: WeightedRandomAgent(seed),
    "victory_point": lambda seed, **kw: VictoryPointAgent(seed),
    "greedy": lambda seed, **kw: GreedyAgent(kw.get("weights")),
}


def make_agent(spec, seed):
    name, kw = (spec, {}) if isinstance(spec, str) else spec
    if name not in AGENTS:
        raise ValueError(f"unknown agent {name}, pick from {sorted(AGENTS)}")
    return AGENTS[name](seed, **kw)


def spec_name(spec):
    return spec if isinstance(spec, str) else spec[0]


def describe(spec):
    name, kw = (spec, {}) if isinstance(spec, str) else spec
    out = {"name": name}
    if name == "greedy":
        out["weights"] = dict(WEIGHTS, **(kw.get("weights") or {}))
    return out
