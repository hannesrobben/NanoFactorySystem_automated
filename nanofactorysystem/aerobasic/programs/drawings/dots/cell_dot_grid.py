##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################

import math

MIN_EDGE_MARGIN = 5.0        # um   hard floor on the clearance dot -> pad edge
# ------------------------------------------------------------------------


def _lattice(cellsize: float, pitch: float, edge_margin: float) -> list[float]:
    """Centred 1D lattice of coordinates along one side, empty if nothing fits."""
    usable = cellsize - 2.0 * max(edge_margin, MIN_EDGE_MARGIN)
    if usable < 0.0:
        return []
    n = int(usable / pitch) + 1
    return [(i - (n - 1) / 2.0) * pitch for i in range(n)]


def get_cell_dots(cellsize: float,
                  pitch: float,
                  edge_margin: float,
                  serpentine: bool = True) -> list[tuple[float, float]]:
    """Centred square grid of dot centres in a cell, returned in print order."""
    offs = _lattice(cellsize, pitch, edge_margin)

    dots = []
    for j, y in enumerate(offs):
        row = offs if (not serpentine or j % 2 == 0) else offs[::-1]
        dots += [(x, y) for x in row]
    return dots


def grid_shape(cellsize: float,
               pitch: float,
               edge_margin: float) -> tuple[int, float]:
    """(dots per side, grid extent in um)."""
    offs = _lattice(cellsize, pitch, edge_margin)
    if not offs:
        return 0, 0.0
    return len(offs), (len(offs) - 1) * pitch


def max_jump(dots: list[tuple[float, float]]) -> float:
    """Longest consecutive travel in print order - should equal pitch."""
    if len(dots) < 2:
        return 0.0
    return max(math.dist(a, b) for a, b in zip(dots, dots[1:]))


def show(dots, cellsize=None, title="Cell dots", path=True):
    """Plot the dot grid with matplotlib."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 6))
    if path and len(dots) > 1:
        ax.plot([d[0] for d in dots], [d[1] for d in dots],
                color="0.75", lw=0.8, zorder=1)
    ax.scatter([d[0] for d in dots], [d[1] for d in dots],
               s=18, color="tab:red", zorder=2)
    if dots:
        ax.scatter([dots[0][0]], [dots[0][1]], s=60, facecolors="none",
                   edgecolors="tab:green", zorder=3)
    if cellsize is not None:
        h = cellsize / 2.0
        ax.plot([-h, h, h, -h, -h], [-h, -h, h, h, -h], color="0.6", lw=0.8, ls="--")
        ax.axhline(0, color="0.8", lw=0.5, ls=":")
        ax.axvline(0, color="0.8", lw=0.5, ls=":")
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("X (um)")
    ax.set_ylabel("Y (um)")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":

    # matches power-vs-dwell-dotgrid.py: PAD_SIZE, PITCH, EDGE_MARGIN
    cellsize, pitch, edge_margin = 100.0, 20.0, 10.0
    dots = get_cell_dots(cellsize, pitch, edge_margin)
    n, extent = grid_shape(cellsize, pitch, edge_margin)

    print(f"cellsize {cellsize} um -> {n}x{n} = {len(dots)} dots, "
          f"extent {extent} um, max jump {max_jump(dots):.3f} um\n")
    for i, (x, y) in enumerate(dots):
        print(f"Dot {i:3d}:  ({x:7.2f}, {y:7.2f})")
    show(dots, cellsize=cellsize)
