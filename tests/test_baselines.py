from collections import Counter

from catanatron.models.enums import Action, ActionType
from catanatron.models.player import Color

from src.agents.baselines import RandomAgent, VictoryPointAgent, WeightedRandomAgent, vp_gain
from src.common.engine import play_game
from tests.helpers import blank_state

RED = Color.RED


def act(kind, value=None):
    return Action(RED, kind, value)


def test_weighted_random_prefers_cities():
    agent = WeightedRandomAgent(seed=1)
    acts = [act(ActionType.END_TURN), act(ActionType.BUILD_CITY, 3), act(ActionType.BUILD_SETTLEMENT, 7)]
    picks = Counter(agent.decide({}, acts).action_type for _ in range(2000))
    assert picks[ActionType.BUILD_CITY] > picks[ActionType.BUILD_SETTLEMENT] > picks[ActionType.END_TURN]


def test_vp_agent_takes_points():
    agent = VictoryPointAgent(seed=1)
    state = blank_state()
    acts = [act(ActionType.END_TURN), act(ActionType.BUY_DEVELOPMENT_CARD), act(ActionType.BUILD_CITY, 3)]
    assert agent.decide(state, acts).action_type == ActionType.BUILD_CITY


def test_vp_gain_for_longest_road():
    state = blank_state(me_roads=[(0, 1), (1, 2), (2, 3), (3, 4)], me_settlements=[0])
    state["longest_road_holder"] = None
    assert vp_gain(state, act(ActionType.BUILD_ROAD, (4, 5))) == 2
    state["opp"]["road_length"] = 5
    assert vp_gain(state, act(ActionType.BUILD_ROAD, (4, 5))) == 0
    state["opp"]["road_length"] = 0
    state["longest_road_holder"] = "me"
    assert vp_gain(state, act(ActionType.BUILD_ROAD, (4, 5))) == 0


def test_vp_gain_for_largest_army():
    state = blank_state()
    state["largest_army_holder"] = None
    state["me"]["knights_played"] = 2
    assert vp_gain(state, act(ActionType.PLAY_KNIGHT_CARD)) == 2
    state["opp"]["knights_played"] = 3
    state["largest_army_holder"] = "opp"
    assert vp_gain(state, act(ActionType.PLAY_KNIGHT_CARD)) == 0
    state["me"]["knights_played"] = 3
    assert vp_gain(state, act(ActionType.PLAY_KNIGHT_CARD)) == 2


def win_rate(make_a, make_b, games=60):
    wins = 0
    for seed in range(1, games + 1):
        log = play_game(make_a(seed), make_b(seed + 1000), seed, swap_order=seed % 2 == 0)
        wins += log["winner"] == "a"
    return wins / games


def test_vp_agent_beats_random():
    assert win_rate(VictoryPointAgent, RandomAgent, games=200) > 0.58


def test_weighted_random_completes_games():
    assert 0.3 < win_rate(WeightedRandomAgent, RandomAgent, games=40) < 0.8
