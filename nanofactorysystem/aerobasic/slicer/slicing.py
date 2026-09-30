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

    With a voxel height (params.voxel_height_um > 0) the first and the last
    plane lie half a voxel height inside the bottom and top surface, so the
    voxels of the outer layers end at the design surfaces; the planes in
    between are spaced evenly with at most layer_height_um. A part thinner
    than one voxel gets one plane at mid-height (with a warning).
    """
    z_min, z_max = mesh.bounds[:, 2]
    if params.voxel_height_um > 0:
        return _voxel_z_levels(float(z_min), float(z_max), params)
    start = z_min + params.z_epsilon_um
    if start >= z_max:
        raise ValueError(
            f"Model height ({z_max - z_min:.3f} um) smaller than z_epsilon."
        )
    return np.arange(start, z_max, params.layer_height_um)


def _voxel_z_levels(z_min: float, z_max: float, params: SlicingParameters) -> np.ndarray:
    """Slice planes for a known voxel height (see compute_z_levels)."""
    half = params.voxel_height_um / 2
    eps = params.z_epsilon_um
    bottom = max(z_min + half, z_min + eps)
    top = min(z_max - half, z_max - eps)
    if top <= bottom:
        log.warning("Model height %.3f um is not larger than the voxel height %.3f um: one slice at mid-height",
                    z_max - z_min, params.voxel_height_um)
        return np.array([(z_min + z_max) / 2])
    n_planes = int(np.ceil((top - bottom) / params.layer_height_um - 1e-9)) + 1
    return np.linspace(bottom, top, n_planes)


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
