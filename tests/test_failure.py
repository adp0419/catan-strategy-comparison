from src.agents.agent_a import GreedyAgent
from src.agents.archetypes import CitiesAndRoads, OreWheatSheep
from src.agents.failure import COOLDOWN, THRESHOLD, WINDOW, Monitor, core, eta
from src.common.board import RESOURCES
from src.common.engine import extract_state, legal_actions, new_game, step
from src.common.probability import node_production
from src.common.robber import robber_damage
from tests.helpers import blank_state


def after_setup(seed):
    game = new_game(seed)
    agent = GreedyAgent()
    while game.state.is_initial_build_phase:
        color = game.state.current_color()
        step(game, agent.decide(extract_state(game, color), legal_actions(game)))
    return extract_state(game, game.state.colors[0])


def test_core_resources_are_the_plan_heavy_ones():
    assert core(OreWheatSheep.profile) == {"ORE", "WHEAT"}
    assert core(CitiesAndRoads.profile) == set(RESOURCES)


def test_eta_counts_turns_to_ten():
    prod = {r: 0.2 for r in RESOURCES}
    assert eta(6, prod) == 4 / (2 * 1.0 / 4)
    assert eta(10, prod) == 0
    assert eta(3, {r: 0.0 for r in RESOURCES}) == float("inf")


def test_quiet_position_has_no_alarm():
    state = after_setup(1)
    mon = Monitor()
    level = mon.update(state, CitiesAndRoads(), None)
    assert level < THRESHOLD and not mon.alarm(state)


def test_dead_end_when_core_resource_missing_and_no_port():
    state = blank_state()
    board = state["board"]
    node = next(n for n in range(len(board["nodes"])) if node_production(board, n)["ORE"] == 0 and node_production(board, n)["WHEAT"] > 0)
    state["me"]["settlements"] = [node]
    mon = Monitor()
    mon.update(state, OreWheatSheep(), None)
    assert mon.signals["dead_end"] == 1.0
    assert mon.alarm(state)


def test_alarm_has_cooldown():
    state = blank_state()
    board = state["board"]
    node = next(n for n in range(len(board["nodes"])) if node_production(board, n)["ORE"] == 0)
    state["me"]["settlements"] = [node]
    mon = Monitor()
    mon.update(state, OreWheatSheep(), None)
    assert mon.alarm(state)
    assert not mon.alarm(dict(state, turn=state["turn"] + COOLDOWN - 1))
    assert mon.alarm(dict(state, turn=state["turn"] + COOLDOWN))


def test_salvage_prefers_a_knight_when_choked():
    state = after_setup(2)
    mon = Monitor()
    mon.signals = {"choked": 1.0}
    assert mon.salvage(state) is None
    state["me"]["dev_cards"] = dict(state["me"]["dev_cards"], KNIGHT=1)
    assert mon.salvage(state) == "knight"


def test_stall_grows_when_milestone_never_changes():
    state = after_setup(3)
    mon = Monitor()
    arch = CitiesAndRoads()
    mon.update(state, arch, None)
    assert mon.signals["stalled"] == 0
    mon.update(dict(state, turn=state["turn"] + 36), arch, None)
    assert mon.signals["stalled"] == 1.0


def test_target_lost_severity_depends_on_alternatives():
    state = after_setup(4)
    mon = Monitor()
    target = next(n for n in range(len(state["board"]["nodes"])) if node_production(state["board"], n) and sum(node_production(state["board"], n).values()) > 0)
    mon.target_lost(state, target)
    assert 0.0 <= mon.lost <= 1.0


def test_shortfall_counts_only_full_windows():
    state = after_setup(5)
    mon = Monitor()
    arch = CitiesAndRoads()
    mon.update(state, arch, None)
    assert mon.signals["shortfall"] == 0
    mon.rolls.extend([(0, 1.0)] * WINDOW)
    mon.cursor = len(state["log"])
    mon.update(state, arch, None)
    assert mon.signals["shortfall"] == 1.0


def test_robber_choke_only_counts_core_hexes():
    state = after_setup(6)
    mine = [h for h in state["board"]["hexes"] if robber_damage(state, "me", h["id"]) > 0]
    off = next((h for h in mine if h["resource"] not in core(OreWheatSheep.profile)), None)
    if off is None:
        return
    mon = Monitor()
    for i in range(3):
        mon.update(dict(state, robber_hex=off["id"], turn=state["turn"] + i), OreWheatSheep(), None)
    assert mon.signals["choked"] == 0
