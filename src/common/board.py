import math
from collections import deque

RESOURCES = ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE")
GENERIC = "3:1"
BANK_RATIO = 4
GENERIC_RATIO = 3
PORT_RATIO = 2


def edge_key(a, b):
    return (a, b) if a < b else (b, a)


def other(player):
    return "opp" if player == "me" else "me"


def adjacent_hexes(board, node):
    return [board["hexes"][h] for h in board["nodes"][node]["hexes"]]


def adjacent_nodes(board, node):
    return board["nodes"][node]["neighbors"]


def node_ports(board):
    return {n: p["resource"] for p in board["ports"] for n in p["nodes"]}


def buildings(state, player):
    return set(state[player]["settlements"]) | set(state[player]["cities"])


def occupied_nodes(state):
    return buildings(state, "me") | buildings(state, "opp")


def roads(state, player):
    return {edge_key(*e) for e in state[player]["roads"]}


def all_roads(state):
    return roads(state, "me") | roads(state, "opp")


def network_nodes(state, player):
    nodes = buildings(state, player)
    for a, b in roads(state, player):
        nodes.update((a, b))
    return nodes - buildings(state, other(player))


def distance_rule_ok(state, node):
    taken = occupied_nodes(state)
    if node in taken:
        return False
    return not any(n in taken for n in adjacent_nodes(state["board"], node))


def buildable_nodes(state, player):
    if state["phase"] == "placement":
        cands = range(len(state["board"]["nodes"]))
    else:
        cands = network_nodes(state, player)
    return sorted(n for n in cands if distance_rule_ok(state, n))


def open_edges_from(state, nodes):
    taken = all_roads(state)
    board = state["board"]
    edges = set()
    for n in nodes:
        for m in adjacent_nodes(board, n):
            e = edge_key(n, m)
            if e not in taken:
                edges.add(e)
    return sorted(edges)


def buildable_edges(state, player):
    if state["phase"] == "placement":
        own = roads(state, player)
        bare = [s for s in state[player]["settlements"] if not any(s in e for e in own)]
        return open_edges_from(state, bare)
    return open_edges_from(state, network_nodes(state, player))


def road_distances(state, player):
    board = state["board"]
    own = roads(state, player)
    blocked_edges = roads(state, other(player))
    blocked_nodes = buildings(state, other(player))
    dist = {n: 0 for n in network_nodes(state, player)}
    queue = deque(dist)
    while queue:
        n = queue.popleft()
        for m in adjacent_nodes(board, n):
            e = edge_key(n, m)
            if m in blocked_nodes or e in blocked_edges:
                continue
            cost = 0 if e in own else 1
            d = dist[n] + cost
            if d < dist.get(m, math.inf):
                dist[m] = d
                if cost == 0:
                    queue.appendleft(m)
                else:
                    queue.append(m)
    return dist


def road_distance(state, player, node):
    return road_distances(state, player).get(node, math.inf)


def port_access(state, player):
    ports = state[player]["ports"]
    base = GENERIC_RATIO if GENERIC in ports else BANK_RATIO
    return {r: PORT_RATIO if r in ports else base for r in RESOURCES}
