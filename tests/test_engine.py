import pytest
from catanatron.models.enums import ActionType
from catanatron.state_functions import get_actual_victory_points, player_key

from src.common.engine import DEV_PLAYS, legal_actions
from tests.helpers import first_of, new_game, play_setup, refresh, set_hand, start_turn_of

CARDS = {card: atype for atype, card in DEV_PLAYS.items()}


def ready_game():
    game = new_game()
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
