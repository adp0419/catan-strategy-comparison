from catanatron.models.enums import Action, ActionType

from src.agents.agent_a import with_road
from src.agents.archetypes import MAX_CITIES, MAX_ROADS, MAX_SETTLEMENTS, with_settlements
from src.common.board import RESOURCES, buildable_edges, buildable_nodes, port_access
from src.common.economy import COSTS, can_afford_with_trades, missing
from src.common.probability import expected_production
from src.common.robber import expected_discard_loss

HORIZON = 2
TOP_K = 3
DISCOUNT = 0.8
ROLLS_PER_TURN = 2
MAX_BUYS = 3
CARDS_PER_VP = 4

BUILDS = {
    ActionType.BUILD_SETTLEMENT: "settlement",
    ActionType.BUILD_CITY: "city",
    ActionType.BUILD_ROAD: "road",
    ActionType.BUY_DEVELOPMENT_CARD: "dev_card",
}
PLANNABLE = set(BUILDS) | {ActionType.MARITIME_TRADE, ActionType.END_TURN}


def pay(hand, item, ratios):
    cost = COSTS[item]
    short = sum(missing(hand, item).values())
    out = {r: max(0.0, hand[r] - cost.get(r, 0)) for r in RESOURCES}
    for r in sorted(RESOURCES, key=lambda r: (ratios[r], -out[r], RESOURCES.index(r))):
        if short <= 0:
            break
        lots = min(short, int(out[r] // ratios[r]))
        out[r] -= lots * ratios[r]
        short -= lots
    return out


def with_hand(state, hand):
    return dict(state, me=dict(state["me"], hand=hand))


def with_city(state, node):
    me = dict(state["me"])
    me["settlements"] = [n for n in me["settlements"] if n != node]
    me["cities"] = list(me["cities"]) + [node]
    return dict(state, me=me)


def build(state, item, value):
    hand = pay(state["me"]["hand"], item, port_access(state, "me"))
    state = with_hand(state, hand)
    if item == "settlement":
        return with_settlements(state, [value])
    if item == "city":
        return with_city(state, value)
    if item == "road":
        return with_road(state, value)
    return state


def after(state, act):
    kind = act.action_type
    if kind in BUILDS:
        return build(state, BUILDS[kind], act.value)
    if kind == ActionType.MARITIME_TRADE:
        give = [r for r in act.value[:4] if r is not None]
        hand = dict(state["me"]["hand"])
        hand[give[0]] -= len(give)
        hand[act.value[4]] += 1
        return with_hand(state, hand)
    return state


def produce(state):
    prod = expected_production(state, "me")
    hand = {r: state["me"]["hand"][r] + ROLLS_PER_TURN * prod[r] for r in RESOURCES}
    return with_hand(state, hand)


class Lookahead:
    def __init__(self, agent, horizon=HORIZON, top_k=TOP_K, discount=DISCOUNT):
        self.agent = agent
        self.horizon = horizon
        self.top_k = top_k
        self.discount = discount

    def applies(self, state, actions):
        if state["phase"] != "main" or self.horizon <= 0:
            return False
        kinds = {a.action_type for a in actions}
        return ActionType.END_TURN in kinds and kinds <= PLANNABLE

    def adjust(self, state, actions, scores, arch):
        if not self.applies(state, actions):
            return scores
        floor = self.agent.base.w["pass"]
        worth = [i for i in range(len(actions)) if scores[i] > floor]
        order = [i for i in sorted(worth, key=lambda i: -scores[i]) if actions[i].action_type != ActionType.END_TURN]
        out = {}
        for i, act in enumerate(actions):
            if act.action_type == ActionType.END_TURN:
                out[i] = scores[i] + self.future(state, arch, False)
        for i in order[: self.top_k]:
            act = actions[i]
            now = 0.0 if act.action_type == ActionType.MARITIME_TRADE else scores[i]
            out[i] = now + self.future(after(state, act), arch, True)
        low = min(out.values()) - 1
        return [out.get(i, low) for i in range(len(actions))]

    def future(self, state, arch, this_turn):
        total = 0.0
        if this_turn:
            total, state = self.spend(state, arch, 1.0)
        for t in range(1, self.horizon + 1):
            total -= self.discount ** t * self.discard_cost(state)
            state = produce(state)
            val, state = self.spend(state, arch, self.discount ** t)
            total += val
        return total

    def spend(self, state, arch, weight):
        total = 0.0
        for _ in range(MAX_BUYS):
            buy = self.best_buy(state, arch)
            if buy is None:
                break
            val, item, value = buy
            total += weight * val
            state = build(state, item, value)
        return total, state

    def discard_cost(self, state):
        cards = int(sum(state["me"]["hand"].values()))
        return ROLLS_PER_TURN * expected_discard_loss(cards) * self.agent.base.w["vp"] / CARDS_PER_VP

    def options(self, state):
        me = state["me"]
        ratios = port_access(state, "me")
        whole = {r: int(v + 1e-9) for r, v in me["hand"].items()}
        ok = lambda item: can_afford_with_trades(whole, item, ratios)
        out = []
        if ok("city") and len(me["cities"]) < MAX_CITIES:
            out += [(ActionType.BUILD_CITY, n) for n in me["settlements"]]
        if ok("settlement") and len(me["settlements"]) < MAX_SETTLEMENTS:
            out += [(ActionType.BUILD_SETTLEMENT, n) for n in buildable_nodes(state, "me")]
        if ok("road") and len(me["roads"]) < MAX_ROADS:
            out += [(ActionType.BUILD_ROAD, e) for e in buildable_edges(state, "me")]
        if ok("dev_card") and state["dev_deck_remaining"] > 0:
            out.append((ActionType.BUY_DEVELOPMENT_CARD, None))
        return [Action(None, kind, value) for kind, value in out]

    def best_buy(self, state, arch):
        weights = arch.action_weights(state)
        mile = arch.next_milestone(state)
        cache = {}
        best = None
        for act in self.options(state):
            score = self.agent.score(state, act, arch, weights, mile, cache)
            if score > self.agent.base.w["pass"] and (best is None or score > best[0]):
                best = (score, BUILDS[act.action_type], act.value)
        return best
