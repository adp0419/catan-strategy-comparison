from catanatron.models.enums import ActionType

from src.common.board import (
    RESOURCES,
    buildable_edges,
    buildable_nodes,
    distance_rule_ok,
    node_ports,
    port_access,
    road_distances,
)
from src.common.economy import COSTS, can_afford, can_afford_with_trades, effective_hand_value, missing
from src.common.probability import expected_production, node_production, number_collision
from src.common.robber import robber_damage, steal_ev
from src.common.scoring import BONUS_VP, longest_road_length, takes_largest_army, takes_longest_road

PIPS_PER_CARD = 36

WEIGHTS = {
    "pips": 1.0,
    "diversity": 3.0,
    "port_generic": 2.0,
    "port_match": 0.4,
    "collision": 1.0,
    "vp": 8.0,
    "city": 1.0,
    "road_reach": 0.6,
    "reach_depth": 2,
    "road_progress": 1.0,
    "dev": 6.0,
    "trade_cost": 4.0,
    "robber_damage": 1.0,
    "robber_self": 1.0,
    "steal": 3.0,
    "knight_relief": 1.0,
    "road_building": 0.8,
    "plenty": 0.9,
    "monopoly": 3.0,
    "monopoly_min": 2.0,
    "pass": 0.01,
}


def pips_of(prod):
    return {r: v * PIPS_PER_CARD for r, v in prod.items()}


def with_road(state, edge):
    me = dict(state["me"], roads=list(state["me"]["roads"]) + [edge])
    return dict(state, me=me)


def hex_by_coord(state, coord):
    return next(h for h in state["board"]["hexes"] if tuple(h["coord"]) == tuple(coord))


class GreedyAgent:
    name = "greedy"

    def __init__(self, weights=None):
        self.w = dict(WEIGHTS, **(weights or {}))

    def decide(self, state, actions):
        if len(actions) == 1:
            return actions[0]
        scores = self.scores(state, actions)
        return actions[max(range(len(actions)), key=lambda i: scores[i])]

    def scores(self, state, actions):
        cache = {}
        return [self.score(state, a, cache) for a in actions]

    def score(self, state, act, cache):
        kind = act.action_type
        if kind == ActionType.BUILD_SETTLEMENT:
            return self.settlement_value(state, act.value) + (self.w["vp"] if state["phase"] == "main" else 0)
        if kind == ActionType.BUILD_CITY:
            return self.city_value(state, act.value)
        if kind == ActionType.BUILD_ROAD:
            return self.road_value(state, act.value, cache)
        if kind == ActionType.BUY_DEVELOPMENT_CARD:
            return self.w["dev"]
        if kind == ActionType.MARITIME_TRADE:
            return self.trade_value(state, act.value, cache)
        if kind == ActionType.MOVE_ROBBER:
            return self.robber_value(state, act.value)
        if kind == ActionType.PLAY_KNIGHT_CARD:
            return self.knight_value(state)
        if kind == ActionType.PLAY_ROAD_BUILDING:
            return self.road_building_value(state, cache)
        if kind == ActionType.PLAY_YEAR_OF_PLENTY:
            return self.plenty_value(state, act.value, cache)
        if kind == ActionType.PLAY_MONOPOLY:
            return self.monopoly_value(state, act.value)
        return self.w["pass"]

    def settlement_value(self, state, node):
        board = state["board"]
        w = self.w
        prod = pips_of(node_production(board, node))
        mine = expected_production(state, "me", robber=False)
        val = w["pips"] * sum(prod.values())
        val += w["diversity"] * sum(1 for r in RESOURCES if prod[r] > 0 and mine[r] == 0)
        port = node_ports(board).get(node)
        if port == "3:1":
            val += w["port_generic"]
        elif port:
            val += w["port_match"] * (mine[port] * PIPS_PER_CARD + prod[port])
        val -= w["collision"] * max(0.0, number_collision(state, "me", node)) * PIPS_PER_CARD
        return val

    def city_value(self, state, node):
        gain = sum(pips_of(node_production(state["board"], node)).values())
        return self.w["city"] * gain + self.w["vp"]

    def reach(self, state):
        dist = road_distances(state, "me")
        best = 0.0
        for node, d in dist.items():
            if d > self.w["reach_depth"] or not distance_rule_ok(state, node):
                continue
            best = max(best, self.settlement_value(state, node) / (1 + d))
        return best

    def road_value(self, state, edge, cache):
        if "reach" not in cache:
            cache["reach"] = self.reach(state)
        hyp = with_road(state, edge)
        val = self.w["road_reach"] * max(0.0, self.reach(hyp) - cache["reach"])
        if state["phase"] == "main":
            if takes_longest_road(state, edge):
                val += BONUS_VP * self.w["vp"]
            else:
                mine = longest_road_length(state, "me")
                new = longest_road_length(hyp, "me")
                if new > mine and new >= 3 and new >= state["opp"]["road_length"] - 1:
                    val += self.w["road_progress"]
        return val

    def item_values(self, state, cache):
        if "items" in cache:
            return cache["items"]
        items = {}
        nodes = buildable_nodes(state, "me")
        if nodes:
            items["settlement"] = max(self.settlement_value(state, n) for n in nodes) + self.w["vp"]
        if state["me"]["settlements"]:
            items["city"] = max(self.city_value(state, n) for n in state["me"]["settlements"])
        edges = buildable_edges(state, "me")
        if edges:
            best = max(self.road_value(state, e, cache) for e in edges)
            if best > self.w["pass"]:
                items["road"] = best
        if state["dev_deck_remaining"] > 0:
            items["dev_card"] = self.w["dev"]
        cache["items"] = items
        return items

    def unlocked(self, state, hand, cache):
        ratios = port_access(state, "me")
        best = 0.0
        for item, val in self.item_values(state, cache).items():
            if can_afford(state["me"]["hand"], item):
                continue
            if can_afford_with_trades(hand, item, ratios):
                best = max(best, val)
        return best

    def trade_value(self, state, offer, cache):
        give = [r for r in offer[:4] if r is not None]
        get = offer[4]
        hand = dict(state["me"]["hand"])
        hand[give[0]] -= len(give)
        hand[get] += 1
        gain = 0.0
        ratios = port_access(state, "me")
        for item, val in self.item_values(state, cache).items():
            if can_afford(state["me"]["hand"], item) or missing(state["me"]["hand"], item)[get] == 0:
                continue
            if COSTS[item].get(give[0], 0) > state["me"]["hand"][give[0]] - len(give):
                continue
            if can_afford_with_trades(hand, item, ratios):
                gain = max(gain, val)
        if gain == 0:
            return 0.0
        loss = effective_hand_value(state["me"]["hand"], ratios) - effective_hand_value(hand, ratios)
        return gain - self.w["trade_cost"] * max(0.0, loss)

    def robber_value(self, state, value):
        coord, victim, _ = value
        h = hex_by_coord(state, coord)
        w = self.w
        val = w["robber_damage"] * robber_damage(state, "opp", h["id"]) * PIPS_PER_CARD
        val -= w["robber_self"] * robber_damage(state, "me", h["id"]) * PIPS_PER_CARD
        if victim is not None:
            val += w["steal"] * steal_ev(state, "opp", h["id"])
        return val

    def knight_value(self, state):
        own = robber_damage(state, "me", state["robber_hex"]) * PIPS_PER_CARD
        val = self.w["knight_relief"] * own
        if takes_largest_army(state):
            val += BONUS_VP * self.w["vp"]
        return val

    def road_building_value(self, state, cache):
        dist = road_distances(state, "me")
        best = 0.0
        for node, d in dist.items():
            if 1 <= d <= 2 and distance_rule_ok(state, node):
                best = max(best, self.settlement_value(state, node))
        return self.w["road_building"] * best

    def plenty_value(self, state, cards, cache):
        hand = dict(state["me"]["hand"])
        for r in cards:
            hand[r] += 1
        return self.w["plenty"] * self.unlocked(state, hand, cache)

    def monopoly_value(self, state, res):
        prod = expected_production(state, "opp", robber=False)
        total = sum(prod.values())
        share = prod[res] / total if total else 1 / len(RESOURCES)
        est = state["opp"]["hand_size"] * share
        if est < self.w["monopoly_min"]:
            return 0.0
        return self.w["monopoly"] * est
