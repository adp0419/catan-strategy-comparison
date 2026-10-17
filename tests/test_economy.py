import math

import pytest

from src.common.economy import (
    COSTS,
    can_afford,
    can_afford_with_trades,
    effective_hand_value,
    missing,
    rolls_to_afford,
    trade_plan,
    turns_to_afford,
)

BANK = {r: 4 for r in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE")}
NONE = {r: 0.0 for r in BANK}


def hand(**counts):
    return {r: counts.get(r, 0) for r in BANK}


def test_costs_are_base_game():
    assert COSTS["road"] == {"WOOD": 1, "BRICK": 1}
    assert COSTS["settlement"] == {"WOOD": 1, "BRICK": 1, "SHEEP": 1, "WHEAT": 1}
    assert COSTS["city"] == {"WHEAT": 2, "ORE": 3}
    assert COSTS["dev_card"] == {"SHEEP": 1, "WHEAT": 1, "ORE": 1}


def test_can_afford_and_missing():
    h = hand(WHEAT=2, ORE=2)
    assert not can_afford(h, "city")
    assert missing(h, "city")["ORE"] == 1
    assert can_afford(hand(WHEAT=2, ORE=3), "city")


def test_trade_plan_bank_four_to_one():
    h = hand(WOOD=5, WHEAT=2, ORE=2)
    assert trade_plan(h, "city", BANK) == [("WOOD", 4, "ORE")]
    assert trade_plan(hand(WOOD=3, WHEAT=2, ORE=2), "city", BANK) is None


def test_trade_plan_never_spends_needed_cards():
    h = hand(WHEAT=6, ORE=1)
    assert trade_plan(h, "city", BANK) is None
    h = hand(WHEAT=10, ORE=1)
    assert trade_plan(h, "city", BANK) == [("WHEAT", 4, "ORE"), ("WHEAT", 4, "ORE")]


def test_trade_plan_prefers_cheapest_port():
    ratios = dict(BANK, SHEEP=2, WOOD=3)
    h = hand(WOOD=3, SHEEP=2, WHEAT=2, ORE=2)
    assert trade_plan(h, "city", ratios) == [("SHEEP", 2, "ORE")]
    assert can_afford_with_trades(h, "city", ratios)


def test_effective_hand_value():
    ratios = dict(BANK, SHEEP=2)
    assert effective_hand_value(hand(WOOD=4, SHEEP=2), ratios) == pytest.approx(2.0)


def test_rolls_to_afford_zero_when_affordable():
    assert rolls_to_afford(hand(WOOD=1, BRICK=1), NONE, "road", BANK) == 0
    assert rolls_to_afford(hand(WOOD=5, BRICK=0), NONE, "road", BANK) == 0


def test_rolls_to_afford_infinite_without_income():
    assert rolls_to_afford(hand(WOOD=1), NONE, "road", BANK) == math.inf


def test_rolls_to_afford_from_production():
    prod = dict(NONE, BRICK=5 / 36)
    assert rolls_to_afford(hand(WOOD=1), prod, "road", BANK) == pytest.approx(36 / 5, abs=0.02)


def test_rolls_to_afford_through_trades():
    prod = dict(NONE, WOOD=10 / 36)
    assert rolls_to_afford(hand(), prod, "road", BANK) == pytest.approx(5 * 36 / 10, abs=0.02)
    ports = dict(BANK, WOOD=2)
    assert rolls_to_afford(hand(), prod, "road", ports) == pytest.approx(3 * 36 / 10, abs=0.02)


def test_turns_to_afford_reads_state():
    board = {
        "hexes": [{"id": 0, "resource": "BRICK", "number": 6}],
        "nodes": [{"id": 0, "hexes": [0], "neighbors": []}],
    }
    me = {"hand": hand(WOOD=1), "settlements": [0], "cities": [], "ports": []}
    opp = {"settlements": [], "cities": [], "ports": []}
    state = {"board": board, "robber_hex": None, "me": me, "opp": opp}
    assert turns_to_afford(state, "me", "road") == pytest.approx(36 / 5, abs=0.02)
    with pytest.raises(ValueError):
        turns_to_afford(state, "opp", "road")
