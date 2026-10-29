from catanatron.models.enums import Action, ActionType
from catanatron.models.player import Color

from src.agents.agent_a import GreedyAgent
from src.agents.agent_b import StrategicAgent
from src.agents.archetypes import DevRush
from src.agents.opponent import OpponentModel
from src.agents.reactor import RACE_VP, Race, Reactor, army_steal, combined, fastest, road_steal
from src.agents.registry import VARIANTS, describe, make_agent
from src.common.engine import extract_state, legal_actions, new_game, play_game, step


def after_setup(seed):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.state.is_initial_build_phase:
        color = game.state.current_color()
        step(game, agent.decide(extract_state(game, color), legal_actions(game)))
    return extract_state(game, game.state.colors[0])


def near_win(state, vp=RACE_VP):
    return dict(state, opp=dict(state["opp"], visible_vp=vp, dev_cards_count=0))


def test_combined_cost():
    assert combined(("road", 2), ("settlement", 1)) == {"WOOD": 3, "BRICK": 3, "SHEEP": 1, "WHEAT": 1}


def test_race_only_when_opponent_close():
    state = after_setup(1)
    model = OpponentModel().update(state)
    reactor = Reactor()
    arch = DevRush()
    assert reactor.override(state, arch, model) is arch
    assert reactor.race_from is None
    race = reactor.override(near_win(state), arch, model)
    assert isinstance(race, Race) and reactor.race_from == state["turn"]
    assert reactor.override(dict(near_win(state), phase="placement"), arch, model) is arch


def test_race_uses_hidden_vp_estimate():
    state = after_setup(2)
    model = OpponentModel().update(state)
    close = dict(state, opp=dict(state["opp"], visible_vp=RACE_VP - 1, dev_cards_count=10))
    assert model.estimated_vp(close) >= RACE_VP
    assert isinstance(Reactor().override(close, DevRush(), model), Race)


def test_race_without_model_uses_visible_vp():
    state = after_setup(3)
    assert isinstance(Reactor().override(near_win(state), DevRush(), None), Race)


def test_race_milestone_is_fastest_vp():
    state = after_setup(4)
    state["me"]["hand"] = {"WOOD": 0, "BRICK": 0, "SHEEP": 0, "WHEAT": 2, "ORE": 3}
    assert fastest(state) == "city"
    race = Race(DevRush())
    assert race.next_milestone(state) == "city"
    assert race.action_weights(state)["dev_card"] < race.action_weights(state)["city"]


def test_army_steal_needs_a_knight_in_hand():
    state = after_setup(5)
    state["opp"]["knights_played"] = 2
    state["me"]["knights_played"] = 2
    assert not army_steal(state)
    state["me"]["dev_cards"] = dict(state["me"]["dev_cards"], KNIGHT=1)
    assert army_steal(state)
    assert fastest(state) == "knight"


def test_road_steal_within_two_roads():
    state = after_setup(6)
    state["opp"]["road_length"] = 4
    state["longest_road_holder"] = None
    need = road_steal(state)
    assert need is None or 0 < need <= 2


def test_variants_are_registered_with_names():
    for name, kw in VARIANTS.items():
        agent = make_agent(name, 1)
        assert agent.name == name
        assert describe(name)["config"] == kw
    assert make_agent("strategic_no_lookahead", 1).look.horizon == 0
    assert make_agent("strategic_no_opp_model", 1).model is None
    assert make_agent("strategic_no_replan", 1).planner.replan is False
    assert make_agent("strategic_no_reactor", 1).reactor is None
    assert make_agent("strategic_placement_only", 1).placement_only


def test_placement_only_plays_greedy_after_setup():
    state = after_setup(7)
    agent = StrategicAgent(placement_only=True)
    agent.observe(state)
    assert agent.planner.replan is False
    opts = [Action(Color.RED, ActionType.END_TURN, None), Action(Color.RED, ActionType.BUY_DEVELOPMENT_CARD, None)]
    assert agent.scores(state, opts) == GreedyAgent().scores(state, opts)


def test_every_variant_finishes_games():
    for name in VARIANTS:
        log = play_game(make_agent(name, 1), GreedyAgent(), seed=21)
        assert log["winner"] in ("a", "b")
        assert log["agents"]["a"] == name
