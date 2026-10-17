import math

from src.common.board import RESOURCES, port_access
from src.common.probability import expected_production

COSTS = {
    "road": {"WOOD": 1, "BRICK": 1},
    "settlement": {"WOOD": 1, "BRICK": 1, "SHEEP": 1, "WHEAT": 1},
    "city": {"WHEAT": 2, "ORE": 3},
    "dev_card": {"SHEEP": 1, "WHEAT": 1, "ORE": 1},
}
MAX_ROLLS = 500
TOLERANCE = 0.01


def cost_of(item):
    return COSTS[item] if isinstance(item, str) else item


def missing(hand, item):
    cost = cost_of(item)
    return {r: max(0, cost.get(r, 0) - hand.get(r, 0)) for r in RESOURCES}


def surplus(hand, item):
    cost = cost_of(item)
    return {r: max(0, hand.get(r, 0) - cost.get(r, 0)) for r in RESOURCES}


def can_afford(hand, item):
    return not any(missing(hand, item).values())


def trade_capacity(hand, item, ratios):
    spare = surplus(hand, item)
    return sum(int(spare[r] // ratios[r]) for r in RESOURCES)


def can_afford_with_trades(hand, item, ratios):
    return trade_capacity(hand, item, ratios) >= sum(missing(hand, item).values())


def trade_plan(hand, item, ratios):
    need = [r for r, n in missing(hand, item).items() for _ in range(n)]
    spare = surplus(hand, item)
    plan = []
    for get in need:
        options = [r for r in RESOURCES if spare[r] >= ratios[r]]
        if not options:
            return None
        give = min(options, key=lambda r: (ratios[r], -spare[r], RESOURCES.index(r)))
        spare[give] -= ratios[give]
        plan.append((give, ratios[give], get))
    return plan


def effective_hand_value(hand, ratios):
    return sum(hand.get(r, 0) / ratios[r] for r in RESOURCES)


def affordable_after(hand, prod, rolls, item, ratios):
    future = {r: hand.get(r, 0) + prod.get(r, 0) * rolls for r in RESOURCES}
    return trade_capacity(future, item, ratios) >= sum(missing(future, item).values()) - 1e-9


def rolls_to_afford(hand, prod, item, ratios):
    if can_afford_with_trades(hand, item, ratios):
        return 0.0
    if not affordable_after(hand, prod, MAX_ROLLS, item, ratios):
        return math.inf
    lo, hi = 0.0, float(MAX_ROLLS)
    while hi - lo > TOLERANCE:
        mid = (lo + hi) / 2
        if affordable_after(hand, prod, mid, item, ratios):
            hi = mid
        else:
            lo = mid
    return hi


def turns_to_afford(state, player, item):
    hand = state["me"]["hand"] if player == "me" else None
    if hand is None:
        raise ValueError("opponent hand is hidden")
    return rolls_to_afford(hand, expected_production(state, player), item, port_access(state, player))
