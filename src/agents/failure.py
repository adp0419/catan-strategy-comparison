from collections import deque

from src.agents.archetypes import SPACE_DEPTH, spots
from src.common.board import RESOURCES, port_access
from src.common.probability import DESERT, expected_production, node_pips
from src.common.robber import robber_damage

WIN_VP = 10
CARDS_PER_VP = 4
CORE_SHARE = 0.75
WINDOW = 12
SHORTFALL_FLOOR = 0.3
STALL_TURNS = 12
ROBBER_TURNS = 3
THRESHOLD = 1.0
COOLDOWN = 6
SIGNAL_WEIGHTS = {"target_lost": 0.6, "choked": 0.5, "shortfall": 0.5, "stalled": 0.4, "tempo": 0.4, "dead_end": 1.0}


def core(profile):
    top = max(profile.values())
    return {r for r in RESOURCES if profile.get(r, 0.0) >= CORE_SHARE * top}


def eta(vp, prod):
    rate = 2 * sum(prod.values()) / CARDS_PER_VP
    return max(0.0, WIN_VP - vp) / rate if rate > 0 else float("inf")


class Monitor:
    def __init__(self):
        self.cursor = 0
        self.rolls = deque(maxlen=WINDOW)
        self.robber = None
        self.robber_turns = 0
        self.mile = None
        self.mile_since = None
        self.lost = 0.0
        self.last_alarm = None
        self.signals = {}

    def observe_rolls(self, state, keep):
        board = state["board"]
        if self.robber is None:
            self.robber = next(tuple(h["coord"]) for h in board["hexes"] if h["resource"] == DESERT)
        mine = set(state["me"]["settlements"])
        cities = set(state["me"]["cities"])
        prod = expected_production(state, "me", robber=False)
        expect = sum(prod[r] for r in keep)
        log = state["log"]
        for entry in log[self.cursor:]:
            if entry["action"] == "MOVE_ROBBER":
                self.robber = tuple(entry["value"][0])
            elif entry["action"] == "ROLL" and state["phase"] == "main":
                number = sum(entry["value"])
                got = 0
                for h in board["hexes"]:
                    if h["number"] != number or h["resource"] not in keep or tuple(h["coord"]) == self.robber:
                        continue
                    got += sum(2 if n in cities else 1 for n in h["nodes"] if n in mine or n in cities)
                self.rolls.append((got, expect))
        self.cursor = len(log)

    def target_lost(self, state, target):
        before = node_pips(state["board"], target)
        alts = [node_pips(state["board"], n) for n, _ in spots(state, SPACE_DEPTH)]
        best = max(alts, default=0)
        self.lost = max(0.0, 1 - best / before) if before else 0.0

    def update(self, state, arch, model):
        profile = arch.target_profile(state)
        keep = core(profile)
        self.observe_rolls(state, keep)
        mile = arch.next_milestone(state)
        if mile != self.mile:
            self.mile, self.mile_since = mile, state["turn"]
        hurt = robber_damage(state, "me", state["robber_hex"]) > 0
        hex_res = state["board"]["hexes"][state["robber_hex"]]["resource"]
        self.robber_turns = self.robber_turns + 1 if hurt and hex_res in keep else 0
        prod = expected_production(state, "me", robber=False)
        ratios = port_access(state, "me")
        got = sum(g for g, _ in self.rolls)
        want = sum(e for _, e in self.rolls)
        short = 1 - got / want if want > 0 and len(self.rolls) >= WINDOW // 2 else 0.0
        opp_vp = model.estimated_vp(state) if model else state["opp"]["visible_vp"]
        mine, theirs = eta(state["me"]["vp"], prod), eta(opp_vp, expected_production(state, "opp", robber=False))
        self.signals = {
            "target_lost": self.lost,
            "choked": min(1.0, self.robber_turns / ROBBER_TURNS),
            "shortfall": max(0.0, (short - SHORTFALL_FLOOR) / (1 - SHORTFALL_FLOOR)),
            "stalled": min(1.0, max(0.0, (state["turn"] - self.mile_since - STALL_TURNS) / STALL_TURNS)),
            "tempo": min(1.0, max(0.0, (mine - theirs) / mine)) if 0 < mine < float("inf") else 0.0,
            "dead_end": 1.0 if any(prod[r] == 0 and ratios[r] == 4 for r in keep) else 0.0,
        }
        self.lost = 0.0
        return self.score()

    def score(self):
        return sum(SIGNAL_WEIGHTS[k] * v for k, v in self.signals.items())

    def alarm(self, state):
        if self.score() < THRESHOLD:
            return False
        if self.last_alarm is not None and state["turn"] - self.last_alarm < COOLDOWN:
            return False
        self.last_alarm = state["turn"]
        return True

    def salvage(self, state):
        cards = state["me"]["dev_cards"]
        if self.signals.get("choked", 0) >= 1 and cards.get("KNIGHT", 0) > 0:
            return "knight"
        if self.signals.get("dead_end", 0) >= 1 and cards.get("YEAR_OF_PLENTY", 0) > 0:
            return "plenty"
        return None

    def reset(self, state):
        self.mile_since = state["turn"]
        self.rolls.clear()
