from src.agents.agent_a import GreedyAgent
from src.agents.archetypes import DEFAULT, DevRush
from src.agents.planner import CHECK_EVERY, DEFAULT_EDGE, ROBBER_TURNS, Planner, pick
from src.common.engine import extract_state, legal_actions, new_game, step
from src.common.robber import robber_damage

SCORES = {"expansion": 10.0, "ore_wheat_sheep": 9.0, "longest_road": 8.0, "cities_and_roads": 10.0, "port_play": 0.0, "dev_rush": 7.0}


def after_setup(seed):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.state.is_initial_build_phase:
        color = game.state.current_color()
        step(game, agent.decide(extract_state(game, color), legal_actions(game)))
    return extract_state(game, game.state.colors[0])


def watched_game(seed, planner, turns=None):
    game = new_game(seed)
    agent = GreedyAgent()
    me = game.state.colors[0]
    while game.winning_color() is None and game.state.num_turns < (turns or 500):
        color = game.state.current_color()
        state = extract_state(game, color)
        if color == me:
            planner.update(state)
        step(game, agent.decide(state, legal_actions(game)))
    return planner


def test_pick_defaults_unless_a_specialist_clearly_wins():
    assert pick(SCORES) == DEFAULT
    assert pick(dict(SCORES, expansion=10.0 * DEFAULT_EDGE)) == DEFAULT
    assert pick(dict(SCORES, expansion=10.0 * DEFAULT_EDGE + 0.1)) == "expansion"


def test_pick_breaks_ties_by_name():
    flat = {n: 5.0 for n in SCORES}
    assert pick(flat, edge=1.0) == DEFAULT
    assert pick(dict(flat, cities_and_roads=1.0), edge=1.0) == "dev_rush"


def test_switch_needs_margin():
    p = Planner()
    p.checkpoint(after_setup(1), "start")
    p.plan = "longest_road"
    assert p.choose(dict(SCORES, longest_road=9.0)) == "longest_road"
    assert p.choose(dict(SCORES, longest_road=7.0)) == DEFAULT
    assert p.choose({k: v for k, v in SCORES.items() if k != "longest_road"}) == DEFAULT


def test_picks_a_plan_on_first_call():
    state = extract_state(new_game(2), new_game(2).state.colors[0])
    p = Planner()
    arch = p.update(state)
    assert arch is not None and arch.name == p.plan
    assert p.history[0]["reason"] == "start" and p.switches == []


def test_rechecks_after_placement_then_periodically():
    p = watched_game(3, Planner(), turns=4 * CHECK_EVERY)
    reasons = [h["reason"] for h in p.history]
    assert reasons[0] == "start"
    assert reasons[1] == "placement_done"
    assert reasons.count("start") == 1
    assert "periodic" in reasons


def test_one_check_per_turn():
    p = watched_game(4, Planner(), turns=60)
    turns = [h["turn"] for h in p.history[1:]]
    assert len(turns) == len(set(turns))


def test_fixed_plan_never_switches():
    p = watched_game(5, Planner(replan=False))
    assert len(p.history) == 1 and p.switches == []


def test_dead_plan_is_replaced():
    state = after_setup(6)
    p = Planner()
    p.update(state)
    p.placed = True
    p.plan, p.arch = "dev_rush", DevRush()
    state = dict(state, dev_deck_remaining=0, turn=state["turn"] + 1)
    p.update(state)
    assert p.plan != "dev_rush"
    assert p.switches[-1]["reason"] == "dead"


def test_parked_robber_triggers_check():
    state = after_setup(7)
    p = Planner()
    p.update(state)
    p.placed = True
    mine = next(h["id"] for h in state["board"]["hexes"] if robber_damage(state, "me", h["id"]) > 0)
    for i in range(1, ROBBER_TURNS + 1):
        p.update(dict(state, robber_hex=mine, turn=state["turn"] + i))
    assert p.history[-1]["reason"] == "robber"


def test_opponent_near_win_triggers_once():
    state = after_setup(8)
    p = Planner()
    p.update(state)
    p.placed = True
    opp = dict(state["opp"], visible_vp=7)
    p.update(dict(state, opp=opp, turn=state["turn"] + 1))
    p.update(dict(state, opp=opp, turn=state["turn"] + 2))
    assert [h["reason"] for h in p.history].count("opp_vp") == 1


def test_no_plan_thrash_in_real_games():
    switches = [len(watched_game(seed, Planner()).switches) for seed in range(1, 11)]
    assert max(switches) <= 3
