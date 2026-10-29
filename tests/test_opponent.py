from catanatron.models.enums import Action, ActionType
from catanatron.models.player import Color
from catanatron.state_functions import player_num_resource_cards

from src.agents.agent_a import GreedyAgent
from src.agents.agent_b import MONOPOLY_MIN, StrategicAgent
from src.agents.opponent import DEV_DECK, OpponentModel, mirror
from src.common.board import RESOURCES
from src.common.engine import extract_state, legal_actions, new_game, play_game, step

RED = Color.RED


def run(seed, turns=500, each=None):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.winning_color() is None and game.state.num_turns < turns:
        color = game.state.current_color()
        state = extract_state(game, color)
        if each:
            each(game, color, state)
        step(game, agent.decide(state, legal_actions(game)))
    return game


def test_log_hides_opponent_dev_cards_only():
    game = run(3)
    me, opp = game.state.colors
    view = extract_state(game, me)["log"]
    buys = [e for e in view if e["action"] == "BUY_DEVELOPMENT_CARD"]
    assert any(e["player"] == "opp" for e in buys) and any(e["player"] == "me" for e in buys)
    assert all(e["value"] is None for e in buys if e["player"] == "opp")
    assert all(e["value"] in DEV_DECK for e in buys if e["player"] == "me")
    theirs = extract_state(game, opp)["log"]
    assert len(theirs) == len(view) == len(game.state.actions)


def test_log_uses_relative_names():
    game = run(3)
    view = extract_state(game, game.state.colors[0])["log"]
    assert {e["player"] for e in view} == {"me", "opp"}
    robs = [e["value"] for e in view if e["action"] == "MOVE_ROBBER"]
    assert robs and all(v[1] in ("me", "opp", None) for v in robs)


def test_hand_tracking_matches_truth():
    hits, total = [0], [0]

    def checker(model):
        def check(game, color, state):
            me, opp = game.state.colors
            if color != me or state["phase"] != "main":
                return
            model.update(state)
            truth = {r: player_num_resource_cards(game.state, opp, r) for r in RESOURCES}
            total[0] += 1
            hits[0] += all(abs(model.hand[r] - truth[r]) < 0.01 for r in RESOURCES)

        return check

    for seed in range(1, 6):
        run(seed, each=checker(OpponentModel()))
    assert total[0] > 300
    assert hits[0] / total[0] >= 0.95


def test_belief_always_sums_to_hand_size():
    def check(game, color, state):
        model = OpponentModel().update(state)
        assert abs(sum(model.hand.values()) - state["opp"]["hand_size"]) < 1e-9
        assert all(v >= 0 for v in model.hand.values())

    run(4, turns=60, each=check)


def test_vp_card_odds_use_my_own_draws():
    model = OpponentModel()
    assert model.vp_card_odds() == 5 / 25
    model.my_draws["VICTORY_POINT"] += 1
    model.my_draws["KNIGHT"] += 2
    assert model.vp_card_odds() == 4 / 22


def test_estimated_vp_adds_hidden_cards():
    game = run(5, turns=150)
    state = extract_state(game, game.state.colors[0])
    model = OpponentModel().update(state)
    expect = state["opp"]["visible_vp"] + state["opp"]["dev_cards_count"] * model.vp_card_odds()
    assert model.estimated_vp(state) == expect


def test_mirror_swaps_sides():
    game = run(6, turns=80)
    state = extract_state(game, game.state.colors[0])
    flip = mirror(state, {r: 1.0 for r in RESOURCES})
    assert flip["me"]["settlements"] == state["opp"]["settlements"]
    assert flip["opp"]["roads"] == state["me"]["roads"]
    assert flip["me"]["hand"] == {r: 1.0 for r in RESOURCES}
    swap = {"me": "opp", "opp": "me", None: None}
    assert flip["longest_road_holder"] == swap[state["longest_road_holder"]]


def test_infers_an_archetype_with_normalized_weights():
    game = run(7, turns=80)
    state = extract_state(game, game.state.colors[0])
    model = OpponentModel().update(state)
    assert model.archetype(state) is not None
    weights = model.key_weights(state)
    assert abs(sum(weights.values()) / len(weights) - 1) < 1e-9


def test_monopoly_uses_tracked_hand():
    agent = StrategicAgent()
    agent.model.hand = {"WOOD": 4.0, "BRICK": 1.0, "SHEEP": 0.0, "WHEAT": 0.0, "ORE": 0.0}
    assert agent.monopoly_value("WOOD") == agent.base.w["monopoly"] * 4.0
    assert agent.monopoly_value("BRICK") == 0
    assert MONOPOLY_MIN > agent.base.w["monopoly_min"]


def test_robber_term_follows_key_resources():
    game = run(8, turns=80)
    state = extract_state(game, game.state.colors[0])
    agent = StrategicAgent()
    agent.model.update(state)
    hit = next(h for h in state["board"]["hexes"] if h["resource"] in RESOURCES and any(n in state["opp"]["settlements"] for n in h["nodes"]))
    move = Action(RED, ActionType.MOVE_ROBBER, (tuple(hit["coord"]), None, None))
    agent.model.key_weights = lambda s: {r: 1.0 for r in RESOURCES}
    assert agent.opponent_term(state, move, "robber") == 0
    agent.model.key_weights = lambda s: {r: 2.0 for r in RESOURCES}
    assert agent.opponent_term(state, move, "robber") > 0
    assert agent.opponent_term(state, move, "settlement") == 0


def test_no_model_ablation():
    agent = StrategicAgent(opp_model=False)
    assert agent.model is None
    log = play_game(agent, GreedyAgent(), seed=14)
    assert log["plans"]["a"]["opp_plan"] is None
    assert play_game(StrategicAgent(), GreedyAgent(), seed=14)["plans"]["a"]["opp_plan"] is not None
