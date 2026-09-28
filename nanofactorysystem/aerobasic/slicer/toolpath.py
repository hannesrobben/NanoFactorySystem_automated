# toolpath.py
"""Toolpath intermediate representation (IR) — the central contract.

Everything downstream of the slicer (optimizer, translator, storage, time
model, comparison analyses) speaks only this format. Design (docs/01 §5):

    ToolpathJob
      └── ElementGroup (kind = "layer" | "shell")
            └── PathElement (points (M, 3) um, closed, role, overrides)

Key properties:
  * Points are ALWAYS 3D in structure-local um. A planar layer simply has
    constant z — a special case, not a special type. Tilted layers and
    shell paths need no extra handling.
  * `closed` distinguishes a contour ride (laser stays on around a ring)
    from an open hatch line. Closed elements store the ring WITHOUT a
    duplicated end point.
  * power/speed = None means "use job default"; a value is an override —
    the hook for future adaptive power without a format change.
  * `role` carries semantics for the translator (element-type dispatch),
    the optimizer (contours keep order, infill is permutable) and analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterator

import numpy as np
from shapely.geometry import MultiPolygon

from .parameters import JobParameters

ROLE_SHELL = "shell"
ROLE_CONTOUR = "contour"
ROLE_INFILL = "infill"
ROLES = (ROLE_SHELL, ROLE_CONTOUR, ROLE_INFILL)

KIND_LAYER = "layer"
KIND_SHELL = "shell"
KINDS = (KIND_LAYER, KIND_SHELL)


@dataclass
class PathElement:
    """One continuous laser-on path.

    Attributes:
        points: (M, 3) float64, structure-local um. Closed rings are stored
            without repeating the first point at the end.
        closed: True = ring (laser returns to start), False = open path.
        role: one of ROLES — semantic tag, not a rendering hint.
        power_mw / speed_um_s: None = job default, value = override.
        meta: free-form per-element metadata.
    """
    points: np.ndarray
    closed: bool = False
    role: str = ROLE_INFILL
    power_mw: float | None = None
    speed_um_s: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        pts = np.asarray(self.points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 3:
            raise ValueError(f"points must be (M, 3), got {pts.shape}")
        if pts.shape[0] < 2:
            raise ValueError("a path needs at least 2 points")
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got '{self.role}'")
        # convention: closed rings without duplicated end point
        if self.closed and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
            if pts.shape[0] < 3:
                raise ValueError("closed path needs at least 3 distinct points")
        self.points = pts

    # --- geometry ---------------------------------------------------------

    @property
    def start(self) -> np.ndarray:
        return self.points[0]

    @property
    def end(self) -> np.ndarray:
        """Where the laser ends up: ring -> back at start."""
        return self.points[0] if self.closed else self.points[-1]

    @property
    def length_um(self) -> float:
        seg = np.linalg.norm(np.diff(self.points, axis=0), axis=1).sum()
        if self.closed:
            seg += np.linalg.norm(self.points[-1] - self.points[0])
        return float(seg)

    @property
    def n_vertices(self) -> int:
        return self.points.shape[0]

    # --- transformations used by the optimizer ----------------------------

    def reversed(self) -> "PathElement":
        """Same path, opposite direction (for open paths)."""
        return replace(self, points=self.points[::-1].copy())

    def with_start_index(self, i: int) -> "PathElement":
        """Closed rings only: rotate the point list so vertex i comes first.

        A ring has no natural start — the optimizer picks the vertex
        closest to the current laser position.
        """
        if not self.closed:
            raise ValueError("start rotation only defined for closed paths")
        return replace(self, points=np.roll(self.points, -int(i), axis=0))

    @classmethod
    def from_segment_2d(cls, x0, y0, x1, y1, z, **kw) -> "PathElement":
        pts = np.array([[x0, y0, z], [x1, y1, z]], dtype=np.float64)
        return cls(points=pts, closed=False, **kw)

    @classmethod
    def from_polyline_2d(cls, xy: np.ndarray, z: float, **kw) -> "PathElement":
        xy = np.asarray(xy, dtype=np.float64)
        pts = np.column_stack([xy, np.full(len(xy), float(z))])
        return cls(points=pts, **kw)

    def __repr__(self) -> str:
        kind = "ring" if self.closed else "path"
        return (f"PathElement({self.role} {kind}, {self.n_vertices} pts, "
                f"{self.length_um:.1f} um)")


@dataclass
class ElementGroup:
    """A printable unit: one layer (constant/near-constant z) or one shell.

    Layer groups keep the design cross-section (`contours`) for in-situ
    DHM comparison; shell groups have no per-layer contour (docs/02 §4).
    """
    kind: str
    elements: list[PathElement] = field(default_factory=list)
    z_um: float | None = None
    contours: MultiPolygon | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got '{self.kind}'")
        if self.kind == KIND_LAYER and self.z_um is None:
            raise ValueError("layer groups require z_um")

    def __len__(self) -> int:
        return len(self.elements)

    def __iter__(self) -> Iterator[PathElement]:
        return iter(self.elements)

    @property
    def mark_length_um(self) -> float:
        return sum(e.length_um for e in self.elements)

    @property
    def area_um2(self) -> float | None:
        return self.contours.area if self.contours is not None else None

    def __repr__(self) -> str:
        z = f", z={self.z_um:.3f} um" if self.z_um is not None else ""
        return f"ElementGroup({self.kind}{z}, {len(self.elements)} elements)"


@dataclass
class ToolpathJob:
    """A complete sliced job in IR form: parameters + groups + provenance."""
    params: JobParameters
    groups: list[ElementGroup] = field(default_factory=list)
    source_file: str = ""
    recipe: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.groups)

    def __iter__(self) -> Iterator[ElementGroup]:
        return iter(self.groups)

    def __getitem__(self, i: int) -> ElementGroup:
        return self.groups[i]

    @property
    def n_elements(self) -> int:
        return sum(len(g) for g in self.groups)

    @property
    def mark_length_um(self) -> float:
        return sum(g.mark_length_um for g in self.groups)

    def summary(self) -> str:
        kinds = {}
        for g in self.groups:
            kinds[g.kind] = kinds.get(g.kind, 0) + 1
        kinds_s = ", ".join(f"{v} {k}" for k, v in kinds.items())
        return (f"ToolpathJob: {len(self.groups)} groups ({kinds_s}), "
                f"{self.n_elements} elements, "
                f"mark length {self.mark_length_um / 1000:.2f} mm")


# --------------------------------------------------------------------------
# builder: slicer-internal Layer objects -> IR
# --------------------------------------------------------------------------

def group_from_layer(layer) -> ElementGroup:
    """Convert one slicer Layer (contour_paths + hatches) to an ElementGroup.

    Order convention (docs/01 §6): contour rings first (as produced,
    outer -> inner), then infill lines.
    """
    z = float(layer.z_um)
    elements: list[PathElement] = []

    for path in layer.contour_paths:
        elements.append(PathElement.from_polyline_2d(
            path[:, :2], z, closed=True, role=ROLE_CONTOUR))

    for x0, y0, x1, y1 in np.asarray(layer.hatches, dtype=np.float64):
        elements.append(PathElement.from_segment_2d(
            x0, y0, x1, y1, z, role=ROLE_INFILL))

    return ElementGroup(kind=KIND_LAYER, elements=elements, z_um=z,
                        contours=layer.contours,
                        meta=dict(layer.meta))


def build_job(layers, params: JobParameters, source_file: str = "",
              recipe: list[dict] | None = None) -> ToolpathJob:
    """Assemble a ToolpathJob from sliced+hatched Layer objects."""
    groups = [group_from_layer(l) for l in layers]
    return ToolpathJob(params=params, groups=groups,
                       source_file=source_file, recipe=recipe or [])
