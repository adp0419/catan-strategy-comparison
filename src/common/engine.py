import hashlib
import random
import weakref
from collections import Counter, defaultdict

from catanatron.game import TURNS_LIMIT, Game
from catanatron.models.actions import generate_playable_actions
from catanatron.models.board import get_edges
from catanatron.models.enums import (
    CITY,
    DEVELOPMENT_CARDS,
    RESOURCES,
    ROAD,
    SETTLEMENT,
    Action,
    ActionPrompt,
    ActionType,
)
from catanatron.models.map import BASE_MAP_TEMPLATE, PORT_DIRECTION_TO_NODEREFS, CatanMap
from catanatron.models.player import Color, Player
from catanatron.state_functions import (
    get_actual_victory_points,
    get_dev_cards_in_hand,
    get_largest_army,
    get_longest_road_color,
    get_played_dev_cards,
    get_visible_victory_points,
    player_can_play_dev,
    player_deck_to_array,
    player_key,
    player_num_dev_cards,
    player_num_resource_cards,
)

from src.common.board import edge_key
from src.common.scoring import LONGEST_ROAD_MIN, trail_length

SEATS = (Color.RED, Color.BLUE)
VPS_TO_WIN = 10

DEV_PLAYS = {
    ActionType.PLAY_KNIGHT_CARD: "KNIGHT",
    ActionType.PLAY_YEAR_OF_PLENTY: "YEAR_OF_PLENTY",
    ActionType.PLAY_MONOPOLY: "MONOPOLY",
    ActionType.PLAY_ROAD_BUILDING: "ROAD_BUILDING",
}

ALLOWED = {
    ActionType.ROLL,
    ActionType.MOVE_ROBBER,
    ActionType.DISCARD,
    ActionType.BUILD_ROAD,
    ActionType.BUILD_SETTLEMENT,
    ActionType.BUILD_CITY,
    ActionType.BUY_DEVELOPMENT_CARD,
    ActionType.MARITIME_TRADE,
    ActionType.END_TURN,
    *DEV_PLAYS,
}

RED_NUMBERS = (6, 8)

_boards = weakref.WeakKeyDictionary()


def red_numbers_touch(catan_map):
    reds = [set(t.nodes.values()) for t in catan_map.land_tiles.values() if t.number in RED_NUMBERS]
    return any(len(a & b) >= 2 for i, a in enumerate(reds) for b in reds[i + 1 :])


def new_map():
    while True:
        catan_map = CatanMap.from_template(BASE_MAP_TEMPLATE)
        if not red_numbers_touch(catan_map):
            return catan_map


def new_game(seed, order=SEATS):
    random.seed(seed)
    catan_map = new_map()
    game = Game([Player(c) for c in SEATS], seed=seed, vps_to_win=VPS_TO_WIN, catan_map=catan_map)
    st = game.state
    st.players = sorted(st.players, key=lambda p: order.index(p.color))
    st.colors = tuple(order)
    st.color_to_index = {c: i for i, c in enumerate(order)}
    st.playable_actions = generate_playable_actions(st)
    game.dice_rng = random.Random(f"dice-{seed}")
    game.event_rng = random.Random(f"event-{seed}")
    return game


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


def free_roads(st, color):
    if st.player_state[f"{player_key(st, color)}_ROADS_AVAILABLE"] <= 0:
        return []
    return [Action(color, ActionType.BUILD_ROAD, e) for e in st.board.buildable_edges(color)]


def road_building_open(game, color):
    st = game.state
    return (
        st.current_prompt == ActionPrompt.PLAY_TURN
        and st.player_state[f"{player_key(st, color)}_HAS_ROLLED"]
        and player_can_play_dev(st, color, "ROAD_BUILDING")
        and can_play_dev(game, color, "ROAD_BUILDING")
        and len(free_roads(st, color)) > 0
    )


def action_key(act):
    return (act.action_type.value, repr(act.value))


def legal_actions(game):
    return sorted(raw_legal_actions(game), key=action_key)


def raw_legal_actions(game):
    st = game.state
    color = st.current_color()
    if st.is_road_building:
        return free_roads(st, color)
    acts = []
    for act in st.playable_actions:
        if act.action_type not in ALLOWED:
            continue
        card = DEV_PLAYS.get(act.action_type)
        if card and not can_play_dev(game, act.color, card):
            continue
        acts.append(act)
    has_rb = any(a.action_type == ActionType.PLAY_ROAD_BUILDING for a in acts)
    if not has_rb and road_building_open(game, color):
        acts.append(Action(color, ActionType.PLAY_ROAD_BUILDING, None))
    return acts


def resolve(game, act):
    st = game.state
    kind = act.action_type
    if kind == ActionType.ROLL and act.value is None:
        rng = game.dice_rng
        return Action(act.color, kind, (rng.randint(1, 6), rng.randint(1, 6)))
    if kind == ActionType.MOVE_ROBBER and act.value[1] is not None:
        coord, victim, _ = act.value
        card = game.event_rng.choice(player_deck_to_array(st, victim))
        return Action(act.color, kind, (coord, victim, card))
    if kind == ActionType.DISCARD:
        hand = player_deck_to_array(st, act.color)
        return Action(act.color, kind, game.event_rng.sample(hand, len(hand) // 2))
    return act


def owed_by_roll(st, number):
    owed = {c: Counter() for c in st.colors}
    board = st.board
    for coord, tile in board.map.land_tiles.items():
        if tile.number != number or coord == board.robber_coordinate:
            continue
        for node in tile.nodes.values():
            building = board.buildings.get(node)
            if building:
                owed[building[0]][tile.resource] += 2 if building[1] == CITY else 1
    return owed


def pay_lone_claimant(st, owed, bank_before):
    for i, res in enumerate(RESOURCES):
        claimants = [c for c in st.colors if owed[c][res] > 0]
        total = sum(owed[c][res] for c in claimants)
        if len(claimants) != 1 or total <= bank_before[i]:
            continue
        give = min(owed[claimants[0]][res], st.resource_freqdeck[i])
        st.player_state[f"{player_key(st, claimants[0])}_{res}_IN_HAND"] += give
        st.resource_freqdeck[i] -= give
    st.playable_actions = generate_playable_actions(st)


def fix_free_roads(st, color):
    if st.free_roads_available > 0 and free_roads(st, color):
        st.is_road_building = True
    else:
        st.is_road_building = False
        st.free_roads_available = 0
    st.playable_actions = generate_playable_actions(st)


def move_bonus(st, flag, old, new):
    for color in st.colors:
        st.player_state[f"{player_key(st, color)}_{flag}"] = color == new
    for color, delta in ((old, -2), (new, 2)):
        if color is None:
            continue
        key = player_key(st, color)
        st.player_state[f"{key}_VICTORY_POINTS"] += delta
        st.player_state[f"{key}_ACTUAL_VICTORY_POINTS"] += delta


def road_lengths(st):
    board = st.board
    lengths = {}
    for color in st.colors:
        edges = {edge_key(*e) for e, c in board.roads.items() if c == color}
        blocked = {n for n, (c, _) in board.buildings.items() if c != color}
        lengths[color] = trail_length(edges, blocked)
    return lengths


def next_road_holder(prev, before, after):
    best = max(after.values())
    leaders = [c for c, n in after.items() if n == best]
    unique = leaders[0] if best >= LONGEST_ROAD_MIN and len(leaders) == 1 else None
    if prev is None or after[prev] < before[prev]:
        return unique
    return prev if after[prev] == best else unique


def update_longest_road(st, prev, before):
    after = road_lengths(st)
    new = next_road_holder(prev, before, after)
    board = st.board
    board.road_lengths = defaultdict(int, after)
    board.road_color = new
    board.road_length = after[new] if new else max(after.values())
    for color in st.colors:
        st.player_state[f"{player_key(st, color)}_LONGEST_ROAD_LENGTH"] = after[color]
    cur = get_longest_road_color(st)
    if cur != new:
        move_bonus(st, "HAS_ROAD", cur, new)


def apply(game, act):
    st = game.state
    free = st.is_road_building
    builds = act.action_type in (ActionType.BUILD_ROAD, ActionType.BUILD_SETTLEMENT)
    if builds:
        prev, before = get_longest_road_color(st), road_lengths(st)
    act = resolve(game, act)
    if act.action_type == ActionType.ROLL:
        owed, bank_before = owed_by_roll(st, sum(act.value)), list(st.resource_freqdeck)
    done = game.execute(act, validate_action=False)
    if act.action_type == ActionType.ROLL:
        pay_lone_claimant(st, owed, bank_before)
    if free or act.action_type == ActionType.PLAY_ROAD_BUILDING:
        fix_free_roads(st, act.color)
    if builds:
        update_longest_road(st, prev, before)
    return done


def step(game, act):
    if act not in legal_actions(game):
        raise ValueError(f"illegal action {act}")
    return apply(game, act)


def board_view(catan_map):
    if catan_map in _boards:
        return _boards[catan_map]
    edges = sorted(tuple(sorted(e)) for e in get_edges())
    nbrs = {n: [] for n in catan_map.adjacent_tiles}
    for a, b in edges:
        nbrs[a].append(b)
        nbrs[b].append(a)
    hexes = [
        {
            "id": t.id,
            "resource": t.resource or "DESERT",
            "number": t.number,
            "nodes": sorted(t.nodes.values()),
        }
        for t in sorted(catan_map.land_tiles.values(), key=lambda t: t.id)
    ]
    nodes = [
        {
            "id": n,
            "hexes": sorted(t.id for t in catan_map.adjacent_tiles[n]),
            "neighbors": sorted(nbrs[n]),
        }
        for n in sorted(nbrs)
    ]
    ports = []
    for port in sorted(catan_map.ports_by_id.values(), key=lambda p: p.id):
        a, b = PORT_DIRECTION_TO_NODEREFS[port.direction]
        ports.append({"resource": port.resource or "3:1", "nodes": sorted([port.nodes[a], port.nodes[b]])})
    view = {"hexes": hexes, "nodes": nodes, "edges": edges, "ports": ports}
    _boards[catan_map] = view
    return view


def player_ports(st, color):
    return sorted({r or "3:1" for r in st.board.get_player_port_resources(color)})


def public_view(st, color):
    blds = st.buildings_by_color[color]
    return {
        "settlements": sorted(blds[SETTLEMENT]),
        "cities": sorted(blds[CITY]),
        "roads": sorted(tuple(sorted(e)) for e in blds[ROAD]),
        "knights_played": get_played_dev_cards(st, color, "KNIGHT"),
        "road_length": st.board.road_lengths[color],
        "ports": player_ports(st, color),
    }


def holder(color, me):
    if color is None:
        return None
    return "me" if color == me else "opp"


def extract_state(game, color):
    st = game.state
    opp = next(c for c in st.colors if c != color)
    me_view = public_view(st, color)
    me_view.update(
        {
            "hand": {r: player_num_resource_cards(st, color, r) for r in RESOURCES},
            "dev_cards": {d: get_dev_cards_in_hand(st, color, d) for d in DEVELOPMENT_CARDS},
            "vp": get_actual_victory_points(st, color),
        }
    )
    opp_view = public_view(st, opp)
    opp_view.update(
        {
            "hand_size": player_num_resource_cards(st, opp),
            "dev_cards_count": player_num_dev_cards(st, opp),
            "visible_vp": get_visible_victory_points(st, opp),
        }
    )
    return {
        "turn": st.num_turns,
        "phase": "placement" if st.is_initial_build_phase else "main",
        "seat": st.colors.index(color),
        "board": board_view(st.board.map),
        "robber_hex": st.board.map.land_tiles[st.board.robber_coordinate].id,
        "me": me_view,
        "opp": opp_view,
        "bank": dict(zip(RESOURCES, st.resource_freqdeck)),
        "dev_deck_remaining": len(st.development_listdeck),
        "longest_road_holder": holder(get_longest_road_color(st), color),
        "largest_army_holder": holder(get_largest_army(st)[0], color),
    }


def board_hash(game):
    view = board_view(game.state.board.map)
    raw = repr([(h["id"], h["resource"], h["number"]) for h in view["hexes"]] + view["ports"])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def play_game(agent_a, agent_b, seed, swap_order=False, turn_limit=TURNS_LIMIT):
    order = (Color.BLUE, Color.RED) if swap_order else SEATS
    slots = {Color.RED: "a", Color.BLUE: "b"}
    agents = {Color.RED: agent_a, Color.BLUE: agent_b}
    game = new_game(seed, order)
    while game.winning_color() is None and game.state.num_turns < turn_limit:
        color = game.state.current_color()
        acts = legal_actions(game)
        act = agents[color].decide(extract_state(game, color), acts)
        if act not in acts:
            raise ValueError(f"{slots[color]} chose illegal action {act}")
        apply(game, act)
    st = game.state
    winner = game.winning_color()
    return {
        "seed": seed,
        "board_hash": board_hash(game),
        "agents": {"a": agent_a.name, "b": agent_b.name},
        "seat_order": [slots[c] for c in order],
        "winner": slots[winner] if winner else None,
        "turns": st.num_turns,
        "final_vp": {slots[c]: get_actual_victory_points(st, c) for c in SEATS},
        "rolls": [sum(a.value) for a in st.actions if a.action_type == ActionType.ROLL],
        "num_actions": len(st.actions),
    }
