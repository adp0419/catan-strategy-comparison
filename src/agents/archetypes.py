from src.agents.agent_a import PIPS_PER_CARD
from src.common.board import RESOURCES, buildable_edges, buildable_nodes, buildings, distance_rule_ok, node_ports, road_distances
from src.common.probability import expected_production, node_pips
from src.common.scoring import longest_road_length

OPENING_SETTLEMENTS = 2
MAX_SETTLEMENTS = 5
MAX_CITIES = 4
MAX_ROADS = 15
DEV_DECK = 25
NEED_FLOOR = 0.4
MATCH_POWER = 1
SPACE_DEPTH = 3
SPACE_TOP = 3
SPACE_FULL = 27
CORRIDOR_DEPTH = 5
CORRIDOR_NODES = 12
CORRIDOR_SPOTS = 3
PORT_SURPLUS = 8
ROAD_LEAD_SAFE = 2
ROAD_DEFICIT_DEAD = 4
EXPAND_TARGET = 4
BALANCED = {r: 1.0 for r in RESOURCES}
ACTIONS = ("settlement", "city", "road", "dev_card", "trade", "robber", "knight", "road_building", "plenty", "monopoly")


def need(pips, resources, amount):
    have = sum(pips[r] for r in resources)
    return NEED_FLOOR + (1 - NEED_FLOOR) * min(1.0, have / amount)


def match(pips, profile):
    dot = sum(profile.get(r, 0.0) * pips[r] for r in RESOURCES)
    a = sum(pips[r] ** 2 for r in RESOURCES) ** 0.5
    b = sum(profile.get(r, 0.0) ** 2 for r in RESOURCES) ** 0.5
    return dot / (a * b) if a and b else 0.0


def fit(pips, profile):
    base = match(pips, BALANCED)
    if not base:
        return 0.0
    return sum(pips.values()) * (match(pips, profile) / base) ** MATCH_POWER


def production_pips(state):
    return {r: v * PIPS_PER_CARD for r, v in expected_production(state, "me", robber=False).items()}


def with_settlements(state, nodes):
    me = dict(state["me"], settlements=list(state["me"]["settlements"]) + list(nodes))
    return dict(state, me=me)


def placements_left(state):
    if state["phase"] != "placement":
        return 0
    return max(0, OPENING_SETTLEMENTS - len(state["me"]["settlements"]))


def owned_ports(state):
    ports = node_ports(state["board"])
    return {ports[n] for n in buildings(state, "me") if n in ports}


def spots(state, depth):
    dist = road_distances(state, "me")
    return [(n, d) for n, d in dist.items() if d <= depth and distance_rule_ok(state, n)]


def best_spot(state, depth, value=None):
    value = value or (lambda n: node_pips(state["board"], n))
    cands = spots(state, depth)
    if not cands:
        return None, None
    node, d = max(cands, key=lambda c: (value(c[0]) / (1 + c[1]), -c[0]))
    return node, d


def space(state):
    vals = sorted((node_pips(state["board"], n) for n, _ in spots(state, SPACE_DEPTH)), reverse=True)
    return min(1.0, sum(vals[:SPACE_TOP]) / SPACE_FULL)


def corridor(state):
    reach = [(n, d) for n, d in road_distances(state, "me").items() if 1 <= d <= CORRIDOR_DEPTH]
    settle = [n for n, _ in reach if distance_rule_ok(state, n)]
    return 0.5 * min(1.0, len(reach) / CORRIDOR_NODES) + 0.5 * min(1.0, len(settle) / CORRIDOR_SPOTS)


def road_deficit(state):
    return state["opp"]["road_length"] - longest_road_length(state, "me")


def can_upgrade(state):
    return bool(state["me"]["settlements"]) and len(state["me"]["cities"]) < MAX_CITIES


def can_settle(state):
    return len(state["me"]["settlements"]) < MAX_SETTLEMENTS


def roads_left(state):
    return MAX_ROADS - len(state["me"]["roads"])


def expand_milestone(state, depth=SPACE_DEPTH):
    if not can_settle(state):
        return None
    if state["phase"] == "main" and buildable_nodes(state, "me"):
        return "settlement"
    if roads_left(state) == 0:
        return None
    node, _ = best_spot(state, depth)
    return f"reach_node_{node}" if node is not None else None


class Archetype:
    name = ""
    profile = {}
    weights = {}

    def target_profile(self, state=None):
        return dict(self.profile)

    def score(self, state, pips):
        raise NotImplementedError

    def value_of(self, state):
        return self.score(state, production_pips(state))

    def node_fit(self, state, node):
        return self.value_of(with_settlements(state, [node]))

    def projected(self, state):
        hyp = state
        for _ in range(placements_left(state)):
            nodes = buildable_nodes(hyp, "me")
            if not nodes:
                break
            best = max(nodes, key=lambda n: (self.node_fit(hyp, n), -n))
            hyp = with_settlements(hyp, [best])
        return hyp

    def viability(self, state):
        return self.value_of(self.projected(state))

    def action_weights(self, state):
        return {a: self.weights.get(a, 1.0) for a in ACTIONS}

    def next_milestone(self, state):
        if state["phase"] == "placement":
            return "settlement"
        return self.milestone(state) or "dev_card"

    def milestone(self, state):
        return expand_milestone(state) or ("city" if can_upgrade(state) else None)

    def is_dead(self, state):
        return False


class Expansion(Archetype):
    name = "expansion"
    profile = {"WOOD": 1.5, "BRICK": 1.5, "SHEEP": 0.9, "WHEAT": 0.9, "ORE": 0.2}
    weights = {"settlement": 1.4, "road": 1.3, "city": 0.9, "dev_card": 0.7}

    def score(self, state, pips):
        val = fit(pips, self.profile) * need(pips, ["WOOD"], 4) * need(pips, ["BRICK"], 4)
        return val * (0.5 + 0.5 * space(state))

    def is_dead(self, state):
        if state["phase"] != "main":
            return False
        return not can_settle(state) or expand_milestone(state) is None


class OreWheatSheep(Archetype):
    name = "ore_wheat_sheep"
    profile = {"ORE": 1.6, "WHEAT": 1.6, "SHEEP": 1.0, "WOOD": 0.4, "BRICK": 0.4}
    weights = {"city": 1.5, "dev_card": 1.3, "knight": 1.2, "monopoly": 1.1, "settlement": 0.9, "road": 0.6}

    def score(self, state, pips):
        sheep = 1.0 if "SHEEP" in owned_ports(state) else need(pips, ["SHEEP"], 3)
        val = fit(pips, self.profile) * need(pips, ["ORE"], 4) * need(pips, ["WHEAT"], 4) * sheep
        return val * (0.9 + 0.1 * min(1.0, (pips["WOOD"] + pips["BRICK"]) / 6))

    def milestone(self, state):
        if can_upgrade(state):
            return "city"
        if state["phase"] == "main" and can_settle(state) and buildable_nodes(state, "me"):
            return "settlement"
        return None

    def is_dead(self, state):
        if state["phase"] != "main":
            return False
        pips = production_pips(state)
        return pips["ORE"] == 0 or pips["WHEAT"] == 0


class LongestRoad(Archetype):
    name = "longest_road"
    profile = {"WOOD": 1.8, "BRICK": 1.8, "SHEEP": 0.5, "WHEAT": 0.5, "ORE": 0.4}
    weights = {"road": 1.8, "road_building": 1.5, "settlement": 1.2, "city": 0.9, "dev_card": 0.7}

    def score(self, state, pips):
        val = fit(pips, self.profile) * need(pips, ["WOOD"], 5) * need(pips, ["BRICK"], 5)
        val *= 0.4 + 0.6 * corridor(state)
        return val * (0.5 if road_deficit(state) >= ROAD_DEFICIT_DEAD else 1.0)

    def milestone(self, state):
        if state["phase"] == "main" and can_settle(state) and buildable_nodes(state, "me"):
            return "settlement"
        lead = longest_road_length(state, "me") - state["opp"]["road_length"]
        if roads_left(state) > 0 and (state["longest_road_holder"] != "me" or lead < ROAD_LEAD_SAFE):
            return "road"
        return "city" if can_upgrade(state) else None

    def is_dead(self, state):
        if state["phase"] != "main" or state["longest_road_holder"] == "me":
            return False
        if roads_left(state) == 0 or not buildable_edges(state, "me"):
            return True
        return road_deficit(state) >= roads_left(state)


class CitiesAndRoads(Archetype):
    name = "cities_and_roads"
    profile = BALANCED

    def score(self, state, pips):
        diversity = sum(1 for r in RESOURCES if pips[r] > 0)
        return sum(pips.values()) * (0.75 + 0.05 * diversity) * need(pips, ["ORE", "WHEAT"], 6)

    def action_weights(self, state):
        early = len(buildings(state, "me")) < EXPAND_TARGET
        out = super().action_weights(state)
        out["settlement"] = 1.1 if early else 1.0
        out["city"] = 1.0 if early else 1.1
        return out

    def milestone(self, state):
        if len(buildings(state, "me")) < EXPAND_TARGET:
            return expand_milestone(state) or ("city" if can_upgrade(state) else None)
        return "city" if can_upgrade(state) else expand_milestone(state)


class PortPlay(Archetype):
    name = "port_play"
    weights = {"trade": 1.3, "settlement": 1.2}

    def port_nodes(self, state, res):
        return [n for n, p in node_ports(state["board"]).items() if p == res]

    def access(self, state, res):
        if res in owned_ports(state):
            return 1.0
        dist = dict(spots(state, SPACE_DEPTH))
        best = min((dist[n] for n in self.port_nodes(state, res) if n in dist), default=None)
        return 0.0 if best is None else 1 / (1 + best)

    def port_profile(self, res):
        return {r: 2.0 if r == res else 0.75 for r in RESOURCES}

    def score_for(self, state, pips, res):
        return fit(pips, self.port_profile(res)) * min(1.0, pips[res] / PORT_SURPLUS) * self.access(state, res)

    def resources(self, state):
        return sorted({p for p in node_ports(state["board"]).values() if p in RESOURCES})

    def score(self, state, pips):
        return max((self.score_for(state, pips, r) for r in self.resources(state)), default=0.0)

    def target(self, state):
        pips = production_pips(state)
        best = max(self.resources(state), key=lambda r: (self.score_for(state, pips, r), r), default=None)
        if best is None or self.score_for(state, pips, best) == 0:
            return None
        return best

    def target_profile(self, state=None):
        res = self.target(state) if state else None
        return self.port_profile(res) if res else dict(BALANCED)

    def milestone(self, state):
        res = self.target(state)
        if res and res not in owned_ports(state) and can_settle(state):
            value = lambda n: 1.0 if n in self.port_nodes(state, res) else 0.0
            node, d = best_spot(state, SPACE_DEPTH, value)
            if node is not None and value(node):
                return "settlement" if d == 0 else f"reach_node_{node}"
        return super().milestone(state)

    def is_dead(self, state):
        return state["phase"] == "main" and self.target(state) is None


class DevRush(Archetype):
    name = "dev_rush"
    profile = {"ORE": 1.5, "WHEAT": 1.3, "SHEEP": 1.5, "WOOD": 0.35, "BRICK": 0.35}
    weights = {"dev_card": 1.8, "knight": 1.4, "city": 1.1, "settlement": 0.9, "road": 0.5}

    def score(self, state, pips):
        val = fit(pips, self.profile) * need(pips, ["ORE"], 4) * need(pips, ["WHEAT"], 4) * need(pips, ["SHEEP"], 4)
        return val * state["dev_deck_remaining"] / DEV_DECK

    def milestone(self, state):
        if state["dev_deck_remaining"] > 0:
            return "dev_card"
        return "city" if can_upgrade(state) else None

    def is_dead(self, state):
        return state["phase"] == "main" and state["dev_deck_remaining"] == 0


ARCHETYPES = (Expansion, OreWheatSheep, LongestRoad, CitiesAndRoads, PortPlay, DevRush)
DEFAULT = CitiesAndRoads.name


def all_archetypes():
    return [cls() for cls in ARCHETYPES]


def by_name(name):
    return next(cls() for cls in ARCHETYPES if cls.name == name)


def viabilities(state):
    return {a.name: a.viability(state) for a in all_archetypes()}
