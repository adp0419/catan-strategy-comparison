import pytest

from src.common.engine import extract_state, new_game
from src.common.probability import (
    expected_production,
    node_pips,
    node_production,
    pips,
    prob_of_resource_within,
    production_variance,
    resource_diversity,
    resource_roll_prob,
    robber_adjusted_production,
    roll_prob,
)

HEXES = [
    {"id": 0, "resource": "WHEAT", "number": 6},
    {"id": 1, "resource": "ORE", "number": 8},
    {"id": 2, "resource": "DESERT", "number": None},
    {"id": 3, "resource": "WOOD", "number": 6},
    {"id": 4, "resource": "BRICK", "number": 8},
    {"id": 5, "resource": "SHEEP", "number": 6},
]
NODE_HEXES = {0: [0, 1, 2], 1: [0, 3], 2: [3], 3: [4], 4: [5]}


def fixture(me_settlements=(), me_cities=(), robber_hex=2):
    board = {
        "hexes": HEXES,
        "nodes": [{"id": n, "hexes": hs, "neighbors": []} for n, hs in NODE_HEXES.items()],
    }
    empty = {"settlements": [], "cities": []}
    me = {"settlements": list(me_settlements), "cities": list(me_cities)}
    return {"board": board, "robber_hex": robber_hex, "me": me, "opp": empty}


def test_pips_table():
    assert [pips(n) for n in range(2, 13)] == [1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]
    assert sum(pips(n) for n in range(2, 13)) == 36
    assert pips(None) == 0
    assert roll_prob(6) == 5 / 36


def test_node_pips_skip_desert():
    board = fixture()["board"]
    assert node_pips(board, 0) == 10
    assert node_pips(board, 1) == 10
    assert node_pips(board, 2) == 5


def test_settlement_and_city_production():
    state = fixture(me_settlements=[0], me_cities=[1])
    prod = expected_production(state, "me")
    assert prod["WHEAT"] == pytest.approx(5 / 36 + 10 / 36)
    assert prod["ORE"] == pytest.approx(5 / 36)
    assert prod["WOOD"] == pytest.approx(10 / 36)
    assert prod["BRICK"] == 0 and prod["SHEEP"] == 0


def test_robber_blocks_hex():
    state = fixture(me_settlements=[0], me_cities=[1], robber_hex=0)
    prod = expected_production(state, "me")
    assert prod["WHEAT"] == 0
    assert prod["WOOD"] == pytest.approx(10 / 36)
    assert expected_production(state, "me", robber=False)["WHEAT"] == pytest.approx(15 / 36)


def test_node_production_for_unowned_spot():
    board = fixture()["board"]
    prod = node_production(board, 0)
    assert prod["WHEAT"] == pytest.approx(5 / 36)
    assert prod["ORE"] == pytest.approx(5 / 36)
    assert node_production(board, 0, robber_hex=1)["ORE"] == 0
    assert node_production(board, 0, mult=2)["WHEAT"] == pytest.approx(10 / 36)


def test_variance_hand_computed():
    state = fixture(me_settlements=[0], me_cities=[1])
    mean = 5 * 5 / 36 + 1 * 5 / 36
    sq = 25 * 5 / 36 + 1 * 5 / 36
    assert production_variance(state, "me") == pytest.approx(sq - mean * mean)


def test_same_number_costs_variance_not_mean():
    stacked = fixture(me_settlements=[2, 4])
    spread = fixture(me_settlements=[2, 3])
    total = lambda st: sum(expected_production(st, "me").values())
    assert total(stacked) == pytest.approx(total(spread)) == pytest.approx(10 / 36)
    assert production_variance(stacked, "me") == pytest.approx(20 / 36 - (10 / 36) ** 2)
    assert production_variance(spread, "me") == pytest.approx(10 / 36 - (10 / 36) ** 2)
    single = fixture(me_settlements=[2])
    assert production_variance(single, "me", extra={4: 1}) == pytest.approx(production_variance(stacked, "me"))
    assert production_variance(single, "me", extra={3: 1}) < production_variance(single, "me", extra={4: 1})


def test_diversity_ignores_robber():
    state = fixture(me_settlements=[0], me_cities=[1], robber_hex=0)
    assert resource_diversity(state, "me") == 3


def test_prob_of_resource_within():
    state = fixture(me_settlements=[0])
    assert resource_roll_prob(state, "me", "ORE") == pytest.approx(5 / 36)
    assert prob_of_resource_within(state, "me", "ORE", 3) == pytest.approx(1 - (31 / 36) ** 3)
    assert prob_of_resource_within(state, "me", "WOOD", 10) == 0
    both = fixture(me_settlements=[0, 1])
    assert resource_roll_prob(both, "me", "WHEAT") == pytest.approx(5 / 36)


def test_real_board_totals():
    game = new_game(4)
    state = extract_state(game, game.state.colors[0])
    board = state["board"]
    total = sum(sum(pips(board["hexes"][h]["number"]) for h in n["hexes"]) for n in board["nodes"])
    assert total == sum(node_pips(board, n["id"]) for n in board["nodes"])
    assert max(node_pips(board, n["id"]) for n in board["nodes"]) <= 15


def test_variance_by_resource():
    state = fixture(me_settlements=[0], me_cities=[1])
    p = 5 / 36
    assert production_variance(state, "me", resource="ORE") == pytest.approx(p - p * p)
    wheat = 3 * 3 * p - (3 * p) ** 2
    assert production_variance(state, "me", resource="WHEAT") == pytest.approx(wheat)


def test_robber_adjusted_production():
    state = fixture(me_settlements=[0], me_cities=[1], robber_hex=0)
    plain = expected_production(state, "me", robber=False)
    assert robber_adjusted_production(state, "me", {}) == pytest.approx(plain)
    adj = robber_adjusted_production(state, "me", {5: 0.2})
    assert adj["WHEAT"] == pytest.approx(plain["WHEAT"] * 0.8)
    assert adj["ORE"] == pytest.approx(plain["ORE"] * 0.8)
