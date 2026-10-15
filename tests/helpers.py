from catanatron.game import Game
from catanatron.models.actions import generate_playable_actions
from catanatron.models.enums import Action, ActionPrompt, ActionType, RESOURCES
from catanatron.models.player import Color, RandomPlayer
from catanatron.state_functions import get_longest_road_length, player_key

COLORS = [Color.RED, Color.BLUE]


def new_game(seed=7):
    return Game([RandomPlayer(c) for c in COLORS], seed=seed)


def set_hand(game, color, **counts):
    key = player_key(game.state, color)
    for res in RESOURCES:
        game.state.player_state[f"{key}_{res}_IN_HAND"] = counts.get(res, 0)
    refresh(game)


def refresh(game):
    game.state.playable_actions = generate_playable_actions(game.state)


def first_of(game, action_type):
    return next(a for a in game.state.playable_actions if a.action_type == action_type)


def play_setup(game, nodes=None):
    nodes = list(nodes or [])
    while game.state.is_initial_build_phase:
        acts = game.state.playable_actions
        if acts[0].action_type == ActionType.BUILD_SETTLEMENT and nodes:
            node = nodes.pop(0)
            act = next(a for a in acts if a.value == node)
        else:
            act = acts[0]
        game.execute(act)


def roll(game, dice=(1, 1)):
    game.execute(Action(game.state.current_color(), ActionType.ROLL, dice), validate_action=False)


def can_roll(game):
    return any(a.action_type == ActionType.ROLL for a in game.state.playable_actions)


def to_roll_of(game, color):
    while not (game.state.current_color() == color and can_roll(game)):
        if can_roll(game):
            roll(game)
        game.execute(first_of(game, ActionType.END_TURN))


def start_turn_of(game, color):
    if game.state.current_color() == color and not can_roll(game):
        game.execute(first_of(game, ActionType.END_TURN))
    to_roll_of(game, color)
    roll(game)


def best_road(game, color):
    best, best_len = None, -1
    for act in game.state.playable_actions:
        if act.action_type != ActionType.BUILD_ROAD:
            continue
        sim = game.copy()
        sim.execute(act)
        length = get_longest_road_length(sim.state, color)
        if length > best_len:
            best, best_len = act, length
    return best


def extend_road(game, color, target):
    while get_longest_road_length(game.state, color) < target:
        set_hand(game, color, WOOD=1, BRICK=1)
        act = best_road(game, color)
        assert act is not None, "ran out of road placements"
        game.execute(act)


CUT_PATH = [0, 5, 4, 3, 2, 1, 6]
CUT_NODE = 3
CUT_LINK = 12
CUT_HOME = 11


def edge_act(game, a, b):
    color = game.state.current_color()
    return Action(color, ActionType.BUILD_ROAD, (a, b))


def far_settlement(game, avoid):
    from catanatron.models.board import get_node_distances

    dist = get_node_distances()
    acts = [a for a in game.state.playable_actions if a.action_type == ActionType.BUILD_SETTLEMENT]
    return max(acts, key=lambda a: (min(dist[a.value][n] for n in avoid), -a.value))


def build_cut_scenario(do):
    game = new_game()
    p1, p2 = game.state.colors
    avoid = CUT_PATH + [CUT_LINK, CUT_HOME]
    setup = [
        Action(p1, ActionType.BUILD_SETTLEMENT, CUT_PATH[0]),
        Action(p1, ActionType.BUILD_ROAD, (CUT_PATH[0], CUT_PATH[1])),
        Action(p2, ActionType.BUILD_SETTLEMENT, CUT_HOME),
        Action(p2, ActionType.BUILD_ROAD, (CUT_HOME, CUT_LINK)),
    ]
    for act in setup:
        do(game, act)
    for _ in range(2):
        do(game, far_settlement(game, avoid))
        do(game, game.state.playable_actions[0])
    start_turn_of(game, p1)
    for a, b in zip(CUT_PATH[1:], CUT_PATH[2:]):
        set_hand(game, p1, WOOD=1, BRICK=1)
        do(game, Action(p1, ActionType.BUILD_ROAD, (a, b)))
    return game, p1, p2


def cut_road(game, p2, do):
    start_turn_of(game, p2)
    set_hand(game, p2, WOOD=1, BRICK=1)
    do(game, Action(p2, ActionType.BUILD_ROAD, (CUT_LINK, CUT_NODE)))
    set_hand(game, p2, WOOD=1, BRICK=1, SHEEP=1, WHEAT=1)
    do(game, Action(p2, ActionType.BUILD_SETTLEMENT, CUT_NODE))
