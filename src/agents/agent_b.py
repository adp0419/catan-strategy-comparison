from catanatron.models.enums import ActionType

from src.agents.agent_a import GreedyAgent, with_road
from src.agents.lookahead import HORIZON, TOP_K, Lookahead
from src.agents.planner import REACH, Planner
from src.common.board import road_distance
from src.common.economy import COSTS, can_afford
from src.common.scoring import longest_road_length

MILESTONE_BONUS = 4.0
PLACEMENT_MIX = 0.25

KINDS = {
    ActionType.BUILD_SETTLEMENT: "settlement",
    ActionType.BUILD_CITY: "city",
    ActionType.BUILD_ROAD: "road",
    ActionType.BUY_DEVELOPMENT_CARD: "dev_card",
    ActionType.MARITIME_TRADE: "trade",
    ActionType.MOVE_ROBBER: "robber",
    ActionType.PLAY_KNIGHT_CARD: "knight",
    ActionType.PLAY_ROAD_BUILDING: "road_building",
    ActionType.PLAY_YEAR_OF_PLENTY: "plenty",
    ActionType.PLAY_MONOPOLY: "monopoly",
}

ITEMS = {"settlement": "settlement", "city": "city", "dev_card": "dev_card", "road": "road"}


def after_trade(hand, offer):
    give = [r for r in offer[:4] if r is not None]
    out = dict(hand)
    out[give[0]] -= len(give)
    out[offer[4]] += 1
    return out


def milestone_item(mile):
    if mile.startswith(REACH):
        return "road"
    return ITEMS.get(mile)


class StrategicAgent:
    name = "strategic"

    def __init__(self, replan=True, bonus=MILESTONE_BONUS, mix=PLACEMENT_MIX, horizon=HORIZON, top_k=TOP_K):
        self.base = GreedyAgent()
        self.planner = Planner(replan=replan)
        self.bonus = bonus
        self.mix = mix
        self.look = Lookahead(self, horizon=horizon, top_k=top_k)

    def decide(self, state, actions):
        if len(actions) == 1:
            self.planner.update(state)
            return actions[0]
        scores = self.scores(state, actions)
        return actions[max(range(len(actions)), key=lambda i: scores[i])]

    def scores(self, state, actions):
        arch = self.planner.update(state)
        weights = arch.action_weights(state)
        mile = arch.next_milestone(state)
        cache = {}
        scores = [self.score(state, a, arch, weights, mile, cache) for a in actions]
        return self.look.adjust(state, actions, scores, arch)

    def score(self, state, act, arch, weights, mile, cache):
        kind = KINDS.get(act.action_type)
        base = self.base.score(state, act, cache)
        if kind == "settlement" and state["phase"] == "placement":
            base = (1 - self.mix) * base + self.mix * arch.node_fit(state, act.value)
        val = base * weights[kind] if kind and base > 0 else base
        return val + self.milestone_bonus(state, act, kind, mile)

    def milestone_bonus(self, state, act, kind, mile):
        if state["phase"] != "main" or kind is None:
            return 0.0
        if mile.startswith(REACH):
            node = int(mile[len(REACH):])
            if kind == "settlement" and act.value == node:
                return self.bonus
            if kind == "road":
                now = road_distance(state, "me", node)
                after = road_distance(with_road(state, act.value), "me", node)
                return self.bonus / (1 + after) if after < now else 0.0
            return self.trade_bonus(state, act, kind, "road")
        if kind == mile:
            if kind == "road":
                grows = longest_road_length(state, "me", extra=(act.value,)) > longest_road_length(state, "me")
                return self.bonus if grows else 0.0
            return self.bonus
        return self.trade_bonus(state, act, kind, milestone_item(mile))

    def trade_bonus(self, state, act, kind, item):
        if kind != "trade" or item not in COSTS:
            return 0.0
        hand = state["me"]["hand"]
        if can_afford(hand, item):
            return 0.0
        new = after_trade(hand, act.value)
        if any(v < 0 for v in new.values()):
            return 0.0
        return self.bonus if can_afford(new, item) else 0.0

    def report(self):
        p = self.planner
        return {
            "start": p.history[0]["plan"] if p.history else None,
            "final": p.plan,
            "switches": p.switches,
            "checks": len(p.history),
        }
