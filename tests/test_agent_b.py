from catanatron.models.enums import Action, ActionType
from catanatron.models.player import Color

from src.agents.agent_a import GreedyAgent, with_road
from src.agents.agent_b import MILESTONE_BONUS, StrategicAgent
from src.agents.archetypes import by_name
from src.agents.baselines import RandomAgent
from src.agents.registry import make_agent
from src.common.board import buildable_edges, road_distance
from src.common.engine import extract_state, legal_actions, new_game, play_game, step
from src.sim.match import summarize

RED = Color.RED


def act(kind, value=None):
    return Action(RED, kind, value)


def after_setup(seed):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.state.is_initial_build_phase:
        color = game.state.current_color()
        step(game, agent.decide(extract_state(game, color), legal_actions(game)))
    return extract_state(game, game.state.colors[0])


def agent_on(state, plan, **kw):
    agent = StrategicAgent(**kw)
    agent.planner.update(state)
    agent.planner.placed = True
    agent.planner.plan, agent.planner.arch = plan, by_name(plan)
    agent.planner.last_check = state["turn"]
    return agent


def parts(agent, state):
    arch = agent.planner.arch
    return arch, arch.action_weights(state), arch.next_milestone(state)


def test_registry_builds_strategic():
    assert make_agent("strategic", 1).name == "strategic"
    assert make_agent(("strategic", {"replan": False}), 1).planner.replan is False


def test_plays_legal_games_and_reports_plans():
    log = play_game(StrategicAgent(), RandomAgent(3), seed=11)
    assert log["winner"] == "a"
    plan = log["plans"]["a"]
    assert plan["start"] and plan["final"] and plan["checks"] >= 2
    assert "b" not in log["plans"]


def test_same_seed_same_game():
    one = play_game(StrategicAgent(), GreedyAgent(), seed=12)
    two = play_game(StrategicAgent(), GreedyAgent(), seed=12)
    assert one["rolls"] == two["rolls"] and one["winner"] == two["winner"] and one["plans"] == two["plans"]


def test_beats_random():
    logs = [play_game(StrategicAgent(), RandomAgent(s), seed=s, swap_order=s % 2 == 1) for s in range(20, 30)]
    assert summarize(logs)["a_rate"] >= 0.9


def test_city_milestone_gets_bonus():
    state = after_setup(1)
    agent = agent_on(state, "ore_wheat_sheep")
    arch, weights, mile = parts(agent, state)
    assert mile == "city"
    node = state["me"]["settlements"][0]
    city = act(ActionType.BUILD_CITY, node)
    base = agent.base.score(state, city, {})
    assert agent.score(state, city, arch, weights, mile, {}) == base * weights["city"] + MILESTONE_BONUS


def test_negative_scores_are_not_amplified():
    state = after_setup(2)
    agent = agent_on(state, "port_play")
    arch, weights, mile = parts(agent, state)
    me = state["me"]["settlements"][0]
    own_hex = next(h for h in state["board"]["hexes"] if me in h["nodes"] and h["resource"] != "DESERT")
    robber = act(ActionType.MOVE_ROBBER, (tuple(own_hex["coord"]), None, None))
    base = agent.base.score(state, robber, {})
    assert base < 0
    assert agent.score(state, robber, arch, weights, mile, {}) == base


def test_road_toward_target_gets_bonus():
    state = after_setup(3)
    agent = agent_on(state, "expansion")
    node = next(n for n in range(len(state["board"]["nodes"])) if road_distance(state, "me", n) == 2)
    mile = f"reach_node_{node}"
    roads = buildable_edges(state, "me")
    closer = [e for e in roads if road_distance(with_road(state, e), "me", node) < 2]
    away = [e for e in roads if road_distance(with_road(state, e), "me", node) >= 2]
    assert closer and away
    assert agent.milestone_bonus(state, act(ActionType.BUILD_ROAD, closer[0]), "road", mile) == MILESTONE_BONUS / 2
    assert agent.milestone_bonus(state, act(ActionType.BUILD_ROAD, away[0]), "road", mile) == 0


def test_trade_that_completes_milestone_gets_bonus():
    state = after_setup(4)
    agent = agent_on(state, "ore_wheat_sheep")
    state["me"]["hand"] = {"WOOD": 4, "BRICK": 0, "SHEEP": 0, "WHEAT": 2, "ORE": 2}
    good = act(ActionType.MARITIME_TRADE, ("WOOD",) * 4 + ("ORE",))
    bad = act(ActionType.MARITIME_TRADE, ("WOOD",) * 4 + ("SHEEP",))
    assert agent.milestone_bonus(state, good, "trade", "city") == MILESTONE_BONUS
    assert agent.milestone_bonus(state, bad, "trade", "city") == 0


def test_no_bonus_during_placement():
    game = new_game(5)
    state = extract_state(game, game.state.current_color())
    agent = StrategicAgent()
    agent.planner.update(state)
    settle = next(a for a in legal_actions(game) if a.action_type == ActionType.BUILD_SETTLEMENT)
    assert agent.milestone_bonus(state, settle, "settlement", "settlement") == 0


def test_placement_mix_changes_opening_choice_only_when_set():
    game = new_game(6)
    state = extract_state(game, game.state.current_color())
    acts = legal_actions(game)
    pure = StrategicAgent(mix=0.0, bonus=0.0)
    pure.planner.update(state)
    arch = pure.planner.arch
    a_scores = GreedyAgent().scores(state, acts)
    b_scores = pure.scores(state, acts)
    w = arch.action_weights(state)["settlement"]
    assert all(abs(b - a * w) < 1e-9 for a, b in zip(a_scores, b_scores))
