from collections import Counter

from catanatron.models.enums import ActionType
from catanatron.state_functions import get_dev_cards_in_hand

DEV_PLAYS = {
    ActionType.PLAY_KNIGHT_CARD: "KNIGHT",
    ActionType.PLAY_YEAR_OF_PLENTY: "YEAR_OF_PLENTY",
    ActionType.PLAY_MONOPOLY: "MONOPOLY",
    ActionType.PLAY_ROAD_BUILDING: "ROAD_BUILDING",
}


def bought_this_turn(game, color):
    bought = Counter()
    for act in reversed(game.state.actions):
        if act.action_type == ActionType.END_TURN:
            break
        if act.color == color and act.action_type == ActionType.BUY_DEVELOPMENT_CARD:
            bought[act.value] += 1
    return bought


def can_play_dev(game, color, card):
    return get_dev_cards_in_hand(game.state, color, card) - bought_this_turn(game, color)[card] >= 1


def legal_actions(game):
    acts = []
    for act in game.state.playable_actions:
        card = DEV_PLAYS.get(act.action_type)
        if card and not can_play_dev(game, act.color, card):
            continue
        acts.append(act)
    return acts
