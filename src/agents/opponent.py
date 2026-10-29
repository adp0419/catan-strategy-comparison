from collections import Counter

from src.agents.archetypes import by_name, viabilities
from src.agents.planner import pick
from src.common.board import RESOURCES
from src.common.economy import COSTS
from src.common.probability import DESERT

DEV_DECK = {"KNIGHT": 14, "VICTORY_POINT": 5, "ROAD_BUILDING": 2, "YEAR_OF_PLENTY": 2, "MONOPOLY": 2}
VP_CARD = "VICTORY_POINT"
FREE_OPENING_ROADS = 2
OPENING_SETTLEMENTS = 2
ROAD_BUILDING_ROADS = 2
PLAYS = {"PLAY_KNIGHT_CARD", "PLAY_ROAD_BUILDING", "PLAY_YEAR_OF_PLENTY", "PLAY_MONOPOLY"}
FLIP = {"me": "opp", "opp": "me", None: None}


def mirror(state, hand):
    me, opp = state["me"], state["opp"]
    my_hidden = me["dev_cards"].get(VP_CARD, 0)
    new_me = dict(opp, hand=dict(hand), dev_cards={}, vp=opp["visible_vp"])
    new_opp = dict(
        me,
        hand_size=sum(me["hand"].values()),
        dev_cards_count=sum(me["dev_cards"].values()),
        visible_vp=me["vp"] - my_hidden,
    )
    return dict(
        state,
        me=new_me,
        opp=new_opp,
        longest_road_holder=FLIP[state["longest_road_holder"]],
        largest_army_holder=FLIP[state["largest_army_holder"]],
    )


class OpponentModel:
    def __init__(self):
        self.cursor = 0
        self.hand = {r: 0.0 for r in RESOURCES}
        self.robber = None
        self.settlements = 0
        self.roads = 0
        self.free_roads = 0
        self.dev_bought = 0
        self.dev_played = 0
        self.my_draws = Counter()
        self.builds = Counter()
        self.plan = None
        self.towns = set()
        self.cities = set()
        self.my_hand = {r: 0 for r in RESOURCES}

    def update(self, state):
        board = state["board"]
        if self.robber is None:
            self.robber = next(tuple(h["coord"]) for h in board["hexes"] if h["resource"] == DESERT)
        log = state["log"]
        for entry in log[self.cursor:]:
            self.apply(state, entry)
        self.cursor = len(log)
        self.rescale(state)
        self.my_hand = dict(state["me"]["hand"])
        return self

    def take(self, res, n=1):
        self.hand[res] = max(0.0, self.hand[res] - n)

    def pay(self, item):
        for r, n in COSTS[item].items():
            self.take(r, n)

    def paid_for(self, state, number):
        for h in state["board"]["hexes"]:
            if h["number"] != number or tuple(h["coord"]) == self.robber:
                continue
            for n in h["nodes"]:
                if n in self.cities:
                    self.hand[h["resource"]] += 2
                elif n in self.towns:
                    self.hand[h["resource"]] += 1

    def opening_income(self, state, node):
        board = state["board"]
        for h in board["nodes"][node]["hexes"]:
            res = board["hexes"][h]["resource"]
            if res != DESERT:
                self.hand[res] += 1

    def apply(self, state, entry):
        who, kind, val = entry["player"], entry["action"], entry["value"]
        if kind == "ROLL":
            number = sum(val)
            if number != 7:
                self.paid_for(state, number)
            return
        if kind == "MOVE_ROBBER":
            coord, victim, stolen = val
            self.robber = tuple(coord)
            if stolen and victim == "opp":
                self.take(stolen)
            elif stolen and victim == "me":
                self.hand[stolen] += 1
            return
        if kind == "PLAY_MONOPOLY" and who == "me":
            self.hand[val] = 0.0
        if kind == "BUY_DEVELOPMENT_CARD" and who == "me":
            self.my_draws[val] += 1
        if who != "opp":
            return
        if kind in PLAYS:
            self.dev_played += 1
        if kind == "PLAY_MONOPOLY":
            self.hand[val] += self.my_hand.get(val, 0)
        if kind == "BUILD_SETTLEMENT":
            self.settlements += 1
            self.towns.add(val)
            if self.settlements == OPENING_SETTLEMENTS:
                self.opening_income(state, val)
            elif self.settlements > OPENING_SETTLEMENTS:
                self.pay("settlement")
                self.builds["settlement"] += 1
        elif kind == "BUILD_ROAD":
            self.roads += 1
            if self.roads <= FREE_OPENING_ROADS:
                return
            if self.free_roads > 0:
                self.free_roads -= 1
            else:
                self.pay("road")
            self.builds["road"] += 1
        elif kind == "BUILD_CITY":
            self.towns.discard(val)
            self.cities.add(val)
            self.pay("city")
            self.builds["city"] += 1
        elif kind == "BUY_DEVELOPMENT_CARD":
            self.pay("dev_card")
            self.dev_bought += 1
            self.builds["dev_card"] += 1
        elif kind == "PLAY_ROAD_BUILDING":
            self.free_roads = ROAD_BUILDING_ROADS
        elif kind == "PLAY_YEAR_OF_PLENTY":
            for r in val:
                self.hand[r] += 1
        elif kind == "MARITIME_TRADE":
            give = [r for r in val[:4] if r is not None]
            self.take(give[0], len(give))
            self.hand[val[4]] += 1
        elif kind == "DISCARD":
            for r in val or []:
                self.take(r)

    def rescale(self, state):
        size = state["opp"]["hand_size"]
        total = sum(self.hand.values())
        if size == 0:
            self.hand = {r: 0.0 for r in RESOURCES}
        elif total > 0:
            self.hand = {r: v * size / total for r, v in self.hand.items()}
        else:
            self.hand = {r: size / len(RESOURCES) for r in RESOURCES}

    def vp_card_odds(self):
        pool = sum(DEV_DECK.values()) - sum(self.my_draws.values())
        left = DEV_DECK[VP_CARD] - self.my_draws[VP_CARD]
        return left / pool if pool > 0 else 0.0

    def hidden_vp(self, state):
        unplayed = state["opp"]["dev_cards_count"]
        return unplayed * self.vp_card_odds()

    def estimated_vp(self, state):
        return state["opp"]["visible_vp"] + self.hidden_vp(state)

    def archetype(self, state):
        if state["phase"] != "main":
            return None
        if self.plan is None or state["turn"] != self.plan[0]:
            scores = viabilities(mirror(state, self.hand))
            self.plan = (state["turn"], pick(scores))
        return by_name(self.plan[1])

    def key_weights(self, state):
        arch = self.archetype(state)
        if arch is None:
            return {r: 1.0 for r in RESOURCES}
        profile = arch.target_profile(mirror(state, self.hand))
        mean = sum(profile.values()) / len(RESOURCES)
        return {r: profile.get(r, 0.0) / mean for r in RESOURCES}
