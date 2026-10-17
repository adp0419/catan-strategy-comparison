import math

import pytest
from catanatron.models.enums import ActionPrompt, ActionType

from src.agents.baselines import RandomAgent
from src.common.board import (
    adjacent_hexes,
    adjacent_nodes,
    buildable_edges,
    buildable_nodes,
    distance_rule_ok,
    edge_key,
    node_ports,
    port_access,
    road_distance,
)
from src.common.engine import SEATS, apply, extract_state, legal_actions, new_game
from tests.helpers import blank_state


def test_adjacency_on_center_hex():
    state = blank_state()
    board = state["board"]
    assert board["hexes"][0]["nodes"] == [0, 1, 2, 3, 4, 5]
    assert [h["id"] for h in adjacent_hexes(board, 0)] == [0, 5, 6]
    assert adjacent_nodes(board, 0) == [1, 5, 20]


def test_node_ports_cover_nine_ports():
    board = blank_state()["board"]
    ports = node_ports(board)
    assert len(ports) == 18
    assert sorted(set(ports.values())) == ["3:1", "BRICK", "ORE", "SHEEP", "WHEAT", "WOOD"]


def test_distance_rule():
    state = blank_state(me_settlements=[0])
    assert not distance_rule_ok(state, 0)
    for n in (1, 5, 20):
        assert not distance_rule_ok(state, n)
    assert distance_rule_ok(state, 2)


def test_placement_nodes_ignore_connectivity():
    state = blank_state(phase="placement", me_settlements=[0], opp_settlements=[3])
    nodes = buildable_nodes(state, "me")
    assert 0 not in nodes and 1 not in nodes and 2 not in nodes
    assert 40 in nodes


def test_main_nodes_need_own_road():
    state = blank_state(me_settlements=[0], me_roads=[(0, 5), (4, 5), (3, 4)])
    assert buildable_nodes(state, "me") == [3, 4]
    state["opp"]["settlements"] = [2]
    assert buildable_nodes(state, "me") == [4]


def test_placement_road_comes_off_bare_settlement():
    state = blank_state(phase="placement", me_settlements=[0])
    assert buildable_edges(state, "me") == [(0, 1), (0, 5), (0, 20)]
    state["me"]["settlements"] = [0, 10]
    state["me"]["roads"] = [(0, 5)]
    assert all(10 in e for e in buildable_edges(state, "me"))


def test_main_edges_stop_at_enemy_building():
    state = blank_state(me_settlements=[0], me_roads=[(0, 5), (4, 5)], opp_settlements=[4])
    edges = buildable_edges(state, "me")
    assert not any(4 in e for e in edges)
    assert (0, 1) in edges and (0, 20) in edges


def test_road_distance_counts_new_roads_only():
    state = blank_state(me_settlements=[0], me_roads=[(0, 5)])
    assert road_distance(state, "me", 0) == 0
    assert road_distance(state, "me", 5) == 0
    assert road_distance(state, "me", 4) == 1
    assert road_distance(state, "me", 3) == 2


def test_road_distance_avoids_enemy_roads_and_buildings():
    state = blank_state(me_settlements=[0], me_roads=[(0, 5)], opp_roads=[(3, 4)])
    assert road_distance(state, "me", 3) == 3
    state = blank_state(me_settlements=[0], me_roads=[(0, 5)], opp_settlements=[4])
    assert road_distance(state, "me", 4) == math.inf
    assert road_distance(state, "me", 3) == 3


def test_road_distance_without_network_is_infinite():
    assert road_distance(blank_state(), "me", 0) == math.inf


@pytest.mark.parametrize(
    "ports,expected",
    [
        ([], {"WOOD": 4, "BRICK": 4, "SHEEP": 4, "WHEAT": 4, "ORE": 4}),
        (["3:1"], {"WOOD": 3, "BRICK": 3, "SHEEP": 3, "WHEAT": 3, "ORE": 3}),
        (["WOOD"], {"WOOD": 2, "BRICK": 4, "SHEEP": 4, "WHEAT": 4, "ORE": 4}),
        (["3:1", "ORE"], {"WOOD": 3, "BRICK": 3, "SHEEP": 3, "WHEAT": 3, "ORE": 2}),
    ],
)
def test_port_access(ports, expected):
    assert port_access(blank_state(me_ports=ports), "me") == expected


def engine_rates(game, color):
    rates = {}
    for act in legal_actions(game):
        if act.action_type == ActionType.MARITIME_TRADE:
            give = [r for r in act.value[:4] if r is not None]
            rates[give[0]] = min(rates.get(give[0], 9), len(give))
    return rates


def test_matches_engine_across_random_games():
    checks = 0
    for seed in range(1, 31):
        game = new_game(seed, SEATS if seed % 2 else SEATS[::-1])
        agents = {c: RandomAgent(seed * 3 + i) for i, c in enumerate(SEATS)}
        while game.winning_color() is None and game.state.num_turns < 300:
            st = game.state
            color = st.current_color()
            opp = next(c for c in st.colors if c != color)
            state = extract_state(game, color)
            acts = legal_actions(game)
            if st.current_prompt == ActionPrompt.BUILD_INITIAL_SETTLEMENT:
                assert buildable_nodes(state, "me") == sorted(a.value for a in acts)
                checks += 1
            elif st.current_prompt == ActionPrompt.BUILD_INITIAL_ROAD:
                assert buildable_edges(state, "me") == sorted(edge_key(*a.value) for a in acts)
                checks += 1
            elif st.current_prompt == ActionPrompt.PLAY_TURN and not st.is_road_building:
                for side, col in (("me", color), ("opp", opp)):
                    assert buildable_nodes(state, side) == st.board.buildable_node_ids(col)
                    assert buildable_edges(state, side) == sorted(st.board.buildable_edges(col))
                hand = state["me"]["hand"]
                for res, ratio in engine_rates(game, color).items():
                    assert port_access(state, "me")[res] == ratio
                    assert hand[res] >= ratio
                checks += 1
            apply(game, agents[color].decide(state, acts))
    assert checks > 1000
