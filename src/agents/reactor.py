import math

from src.agents.archetypes import ACTIONS, best_spot, can_settle, can_upgrade, roads_left
from src.common.board import buildable_nodes, port_access
from src.common.economy import COSTS, rolls_to_afford
from src.common.probability import expected_production
from src.common.scoring import BONUS_VP, LARGEST_ARMY_MIN, LONGEST_ROAD_MIN, army_size, longest_road_length

RACE_VP = 8
RACE_DEPTH = 2
STEAL_ROADS = 2
RACE_WEIGHTS = {"settlement": 1.2, "city": 1.2, "road": 0.6, "dev_card": 0.8, "road_building": 1.2}


def combined(*items):
    out = {}
    for item, n in items:
        for r, c in COSTS[item].items():
            out[r] = out.get(r, 0) + c * n
    return out


def road_steal(state):
    if state["longest_road_holder"] == "me":
        return None
    mine = longest_road_length(state, "me")
    need = max(LONGEST_ROAD_MIN, state["opp"]["road_length"] + 1) - mine
    if 0 < need <= min(STEAL_ROADS, roads_left(state)):
        return need
    return None


def army_steal(state):
    if state["largest_army_holder"] == "me":
        return False
    need = max(LARGEST_ARMY_MIN, army_size(state, "opp") + 1) - army_size(state, "me")
    return 0 < need <= 1 and state["me"]["dev_cards"].get("KNIGHT", 0) > 0


def swing(state, flag):
    return 2 * BONUS_VP if state[flag] == "opp" else BONUS_VP


def fastest(state):
    hand = state["me"]["hand"]
    prod = expected_production(state, "me")
    ratios = port_access(state, "me")
    opts = []
    if army_steal(state):
        opts.append((0.0, "knight"))
    need = road_steal(state)
    if need:
        opts.append((rolls_to_afford(hand, prod, combined(("road", need)), ratios) / swing(state, "longest_road_holder"), "road"))
    if can_upgrade(state):
        opts.append((rolls_to_afford(hand, prod, "city", ratios), "city"))
    if can_settle(state):
        if buildable_nodes(state, "me"):
            opts.append((rolls_to_afford(hand, prod, "settlement", ratios), "settlement"))
        elif roads_left(state) > 0:
            node, d = best_spot(state, RACE_DEPTH)
            if node is not None:
                cost = combined(("road", d), ("settlement", 1))
                opts.append((rolls_to_afford(hand, prod, cost, ratios), f"reach_node_{node}"))
    opts = [o for o in opts if o[0] < math.inf]
    if not opts:
        return None
    return min(opts, key=lambda o: (o[0], o[1]))[1]


class Race:
    name = "race"

    def __init__(self, plan):
        self.plan = plan

    def action_weights(self, state):
        return {a: RACE_WEIGHTS.get(a, 1.0) for a in ACTIONS}

    def next_milestone(self, state):
        return fastest(state) or self.plan.next_milestone(state)

    def node_fit(self, state, node):
        return self.plan.node_fit(state, node)

    def is_dead(self, state):
        return False


class Reactor:
    def __init__(self, race_vp=RACE_VP):
        self.race_vp = race_vp
        self.race_from = None

    def override(self, state, arch, model):
        if state["phase"] != "main":
            return arch
        vp = model.estimated_vp(state) if model else state["opp"]["visible_vp"]
        if vp < self.race_vp:
            return arch
        if self.race_from is None:
            self.race_from = state["turn"]
        return Race(arch)
