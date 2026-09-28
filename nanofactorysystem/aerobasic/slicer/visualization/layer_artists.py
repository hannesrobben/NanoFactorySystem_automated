# layer_artists.py
"""IR -> render primitives (shared by static flipbook and future slider).

Design rule (docs/05 §4): this module knows only the Toolpath-IR
(``ToolpathJob`` / ``ElementGroup`` / ``PathElement``) and shapely — no
matplotlib Figure/Axes. It converts one ``ElementGroup`` into plain data
structures that any renderer can consume:

    LayerArtistData
        infill_segments   list[(2, 2) ndarray]   open 2-point hatch lines
        contour_paths     list[(M, 2) ndarray]   rings/multi-vertex paths
        contour_closed    list[bool]             one flag per contour path
        design_polygons   list[(exterior, [holes])]  the design cross-section

Keeping the extraction separate from the plotting means the expensive part
(walking thousands of PathElements, stacking coordinates) runs exactly once
per layer and both the PNG flipbook (static.py) and a future interactive
slider (docs/05 §3.1) reuse the identical primitives.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class LayerArtistData:
    """Render-ready primitives of one layer (structure-local µm, 2D)."""
    z_um: float
    #: Open 2-point infill segments, each (2, 2): [[x0, y0], [x1, y1]].
    #: Shaped for direct use in ``matplotlib.collections.LineCollection``.
    infill_segments: list[np.ndarray] = field(default_factory=list)
    #: Contour/shell polylines, each (M, 2). Closed rings are stored
    #: WITH the closing vertex repeated (renderers draw them as-is).
    contour_paths: list[np.ndarray] = field(default_factory=list)
    contour_closed: list[bool] = field(default_factory=list)
    #: Design cross-section from ``ElementGroup.contours``:
    #: one (exterior (K, 2), [hole (L, 2), ...]) tuple per polygon.
    design_polygons: list[tuple[np.ndarray, list[np.ndarray]]] = \
        field(default_factory=list)

    @property
    def n_infill(self) -> int:
        return len(self.infill_segments)

    @property
    def n_contours(self) -> int:
        return len(self.contour_paths)

    def bounds(self) -> tuple[float, float, float, float] | None:
        """(xmin, ymin, xmax, ymax) over all primitives, or None if empty."""
        arrays = list(self.infill_segments) + list(self.contour_paths)
        arrays += [ext for ext, _ in self.design_polygons]
        if not arrays:
            return None
        stacked = np.vstack(arrays)
        (xmin, ymin), (xmax, ymax) = stacked.min(axis=0), stacked.max(axis=0)
        return float(xmin), float(ymin), float(xmax), float(ymax)


def layer_artist_data(group) -> LayerArtistData:
    """Convert one layer ``ElementGroup`` into render primitives.

    Element routing mirrors ``Model3D_Slicer.iterate_layers`` exactly:
    open 2-point infill elements -> segments (the IFOV_Lines track);
    everything else (contour rings, multi-vertex paths) -> contour paths
    (the IFOV_PolyLines track). What you see in the plot is therefore
    what the translator will emit, element for element.
    """
    if group.z_um is None:
        raise ValueError(
            f"group kind='{group.kind}' has no z_um — only layer groups "
            "can be rendered as 2D cross-sections")
    data = LayerArtistData(z_um=float(group.z_um))

    for element in group.elements:
        pts2d = np.asarray(element.points, dtype=np.float64)[:, :2]
        is_plain_infill = (element.role == "infill"
                           and not element.closed
                           and len(pts2d) == 2)
        if is_plain_infill:
            data.infill_segments.append(pts2d)
        else:
            if element.closed:
                # IR stores rings without the repeated end vertex —
                # close them for drawing.
                pts2d = np.vstack([pts2d, pts2d[:1]])
            data.contour_paths.append(pts2d)
            data.contour_closed.append(bool(element.closed))

    if group.contours is not None and not group.contours.is_empty:
        for poly in group.contours.geoms:
            exterior = np.asarray(poly.exterior.coords, dtype=np.float64)
            holes = [np.asarray(ring.coords, dtype=np.float64)
                     for ring in poly.interiors]
            data.design_polygons.append((exterior, holes))

    return data


def job_bounds(job) -> tuple[float, float, float, float]:
    """Common (xmin, ymin, xmax, ymax) over all layer groups of a job.

    Used so every frame of the flipbook shares identical axis limits —
    otherwise autoscaling makes the structure appear to jump/breathe
    between layers.
    """
    xmin = ymin = np.inf
    xmax = ymax = -np.inf
    for group in job.groups:
        if group.z_um is None:
            continue
        b = layer_artist_data(group).bounds()
        if b is None:
            continue
        xmin, ymin = min(xmin, b[0]), min(ymin, b[1])
        xmax, ymax = max(xmax, b[2]), max(ymax, b[3])
    if not np.isfinite([xmin, ymin, xmax, ymax]).all():
        raise ValueError("job contains no renderable layer groups")
    return float(xmin), float(ymin), float(xmax), float(ymax)
