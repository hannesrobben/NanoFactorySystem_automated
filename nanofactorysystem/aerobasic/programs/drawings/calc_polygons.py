"""
Complete working example for:
- analytic function → binary mask → hatch segments

For 2PP applications with DOEs (diffractive optical elements)
"""

import numpy as np
from skimage import measure
import matplotlib.pyplot as plt


def intersect_line_with_segment(p0, d, a, b):
    """Intersection of the line p0 + t*d with the segment a→b"""
    v = b - a
    det = d[0] * (-v[1]) - d[1] * (-v[0])

    if abs(det) < 1e-12:
        return None

    rhs = a - p0
    t = (rhs[0] * (-v[1]) - rhs[1] * (-v[0])) / det
    s = (d[0] * rhs[1] - d[1] * rhs[0]) / det

    if 0 <= s <= 1:
        return t
    return None


def hatch_segments_for_polygon(polygon, hatch_angle_deg, hatch_dist, z):
    """Create hatch lines for a CLOSED polygon"""
    poly = np.array(polygon)
    if len(poly) < 3:
        return []

    theta = np.deg2rad(hatch_angle_deg)
    d = np.array([np.cos(theta), np.sin(theta)])
    n = np.array([-d[1], d[0]])

    # CORRECTION: project all points
    projections = poly @ n
    proj_min = projections.min()
    proj_max = projections.max()

    offsets = np.arange(proj_min, proj_max + hatch_dist, hatch_dist)

    result_segments = []
    edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]

    for off in offsets:
        p0 = n * off

        ts = []
        for a, b in edges:
            t = intersect_line_with_segment(p0, d, a, b)
            if t is not None:
                ts.append(t)

        if len(ts) < 2:
            continue

        ts.sort()

        # Duplikate entfernen
        filtered = [ts[0]]
        for t in ts[1:]:
            if abs(t - filtered[-1]) > 1e-9:
                filtered.append(t)
        ts = filtered

        for i in range(0, len(ts) - 1, 2):
            t0, t1 = ts[i], ts[i + 1]
            p_start = p0 + t0 * d
            p_end = p0 + t1 * d

            if np.linalg.norm(p_end - p_start) > 1e-9:
                result_segments.append(((p_start[0], p_start[1], z),
                                        (p_end[0], p_end[1], z)))

    return result_segments


def binary_mask_to_closed_polygons(mask, xs, ys, min_area=10):
    """
    Convert a binary mask into CLOSED polygons.
    Uses connected components for truly closed regions.
    """
    from skimage.measure import label, regionprops, find_contours

    labels = label(mask)
    regions = regionprops(labels)

    polygons = []
    for region in regions:
        if region.area < min_area:
            continue

        # Mask of this region only
        region_mask = (labels == region.label).astype(float)

        # Kontur finden
        contours = find_contours(region_mask, 0.5)

        for contour in contours:
            poly = []
            for yi, xi in contour:
                x_coord = xs[0] + (xs[-1] - xs[0]) * xi / (len(xs) - 1)
                y_coord = ys[0] + (ys[-1] - ys[0]) * yi / (len(ys) - 1)
                poly.append([x_coord, y_coord])

            poly = np.array(poly)

            # Close if necessary
            if len(poly) > 2 and not np.allclose(poly[0], poly[-1]):
                poly = np.vstack([poly, poly[0]])

            if len(poly) >= 4:
                polygons.append(poly)

    return polygons


def create_grating_with_boundary(x_range, y_range, res, grating_angle_deg,
                                 period, duty_cycle, boundary_func=None):
    """
    Create a grating with an optional boundary.

    boundary_func: function f(x,y) returning True/False (inside/outside)
    """
    xs = np.linspace(x_range[0], x_range[1], res)
    ys = np.linspace(y_range[0], y_range[1], res)
    X, Y = np.meshgrid(xs, ys)

    # Grating direction
    theta = np.deg2rad(grating_angle_deg)

    # Projection onto the grating normal
    S = X * np.cos(theta) + Y * np.sin(theta)

    # Rechteckwelle
    frac = np.mod(S, period) / period
    grating = (frac < duty_cycle).astype(float)

    # Apply the boundary
    if boundary_func is not None:
        boundary = boundary_func(X, Y)
        grating = grating * boundary

    return xs, ys, grating


def circular_boundary(x, y, radius, cx=0, cy=0):
    """Circular boundary"""
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2


def rectangular_boundary(x, y, width, height, cx=0, cy=0):
    """Rectangular boundary"""
    return (np.abs(x - cx) <= width / 2) & (np.abs(y - cy) <= height / 2)


def workflow_example(grating_angle=0,  # degree
                     period=1.5,  # µm
                     duty_cycle=0.5,
                     radius=4.0,
                     hatch_angle=grating_angle,  # Hatching along the stripes
                     hatch_dist=0.2):
    pass


# ========== HAUPTBEISPIEL ==========
if __name__ == '__main__':

    print("=" * 60)
    print("Beispiel: Gitter mit kreisförmiger Begrenzung")
    print("=" * 60)

    # Parameter
    grating_angle = 0  # Grad
    period = 1.5
    duty_cycle = 0.5
    radius = 4.0
    hatch_angle = grating_angle  # Hatching along the stripes
    hatch_dist = 0.2

    # Create a grating with circular boundary
    xs, ys, mask = create_grating_with_boundary(
        x_range=(-5, 5),
        y_range=(-5, 5),
        res=500,
        grating_angle_deg=grating_angle,
        period=period,
        duty_cycle=duty_cycle,
        boundary_func=lambda x, y: circular_boundary(x, y, radius)
    )

    # Extract the polygons
    polygons = binary_mask_to_closed_polygons(mask, xs, ys, min_area=50)
    print(f"Gefundene geschlossene Polygone: {len(polygons)}")

    # Check whether the polygons are closed
    for i, poly in enumerate(polygons):
        is_closed = np.allclose(poly[0], poly[-1])
        area = 0.5 * np.abs(np.sum(poly[:-1, 0] * poly[1:, 1] - poly[1:, 0] * poly[:-1, 1]))
        print(f"  Polygon {i}: {len(poly)} Punkte, geschlossen={is_closed}, Fläche≈{area:.2f}")

    # Hatch-Segmente erzeugen
    all_segments = []
    for poly in polygons:
        segs = hatch_segments_for_polygon(poly, hatch_angle, hatch_dist, z=0)
        all_segments.extend(segs)

    print(f"\nGesamte Hatch-Segmente: {len(all_segments)}")

    # ========== VISUALISIERUNG ==========
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # 1) Binary mask
    ax = axes[0]
    ax.imshow(mask, extent=[xs[0], xs[-1], ys[0], ys[-1]],
              origin='lower', cmap='viridis')
    circle = plt.Circle((0, 0), radius, fill=False, color='red', linewidth=2)
    ax.add_patch(circle)
    ax.set_title(f"Gitter (θ={grating_angle}°, T={period})")
    ax.set_aspect('equal')

    # 2) Extrahierte Polygone
    ax = axes[1]
    ax.set_aspect('equal')
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(polygons), 1)))
    for i, poly in enumerate(polygons):
        ax.fill(poly[:, 0], poly[:, 1], alpha=0.6,
                facecolor=colors[i % len(colors)],
                edgecolor='black', linewidth=1)
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.set_title(f"Geschlossene Polygone ({len(polygons)})")
    ax.grid(True, alpha=0.3)

    # 3) Hatch-Segmente
    ax = axes[2]
    ax.set_aspect('equal')

    # Polygons as outline
    for poly in polygons:
        ax.plot(poly[:, 0], poly[:, 1], 'gray', linewidth=0.5, alpha=0.5)

    # Hatch lines
    for seg in all_segments:
        p1, p2 = seg
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'b-', linewidth=0.3)

    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.set_title(f"Hatch-Segmente ({len(all_segments)})")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('complete_example.png', dpi=150)
    print("\nGespeichert: complete_example.png")

    # ========== SECOND EXAMPLE: without boundary (stripe structure) ==========
    print("\n" + "=" * 60)
    print("Beispiel 2: Streifenstruktur ohne Begrenzung")
    print("=" * 60)

    # Here: the original problem
    # Solution: the stripes have to be clipped to an area

    xs2, ys2, mask2 = create_grating_with_boundary(
        x_range=(-4, 4),  # Smaller area than the grating
        y_range=(-4, 4),
        res=400,
        grating_angle_deg=0,
        period=2.0,
        duty_cycle=0.5,
        boundary_func=lambda x, y: rectangular_boundary(x, y, 7, 7)
    )

    polygons2 = binary_mask_to_closed_polygons(mask2, xs2, ys2, min_area=100)
    print(f"Polygone: {len(polygons2)}")

    segments2 = []
    for poly in polygons2:
        segs = hatch_segments_for_polygon(poly, 90, 0.3, z=0)  # 90° Hatching
        segments2.extend(segs)

    print(f"Hatch-Segmente: {len(segments2)}")

    # Visualisation
    fig2, ax2 = plt.subplots(figsize=(8, 8))
    ax2.set_aspect('equal')

    for poly in polygons2:
        ax2.fill(poly[:, 0], poly[:, 1], alpha=0.3, facecolor='yellow',
                 edgecolor='red', linewidth=1)

    for seg in segments2:
        p1, p2 = seg
        ax2.plot([p1[0], p2[0]], [p1[1], p2[1]], 'b-', linewidth=0.5)

    ax2.set_xlim(-5, 5)
    ax2.set_ylim(-5, 5)
    ax2.set_title(f"Streifen mit 90° Hatching ({len(segments2)} Segmente)")
    ax2.grid(True, alpha=0.3)

    plt.savefig('stripes_example.png', dpi=150)
    print("Gespeichert: stripes_example.png")
