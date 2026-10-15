import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, RegularPolygon

from catanatron.models.enums import CITY
from catanatron.models.map import PORT_DIRECTION_TO_NODEREFS, LandTile, NodeRef, Port
from catanatron.state_functions import get_actual_victory_points, get_longest_road_color, get_largest_army

from src.agents.baselines import RandomAgent
from src.common.engine import SEATS, apply, extract_state, legal_actions, new_game

SIZE = 1.0
TILE_COLORS = {
    "WOOD": "#4f7942",
    "BRICK": "#b5532f",
    "SHEEP": "#9acd5a",
    "WHEAT": "#e8c547",
    "ORE": "#8a8d91",
    None: "#e3d3a8",
}
PLAYER_COLORS = {"RED": "#d62728", "BLUE": "#1f5fbf"}
CORNERS = {
    NodeRef.NORTH: 90,
    NodeRef.NORTHEAST: 30,
    NodeRef.SOUTHEAST: -30,
    NodeRef.SOUTH: -90,
    NodeRef.SOUTHWEST: -150,
    NodeRef.NORTHWEST: 150,
}
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}


def center(coord):
    x, y, _ = coord
    return (math.sqrt(3) * SIZE * (x - y) / 2, 1.5 * SIZE * (x + y))


def corner(coord, ref):
    cx, cy = center(coord)
    ang = math.radians(CORNERS[ref])
    return (cx + SIZE * math.cos(ang), cy + SIZE * math.sin(ang))


def node_positions(catan_map):
    pos = {}
    for coord, tile in catan_map.land_tiles.items():
        for ref, node in tile.nodes.items():
            pos[node] = corner(coord, ref)
    return pos


def draw_tile(ax, coord, tile, robber):
    cx, cy = center(coord)
    ax.add_patch(RegularPolygon((cx, cy), 6, radius=SIZE, orientation=0, facecolor=TILE_COLORS[tile.resource], edgecolor="#5c4a32", linewidth=1.5))
    label = tile.resource or "DESERT"
    ax.text(cx, cy + 0.5, label.title(), ha="center", va="center", fontsize=7, color="#222")
    if tile.number:
        hot = tile.number in (6, 8)
        ax.add_patch(Circle((cx, cy), 0.32, facecolor="#f8f1df", edgecolor="#5c4a32", zorder=3))
        ax.text(cx, cy + 0.04, str(tile.number), ha="center", va="center", fontsize=11, fontweight="bold", color="#c0392b" if hot else "#222", zorder=4)
        ax.text(cx, cy - 0.17, "•" * PIPS[tile.number], ha="center", va="center", fontsize=5, color="#c0392b" if hot else "#222", zorder=4)
    if robber:
        ax.add_patch(Circle((cx - 0.5, cy - 0.25), 0.16, facecolor="#222", edgecolor="white", zorder=5))


def draw_port(ax, coord, port):
    a, b = PORT_DIRECTION_TO_NODEREFS[port.direction]
    ax_, ay_ = corner(coord, a)
    bx_, by_ = corner(coord, b)
    cx, cy = center(coord)
    mx, my = (ax_ + bx_) / 2, (ay_ + by_) / 2
    lx, ly = cx + (mx - cx) * 0.25, cy + (my - cy) * 0.25
    ax.plot([ax_, lx, bx_], [ay_, ly, by_], color="#7a5c3a", linewidth=1.2, zorder=1)
    text = "3:1" if port.resource is None else f"2:1\n{port.resource.title()}"
    ax.text(lx, ly, text, ha="center", va="center", fontsize=6.5, zorder=2, bbox={"boxstyle": "round,pad=0.25", "facecolor": TILE_COLORS[port.resource] if port.resource else "white", "edgecolor": "#7a5c3a"})


def render(game, path, title=""):
    st = game.state
    catan_map = st.board.map
    pos = node_positions(catan_map)
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.set_aspect("equal")
    ax.axis("off")
    for coord, tile in catan_map.tiles.items():
        if isinstance(tile, LandTile):
            draw_tile(ax, coord, tile, coord == st.board.robber_coordinate)
        elif isinstance(tile, Port):
            draw_port(ax, coord, tile)
    seen = set()
    for edge, color in st.board.roads.items():
        key = tuple(sorted(edge))
        if key in seen:
            continue
        seen.add(key)
        (x1, y1), (x2, y2) = pos[edge[0]], pos[edge[1]]
        ax.plot([x1, x2], [y1, y2], color=PLAYER_COLORS[color.value], linewidth=5, solid_capstyle="round", zorder=6)
    for node, (color, kind) in st.board.buildings.items():
        x, y = pos[node]
        fill = PLAYER_COLORS[color.value]
        if kind == CITY:
            ax.add_patch(Polygon([(x - 0.2, y - 0.17), (x + 0.2, y - 0.17), (x + 0.2, y + 0.08), (x, y + 0.24), (x - 0.2, y + 0.08)], facecolor=fill, edgecolor="white", linewidth=1.5, zorder=7))
        else:
            ax.add_patch(RegularPolygon((x, y), 4, radius=0.17, orientation=math.pi / 4, facecolor=fill, edgecolor="white", linewidth=1.5, zorder=7))
    lines = []
    road, army = get_longest_road_color(st), get_largest_army(st)[0]
    for i, color in enumerate(st.colors):
        tags = [t for t, c in (("longest road", road), ("largest army", army)) if c == color]
        extra = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"Seat {i + 1}: {color.value}  {get_actual_victory_points(st, color)} VP{extra}")
    ax.set_title(title + ("\n" if title else "") + "    |    ".join(lines), fontsize=10)
    ax.autoscale_view()
    ax.margins(0.03)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def play_until(seed, moves=None, swap=False):
    game = new_game(seed, SEATS[::-1] if swap else SEATS)
    agents = {c: RandomAgent(seed * 7 + i) for i, c in enumerate(SEATS)}
    count = 0
    while game.winning_color() is None and game.state.num_turns < 1000:
        if moves is not None and count >= moves:
            break
        color = game.state.current_color()
        apply(game, agents[color].decide(extract_state(game, color), legal_actions(game)))
        count += 1
    return game


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--moves", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    game = play_until(args.seed, args.moves)
    stage = "empty board" if args.moves == 0 else (f"after {args.moves} moves" if args.moves else "final position")
    out = args.out or f"data/boards/seed{args.seed}_{'final' if args.moves is None else args.moves}.png"
    winner = game.winning_color()
    title = f"Seed {args.seed}, random vs random, {stage}, turn {game.state.num_turns}"
    if args.moves is None and winner:
        title += f", winner {winner.value}"
    print(render(game, out, title))


if __name__ == "__main__":
    main()
