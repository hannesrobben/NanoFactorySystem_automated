# preprocess.py
"""Stage 0 — validator, converter, improver (docs/00 §2, §3.4).

Takes *any* supported geometry source, validates it, repairs it
deterministically, scales it to um, and writes the result as a
ground-truth GLB with a full repair protocol and SHA-256 hashes.
From here on the slicer is guaranteed to always see the same kind of
input: a single, unit-clean trimesh.Trimesh.

Reproducibility rules:
  * Every repair action is recorded (it changes geometry, hence
    potentially the scientific result).
  * The report carries hashes of the source file and of the ground truth,
    forming the provenance chain source -> ground truth -> job.h5
    (docs/02 §5).
  * Nothing is corrected silently: unit-plausibility issues produce
    warnings with a suggestion, never an automatic rescale.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import trimesh

from . import geometry_io, units

log = logging.getLogger(__name__)


@dataclass
class PreprocessReport:
    """Complete protocol of what the preprocessor saw and did."""
    source: str = ""
    unit: str = "um"
    scale_to_um: float = 1.0
    sha256_source: str | None = None
    sha256_ground_truth: str | None = None
    ground_truth_path: str | None = None
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    watertight_before: bool = False
    watertight_after: bool = False
    stats_before: dict = field(default_factory=dict)
    stats_after: dict = field(default_factory=dict)

    @property
    def is_printable(self) -> bool:
        """Watertight with positive volume — safe to slice."""
        return (self.watertight_after
                and self.stats_after.get("volume_um3", 0.0) > 0.0)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, **kw) -> str:
        return json.dumps(self.to_dict(), default=str, **kw)

    def __str__(self) -> str:
        state = "printable" if self.is_printable else "NOT printable"
        lines = [f"PreprocessReport [{state}] source={self.source}"]
        lines += [f"  action: {a}" for a in self.actions]
        lines += [f"  WARNING: {w}" for w in self.warnings]
        return "\n".join(lines)


@dataclass
class PreprocessResult:
    mesh: trimesh.Trimesh
    report: PreprocessReport


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def _mesh_stats(mesh: trimesh.Trimesh) -> dict:
    return {
        "n_vertices": int(len(mesh.vertices)),
        "n_faces": int(len(mesh.faces)),
        "extents_um": [float(x) for x in mesh.extents],
        "volume_um3": float(mesh.volume) if mesh.is_watertight else None,
        "euler_number": int(mesh.euler_number),
    }


# --------------------------------------------------------------------------
# repair steps (deterministic, each one logged)
# --------------------------------------------------------------------------

def _repair(mesh: trimesh.Trimesh, report: PreprocessReport) -> trimesh.Trimesh:
    def note(action: str) -> None:
        report.actions.append(action)
        log.info("preprocess: %s", action)

    n_v, n_f = len(mesh.vertices), len(mesh.faces)
    mesh.merge_vertices()
    if len(mesh.vertices) != n_v:
        note(f"merged duplicate vertices: {n_v} -> {len(mesh.vertices)}")

    keep = mesh.nondegenerate_faces()
    if not keep.all():
        mesh.update_faces(keep)
        note(f"removed {int((~keep).sum())} degenerate faces")

    unique = mesh.unique_faces()
    if not unique.all():
        mesh.update_faces(unique)
        note(f"removed {int((~unique).sum())} duplicate faces")

    if len(mesh.faces) != n_f and len(mesh.faces) == 0:
        raise ValueError("mesh has no valid faces after cleanup")

    if not mesh.is_winding_consistent or not mesh.is_watertight:
        trimesh.repair.fix_normals(mesh)
        note("fixed face winding / normals")

    if not mesh.is_watertight:
        before = mesh.is_watertight
        trimesh.repair.fill_holes(mesh)
        if mesh.is_watertight and not before:
            note("filled holes -> mesh is now watertight")
        else:
            note("attempted hole filling (mesh still not watertight)")

    if mesh.is_watertight and mesh.volume < 0:
        mesh.invert()
        note("inverted mesh (negative volume -> normals pointed inward)")

    return mesh


# --------------------------------------------------------------------------
# main entry point
# --------------------------------------------------------------------------

def run(
    source: str | Path | np.ndarray,
    *,
    unit: str = "um",
    pixel_size: float | None = None,
    base_height: float = 0.0,
    repair: bool = True,
    strict: bool = False,
    ground_truth_path: str | Path | None = None,
) -> PreprocessResult:
    """Validate, repair, unit-scale and persist a geometry source.

    Args:
        source: Mesh file path or 2D numpy height map.
        unit: Unit of the source coordinates (and of pixel_size /
            base_height for height maps). Converted exactly once, here.
        pixel_size: Lateral pixel size for height maps, in `unit`.
        base_height: Solid base below z=0 for height maps, in `unit`.
        repair: Run the deterministic repair pipeline.
        strict: Raise if the result is not printable (watertight, V > 0)
            instead of only warning.
        ground_truth_path: Where to write the GLB ground truth.
            None = "<source>_ground_truth.glb" next to the source;
            for array input None disables writing.

    Returns:
        PreprocessResult(mesh in um, report with actions/warnings/hashes).
    """
    report = PreprocessReport(unit=unit,
                              scale_to_um=units.scale_to_um(unit))

    # --- load + hash + scale ------------------------------------------------
    if isinstance(source, np.ndarray):
        report.source = "<height map>"
        report.sha256_source = _sha256_array(source)
        if pixel_size is None:
            raise ValueError("pixel_size is required for height map input")
        mesh = geometry_io.heightmap_to_mesh(
            np.asarray(source, dtype=np.float64) * report.scale_to_um,
            units.to_um(pixel_size, unit),
            units.to_um(base_height, unit),
        )
        report.actions.append(
            f"built watertight mesh from {source.shape} height map "
            f"(pixel {units.to_um(pixel_size, unit):.3f} um)")
    else:
        src = Path(source)
        report.source = str(src)
        report.sha256_source = _sha256_file(src)
        mesh = geometry_io.load_geometry(src, unit_scale=report.scale_to_um)
    if report.scale_to_um != 1.0:
        report.actions.append(
            f"scaled coordinates from {unit} to um "
            f"(factor {report.scale_to_um:g})")

    # --- validate before ------------------------------------------------
    report.watertight_before = bool(mesh.is_watertight)
    report.stats_before = _mesh_stats(mesh)

    # --- repair -----------------------------------------------------------
    if repair:
        mesh = _repair(mesh, report)

    # --- validate after ---------------------------------------------------
    report.watertight_after = bool(mesh.is_watertight)
    report.stats_after = _mesh_stats(mesh)
    report.warnings.extend(units.plausibility_warnings(mesh.extents))
    if not report.watertight_after:
        report.warnings.append(
            "mesh is not watertight — slicing may produce open contours")

    if strict and not report.is_printable:
        raise ValueError(f"preprocess failed strict check:\n{report}")

    # --- ground truth -------------------------------------------------------
    if ground_truth_path is None and not isinstance(source, np.ndarray):
        ground_truth_path = Path(source).with_name(
            Path(source).stem + "_ground_truth.glb")
    if ground_truth_path is not None:
        gt = geometry_io.save_as_glb(
            mesh, ground_truth_path,
            metadata={"preprocess_report": report.to_dict()})
        report.ground_truth_path = str(gt)
        report.sha256_ground_truth = _sha256_file(gt)
        report.actions.append(f"wrote ground truth {gt.name}")

    for w in report.warnings:
        log.warning("preprocess: %s", w)
    return PreprocessResult(mesh=mesh, report=report)
