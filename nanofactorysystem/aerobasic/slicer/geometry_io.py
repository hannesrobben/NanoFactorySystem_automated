# geometry_io.py
"""Stage 1 — data ingestion.

Everything becomes a trimesh.Trimesh in physical units (um), regardless of
whether it started as STL, GLB, OBJ, PLY or a height map. The canonical
on-disk format for geometry is GLB (binary, float64-capable, metadata via
JSON header) — see save_as_glb().
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

MESH_SUFFIXES = {".stl", ".glb", ".gltf", ".obj", ".ply", ".3mf", ".off"}


def load_geometry(
    source: str | Path | np.ndarray,
    *,
    unit_scale: float = 1.0,
    pixel_size_um: float | None = None,
    base_height_um: float = 0.0,
) -> trimesh.Trimesh:
    """Load any supported geometry source into a Trimesh in um.

    Args:
        source: Path to a mesh file, or a 2D numpy array (height map in um).
        unit_scale: Multiplier applied to mesh coordinates. E.g. an STL
            designed in mm needs unit_scale=1000 to land in um.
        pixel_size_um: Lateral pixel size — required for height maps.
        base_height_um: Extrusion base below z=0 for height maps (gives the
            surface a solid, watertight underside).

    Returns:
        A single, processed trimesh.Trimesh.
    """
    if isinstance(source, np.ndarray):
        if pixel_size_um is None:
            raise ValueError("pixel_size_um is required for height map input")
        mesh = heightmap_to_mesh(source, pixel_size_um, base_height_um)
    else:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() not in MESH_SUFFIXES:
            raise ValueError(
                f"Unsupported format '{path.suffix}'. "
                f"Supported: {sorted(MESH_SUFFIXES)} or 2D numpy height map."
            )
        loaded = trimesh.load(path, force="mesh")
        mesh = _ensure_single_mesh(loaded)

    if unit_scale != 1.0:
        mesh.apply_scale(unit_scale)

    return mesh


def _ensure_single_mesh(obj) -> trimesh.Trimesh:
    """Collapse a possible Scene into a single Trimesh."""
    if isinstance(obj, trimesh.Trimesh):
        return obj
    if isinstance(obj, trimesh.Scene):
        return obj.to_mesh()
    raise TypeError(f"Cannot interpret loaded object of type {type(obj)}")


def heightmap_to_mesh(
    height_map: np.ndarray,
    pixel_size_um: float,
    base_height_um: float = 0.0,
) -> trimesh.Trimesh:
    """Convert a 2D height map to a watertight surface mesh.

    The grid (rows=y, cols=x) is triangulated into a top surface; side
    walls and a bottom plate close the volume so that planar slicing
    yields proper closed contours.
    """
    hm = np.asarray(height_map, dtype=np.float64)
    if hm.ndim != 2:
        raise ValueError("height map must be a 2D array")
    ny, nx = hm.shape
    if nx < 2 or ny < 2:
        raise ValueError("height map needs at least 2x2 pixels")

    xs = np.arange(nx, dtype=np.float64) * pixel_size_um
    ys = np.arange(ny, dtype=np.float64) * pixel_size_um
    xx, yy = np.meshgrid(xs, ys)

    # --- top surface vertices ---
    top = np.column_stack([xx.ravel(), yy.ravel(), hm.ravel()])
    # --- bottom vertices (flat plate at -base_height) ---
    bottom = top.copy()
    bottom[:, 2] = -base_height_um

    verts = np.vstack([top, bottom])
    n = nx * ny  # offset of bottom vertices

    def vid(r: int, c: int) -> int:
        return r * nx + c

    faces: list[list[int]] = []
    # top surface (two triangles per cell, CCW seen from +z)
    for r in range(ny - 1):
        for c in range(nx - 1):
            a, b = vid(r, c), vid(r, c + 1)
            d, e = vid(r + 1, c), vid(r + 1, c + 1)
            faces.append([a, e, b])
            faces.append([a, d, e])
    # bottom surface (reversed winding)
    for r in range(ny - 1):
        for c in range(nx - 1):
            a, b = vid(r, c) + n, vid(r, c + 1) + n
            d, e = vid(r + 1, c) + n, vid(r + 1, c + 1) + n
            faces.append([a, b, e])
            faces.append([a, e, d])
    # side walls
    for c in range(nx - 1):  # front (r=0) and back (r=ny-1)
        a, b = vid(0, c), vid(0, c + 1)
        faces.append([a, b, b + n]); faces.append([a, b + n, a + n])
        a, b = vid(ny - 1, c), vid(ny - 1, c + 1)
        faces.append([b, a, a + n]); faces.append([b, a + n, b + n])
    for r in range(ny - 1):  # left (c=0) and right (c=nx-1)
        a, b = vid(r, 0), vid(r + 1, 0)
        faces.append([b, a, a + n]); faces.append([b, a + n, b + n])
        a, b = vid(r, nx - 1), vid(r + 1, nx - 1)
        faces.append([a, b, b + n]); faces.append([a, b + n, a + n])

    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    return mesh


def save_as_glb(mesh: trimesh.Trimesh, path: str | Path,
                metadata: dict | None = None) -> Path:
    """Persist geometry in the canonical GLB format (with JSON metadata)."""
    path = Path(path).with_suffix(".glb")
    if metadata:
        mesh.metadata.update(metadata)
    mesh.export(path)
    return path
