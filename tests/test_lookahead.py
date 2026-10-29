from catanatron.models.enums import Action, ActionType
from catanatron.models.player import Color

from src.agents.agent_a import GreedyAgent
from src.agents.agent_b import StrategicAgent
from src.agents.archetypes import by_name
from src.agents.lookahead import after, pay, produce
from src.common.board import buildable_edges
from src.common.engine import extract_state, legal_actions, new_game, play_game, step
from src.common.probability import expected_production

RED = Color.RED
BANK = {r: 4 for r in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE")}


def act(kind, value=None):
    return Action(RED, kind, value)


def after_setup(seed):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.state.is_initial_build_phase:
        color = game.state.current_color()
        step(game, agent.decide(extract_state(game, color), legal_actions(game)))
    return extract_state(game, game.state.colors[0])


def hand(**counts):
    return {r: counts.get(r, 0) for r in BANK}


def agent_on(state, plan, **kw):
    agent = StrategicAgent(**kw)
    agent.planner.update(state)
    agent.planner.placed = True
    agent.planner.plan, agent.planner.arch = plan, by_name(plan)
    agent.planner.last_check = state["turn"]
    return agent


def test_pay_takes_exact_cost():
    assert pay(hand(WHEAT=2, ORE=3, WOOD=1), "city", BANK) == hand(WOOD=1)


def test_pay_covers_shortfall_with_trades():
    out = pay(hand(WHEAT=2, ORE=2, WOOD=4), "city", BANK)
    assert out == hand()


def test_after_city_and_trade():
    state = after_setup(1)
    node = state["me"]["settlements"][0]
    state["me"]["hand"] = hand(WHEAT=2, ORE=3, WOOD=4)
    built = after(state, act(ActionType.BUILD_CITY, node))
    assert node in built["me"]["cities"] and node not in built["me"]["settlements"]
    assert built["me"]["hand"] == hand(WOOD=4)
    traded = after(state, act(ActionType.MARITIME_TRADE, ("WOOD",) * 4 + ("SHEEP",)))
    assert traded["me"]["hand"] == hand(WHEAT=2, ORE=3, SHEEP=1)
    assert state["me"]["hand"] == hand(WHEAT=2, ORE=3, WOOD=4)


def test_produce_adds_two_rolls_of_income():
    state = after_setup(2)
    prod = expected_production(state, "me")
    out = produce(state)
    assert all(abs(out["me"]["hand"][r] - state["me"]["hand"][r] - 2 * prod[r]) < 1e-9 for r in BANK)


def test_only_runs_on_build_decisions():
    state = after_setup(3)
    look = StrategicAgent().look
    assert look.applies(state, [act(ActionType.END_TURN), act(ActionType.BUY_DEVELOPMENT_CARD)])
    assert not look.applies(state, [act(ActionType.ROLL)])
    assert not look.applies(state, [act(ActionType.END_TURN), act(ActionType.MOVE_ROBBER, ((0, 0, 0), None, None))])
    assert not look.applies(dict(state, phase="placement"), [act(ActionType.END_TURN)])


def test_horizon_zero_changes_nothing():
    state = after_setup(4)
    state["me"]["hand"] = hand(WOOD=2, BRICK=2, SHEEP=1, WHEAT=1, ORE=1)
    agent = agent_on(state, "expansion", horizon=0)
    acts = [act(ActionType.END_TURN), act(ActionType.BUY_DEVELOPMENT_CARD)]
    arch = agent.planner.arch
    raw = [agent.score(state, a, arch, arch.action_weights(state), arch.next_milestone(state), {}) for a in acts]
    assert agent.scores(state, acts) == raw


def test_choice_stays_on_shortlist():
    state = after_setup(5)
    state["me"]["hand"] = hand(WOOD=3, BRICK=3, SHEEP=1, WHEAT=1, ORE=1)
    agent = agent_on(state, "expansion", top_k=1)
    acts = [act(ActionType.END_TURN)] + [act(ActionType.BUILD_ROAD, e) for e in buildable_edges(state, "me")]
    arch = agent.planner.arch
    raw = [agent.score(state, a, arch, arch.action_weights(state), arch.next_milestone(state), {}) for a in acts]
    out = agent.scores(state, acts)
    top = max(range(1, len(acts)), key=lambda i: raw[i])
    keep = {0, top} if raw[top] > agent.base.w["pass"] else {0}
    low = min(out[i] for i in keep)
    assert all(out[i] < low for i in range(len(acts)) if i not in keep)


def test_hoarding_costs_discard_risk():
    state = after_setup(6)
    look = StrategicAgent().look
    assert look.discard_cost(dict(state, me=dict(state["me"], hand=hand(WOOD=7)))) == 0
    assert look.discard_cost(dict(state, me=dict(state["me"], hand=hand(WOOD=8)))) > 0


def test_rollout_does_not_touch_real_state():
    state = after_setup(7)
    state["me"]["hand"] = hand(WOOD=2, BRICK=2, SHEEP=2, WHEAT=2, ORE=3)
    before = repr(state)
    agent = agent_on(state, "cities_and_roads")
    agent.scores(state, [act(ActionType.END_TURN), act(ActionType.BUILD_CITY, state["me"]["settlements"][0])])
    assert repr(state) == before


def test_games_with_lookahead_are_reproducible():
    one = play_game(StrategicAgent(horizon=3), GreedyAgent(), seed=13)
    two = play_game(StrategicAgent(horizon=3), GreedyAgent(), seed=13)
    assert one["rolls"] == two["rolls"] and one["winner"] == two["winner"]
