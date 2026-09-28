

import math

ANGLES = {"TL": 0.0, "TR": 45.0, "BL": 135.0, "BR": 90.0}
min_edge_margin =3.0

def _clip(mx: float, my: float, dx: float, dy: float,
          x0: float, x1: float, y0: float, y1: float) -> tuple[float, float] | None:
    """Clip the infinite line (mx,my)+t*(dx,dy) to a box; return (t_min, t_max) or None."""
    t_min, t_max = -math.inf, math.inf
    for pos, d, lo, hi in ((mx, dx, x0, x1), (my, dy, y0, y1)):
        if d == 0.0:
            if not lo <= pos <= hi:
                return None
        else:
            a, b = (lo - pos) / d, (hi - pos) / d
            t_min, t_max = max(t_min, min(a, b)), min(t_max, max(a, b))
    return (t_min, t_max) if t_min <= t_max else None


def _quadrant(cx: float, cy: float, size: float, spacing: float,
              angle_deg: float, margin: float) -> list[list[tuple[float, float]]]:
    """Parallel lines at `angle_deg` filling one quadrant box (shrunk by `margin`)."""
    a = math.radians(angle_deg)
    ax, ay = math.cos(a), math.sin(a)            # along the line
    px, py = -math.sin(a), math.cos(a)           # perpendicular (stepping)
    x0, x1 = cx - size / 2 + margin, cx + size / 2 - margin
    y0, y1 = cy - size / 2 + margin, cy + size / 2 - margin

    lines = []
    n = max(int(size * math.sqrt(2) / spacing) + 1, 1)
    for i in range(n):
        d = (i - (n - 1) / 2) * spacing
        mx, my = cx + d * px, cy + d * py
        clip = _clip(mx, my, ax, ay, x0, x1, y0, y1)
        if clip is None or clip[1] - clip[0] < 1e-9:
            continue
        t0, t1 = clip
        lines.append([(mx + t0 * ax, my + t0 * ay), (mx + t1 * ax, my + t1 * ay)])
    return lines


def get_cell_points(fov, distance_between_lines=10.0, edge_margin=0.5):
    edge_margin = max(edge_margin , min_edge_margin)
    size, q = fov / 2.0, fov / 4.0
    centers = {"TL": (-q, q), "TR": (q, q), "BL": (-q, -q), "BR": (q, -q)}
    points = []
    for name in ("TL", "TR", "BL", "BR"):
        cx, cy = centers[name]
        points += _quadrant(cx, cy, size, distance_between_lines, ANGLES[name], edge_margin)
    return points

def show(points, fov=None, title="Cell points"):
    """Plot the cell points with matplotlib (one line per segment)."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 6))
    for s, e in points:
        ax.plot([s[0], e[0]], [s[1], e[1]], color="tab:blue", lw=1.2)
    if fov is not None:
        h = fov / 2.0
        ax.plot([-h, h, h, -h, -h], [-h, -h, h, h, -h], color="0.6", lw=0.8, ls="--")
        ax.axhline(0, color="0.8", lw=0.5, ls=":"); ax.axvline(0, color="0.8", lw=0.5, ls=":")
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("X (um)"); ax.set_ylabel("Y (um)")
    plt.tight_layout(); plt.show()


    

if __name__ == "__main__":
    points = get_cell_points(fov=150.0, distance_between_lines=10.0)
    print(f"{len(points)} segments ({2 * len(points)} points)\n")
    for i, (s, e) in enumerate(points):
        print(f"Line {i:3d}:  ({s[0]:7.2f}, {s[1]:7.2f})  ->  ({e[0]:7.2f}, {e[1]:7.2f})")
    show(points, fov=150.0)
