# hatching.py
"""Stage 3 — hatching.

Strategies are plain functions registered by name. A strategy receives one
layer's contours (MultiPolygon) plus context and returns an (N, 4) array
of hatch segments. New techniques (spiral, adaptive, greyscale, ...) are
added with @register_strategy — no if/elif chains anywhere.

Performance note: all scan lines of a layer are clipped against the
polygon in a *single* shapely intersection call (vectorized in GEOS),
instead of one Python-level call per line.
"""
from __future__ import annotations

import logging
from typing import Callable, Protocol

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon

from .model import Layer, as_multipolygon
from .parameters import SlicingParameters

log = logging.getLogger(__name__)

EMPTY = np.empty((0, 4), dtype=np.float64)


class HatchStrategy(Protocol):
    def __call__(self, contours: MultiPolygon, layer_index: int,
                 params: SlicingParameters) -> np.ndarray: ...


_REGISTRY: dict[str, HatchStrategy] = {}


def register_strategy(name: str) -> Callable[[HatchStrategy], HatchStrategy]:
    """Decorator: register a hatching strategy under a name."""
    def deco(func: HatchStrategy) -> HatchStrategy:
        if name in _REGISTRY:
            raise KeyError(f"Strategy '{name}' already registered")
        _REGISTRY[name] = func
        return func
    return deco


def available_strategies() -> list[str]:
    return sorted(_REGISTRY)


def get_strategy(name: str) -> HatchStrategy:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown hatch strategy '{name}'. "
            f"Available: {available_strategies()}"
        ) from None


# --------------------------------------------------------------------------
# core primitive: clip parallel scan lines against a polygon
# --------------------------------------------------------------------------

def _linear_hatch(contours: MultiPolygon, spacing: float,
                  angle_deg: float = 0.0) -> np.ndarray:
    """Parallel hatch lines at an arbitrary angle, clipped to the polygon.

    Implementation: rotate the polygon by -angle around its centroid, hatch
    with horizontal lines, rotate the resulting segments back. This keeps
    the scan-line generation trivially axis-aligned for any angle.
    """
    if contours.is_empty:
        return EMPTY

    origin = contours.centroid
    poly = (affinity.rotate(contours, -angle_deg, origin=origin)
            if angle_deg % 180.0 else contours)

    xmin, ymin, xmax, ymax = poly.bounds
    # center the raster on the bbox so both margins are symmetric
    span = ymax - ymin
    n_lines = int(span // spacing) + 1
    y0 = ymin + 0.5 * (span - (n_lines - 1) * spacing)
    ys = y0 + np.arange(n_lines) * spacing

    scan = MultiLineString([((xmin - spacing, y), (xmax + spacing, y))
                            for y in ys])
    clipped = poly.intersection(scan)  # single GEOS call for all lines

    segments = _extract_segments(clipped)
    if segments.size and angle_deg % 180.0:
        segments = _rotate_segments(segments, angle_deg, origin)
    return segments


def _extract_segments(geom) -> np.ndarray:
    """Any shapely result -> (N, 4) array of straight segments."""
    lines: list[LineString] = []
    stack = [geom]
    while stack:
        g = stack.pop()
        if g.is_empty:
            continue
        if isinstance(g, LineString):
            lines.append(g)
        elif hasattr(g, "geoms"):  # Multi*/GeometryCollection
            stack.extend(g.geoms)
        # Points (tangent touches) are dropped deliberately

    if not lines:
        return EMPTY

    out: list[np.ndarray] = []
    for ls in lines:
        c = np.asarray(ls.coords)
        # a LineString may have >2 vertices -> split into segments
        out.append(np.hstack([c[:-1], c[1:]]))
    return np.vstack(out).astype(np.float64)


def _rotate_segments(seg: np.ndarray, angle_deg: float, origin) -> np.ndarray:
    a = np.deg2rad(angle_deg)
    c, s = np.cos(a), np.sin(a)
    rot = np.array([[c, -s], [s, c]])
    ox, oy = origin.x, origin.y
    pts = seg.reshape(-1, 2) - (ox, oy)
    pts = pts @ rot.T + (ox, oy)
    return pts.reshape(-1, 4)


# --------------------------------------------------------------------------
# built-in strategies
# --------------------------------------------------------------------------

@register_strategy("linear_x")
def hatch_linear_x(contours, layer_index, params):
    return _linear_hatch(contours, params.hatch_spacing_um,
                         params.hatch_angle_deg)


@register_strategy("linear_y")
def hatch_linear_y(contours, layer_index, params):
    return _linear_hatch(contours, params.hatch_spacing_um,
                         params.hatch_angle_deg + 90.0)


@register_strategy("alternating")
def hatch_alternating(contours, layer_index, params):
    """X on even layers, Y on odd layers — improves isotropy."""
    angle = params.hatch_angle_deg + (90.0 if layer_index % 2 else 0.0)
    return _linear_hatch(contours, params.hatch_spacing_um, angle)


@register_strategy("cross")
def hatch_cross(contours, layer_index, params):
    """X and Y in the *same* layer (dense, e.g. for critical layers)."""
    a = _linear_hatch(contours, params.hatch_spacing_um, params.hatch_angle_deg)
    b = _linear_hatch(contours, params.hatch_spacing_um,
                      params.hatch_angle_deg + 90.0)
    return np.vstack([a, b]) if a.size or b.size else EMPTY


@register_strategy("concentric")
def hatch_concentric(contours, layer_index, params):
    """Inward offset contours (shapely buffer) until the area vanishes."""
    segments: list[np.ndarray] = []
    step = params.hatch_spacing_um
    current = contours
    guard = 100_000  # hard iteration cap
    while not current.is_empty and guard:
        guard -= 1
        for poly in as_multipolygon(current).geoms:
            for ring in [poly.exterior, *poly.interiors]:
                c = np.asarray(ring.coords)
                if len(c) >= 2:
                    segments.append(np.hstack([c[:-1], c[1:]]))
        current = current.buffer(-step, join_style="mitre")
    return np.vstack(segments) if segments else EMPTY


# --------------------------------------------------------------------------
# layer processing
# --------------------------------------------------------------------------

def extract_contour_paths(contours: MultiPolygon,
                          n_lines: int, offset: float) -> list[np.ndarray]:
    """Perimeter polylines: n_lines rings, each `offset` further inward."""
    paths: list[np.ndarray] = []
    current = contours
    for _ in range(n_lines):
        if current.is_empty:
            break
        for poly in as_multipolygon(current).geoms:
            for ring in [poly.exterior, *poly.interiors]:
                paths.append(np.asarray(ring.coords, dtype=np.float64))
        current = current.buffer(-offset, join_style="mitre")
    return paths


def hatch_layer(layer: Layer, params: SlicingParameters) -> Layer:
    """Fill one layer in place: contour paths + infill hatches."""
    region = layer.contours

    # optional shrink to compensate the lateral voxel radius
    if params.contour_offset_um > 0:
        region = as_multipolygon(
            region.buffer(-params.contour_offset_um, join_style="mitre")
        )

    if params.num_contour_lines > 0:
        layer.contour_paths = extract_contour_paths(
            region, params.num_contour_lines, params.hatch_spacing_um
        )
        # infill starts inside the innermost perimeter
        region = as_multipolygon(region.buffer(
            -params.num_contour_lines * params.hatch_spacing_um,
            join_style="mitre",
        ))

    strategy = get_strategy(params.hatch_strategy)
    layer.hatches = strategy(region, layer.index, params)
    return layer


def hatch_layers(layers: list[Layer], params: SlicingParameters) -> list[Layer]:
    for layer in layers:
        hatch_layer(layer, params)
    return layers
