import pytest

from src.common.probability import roll_prob
from src.common.robber import (
    can_steal,
    discard_loss,
    expected_discard_loss,
    hex_yield,
    robber_damage,
    steal_ev,
    steal_odds,
)
from src.common.scoring import army_size, longest_road_length, victory_points, visible_victory_points
from tests.helpers import blank_state

RING = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (0, 5)]


def test_longest_road_chain_and_loop():
    assert longest_road_length(blank_state(), "me") == 0
    assert longest_road_length(blank_state(me_roads=RING[:3]), "me") == 3
    assert longest_road_length(blank_state(me_roads=RING), "me") == 6


def test_longest_road_fork_counts_one_branch():
    state = blank_state(me_roads=[(0, 1), (1, 2), (0, 5), (0, 20)])
    assert longest_road_length(state, "me") == 3


def test_enemy_settlement_breaks_road():
    state = blank_state(me_roads=RING[:4], opp_settlements=[2])
    assert longest_road_length(state, "me") == 2
    state = blank_state(me_roads=RING[:4], opp_settlements=[4])
    assert longest_road_length(state, "me") == 4


def test_longest_road_with_hypothetical_edge():
    state = blank_state(me_roads=RING[:4])
    assert longest_road_length(state, "me", extra=[(4, 5)]) == 5
    assert longest_road_length(state, "me") == 4


def test_victory_points_hide_opponent_cards():
    state = blank_state()
    state["me"]["vp"] = 6
    state["me"]["dev_cards"]["VICTORY_POINT"] = 2
    state["opp"]["visible_vp"] = 4
    assert victory_points(state, "me") == 6
    assert visible_victory_points(state, "me") == 4
    assert victory_points(state, "opp") == visible_victory_points(state, "opp") == 4


def test_army_size():
    state = blank_state()
    state["opp"]["knights_played"] = 3
    assert army_size(state, "opp") == 3


def producing_hex(state):
    return next(h for h in state["board"]["hexes"] if h["resource"] != "DESERT")


def test_hex_yield_and_damage():
    state = blank_state()
    h = producing_hex(state)
    state["opp"]["settlements"] = [h["nodes"][0]]
    state["opp"]["cities"] = [h["nodes"][2]]
    assert hex_yield(state, "opp", h["id"]) == pytest.approx(3 * roll_prob(h["number"]))
    assert robber_damage(state, "opp", h["id"]) == hex_yield(state, "opp", h["id"])
    desert = next(x for x in state["board"]["hexes"] if x["resource"] == "DESERT")
    assert hex_yield(state, "opp", desert["id"]) == 0


def test_steal_needs_building_and_cards():
    state = blank_state()
    h = producing_hex(state)
    state["opp"]["settlements"] = [h["nodes"][0]]
    state["opp"]["hand_size"] = 0
    assert not can_steal(state, "opp", h["id"])
    assert steal_ev(state, "opp", h["id"]) == 0
    state["opp"]["hand_size"] = 3
    assert can_steal(state, "opp", h["id"])
    assert steal_ev(state, "opp", h["id"]) == 1.0
    other_hex = next(x for x in state["board"]["hexes"] if h["nodes"][0] not in x["nodes"])
    assert steal_ev(state, "opp", other_hex["id"]) == 0


def test_steal_odds():
    assert steal_odds({"WOOD": 3, "ORE": 1}) == {"WOOD": 0.75, "ORE": 0.25}
    assert steal_odds({"WOOD": 0}) == {"WOOD": 0.0}


def test_discard_loss():
    assert discard_loss(7) == 0
    assert discard_loss(8) == 4
    assert discard_loss(9) == 4
    assert expected_discard_loss(10) == pytest.approx(5 / 6)
