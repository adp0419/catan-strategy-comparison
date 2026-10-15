from collections import Counter

import pytest
from catanatron.game import Game
from catanatron.models.enums import ActionPrompt, ActionType, RESOURCES
from catanatron.models.player import RandomPlayer
from catanatron.players.weighted_random import WeightedRandomPlayer
from catanatron.state_functions import (
    get_actual_victory_points,
    get_largest_army,
    get_longest_road_color,
    player_key,
    player_num_resource_cards,
)

from tests.helpers import (
    COLORS,
    extend_road,
    first_of,
    new_game,
    play_setup,
    refresh,
    roll,
    set_hand,
    build_cut_scenario,
    cut_road,
    start_turn_of,
    to_roll_of,
)


def test_two_player_game_completes_with_winner():
    for seed in range(1, 21):
        game = Game([WeightedRandomPlayer(c) for c in COLORS], seed=seed)
        winner = game.play()
        assert winner in COLORS
        assert get_actual_victory_points(game.state, winner) >= 10
        assert len(game.state.colors) == 2


def test_setup_is_snake_order():
    game = new_game()
    play_setup(game)
    p1, p2 = game.state.colors
    builds = [a.color for a in game.state.actions if a.action_type == ActionType.BUILD_SETTLEMENT]
    assert builds == [p1, p2, p2, p1]


def test_only_second_settlement_pays_out():
    game = new_game()
    p1, p2 = game.state.colors
    game.execute(game.state.playable_actions[0])
    assert player_num_resource_cards(game.state, p1) == 0
    play_setup(game)
    for color in (p1, p2):
        second = game.state.buildings_by_color[color]["SETTLEMENT"][1]
        tiles = game.state.board.map.adjacent_tiles[second]
        expected = Counter(t.resource for t in tiles if t.resource is not None)
        for res in RESOURCES:
            assert player_num_resource_cards(game.state, color, res) == expected[res]


def trade_rates(game, color):
    rates = {}
    for act in game.state.playable_actions:
        if act.action_type == ActionType.MARITIME_TRADE:
            give_res = [r for r in act.value[:4] if r is not None]
            rates[give_res[0]] = min(rates.get(give_res[0], 9), len(give_res))
    return rates


def port_node(game, res):
    taken = set(game.state.board.buildings)
    return sorted(n for n in game.state.board.map.port_nodes[res] if n not in taken)[0]


def test_bank_trade_is_four_to_one_without_port():
    game = new_game()
    port_nodes = set().union(*game.state.board.map.port_nodes.values())
    while game.state.is_initial_build_phase:
        acts = game.state.playable_actions
        if acts[0].action_type == ActionType.BUILD_SETTLEMENT:
            acts = [a for a in acts if a.value not in port_nodes]
        game.execute(acts[0])
    p1 = game.state.colors[0]
    start_turn_of(game, p1)
    set_hand(game, p1, WOOD=4)
    assert trade_rates(game, p1) == {"WOOD": 4}


def test_generic_port_is_three_to_one():
    game = new_game()
    p1 = game.state.colors[0]
    play_setup(game, [port_node(game, None)])
    start_turn_of(game, p1)
    set_hand(game, p1, WOOD=3)
    assert trade_rates(game, p1) == {"WOOD": 3}


@pytest.mark.parametrize("res", RESOURCES)
def test_resource_port_is_two_to_one(res):
    game = new_game()
    p1 = game.state.colors[0]
    play_setup(game, [port_node(game, res)])
    start_turn_of(game, p1)
    set_hand(game, p1, **{res: 2})
    assert trade_rates(game, p1) == {res: 2}


def test_seven_forces_discard_then_robber_and_steal():
    game = new_game()
    play_setup(game)
    p1, p2 = game.state.colors
    to_roll_of(game, p1)
    set_hand(game, p1, WOOD=2)
    set_hand(game, p2, WOOD=5, BRICK=4)
    roll(game, (3, 4))

    assert game.state.current_prompt == ActionPrompt.DISCARD
    assert game.state.current_color() == p2
    discards = game.state.playable_actions
    assert len(discards) == 1 and discards[0].value is None
    game.execute(discards[0])
    assert player_num_resource_cards(game.state, p2) == 5
    assert player_num_resource_cards(game.state, p1) == 2

    assert game.state.current_prompt == ActionPrompt.MOVE_ROBBER
    assert game.state.current_color() == p1
    old = game.state.board.robber_coordinate
    moves = game.state.playable_actions
    assert all(m.value[0] != old for m in moves)
    steal = next(m for m in moves if m.value[1] == p2)
    game.execute(steal)
    assert player_num_resource_cards(game.state, p2) == 4
    assert player_num_resource_cards(game.state, p1) == 3


def test_no_discard_at_seven_cards():
    game = new_game()
    play_setup(game)
    p1, p2 = game.state.colors
    to_roll_of(game, p1)
    set_hand(game, p2, WOOD=7)
    roll(game, (3, 4))
    assert game.state.current_prompt == ActionPrompt.MOVE_ROBBER


def test_longest_road_needs_five():
    game = new_game()
    play_setup(game)
    p1, _ = game.state.colors
    start_turn_of(game, p1)
    extend_road(game, p1, 4)
    assert get_longest_road_color(game.state) is None
    vp = get_actual_victory_points(game.state, p1)
    extend_road(game, p1, 5)
    assert get_longest_road_color(game.state) == p1
    assert get_actual_victory_points(game.state, p1) == vp + 2


def test_longest_road_transfers_only_when_beaten():
    game = new_game()
    play_setup(game)
    p1, p2 = game.state.colors
    start_turn_of(game, p1)
    extend_road(game, p1, 5)
    start_turn_of(game, p2)
    extend_road(game, p2, 5)
    assert get_longest_road_color(game.state) == p1
    p1_vp = get_actual_victory_points(game.state, p1)
    p2_vp = get_actual_victory_points(game.state, p2)
    extend_road(game, p2, 6)
    assert get_longest_road_color(game.state) == p2
    assert get_actual_victory_points(game.state, p1) == p1_vp - 2
    assert get_actual_victory_points(game.state, p2) == p2_vp + 2


def play_knight(game, color):
    key = player_key(game.state, color)
    game.state.player_state[f"{key}_KNIGHT_IN_HAND"] += 1
    refresh(game)
    game.execute(first_of(game, ActionType.PLAY_KNIGHT_CARD))
    game.execute(game.state.playable_actions[0])


def test_largest_army_needs_three_and_transfers_on_more():
    game = new_game()
    play_setup(game)
    p1, p2 = game.state.colors
    for _ in range(2):
        start_turn_of(game, p1)
        play_knight(game, p1)
    assert get_largest_army(game.state)[0] is None
    start_turn_of(game, p1)
    vp = get_actual_victory_points(game.state, p1)
    play_knight(game, p1)
    assert get_largest_army(game.state) == (p1, 3)
    assert get_actual_victory_points(game.state, p1) == vp + 2

    for _ in range(3):
        start_turn_of(game, p2)
        play_knight(game, p2)
    assert get_largest_army(game.state)[0] == p1
    start_turn_of(game, p2)
    play_knight(game, p2)
    assert get_largest_army(game.state) == (p2, 4)
    assert get_actual_victory_points(game.state, p1) == vp


def test_dev_deck_is_base_game():
    game = new_game()
    assert Counter(game.state.development_listdeck) == {
        "KNIGHT": 14,
        "VICTORY_POINT": 5,
        "YEAR_OF_PLENTY": 2,
        "ROAD_BUILDING": 2,
        "MONOPOLY": 2,
    }


def test_victory_detected_on_triggering_action():
    game = new_game()
    play_setup(game)
    p1 = game.state.colors[0]
    start_turn_of(game, p1)
    key = player_key(game.state, p1)
    game.state.player_state[f"{key}_ACTUAL_VICTORY_POINTS"] = 9
    game.state.player_state[f"{key}_VICTORY_POINTS"] = 9
    set_hand(game, p1, WHEAT=2, ORE=3)
    assert game.winning_color() is None
    game.execute(first_of(game, ActionType.BUILD_CITY))
    assert game.winning_color() == p1


def test_engine_has_no_player_trade_actions():
    names = {t.name for t in ActionType}
    assert "MARITIME_TRADE" in names
    assert not any("OFFER" in n or "ACCEPT" in n or "DOMESTIC" in n for n in names)


def test_seat_order_is_set_by_seed():
    orders = {Game([RandomPlayer(c) for c in COLORS], seed=s).state.colors for s in range(1, 40)}
    assert len(orders) == 2


def test_dev_card_playable_on_turn_bought():
    game = new_game()
    play_setup(game)
    p1 = game.state.colors[0]
    start_turn_of(game, p1)
    game.state.development_listdeck.append("KNIGHT")
    set_hand(game, p1, SHEEP=1, WHEAT=1, ORE=1)
    game.execute(first_of(game, ActionType.BUY_DEVELOPMENT_CARD))
    assert any(a.action_type == ActionType.PLAY_KNIGHT_CARD for a in game.state.playable_actions)


def test_road_building_requires_road_money():
    game = new_game()
    play_setup(game)
    p1 = game.state.colors[0]
    start_turn_of(game, p1)
    key = player_key(game.state, p1)
    game.state.player_state[f"{key}_ROAD_BUILDING_IN_HAND"] = 1
    set_hand(game, p1)
    assert not any(a.action_type == ActionType.PLAY_ROAD_BUILDING for a in game.state.playable_actions)
    set_hand(game, p1, WOOD=1, BRICK=1)
    assert any(a.action_type == ActionType.PLAY_ROAD_BUILDING for a in game.state.playable_actions)


def raw(game, act):
    game.execute(act, validate_action=False)


def test_cut_road_keeps_longest_road_below_five():
    game, p1, p2 = build_cut_scenario(raw)
    assert get_longest_road_color(game.state) == p1
    cut_road(game, p2, raw)
    assert game.state.board.road_lengths[p1] == 3
    assert get_longest_road_color(game.state) == p1


def test_raw_engine_lets_red_numbers_touch():
    from src.common.engine import red_numbers_touch

    touching = sum(red_numbers_touch(new_game(seed).state.board.map) for seed in range(1, 51))
    assert touching > 0
