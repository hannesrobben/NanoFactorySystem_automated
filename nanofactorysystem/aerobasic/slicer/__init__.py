"""tpp_slicer — modular slicing/hatching pipeline for TPP fabrication.

Public API (units strictly um internally; see units.py):
    slice_geometry            full pipeline (preprocess -> slice -> hatch -> IR)
    preprocess.run            stage 0 standalone (validate/repair/ground truth)
    ToolpathJob/ElementGroup/PathElement   the Toolpath-IR
    optimize_job              path optimizer (minimizes print *time*)
    estimate_toolpath         print time model
    save_job/load_job/read_group/iter_groups/write_dhm/write_surface_scan
    register_strategy         hatching extension point
"""
from .parameters import JobParameters, SlicingParameters, LaserParameters
from .toolpath import (ToolpathJob, ElementGroup, PathElement, build_job,
                       ROLE_SHELL, ROLE_CONTOUR, ROLE_INFILL,
                       KIND_LAYER, KIND_SHELL)
from .pipeline import slice_geometry
from .preprocess import run as preprocess_geometry, PreprocessReport
from .optimizer import optimize_job, optimize_group, OptimizationResult
from .timing import (MotionParameters, TimeEstimate, estimate_toolpath,
                     estimate_group, move_time_s)
from .geometry_io import load_geometry, heightmap_to_mesh, save_as_glb
from .hatching import register_strategy, available_strategies
from .storage import (save_job, load_job, read_group, iter_groups,
                      num_groups, read_params, read_time_estimate,
                      write_dhm, write_surface_scan)
from .units import to_um, from_um, UM_PER_UNIT

__all__ = [
    "JobParameters", "SlicingParameters", "LaserParameters",
    "ToolpathJob", "ElementGroup", "PathElement", "build_job",
    "ROLE_SHELL", "ROLE_CONTOUR", "ROLE_INFILL", "KIND_LAYER", "KIND_SHELL",
    "slice_geometry", "preprocess_geometry", "PreprocessReport",
    "optimize_job", "optimize_group", "OptimizationResult",
    "MotionParameters", "TimeEstimate", "estimate_toolpath",
    "estimate_group", "move_time_s",
    "load_geometry", "heightmap_to_mesh", "save_as_glb",
    "register_strategy", "available_strategies",
    "save_job", "load_job", "read_group", "iter_groups", "num_groups",
    "read_params", "read_time_estimate", "write_dhm", "write_surface_scan",
    "to_um", "from_um", "UM_PER_UNIT",
]
__version__ = "0.3.0"
