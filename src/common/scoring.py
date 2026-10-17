from collections import defaultdict

from src.common.board import buildings, edge_key, other, roads

LONGEST_ROAD_MIN = 5
LARGEST_ARMY_MIN = 3
BONUS_VP = 2


def victory_points(state, player):
    if player == "me":
        return state["me"]["vp"]
    return state["opp"]["visible_vp"]


def visible_victory_points(state, player):
    if player == "me":
        return state["me"]["vp"] - state["me"]["dev_cards"]["VICTORY_POINT"]
    return state["opp"]["visible_vp"]


def trail_length(edges, blocked):
    links = defaultdict(list)
    for a, b in edges:
        links[a].append(b)
        links[b].append(a)

    def walk(node, used):
        if used and node in blocked:
            return 0
        best = 0
        for nxt in links[node]:
            e = edge_key(node, nxt)
            if e not in used:
                used.add(e)
                best = max(best, 1 + walk(nxt, used))
                used.remove(e)
        return best

    return max((walk(n, set()) for n in links), default=0)


def longest_road_length(state, player, extra=()):
    edges = roads(state, player) | {edge_key(*e) for e in extra}
    return trail_length(edges, buildings(state, other(player)))


def army_size(state, player):
    return state[player]["knights_played"]


def takes_longest_road(state, edge, player="me"):
    holder = "me" if player == "me" else "opp"
    if state["longest_road_holder"] == holder:
        return False
    length = longest_road_length(state, player, extra=[edge])
    return length >= LONGEST_ROAD_MIN and length > state[other(player)]["road_length"]


def takes_largest_army(state, player="me"):
    if state["largest_army_holder"] == player:
        return False
    knights = army_size(state, player) + 1
    return knights >= LARGEST_ARMY_MIN and knights > army_size(state, other(player))
