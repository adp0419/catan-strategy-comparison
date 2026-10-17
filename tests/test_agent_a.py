from catanatron.models.enums import Action, ActionType
from catanatron.models.player import Color

from src.agents.agent_a import GreedyAgent
from src.agents.baselines import RandomAgent, VictoryPointAgent
from src.common.engine import play_game
from src.common.probability import node_pips
from tests.helpers import blank_state

RED = Color.RED


def act(kind, value=None):
    return Action(RED, kind, value)


def two_hexes(state):
    hexes = [h for h in state["board"]["hexes"] if h["resource"] != "DESERT"]
    a = hexes[0]
    b = next(h for h in hexes if not set(h["nodes"]) & set(a["nodes"]))
    return a, b


def end():
    return act(ActionType.END_TURN)


def test_builds_city_over_ending_turn():
    state = blank_state(me_settlements=[0])
    state["me"]["hand"] = {"WOOD": 0, "BRICK": 0, "SHEEP": 0, "WHEAT": 2, "ORE": 3}
    choice = GreedyAgent().decide(state, [end(), act(ActionType.BUILD_CITY, 0)])
    assert choice.action_type == ActionType.BUILD_CITY


def test_trades_only_to_complete_a_purchase():
    state = blank_state(me_settlements=[0])
    state["me"]["hand"] = {"WOOD": 4, "BRICK": 0, "SHEEP": 0, "WHEAT": 2, "ORE": 2}
    to_ore = act(ActionType.MARITIME_TRADE, ("WOOD",) * 4 + ("ORE",))
    to_brick = act(ActionType.MARITIME_TRADE, ("WOOD",) * 4 + ("BRICK",))
    assert GreedyAgent().decide(state, [end(), to_brick, to_ore]) == to_ore
    state["me"]["hand"] = {"WOOD": 4, "BRICK": 0, "SHEEP": 0, "WHEAT": 0, "ORE": 0}
    assert GreedyAgent().decide(state, [end(), to_ore]).action_type == ActionType.END_TURN


def test_robber_hits_opponent_not_self():
    state = blank_state()
    mine, theirs = two_hexes(state)
    state["me"]["settlements"] = [mine["nodes"][0]]
    state["opp"]["settlements"] = [theirs["nodes"][0]]
    state["opp"]["hand_size"] = 3
    hit_them = act(ActionType.MOVE_ROBBER, (tuple(theirs["coord"]), RED, None))
    hit_me = act(ActionType.MOVE_ROBBER, (tuple(mine["coord"]), None, None))
    assert GreedyAgent().decide(state, [hit_me, hit_them]) == hit_them


def test_knight_only_when_robbed_or_army_in_reach():
    state = blank_state()
    mine, theirs = two_hexes(state)
    state["me"]["settlements"] = [mine["nodes"][0]]
    acts = [act(ActionType.PLAY_KNIGHT_CARD), act(ActionType.ROLL)]
    state["robber_hex"] = mine["id"]
    assert GreedyAgent().decide(state, acts).action_type == ActionType.PLAY_KNIGHT_CARD
    state["robber_hex"] = theirs["id"]
    assert GreedyAgent().decide(state, acts).action_type == ActionType.ROLL
    state["me"]["knights_played"] = 2
    state["largest_army_holder"] = None
    assert GreedyAgent().decide(state, acts).action_type == ActionType.PLAY_KNIGHT_CARD


def test_pure_pip_placement_takes_highest_pips():
    state = blank_state(phase="placement")
    agent = GreedyAgent({"diversity": 0, "port_generic": 0, "port_match": 0, "collision": 0})
    acts = [act(ActionType.BUILD_SETTLEMENT, n) for n in range(54)]
    best = max(range(54), key=lambda n: node_pips(state["board"], n))
    choice = agent.decide(state, acts)
    assert node_pips(state["board"], choice.value) == node_pips(state["board"], best)


def test_decisions_are_deterministic():
    state = blank_state(phase="placement")
    acts = [act(ActionType.BUILD_SETTLEMENT, n) for n in range(54)]
    assert GreedyAgent().decide(state, acts) == GreedyAgent().decide(state, acts)


def test_beats_baselines():
    for make in (RandomAgent, VictoryPointAgent):
        wins = 0
        for seed in range(1, 31):
            log = play_game(GreedyAgent(), make(seed), seed, swap_order=seed % 2 == 0)
            wins += log["winner"] == "a"
        assert wins >= 28, make.name


def test_agent_keeps_no_state_between_decisions():
    agent = GreedyAgent()
    before = dict(vars(agent))
    play_game(agent, RandomAgent(1), seed=3)
    assert vars(agent) == before
    assert set(vars(agent)) == {"w"}
