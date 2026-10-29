from src.agents.archetypes import DEFAULT, by_name, viabilities
from src.common.board import distance_rule_ok
from src.common.robber import robber_damage

DEFAULT_EDGE = 1.15
SWITCH_MARGIN = 1.25
CHECK_EVERY = 10
ROBBER_TURNS = 3
OPP_VP_ALERT = 7
REACH = "reach_node_"


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
        self.robber_hex = None
        self.robber_turns = 0
        self.opp_alerted = False
        self.target = None

    def update(self, state):
        reason = self.trigger(state)
        if reason:
            self.checkpoint(state, reason)
        self.track_target(state)
        return self.arch

    def trigger(self, state):
        new_turn = state["turn"] != self.last_turn
        if new_turn:
            self.last_turn = state["turn"]
            self.track_robber(state)
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
            return "target_lost"
        if self.robber_turns >= ROBBER_TURNS:
            self.robber_turns = 0
            return "robber"
        if state["opp"]["visible_vp"] >= OPP_VP_ALERT and not self.opp_alerted:
            self.opp_alerted = True
            return "opp_vp"
        if state["turn"] - self.last_check >= self.every:
            return "periodic"
        return None

    def track_robber(self, state):
        hex_id = state["robber_hex"]
        hurt = state["phase"] == "main" and robber_damage(state, "me", hex_id) > 0
        if hurt and hex_id == self.robber_hex:
            self.robber_turns += 1
        else:
            self.robber_turns = 1 if hurt else 0
        self.robber_hex = hex_id

    def track_target(self, state):
        mile = self.arch.next_milestone(state) if state["phase"] == "main" else ""
        self.target = int(mile[len(REACH):]) if mile.startswith(REACH) else None

    def checkpoint(self, state, reason):
        scores = viabilities(state)
        alive = {n: s for n, s in scores.items() if not by_name(n).is_dead(state)}
        self.last_check = state["turn"]
        choice = self.choose(alive)
        self.history.append({"turn": state["turn"], "reason": reason, "plan": choice, "scores": scores})
        if choice != self.plan:
            if self.plan is not None:
                self.switches.append({"turn": state["turn"], "from": self.plan, "to": choice, "reason": reason})
            self.plan = choice
            self.arch = by_name(choice)

    def choose(self, scores):
        best = pick(scores, self.edge)
        if self.plan not in scores or best == self.plan:
            return best
        if scores[best] > self.margin * scores[self.plan]:
            return best
        return self.plan
