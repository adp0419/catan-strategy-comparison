from src.agents.archetypes import DEFAULT, by_name, viabilities
from src.agents.failure import Monitor
from src.common.board import distance_rule_ok

DEFAULT_EDGE = 1.15
SWITCH_MARGIN = 1.25
PIVOT_MARGIN = 1.05
CHECK_EVERY = 10
OPP_VP_ALERT = 7
REACH = "reach_node_"
PIVOT_DEFAULT = 0.15
PIVOT_COST = {
    ("expansion", "longest_road"): 0.0,
    ("expansion", "cities_and_roads"): 0.0,
    ("longest_road", "expansion"): 0.0,
    ("longest_road", "cities_and_roads"): 0.05,
    ("cities_and_roads", "expansion"): 0.05,
    ("cities_and_roads", "longest_road"): 0.1,
    ("ore_wheat_sheep", "dev_rush"): 0.05,
    ("dev_rush", "ore_wheat_sheep"): 0.05,
    ("ore_wheat_sheep", "cities_and_roads"): 0.05,
    ("dev_rush", "cities_and_roads"): 0.05,
    ("cities_and_roads", "ore_wheat_sheep"): 0.1,
    ("cities_and_roads", "dev_rush"): 0.1,
    ("port_play", "cities_and_roads"): 0.05,
    ("expansion", "ore_wheat_sheep"): 0.35,
    ("longest_road", "ore_wheat_sheep"): 0.35,
    ("expansion", "dev_rush"): 0.3,
    ("longest_road", "dev_rush"): 0.3,
    ("ore_wheat_sheep", "expansion"): 0.25,
    ("ore_wheat_sheep", "longest_road"): 0.3,
    ("dev_rush", "expansion"): 0.25,
    ("dev_rush", "longest_road"): 0.3,
}


def pivot_cost(old, new):
    if old is None or old == new:
        return 0.0
    return PIVOT_COST.get((old, new), PIVOT_DEFAULT)


def pick(scores, edge=DEFAULT_EDGE):
    best = max(sorted(scores), key=lambda n: scores[n])
    if best != DEFAULT and scores[best] <= edge * scores[DEFAULT]:
        return DEFAULT
    return best


class Planner:
    def __init__(self, replan=True, edge=DEFAULT_EDGE, margin=SWITCH_MARGIN, every=CHECK_EVERY):
        self.replan = replan
        self.edge = edge
        self.margin = margin
        self.every = every
        self.plan = None
        self.arch = None
        self.switches = []
        self.history = []
        self.last_check = None
        self.last_turn = None
        self.placed = False
        self.opp_alerted = False
        self.target = None
        self.monitor = Monitor()
        self.salvage = None
        self.degradation = []

    def update(self, state, model=None):
        reason = self.trigger(state, model)
        if reason:
            self.checkpoint(state, reason)
        self.track_target(state)
        return self.arch

    def trigger(self, state, model=None):
        new_turn = state["turn"] != self.last_turn
        if new_turn:
            self.last_turn = state["turn"]
            self.salvage = None
        if self.plan is None:
            return "start"
        if not self.replan:
            return None
        if state["phase"] == "main" and not self.placed:
            self.placed = True
            return "placement_done"
        if state["phase"] != "main" or not new_turn:
            return None
        if self.arch.is_dead(state):
            return "dead"
        if self.target is not None and not distance_rule_ok(state, self.target):
            self.monitor.target_lost(state, self.target)
        level = self.monitor.update(state, self.arch, model)
        self.degradation.append((state["turn"], level))
        if self.monitor.alarm(state):
            fix = self.monitor.salvage(state)
            if fix:
                self.salvage = fix
                self.history.append({"turn": state["turn"], "reason": "salvage", "plan": self.plan, "fix": fix, "signals": dict(self.monitor.signals)})
                return None
            return "degraded"
        if state["opp"]["visible_vp"] >= OPP_VP_ALERT and not self.opp_alerted:
            self.opp_alerted = True
            return "opp_vp"
        if state["turn"] - self.last_check >= self.every:
            return "periodic"
        return None

    def track_target(self, state):
        mile = self.arch.next_milestone(state) if state["phase"] == "main" else ""
        self.target = int(mile[len(REACH):]) if mile.startswith(REACH) else None

    def checkpoint(self, state, reason):
        scores = viabilities(state)
        alive = {n: s for n, s in scores.items() if not by_name(n).is_dead(state)}
        self.last_check = state["turn"]
        choice = self.choose(alive, PIVOT_MARGIN if reason == "degraded" else self.margin)
        entry = {"turn": state["turn"], "reason": reason, "plan": choice, "scores": scores}
        if reason == "degraded":
            entry["signals"] = dict(self.monitor.signals)
            self.monitor.reset(state)
        self.history.append(entry)
        if choice != self.plan:
            if self.plan is not None:
                self.switches.append({"turn": state["turn"], "from": self.plan, "to": choice, "reason": reason})
            self.plan = choice
            self.arch = by_name(choice)

    def choose(self, scores, margin=None):
        margin = self.margin if margin is None else margin
        net = {n: s * (1 - pivot_cost(self.plan, n)) for n, s in scores.items()}
        best = pick(net, self.edge)
        if self.plan not in net or best == self.plan:
            return best
        if net[best] > margin * net[self.plan]:
            return best
        return self.plan
