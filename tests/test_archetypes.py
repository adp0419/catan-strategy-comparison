import pytest

from src.agents.agent_a import GreedyAgent
from src.agents.archetypes import (
    ACTIONS,
    BALANCED,
    CitiesAndRoads,
    DevRush,
    Expansion,
    LongestRoad,
    OreWheatSheep,
    PortPlay,
    all_archetypes,
    by_name,
    fit,
    production_pips,
    viabilities,
)
from src.common.board import RESOURCES, adjacent_nodes, distance_rule_ok, node_ports
from src.common.engine import extract_state, legal_actions, new_game, step
from src.common.probability import node_production
from tests.helpers import blank_state

SEEDS = range(1, 11)


def opening(seed):
    game = new_game(seed)
    return extract_state(game, game.state.current_color())


def after_setup(seed):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.state.is_initial_build_phase:
        color = game.state.current_color()
        step(game, agent.decide(extract_state(game, color), legal_actions(game)))
    return extract_state(game, game.state.colors[0])


def share(pips, resources):
    total = sum(pips.values())
    return sum(pips[r] for r in resources) / total


def rich_node(state, resource):
    board = state["board"]
    return max(range(len(board["nodes"])), key=lambda n: (node_production(board, n)[resource], -n))


@pytest.mark.parametrize("state_of", [opening, after_setup])
def test_every_archetype_answers_the_interface(state_of):
    state = state_of(3)
    for arch in all_archetypes():
        assert arch.viability(state) >= 0
        assert set(arch.action_weights(state)) == set(ACTIONS)
        assert isinstance(arch.next_milestone(state), str)
        assert isinstance(arch.is_dead(state), bool)
        assert set(arch.target_profile(state)) <= set(RESOURCES)


def test_names_are_unique_and_lookup_works():
    names = [a.name for a in all_archetypes()]
    assert len(names) == len(set(names)) == 6
    assert all(by_name(n).name == n for n in names)
    assert set(viabilities(opening(1))) == set(names)


def test_projection_places_two_legal_settlements():
    state = opening(2)
    for arch in all_archetypes():
        picks = arch.projected(state)["me"]["settlements"]
        assert len(picks) == 2
        assert picks[1] not in adjacent_nodes(state["board"], picks[0])
        assert distance_rule_ok(state, picks[0]) and distance_rule_ok(state, picks[1])


def test_no_projection_after_placement():
    state = after_setup(2)
    assert Expansion().projected(state) is state


def test_projections_chase_their_own_resources():
    for seed in SEEDS:
        state = opening(seed)
        ows = production_pips(OreWheatSheep().projected(state))
        exp = production_pips(Expansion().projected(state))
        road = production_pips(LongestRoad().projected(state))
        assert share(ows, ["ORE", "WHEAT"]) > share(exp, ["ORE", "WHEAT"])
        assert share(road, ["WOOD", "BRICK"]) > share(ows, ["WOOD", "BRICK"])


def test_fit_rewards_matching_mix_only():
    balanced = {r: 5.0 for r in RESOURCES}
    lumber = {"WOOD": 9.0, "BRICK": 8.0, "SHEEP": 4.0, "WHEAT": 4.0, "ORE": 0.0}
    assert fit(balanced, BALANCED) == pytest.approx(25.0)
    assert fit(balanced, Expansion.profile) < 25.0
    assert fit(lumber, Expansion.profile) > sum(lumber.values())
    assert fit(lumber, OreWheatSheep.profile) < sum(lumber.values())


def test_wood_brick_board_prefers_expansion_over_ows():
    state = blank_state()
    state["me"]["settlements"] = [rich_node(state, "WOOD"), rich_node(state, "BRICK")]
    assert Expansion().viability(state) > OreWheatSheep().viability(state)
    assert LongestRoad().viability(state) > DevRush().viability(state)


def test_ore_wheat_board_prefers_ows_over_expansion():
    state = blank_state()
    state["me"]["settlements"] = [rich_node(state, "ORE"), rich_node(state, "WHEAT")]
    assert OreWheatSheep().viability(state) > Expansion().viability(state)
    assert OreWheatSheep().viability(state) > LongestRoad().viability(state)


def test_ows_dead_without_ore():
    state = blank_state()
    board = state["board"]
    node = next(n for n in range(len(board["nodes"])) if node_production(board, n)["ORE"] == 0 and node_production(board, n)["WHEAT"] > 0)
    state["me"]["settlements"] = [node]
    assert OreWheatSheep().is_dead(state)
    state["me"]["settlements"].append(rich_node(state, "ORE"))
    assert not OreWheatSheep().is_dead(state)


def test_dev_rush_dies_with_the_deck():
    state = after_setup(4)
    assert not DevRush().is_dead(state)
    assert DevRush().next_milestone(state) == "dev_card"
    state["dev_deck_remaining"] = 0
    assert DevRush().is_dead(state)
    assert DevRush().viability(state) == 0


def test_cities_and_roads_never_dies():
    state = after_setup(5)
    state["dev_deck_remaining"] = 0
    state["me"]["roads"] = [tuple(e) for e in state["board"]["edges"][:15]]
    assert not CitiesAndRoads().is_dead(state)


def test_longest_road_dead_when_out_of_roads():
    state = after_setup(6)
    assert not LongestRoad().is_dead(state)
    state["me"]["roads"] = list(state["me"]["roads"]) + [(i, -i) for i in range(1, 14)]
    assert LongestRoad().is_dead(state)


def test_ows_milestone_is_city():
    assert OreWheatSheep().next_milestone(after_setup(7)) == "city"


def test_expansion_milestone_points_at_a_node():
    state = after_setup(8)
    mile = Expansion().next_milestone(state)
    assert mile == "settlement" or mile.startswith("reach_node_")


def test_placement_milestone_is_settlement():
    assert all(a.next_milestone(opening(1)) == "settlement" for a in all_archetypes())


def test_port_play_targets_owned_matching_port():
    state = blank_state()
    ports = node_ports(state["board"])
    res, port_node = next((p, n) for n, p in sorted(ports.items()) if p in RESOURCES)
    state["me"]["settlements"] = [port_node, rich_node(state, res)]
    pips = production_pips(state)
    if pips[res] < 8:
        state["me"]["cities"] = [rich_node(state, res)]
        state["me"]["settlements"] = [port_node]
    arch = PortPlay()
    assert arch.target(state) == res
    assert arch.target_profile(state)[res] == max(arch.target_profile(state).values())
    assert not arch.is_dead(state)


def test_port_play_dead_once_ports_are_taken():
    state = after_setup(10)
    taken = [n for n, p in node_ports(state["board"]).items() if p in RESOURCES]
    state["opp"]["settlements"] = list(state["opp"]["settlements"]) + taken
    state["me"]["settlements"] = [n for n in state["me"]["settlements"] if n not in taken]
    assert PortPlay().is_dead(state)
    assert PortPlay().viability(state) == 0


def test_action_weights_tilt_the_right_way():
    state = after_setup(9)
    ows = OreWheatSheep().action_weights(state)
    road = LongestRoad().action_weights(state)
    dev = DevRush().action_weights(state)
    assert ows["city"] > ows["road"]
    assert road["road"] > road["city"]
    assert dev["dev_card"] == max(dev.values())
