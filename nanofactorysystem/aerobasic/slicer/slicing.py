# slicing.py
"""Stage 2 — slicing.

One trimesh call (section_multiplane) computes all cross-sections; each
Path2D is converted to shapely polygons via .polygons_full (holes included).
Output is a list of Layer objects with contours only — hatching is the
next stage's job.
"""
from __future__ import annotations

import logging

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union

from .model import Layer, as_multipolygon
from .parameters import SlicingParameters

log = logging.getLogger(__name__)


def compute_z_levels(mesh: trimesh.Trimesh, params: SlicingParameters) -> np.ndarray:
    """Absolute z positions of the slice planes.

    The first plane sits z_epsilon above z_min: slicing exactly at the
    mesh minimum touches it tangentially and produces degenerate sections.
    """
    z_min, z_max = mesh.bounds[:, 2]
    start = z_min + params.z_epsilon_um
    if start >= z_max:
        raise ValueError(
            f"Model height ({z_max - z_min:.3f} um) smaller than z_epsilon."
        )
    return np.arange(start, z_max, params.layer_height_um)


def slice_mesh(mesh: trimesh.Trimesh, params: SlicingParameters) -> list[Layer]:
    """Slice a mesh into layers of shapely MultiPolygons."""
    z_levels = compute_z_levels(mesh, params)

    # heights are relative to plane_origin -> use origin at z=0
    sections = mesh.section_multiplane(
        plane_origin=[0.0, 0.0, 0.0],
        plane_normal=[0.0, 0.0, 1.0],
        heights=z_levels,
    )

    layers: list[Layer] = []
    for i, (z, sec) in enumerate(zip(z_levels, sections)):
        polys = _section_to_multipolygon(sec)
        if polys.is_empty:
            log.debug("Layer %d at z=%.3f um: empty section, skipped", i, z)
            continue
        layers.append(Layer(index=len(layers), z_um=float(z), contours=polys))

    log.info("Sliced mesh into %d non-empty layers (of %d planes)",
             len(layers), len(z_levels))
    return layers


def _section_to_multipolygon(section) -> MultiPolygon:
    """trimesh Path2D -> shapely MultiPolygon (empty on None/degenerate).

    section_multiplane already returns planar Path2D objects; for a
    z-normal plane the local coordinates coincide with world x/y.
    polygons_full gives exterior rings with their interior holes attached.
    """
    if section is None:
        return MultiPolygon([])
    try:
        polys = [p for p in section.polygons_full if p is not None and p.is_valid]
    except (AttributeError, ValueError):
        return MultiPolygon([])
    if not polys:
        return MultiPolygon([])
    # unary_union also repairs touching/overlapping islands
    return as_multipolygon(unary_union(polys))
