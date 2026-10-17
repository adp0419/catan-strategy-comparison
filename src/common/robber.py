from src.common.board import buildings
from src.common.probability import CITY_MULT, DESERT, SETTLEMENT_MULT, roll_prob

SEVEN_PROB = 6 / 36
DISCARD_LIMIT = 7


def hex_yield(state, player, hex_id):
    h = state["board"]["hexes"][hex_id]
    if h["resource"] == DESERT:
        return 0.0
    mult = sum(SETTLEMENT_MULT for n in state[player]["settlements"] if n in h["nodes"])
    mult += sum(CITY_MULT for n in state[player]["cities"] if n in h["nodes"])
    return mult * roll_prob(h["number"])


def robber_damage(state, target, hex_id):
    return hex_yield(state, target, hex_id)


def can_steal(state, target, hex_id):
    on_hex = any(n in state["board"]["hexes"][hex_id]["nodes"] for n in buildings(state, target))
    return on_hex and hand_size(state, target) > 0


def hand_size(state, player):
    if player == "me":
        return sum(state["me"]["hand"].values())
    return state["opp"]["hand_size"]


def steal_ev(state, target, hex_id=None):
    if hex_id is not None and not can_steal(state, target, hex_id):
        return 0.0
    return 1.0 if hand_size(state, target) > 0 else 0.0


def steal_odds(hand):
    total = sum(hand.values())
    return {r: n / total for r, n in hand.items()} if total else {r: 0.0 for r in hand}


def discard_loss(cards):
    return cards // 2 if cards > DISCARD_LIMIT else 0


def expected_discard_loss(cards):
    return SEVEN_PROB * discard_loss(cards)
