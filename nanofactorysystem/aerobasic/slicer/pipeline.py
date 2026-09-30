# pipeline.py
"""Facade: full pipeline from any geometry source to a ToolpathJob.

    from tpp_slicer import slice_geometry, JobParameters
    job = slice_geometry("part.stl", JobParameters(), unit="mm",
                         optimize=True)
    save_job(job, "part_job.h5")

Stages (docs/00 §2): preprocess -> slice -> hatch -> build IR
[-> optimize] -> time estimate. Units: input in `unit`, everything after
the preprocessor strictly in um.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import trimesh

from . import hatching, preprocess, slicing
from .optimizer import optimize_job
from .parameters import JobParameters
from .timing import MotionParameters, estimate_toolpath
from .toolpath import ToolpathJob, build_job
from .voxel import VoxelModel, compensate

log = logging.getLogger(__name__)


def slice_geometry(
    source: str | Path | np.ndarray | trimesh.Trimesh,
    params: JobParameters | None = None,
    *,
    unit: str = "um",
    pixel_size: float | None = None,
    base_height: float = 0.0,
    run_preprocess: bool = True,
    strict: bool = False,
    ground_truth_path: str | Path | None = None,
    optimize: bool = False,
    motion: MotionParameters | None = None,
    voxel_model: VoxelModel | None = None,
) -> ToolpathJob:
    """Full pipeline: any geometry source -> ToolpathJob (IR).

    Args:
        source: Mesh file, height map array, or an already-prepared Trimesh
            (assumed to be in um; skips the preprocessor).
        params: Process parameters (defaults if None).
        unit: Unit of the source data; converted once by the preprocessor.
        pixel_size / base_height: Height-map options, in `unit`.
        run_preprocess: Validate/repair and write ground truth (docs/00).
        strict: Fail instead of warn on non-printable meshes.
        ground_truth_path: Target for the GLB ground truth.
        optimize: Run the path optimizer (order + direction of infill,
            start rotation of contour rings).
        motion: Machine motion model for time estimation/optimization.
        voxel_model: Voxel sizes for the laser parameters (T54). With data
            for params.laser the parameters are compensated
            (voxel.compensate: contour offset, first/last slice, spacing
            per params.slicing.spacing_mode); the values used are in
            job.meta["voxel"]. None or no data: unchanged behaviour.

    Returns:
        ToolpathJob with time estimate in job.meta["time_estimate"].
    """
    params = params or JobParameters()
    compensation = compensate(params, voxel_model)
    params = compensation.params
    motion = motion or MotionParameters(
        mark_speed_um_s=params.laser.scan_speed_um_s)
    t0 = time.perf_counter()

    # --- stage 0: preprocess -------------------------------------------------
    pre_report = None
    if isinstance(source, trimesh.Trimesh):
        mesh, source_name = source, "<in-memory mesh>"
    elif run_preprocess:
        result = preprocess.run(
            source, unit=unit, pixel_size=pixel_size,
            base_height=base_height, strict=strict,
            ground_truth_path=ground_truth_path)
        mesh, pre_report = result.mesh, result.report
        source_name = pre_report.source
    else:
        from . import geometry_io, units
        f = units.scale_to_um(unit)
        mesh = geometry_io.load_geometry(
            source, unit_scale=f,
            pixel_size_um=(units.to_um(pixel_size, unit)
                           if pixel_size is not None else None),
            base_height_um=units.to_um(base_height, unit))
        source_name = (str(source) if not isinstance(source, np.ndarray)
                       else "<height map>")

    # --- stages 1+2: slice + hatch -------------------------------------------
    layers = slicing.slice_mesh(mesh, params.slicing)
    hatching.hatch_layers(layers, params.slicing, compensation.context)

    # --- stage 3: build IR ----------------------------------------------------
    recipe = [{
        "step": "planar_slice_and_hatch",
        "strategy": params.slicing.hatch_strategy,
        "layer_height_um": params.slicing.layer_height_um,
        "hatch_spacing_um": params.slicing.hatch_spacing_um,
        "num_contour_lines": params.slicing.num_contour_lines,
        "contour_offset_um": params.slicing.contour_offset_um,
    }]
    job = build_job(layers, params, source_file=source_name, recipe=recipe)
    if pre_report is not None:
        job.meta["preprocess"] = pre_report.to_dict()
    if voxel_model is not None:
        job.meta["voxel"] = compensation.report

    # --- stage 4 (optional): optimize ------------------------------------------
    if optimize:
        result = optimize_job(job, motion)
        job = result.job

    # --- time estimate (always) --------------------------------------------
    est = estimate_toolpath(job, motion)
    job.meta["time_estimate"] = {
        "total_s": round(est.total_s, 4), "mark_s": round(est.mark_s, 4),
        "travel_s": round(est.travel_s, 4),
        "switch_s": round(est.switch_s, 4), "z_s": round(est.z_s, 4),
    }
    job.meta["slicing_time_s"] = round(time.perf_counter() - t0, 3)
    log.info("%s | est. print time %.2f s | pipeline %.2f s",
             job.summary(), est.total_s, job.meta["slicing_time_s"])
    return job
