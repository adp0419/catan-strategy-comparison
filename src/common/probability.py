from collections import defaultdict

from src.common.board import RESOURCES, adjacent_hexes

PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
DESERT = "DESERT"
SETTLEMENT_MULT = 1
CITY_MULT = 2


def pips(number):
    return PIPS.get(number, 0)


def roll_prob(number):
    return pips(number) / 36


def producing_hexes(board, node, robber_hex=None):
    return [h for h in adjacent_hexes(board, node) if h["resource"] != DESERT and h["id"] != robber_hex]


def node_pips(board, node):
    return sum(pips(h["number"]) for h in producing_hexes(board, node))


def holdings(state, player):
    held = {n: SETTLEMENT_MULT for n in state[player]["settlements"]}
    held.update({n: CITY_MULT for n in state[player]["cities"]})
    return held


def number_yields(board, held, robber_hex=None):
    yields = defaultdict(lambda: defaultdict(int))
    for node, mult in held.items():
        for h in producing_hexes(board, node, robber_hex):
            yields[h["number"]][h["resource"]] += mult
    return yields


def expected_from(yields):
    prod = {r: 0.0 for r in RESOURCES}
    for number, cards in yields.items():
        for res, n in cards.items():
            prod[res] += roll_prob(number) * n
    return prod


def variance_from(yields, resource=None):
    mean = sq = 0.0
    for number, cards in yields.items():
        total = cards.get(resource, 0) if resource else sum(cards.values())
        mean += roll_prob(number) * total
        sq += roll_prob(number) * total * total
    return sq - mean * mean


def robber_of(state, robber):
    return state["robber_hex"] if robber else None


def expected_production(state, player, robber=True):
    held = holdings(state, player)
    return expected_from(number_yields(state["board"], held, robber_of(state, robber)))


def node_production(board, node, robber_hex=None, mult=SETTLEMENT_MULT):
    return expected_from(number_yields(board, {node: mult}, robber_hex))


def production_variance(state, player, robber=True, extra=None, resource=None):
    held = holdings(state, player)
    for node, mult in (extra or {}).items():
        held[node] = max(held.get(node, 0), mult)
    return variance_from(number_yields(state["board"], held, robber_of(state, robber)), resource)


def resource_diversity(state, player):
    return sum(1 for v in expected_production(state, player, robber=False).values() if v > 0)


def resource_roll_prob(state, player, resource, robber=True):
    yields = number_yields(state["board"], holdings(state, player), robber_of(state, robber))
    return sum(roll_prob(n) for n, cards in yields.items() if cards.get(resource, 0) > 0)


def prob_of_resource_within(state, player, resource, rolls, robber=True):
    p = resource_roll_prob(state, player, resource, robber)
    return 1 - (1 - p) ** rolls


def robber_adjusted_production(state, player, downtime):
    prod = {r: 0.0 for r in RESOURCES}
    board = state["board"]
    for node, mult in holdings(state, player).items():
        for h in producing_hexes(board, node):
            prod[h["resource"]] += mult * roll_prob(h["number"]) * (1 - downtime.get(pips(h["number"]), 0.0))
    return prod
