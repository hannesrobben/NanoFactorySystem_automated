"""Cell primitives of test fields (T138, design docs/design/TEST_PRINT_PTD01.md §4.2).

A cell primitive is a pure function that returns ``list[ElementGroup]`` in **cell-local** µm
(origin = cell centre, z = 0 at the fitted plane). Every element carries its own ``power_mw`` and
``meta = {"cell": <cell id>, "part": <part name>}``. Primitives validate their inputs and raise
``ValueError`` naming the cell.

Volume cells are sliced from analytic height maps (no files, no random numbers) with
``slice_geometry``. Without a change to the slicer the planes lie on an aligned grid: every height
map starts at z = 0 and is sliced with ``voxel_height_um = 0``, so the slicer's planes are
``z_epsilon + k·Δz``; the primitive removes ``z_epsilon`` and rounds z to 1 nm, so cells with the
same Δz share their layers. Substrate anchoring (decision D15): the first slice (z = 0) is repeated
downwards at ``z = -k·Δz`` until ``anchor_depth_um`` is reached.

Deviation from the design table: ``dot`` is a short line in the layer plane, not a z line, because
IFOV blocks write in the plane of one layer (A/B galvo axes only).
"""
from __future__ import annotations

import dataclasses
import math
from typing import Iterable, Optional, Sequence, Union

import numpy as np

from nanofactorysystem.aerobasic.slicer import JobParameters, LaserParameters, SlicingParameters, slice_geometry
from nanofactorysystem.aerobasic.slicer.toolpath import (KIND_LAYER, ROLE_CONTOUR, ROLE_INFILL, ElementGroup,
                                                         PathElement)

from .structure import Z_DECIMALS

__all__ = ["DEFAULT_PIXEL_UM", "line", "line_set", "polyline", "dot", "suspended_line", "woodpile", "sliced",
           "pad_map", "pedestal_map", "wedge_map", "cap_map", "pillar_map", "pillar_on_base_map",
           "translate_groups", "groups_bounds"]

# Raster of the analytic height maps: edges of sliced cells are exact within one pixel
DEFAULT_PIXEL_UM = 0.05

Direction = Union[str, float]


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------
def _round_z(z: float) -> float:
    return round(float(z), Z_DECIMALS) + 0.0


def _require(condition: bool, cell_id: str, message: str) -> None:
    if not condition:
        raise ValueError(f"cell {cell_id}: {message}")


def _positive(cell_id: str, **values: float) -> None:
    for name, value in values.items():
        _require(value is not None and float(value) > 0, cell_id, f"{name} must be > 0, got {value}")


def _power(cell_id: str, power_mw: float) -> float:
    _require(power_mw is not None and float(power_mw) > 0, cell_id, f"power_mw must be > 0, got {power_mw}")
    return float(power_mw)


def _angle(cell_id: str, direction: Direction) -> float:
    if isinstance(direction, str):
        _require(direction in ("x", "y"), cell_id, f"direction must be 'x', 'y' or an angle, got {direction!r}")
        return 0.0 if direction == "x" else 90.0
    return float(direction)


def _meta(cell_id: str, part: str, **extra) -> dict:
    return {"cell": cell_id, "part": part, **extra}


def _group(z_um: float, elements: list[PathElement]) -> ElementGroup:
    return ElementGroup(kind=KIND_LAYER, z_um=_round_z(z_um), elements=elements)


def _segment(cell_id: str, part: str, center: Sequence[float], length_um: float, angle_deg: float, z_um: float,
             power_mw: float) -> PathElement:
    dx = 0.5 * length_um * math.cos(math.radians(angle_deg))
    dy = 0.5 * length_um * math.sin(math.radians(angle_deg))
    cx, cy = float(center[0]), float(center[1])
    return PathElement.from_segment_2d(cx - dx, cy - dy, cx + dx, cy + dy, _round_z(z_um), role=ROLE_INFILL,
                                       power_mw=power_mw, meta=_meta(cell_id, part))


def translate_groups(groups: Iterable[ElementGroup], dx_um: float = 0.0, dy_um: float = 0.0,
                     dz_um: float = 0.0) -> list[ElementGroup]:
    """ Copies of the groups moved by (dx, dy, dz); element metadata and powers are kept.

    Parameters
    ----------
    groups : iterable of ElementGroup
    dx_um, dy_um, dz_um : float
        Translation in µm.

    Returns
    -------
    list of ElementGroup
    """

    shift = np.array([dx_um, dy_um, dz_um], dtype=float)
    moved = []
    for group in groups:
        elements = [dataclasses.replace(e, points=e.points + shift, meta=dict(e.meta)) for e in group.elements]
        moved.append(ElementGroup(kind=group.kind, z_um=_round_z(group.z_um + dz_um), elements=elements,
                                  meta=dict(group.meta)))
    return moved


def groups_bounds(groups: Iterable[ElementGroup]) -> tuple[float, float, float, float]:
    """ Bounding box ``(x_min, y_min, x_max, y_max)`` of all element points in µm.

    Raises
    ------
    ValueError
        If there is no element.
    """

    points = [e.points for g in groups for e in g.elements]
    if not points:
        raise ValueError("no elements")
    stacked = np.vstack(points)
    return (float(stacked[:, 0].min()), float(stacked[:, 1].min()), float(stacked[:, 0].max()),
            float(stacked[:, 1].max()))


# ----------------------------------------------------------------------------------------------
# Line primitives
# ----------------------------------------------------------------------------------------------
def line(cell_id: str, *, length_um: float, power_mw: float, direction: Direction = "x", z_um: float = 0.0,
         passes: int = 1, offset_um: Sequence[float] = (0.0, 0.0), part: str = "line") -> list[ElementGroup]:
    """ One straight line, written ``passes`` times.

    Parameters
    ----------
    cell_id : str
        Cell id, stored in ``meta["cell"]`` of every element.
    length_um : float
        Line length.
    power_mw : float
        Laser power of every pass.
    direction : {"x", "y"} or float
        Line direction; a number is an angle in degrees from the x axis.
    z_um : float
        Height of the line relative to the fitted plane.
    passes : int
        Number of exposures of the same line (F1).
    offset_um : (float, float)
        Centre of the line in cell coordinates.
    part : str
        Part name in ``meta["part"]``.

    Returns
    -------
    list of ElementGroup
        One group at ``z_um``.
    """

    _positive(cell_id, length_um=length_um)
    _require(int(passes) >= 1, cell_id, f"passes must be >= 1, got {passes}")
    power = _power(cell_id, power_mw)
    angle = _angle(cell_id, direction)
    elements = [_segment(cell_id, part, offset_um, length_um, angle, z_um, power) for _ in range(int(passes))]
    return [_group(z_um, elements)]


def line_set(cell_id: str, *, n: int, pitch_um: float, length_um: float, power_mw: float, direction: Direction = "x",
             z_um: float = 0.0, passes: int = 1, offset_um: Sequence[float] = (0.0, 0.0),
             part: str = "line_set") -> list[ElementGroup]:
    """ ``n`` parallel lines with centre distance ``pitch_um``, centred on ``offset_um``.

    The lines are written one after another (each ``passes`` times before the next one).

    Parameters
    ----------
    cell_id : str
    n : int
        Number of lines (>= 1).
    pitch_um : float
        Centre-to-centre distance of neighbouring lines.
    length_um, power_mw, direction, z_um, passes, offset_um, part
        As in :func:`line`.

    Returns
    -------
    list of ElementGroup
        One group at ``z_um``.
    """

    _require(int(n) >= 1, cell_id, f"n must be >= 1, got {n}")
    _positive(cell_id, pitch_um=pitch_um, length_um=length_um)
    _require(int(passes) >= 1, cell_id, f"passes must be >= 1, got {passes}")
    power = _power(cell_id, power_mw)
    angle = _angle(cell_id, direction)
    normal = np.array([-math.sin(math.radians(angle)), math.cos(math.radians(angle))])
    elements = []
    for i in range(int(n)):
        center = np.asarray(offset_um, dtype=float) + normal * (i - (int(n) - 1) / 2) * float(pitch_um)
        elements += [_segment(cell_id, part, center, length_um, angle, z_um, power) for _ in range(int(passes))]
    return [_group(z_um, elements)]


def polyline(cell_id: str, *, points: Sequence[Sequence[float]], power_mw: float, closed: bool = False,
             z_um: float = 0.0, part: str = "polyline") -> list[ElementGroup]:
    """ One continuous laser-on path through ``points`` (printed with ``IFOV_PolyLines``).

    Parameters
    ----------
    cell_id : str
    points : sequence of (x, y)
        At least 2 points (3 for a closed path), cell coordinates in µm.
    power_mw : float
    closed : bool
        Return to the first point at the end.
    z_um : float
    part : str

    Returns
    -------
    list of ElementGroup
        One group at ``z_um``.
    """

    xy = np.asarray(points, dtype=float)
    _require(xy.ndim == 2 and xy.shape[1] == 2 and len(xy) >= (3 if closed else 2), cell_id,
             f"polyline needs at least {3 if closed else 2} (x, y) points")
    element = PathElement.from_polyline_2d(xy, _round_z(z_um), closed=closed, role=ROLE_CONTOUR,
                                           power_mw=_power(cell_id, power_mw), meta=_meta(cell_id, part))
    return [_group(z_um, [element])]


def dot(cell_id: str, *, x_um: float, y_um: float, power_mw: float, z_um: float = 0.0, size_um: float = 0.4,
        part: str = "dot") -> list[ElementGroup]:
    """ A dot of the 3-bit field id: a short line of ``size_um`` along x in the layer plane.

    Parameters
    ----------
    cell_id : str
    x_um, y_um : float
        Centre of the dot.
    power_mw : float
    z_um : float
    size_um : float
        Length of the short line.
    part : str

    Returns
    -------
    list of ElementGroup
    """

    return line(cell_id, length_um=size_um, power_mw=power_mw, z_um=z_um, offset_um=(x_um, y_um), part=part)


def suspended_line(cell_id: str, *, span_um: float, z_um: float, power_mw: float, extend_um: float = 0.0,
                   direction: Direction = "x", part: str = "bridge") -> list[ElementGroup]:
    """ A free-standing line between two supports (F2), ``span_um + 2 · extend_um`` long.

    ``extend_um`` lets the line reach into the supports (e.g. half the pedestal width, so that the
    line ends at the pedestal centres).

    Parameters
    ----------
    cell_id : str
    span_um : float
        Free span between the inner faces of the supports.
    z_um : float
        Height of the line (inside the top of the supports, design §9.1).
    power_mw : float
    extend_um : float
        Length added at both ends (>= 0).
    direction : {"x", "y"} or float
    part : str

    Returns
    -------
    list of ElementGroup
    """

    _positive(cell_id, span_um=span_um)
    _require(extend_um >= 0, cell_id, f"extend_um must be >= 0, got {extend_um}")
    return line(cell_id, length_um=span_um + 2 * extend_um, power_mw=power_mw, direction=direction, z_um=z_um,
                part=part)


def woodpile(cell_id: str, *, n_layers: int, rod_pitch_um: float, rod_length_um: float, dz_um: float,
             power_mw: float, z0_um: float = 0.0, part: str = "woodpile") -> list[ElementGroup]:
    """ Woodpile: rod layers alternating along x and y; every second layer of one direction is
    shifted by half a pitch (layers x, y, x', y', …).

    Parameters
    ----------
    cell_id : str
    n_layers : int
        Number of rod layers (>= 1).
    rod_pitch_um : float
        Distance of the rods within one layer.
    rod_length_um : float
        Rod length; the rods cover a square of this size.
    dz_um : float
        Layer distance.
    power_mw : float
    z0_um : float
        Height of the first layer.
    part : str

    Returns
    -------
    list of ElementGroup
        One group per rod layer.
    """

    _require(int(n_layers) >= 1, cell_id, f"n_layers must be >= 1, got {n_layers}")
    _positive(cell_id, rod_pitch_um=rod_pitch_um, rod_length_um=rod_length_um, dz_um=dz_um)
    n_rods = int(math.floor(rod_length_um / rod_pitch_um + 1e-9)) + 1
    _require(n_rods >= 2, cell_id, "rod_length_um must be at least one rod pitch")
    groups = []
    for k in range(int(n_layers)):
        direction = "x" if k % 2 == 0 else "y"
        shifted = (k // 2) % 2 == 1  # one rod less, centred: the rods lie half a pitch off the unshifted ones
        z = z0_um + k * dz_um
        groups += line_set(cell_id, n=n_rods - (1 if shifted else 0), pitch_um=rod_pitch_um, length_um=rod_length_um,
                           power_mw=power_mw, direction=direction, z_um=z, part=f"{part}_{k}")
    return groups


# ----------------------------------------------------------------------------------------------
# Analytic height maps (centred grids with a zero margin)
# ----------------------------------------------------------------------------------------------
def _grid(extent_x_um: float, extent_y_um: float, pixel_um: float) -> tuple[np.ndarray, np.ndarray]:
    nx = int(math.ceil(extent_x_um / pixel_um - 1e-9)) + 3
    ny = int(math.ceil(extent_y_um / pixel_um - 1e-9)) + 3
    xs = (np.arange(nx) - (nx - 1) / 2) * pixel_um
    ys = (np.arange(ny) - (ny - 1) / 2) * pixel_um
    return np.meshgrid(xs, ys)


def _inside(value, half: float) -> np.ndarray:
    return np.abs(value) <= half + 1e-9


def pad_map(size_x_um: float, size_y_um: float, height_um: float, *, ramp_um: float = 0.0,
            pixel_um: float = DEFAULT_PIXEL_UM) -> np.ndarray:
    """ Flat pad, optionally with a ramp on its +x side (F4: unwrapping help for the DHM).

    The footprint ``(size_x + ramp) × size_y`` is centred on the grid; the ramp falls linearly from
    ``height_um`` to 0 over ``ramp_um``.

    Returns
    -------
    np.ndarray
        Heights in µm (rows = y, cols = x), pixel ``pixel_um``, one zero pixel around the footprint.
    """

    total = size_x_um + ramp_um
    x, y = _grid(total, size_y_um, pixel_um)
    left = -total / 2
    heights = np.zeros_like(x)
    inside = _inside(y, size_y_um / 2) & (x >= left - 1e-9) & (x <= left + total + 1e-9)
    flat = x <= left + size_x_um + 1e-9
    heights[inside & flat] = height_um
    if ramp_um > 0:
        ramp = inside & ~flat
        heights[ramp] = height_um * (1.0 - (x[ramp] - (left + size_x_um)) / ramp_um)
    return np.clip(heights, 0.0, None)


def pedestal_map(size_x_um: float, size_y_um: float, height_um: float, *,
                 pixel_um: float = DEFAULT_PIXEL_UM) -> np.ndarray:
    """ Block support (F2 pedestals): a :func:`pad_map` without ramp. """

    return pad_map(size_x_um, size_y_um, height_um, pixel_um=pixel_um)


def wedge_map(length_x_um: float, width_y_um: float, height_um: float, *,
              pixel_um: float = DEFAULT_PIXEL_UM) -> np.ndarray:
    """ Wedge rising linearly along +x from 0 to ``height_um`` over ``length_x_um`` (F5).

    The wedge angle is ``atan(height / length)`` (8 × 6 × 3 µm: 20.6°).
    """

    x, y = _grid(length_x_um, width_y_um, pixel_um)
    inside = _inside(x, length_x_um / 2) & _inside(y, width_y_um / 2)
    heights = np.where(inside, height_um * (x + length_x_um / 2) / length_x_um, 0.0)
    return np.clip(heights, 0.0, None)


def cap_map(diameter_um: float, height_um: float, *, pixel_um: float = DEFAULT_PIXEL_UM) -> np.ndarray:
    """ Spherical cap of base diameter ``diameter_um`` and height ``height_um`` (F5 caps). """

    radius = diameter_um / 2
    sphere = (radius ** 2 + height_um ** 2) / (2 * height_um)
    x, y = _grid(diameter_um, diameter_um, pixel_um)
    rho2 = x ** 2 + y ** 2
    with np.errstate(invalid="ignore"):
        heights = np.sqrt(np.clip(sphere ** 2 - rho2, 0.0, None)) - (sphere - height_um)
    return np.where(rho2 <= radius ** 2 + 1e-9, np.clip(heights, 0.0, None), 0.0)


def pillar_map(diameter_um: float, height_um: float, *, extent_um: Optional[float] = None,
               pixel_um: float = DEFAULT_PIXEL_UM) -> np.ndarray:
    """ Cylinder of diameter ``diameter_um`` and height ``height_um`` on a grid of ``extent_um``. """

    extent = diameter_um if extent_um is None else max(extent_um, diameter_um)
    x, y = _grid(extent, extent, pixel_um)
    return np.where(x ** 2 + y ** 2 <= (diameter_um / 2) ** 2 + 1e-9, float(height_um), 0.0)


def pillar_on_base_map(base_x_um: float, base_y_um: float, base_height_um: float, diameter_um: float,
                       pillar_height_um: float, *, pixel_um: float = DEFAULT_PIXEL_UM) -> np.ndarray:
    """ Pillar on a base as one map: base pad, cylinder up to ``base_height + pillar_height``. """

    x, y = _grid(base_x_um, base_y_um, pixel_um)
    heights = np.where(_inside(x, base_x_um / 2) & _inside(y, base_y_um / 2), float(base_height_um), 0.0)
    pillar = x ** 2 + y ** 2 <= (diameter_um / 2) ** 2 + 1e-9
    heights[pillar] = base_height_um + pillar_height_um
    return heights


# Identical maps are sliced once per process (F2 pedestals, F7 bases): key = map bytes + parameters
_SLICE_CACHE: dict = {}
_SLICE_CACHE_SIZE = 64


def _sliced_layers(heights: np.ndarray, pixel_um: float, slicing: SlicingParameters) -> list:
    """ ``[(z, [PathElement, ...]), ...]`` of a centred height map on the aligned grid, cached.

    The elements are centred (map centre = origin), have z = k·Δz (``z_epsilon`` removed, rounded to
    1 nm) and must not be changed by the caller (copies are made with ``dataclasses.replace``).
    """

    key = (heights.shape, heights.tobytes(), pixel_um, repr(slicing))
    if key not in _SLICE_CACHE:
        job = slice_geometry(heights, JobParameters(slicing=slicing, laser=LaserParameters()),
                             pixel_size=pixel_um, run_preprocess=False)
        ny, nx = heights.shape
        layers = []
        for group in job.groups:
            if not group.elements:
                continue
            z = _round_z(group.z_um - slicing.z_epsilon_um)
            elements = []
            for element in group.elements:
                points = element.points - np.array([(nx - 1) * pixel_um / 2, (ny - 1) * pixel_um / 2, 0.0])
                points[:, 2] = z
                elements.append(dataclasses.replace(element, points=points, meta={}))
            layers.append((z, elements))
        if len(_SLICE_CACHE) >= _SLICE_CACHE_SIZE:
            _SLICE_CACHE.pop(next(iter(_SLICE_CACHE)))
        _SLICE_CACHE[key] = layers
    return _SLICE_CACHE[key]


# ----------------------------------------------------------------------------------------------
# Sliced volume cells
# ----------------------------------------------------------------------------------------------
def sliced(cell_id: str, *, height_map_um: np.ndarray, pixel_um: float, slicing: SlicingParameters, power_mw: float,
           anchor_depth_um: float = 0.0, offset_um: Sequence[float] = (0.0, 0.0), min_z_um: Optional[float] = None,
           part: str = "volume") -> list[ElementGroup]:
    """ Slice an analytic height map into layers on the aligned grid ``k · Δz``, anchored below z = 0.

    Parameters
    ----------
    cell_id : str
    height_map_um : np.ndarray
        Heights in µm (rows = y, cols = x) of a centred grid (the map helpers of this module).
    pixel_um : float
        Pixel size of the map.
    slicing : SlicingParameters
        Hatch distance, slice distance ``layer_height_um`` (= Δz), strategy, contours.
        ``voxel_height_um`` is forced to 0 (aligned grid).
    power_mw : float
        Power of every element.
    anchor_depth_um : float
        Depth below the interface down to which the first slice is repeated (D15); 0 = none.
    offset_um : (float, float)
        Centre of the map in cell coordinates.
    min_z_um : float, optional
        Drop layers below this z (e.g. the part of a pillar inside its base); then the anchor depth
        must be 0.
    part : str

    Returns
    -------
    list of ElementGroup
        Groups in ascending z; anchor layers carry ``meta["part"] = "anchor"``.

    Raises
    ------
    ValueError
        For invalid input or a map that gives no layer.
    """

    heights = np.asarray(height_map_um, dtype=float)
    _require(heights.ndim == 2 and heights.shape[0] >= 2 and heights.shape[1] >= 2, cell_id,
             "height map must be a 2-D array of at least 2 x 2 pixels")
    _require(np.isfinite(heights).all() and heights.min() >= 0, cell_id, "height map must be finite and >= 0")
    _require(heights.max() > slicing.z_epsilon_um, cell_id, "height map has no height")
    _positive(cell_id, pixel_um=pixel_um)
    _require(anchor_depth_um >= 0, cell_id, f"anchor_depth_um must be >= 0, got {anchor_depth_um}")
    _require(not (anchor_depth_um > 0 and min_z_um is not None and min_z_um > 0), cell_id,
             "a cell that starts above z = 0 (min_z_um) cannot be anchored")
    power = _power(cell_id, power_mw)
    slicing = dataclasses.replace(slicing, voxel_height_um=0.0)
    shift = np.array([float(offset_um[0]), float(offset_um[1]), 0.0])
    groups = []
    for z, layer in _sliced_layers(heights, float(pixel_um), slicing):
        if min_z_um is not None and z < _round_z(min_z_um):
            continue
        elements = [dataclasses.replace(element, points=element.points + shift, power_mw=power,
                                        meta=_meta(cell_id, part)) for element in layer]
        groups.append(ElementGroup(kind=KIND_LAYER, z_um=z, elements=elements))
    _require(bool(groups), cell_id, "slicing gave no layer")

    if anchor_depth_um > 0:
        first = groups[0]
        _require(first.z_um == 0.0, cell_id, f"anchoring needs a first layer at z = 0, got {first.z_um}")
        dz = float(slicing.layer_height_um)
        n_anchor = int(math.ceil(anchor_depth_um / dz - 1e-9))
        anchors = []
        for k in range(n_anchor, 0, -1):
            copy = translate_groups([first], dz_um=-k * dz)[0]
            for element in copy.elements:
                element.meta["part"] = "anchor"
            anchors.append(copy)
        groups = anchors + groups
    return groups
