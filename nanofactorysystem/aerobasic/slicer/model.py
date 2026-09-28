# model.py
"""Slicer-internal data model: Layer.

Note: the pipeline OUTPUT is the Toolpath-IR (toolpath.py). Layer is the
intermediate product between slicing and hatching, kept because it carries
the shapely contours needed for hatching and for in-situ DHM comparison.

This is the *contract* between the pipeline stages. Slicing produces it,
hatching enriches it, storage persists it, exporters consume it. No stage
needs to know about any other stage's internals.

Design notes:
    * Contours are shapely (Multi)Polygons — they natively support holes,
      offsets and boolean operations.
    * Hatches are a plain (N, 4) float64 numpy array [x0, y0, x1, y1]:
      the most compact, HDF5-friendly and machine-code-friendly form.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Any

import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .parameters import JobParameters


def as_multipolygon(geom: BaseGeometry | None) -> MultiPolygon:
    """Normalize any shapely geometry to a MultiPolygon (may be empty)."""
    if geom is None or geom.is_empty:
        return MultiPolygon([])
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    # GeometryCollection: keep only polygonal parts
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    return MultiPolygon(polys)


@dataclass
class Layer:
    """One slice of the model.

    Attributes:
        index: Layer number (0 = first printed layer).
        z_um: Absolute z position of the slice plane.
        contours: Cross-section as MultiPolygon (holes included).
        hatches: (N, 4) array of hatch segments [x0, y0, x1, y1] in um.
        contour_paths: Optional perimeter polylines, list of (M, 2) arrays.
        meta: Free-form per-layer metadata (e.g. laser power override).
    """
    index: int
    z_um: float
    contours: MultiPolygon
    hatches: np.ndarray = field(
        default_factory=lambda: np.empty((0, 4), dtype=np.float64)
    )
    contour_paths: list[np.ndarray] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def area_um2(self) -> float:
        return self.contours.area

    @property
    def hatch_length_um(self) -> float:
        if len(self.hatches) == 0:
            return 0.0
        d = self.hatches[:, 2:4] - self.hatches[:, 0:2]
        return float(np.linalg.norm(d, axis=1).sum())

    def __repr__(self) -> str:
        return (
            f"Layer(index={self.index}, z={self.z_um:.3f}um, "
            f"polygons={len(self.contours.geoms)}, hatches={len(self.hatches)})"
        )
