from collections import Counter

import pytest
from catanatron.models.enums import Action, ActionType
from catanatron.state_functions import (
    get_actual_victory_points,
    get_longest_road_color,
    player_key,
    player_num_resource_cards,
)

from src.agents.baselines import RandomAgent
from src.common.engine import (
    DEV_PLAYS,
    SEATS,
    board_hash,
    extract_state,
    legal_actions,
    new_game,
    play_game,
    step,
)
from tests.helpers import build_cut_scenario, cut_road, first_of, play_setup, refresh, set_hand, start_turn_of
from tests.helpers import new_game as raw_game

CARDS = {card: atype for atype, card in DEV_PLAYS.items()}


def ready_game():
    game = raw_game()
    play_setup(game)
    p1 = game.state.colors[0]
    start_turn_of(game, p1)
    return game, p1


def buy(game, color, card):
    game.state.development_listdeck.append(card)
    set_hand(game, color, WOOD=1, BRICK=1, SHEEP=1, WHEAT=1, ORE=1)
    game.execute(first_of(game, ActionType.BUY_DEVELOPMENT_CARD))


def grant(game, color, card):
    key = player_key(game.state, color)
    game.state.player_state[f"{key}_{card}_IN_HAND"] += 1
    refresh(game)


def first_of_legal(game, action_type):
    return next(a for a in legal_actions(game) if a.action_type == action_type)


def same(a, b):
    if a.action_type == ActionType.BUILD_ROAD == b.action_type:
        return a.color == b.color and set(a.value) == set(b.value)
    return a == b


def wrapped(game, act):
    step(game, next((a for a in legal_actions(game) if same(a, act)), act))


def offered(game, card):
    return any(a.action_type == CARDS[card] for a in legal_actions(game))


@pytest.mark.parametrize("card", list(CARDS))
def test_dev_card_not_playable_on_turn_bought(card):
    game, p1 = ready_game()
    buy(game, p1, card)
    assert any(a.action_type == CARDS[card] for a in game.state.playable_actions)
    assert not offered(game, card)


@pytest.mark.parametrize("card", list(CARDS))
def test_dev_card_playable_next_turn(card):
    game, p1 = ready_game()
    buy(game, p1, card)
    start_turn_of(game, game.state.colors[1])
    start_turn_of(game, p1)
    assert offered(game, card)


def test_card_owned_before_turn_still_playable_after_buying_another():
    game, p1 = ready_game()
    grant(game, p1, "KNIGHT")
    buy(game, p1, "KNIGHT")
    assert offered(game, "KNIGHT")


def test_knight_bought_last_turn_playable_before_roll():
    game, p1 = ready_game()
    buy(game, p1, "KNIGHT")
    start_turn_of(game, game.state.colors[1])
    game.execute(first_of(game, ActionType.END_TURN))
    assert any(a.action_type == ActionType.ROLL for a in legal_actions(game))
    assert offered(game, "KNIGHT")


def test_victory_point_card_counts_immediately():
    game, p1 = ready_game()
    vp = get_actual_victory_points(game.state, p1)
    buy(game, p1, "VICTORY_POINT")
    assert get_actual_victory_points(game.state, p1) == vp + 1


def test_only_one_dev_card_per_turn():
    game, p1 = ready_game()
    grant(game, p1, "KNIGHT")
    grant(game, p1, "MONOPOLY")
    game.execute(first_of(game, ActionType.PLAY_KNIGHT_CARD))
    game.execute(game.state.playable_actions[0])
    assert not offered(game, "MONOPOLY")
    assert not offered(game, "KNIGHT")


def test_road_building_needs_no_road_money():
    game, p1 = ready_game()
    grant(game, p1, "ROAD_BUILDING")
    set_hand(game, p1)
    assert offered(game, "ROAD_BUILDING")


def test_road_building_grants_two_free_roads():
    game, p1 = ready_game()
    grant(game, p1, "ROAD_BUILDING")
    set_hand(game, p1)
    roads = len(game.state.buildings_by_color[p1]["ROAD"])
    step(game, first_of_legal(game, ActionType.PLAY_ROAD_BUILDING))
    for _ in range(2):
        acts = legal_actions(game)
        assert acts and all(a.action_type == ActionType.BUILD_ROAD for a in acts)
        step(game, acts[0])
    assert not game.state.is_road_building
    assert len(game.state.buildings_by_color[p1]["ROAD"]) == roads + 2
    assert player_num_resource_cards(game.state, p1) == 0
    assert any(a.action_type == ActionType.END_TURN for a in legal_actions(game))


def test_road_building_stops_when_out_of_roads():
    game, p1 = ready_game()
    grant(game, p1, "ROAD_BUILDING")
    key = player_key(game.state, p1)
    game.state.player_state[f"{key}_ROADS_AVAILABLE"] = 1
    step(game, first_of_legal(game, ActionType.PLAY_ROAD_BUILDING))
    step(game, legal_actions(game)[0])
    assert not game.state.is_road_building
    assert game.state.free_roads_available == 0


def test_paid_road_after_road_building_is_normal():
    game, p1 = ready_game()
    grant(game, p1, "ROAD_BUILDING")
    step(game, first_of_legal(game, ActionType.PLAY_ROAD_BUILDING))
    step(game, legal_actions(game)[0])
    step(game, legal_actions(game)[0])
    set_hand(game, p1, WOOD=1, BRICK=1)
    step(game, first_of_legal(game, ActionType.BUILD_ROAD))
    assert not game.state.is_road_building
    assert any(a.action_type == ActionType.END_TURN for a in legal_actions(game))


def test_cut_road_below_five_clears_longest_road():
    game, p1, p2 = build_cut_scenario(wrapped)
    assert get_longest_road_color(game.state) == p1
    vp = get_actual_victory_points(game.state, p1)
    cut_road(game, p2, wrapped)
    assert get_longest_road_color(game.state) is None
    assert game.state.board.road_color is None
    assert get_actual_victory_points(game.state, p1) == vp - 2
    assert game.state.player_state[f"{player_key(game.state, p1)}_HAS_ROAD"] is False


def test_rejects_illegal_action():
    game, p1 = ready_game()
    with pytest.raises(ValueError):
        step(game, Action(p1, ActionType.BUILD_CITY, 99))


def test_seat_order_is_forced():
    for order in (SEATS, SEATS[::-1]):
        game = new_game(5, order)
        assert game.state.colors == order
        assert legal_actions(game)[0].color == order[0]


def test_same_seed_same_board_across_seat_swap():
    a = new_game(5)
    b = new_game(5, SEATS[::-1])
    c = new_game(6)
    assert board_hash(a) == board_hash(b)
    assert board_hash(a) != board_hash(c)
    assert a.state.development_listdeck == b.state.development_listdeck


def test_seed_zero_is_reproducible():
    assert board_hash(new_game(0)) == board_hash(new_game(0))


def test_dice_stream_independent_of_agents():
    one = play_game(RandomAgent(1), RandomAgent(2), seed=11)
    two = play_game(RandomAgent(3), RandomAgent(4), seed=11, swap_order=True)
    n = min(len(one["rolls"]), len(two["rolls"]))
    assert n > 30
    assert one["rolls"][:n] == two["rolls"][:n]
    assert one["seat_order"] == ["a", "b"] and two["seat_order"] == ["b", "a"]


def test_play_game_is_reproducible():
    one = play_game(RandomAgent(1), RandomAgent(2), seed=12)
    two = play_game(RandomAgent(1), RandomAgent(2), seed=12)
    assert one == two
    assert one["winner"] in ("a", "b")
    assert one["final_vp"][one["winner"]] >= 10


def test_extract_state_hides_opponent_info():
    game, p1 = ready_game()
    p2 = game.state.colors[1]
    grant(game, p2, "VICTORY_POINT")
    game.state.player_state[f"{player_key(game.state, p2)}_ACTUAL_VICTORY_POINTS"] += 1
    grant(game, p2, "KNIGHT")
    st = extract_state(game, p1)
    assert set(st) == {
        "turn", "phase", "seat", "board", "robber_hex", "me", "opp", "bank",
        "dev_deck_remaining", "longest_road_holder", "largest_army_holder",
    }
    assert set(st["opp"]) == {
        "settlements", "cities", "roads", "knights_played", "road_length", "ports",
        "hand_size", "dev_cards_count", "visible_vp",
    }
    assert st["opp"]["dev_cards_count"] == 2
    assert st["opp"]["visible_vp"] == get_actual_victory_points(game.state, p2) - 1
    mine = extract_state(game, p2)
    assert mine["me"]["vp"] == get_actual_victory_points(game.state, p2)
    assert mine["me"]["dev_cards"]["VICTORY_POINT"] == 1


def test_extract_state_board_shape():
    game, p1 = ready_game()
    board = extract_state(game, p1)["board"]
    assert len(board["hexes"]) == 19
    assert len(board["nodes"]) == 54
    assert len(board["edges"]) == 72
    assert len(board["ports"]) == 9
    assert Counter(p["resource"] for p in board["ports"])["3:1"] == 4
    assert Counter(h["resource"] for h in board["hexes"])["DESERT"] == 1
