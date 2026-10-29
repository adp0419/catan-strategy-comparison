from src.agents.agent_a import WEIGHTS, GreedyAgent
from src.agents.agent_b import StrategicAgent
from src.agents.baselines import RandomAgent, VictoryPointAgent, WeightedRandomAgent

VARIANTS = {
    "strategic": {},
    "strategic_no_lookahead": {"horizon": 0},
    "strategic_no_opp_model": {"opp_model": False},
    "strategic_no_replan": {"replan": False},
    "strategic_placement_only": {"placement_only": True},
    "strategic_no_reactor": {"reactor": False},
}


def strategic(name):
    return lambda seed, **kw: StrategicAgent(name=name, **dict(VARIANTS[name], **kw))


AGENTS = {
    "random": lambda seed, **kw: RandomAgent(seed),
    "weighted_random": lambda seed, **kw: WeightedRandomAgent(seed),
    "victory_point": lambda seed, **kw: VictoryPointAgent(seed),
    "greedy": lambda seed, **kw: GreedyAgent(kw.get("weights")),
    **{name: strategic(name) for name in VARIANTS},
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
    if name in VARIANTS:
        out["config"] = dict(VARIANTS[name], **kw)
    return out
