##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Print a 3D model (STL, OBJ, GLB, ...) with the slicer in IFOV mode (one structure).

Only the MODEL block below has to be filled in: the model file, its unit and the slicing values.
Everything else has a working default:

- user, objective, resin drop and substrate data come from the SETTINGS block of ``main.py``
  (the same values as every other task);
- with ``SUBSTRATE_LABEL`` the experiment goes into that substrate below ``dataRoot`` (created if
  new, overlap with earlier experiments checked); with ``SUBSTRATE_LABEL = None`` into
  ``OUTPUT_ROOT`` of ``main.py``;
- the structure is placed in the center of the resin drop (``CENTER = None``);
- the experiment is named ``model3d_<file name>``.

Run with ``mains/`` as working directory::

    cd mains
    python main_3D_model.py              # the experiment (see ASK_EACH_STEP, SHOW_PLOTS)
    python main_3D_model.py --dry-run    # whole experiment on simulated hardware (temporary folder)

The model is sliced by ``Model3D_Slicer`` (program source ``SLICER``). The model file is stored in the
experiment by its path and SHA-256 (``inputs/``), so a restart rebuilds the same programs; do not change the
file afterwards. Former version: ``Experiments/old_experiment/historical/Model_3D_experiment.py`` (T166).
"""

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Optional

# main.py lies next to this file; make it importable however the script is started
sys.path.insert(0, str(Path(__file__).resolve().parent))

import main as settings  # noqa: E402
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D  # noqa: E402
from nanofactorysystem.experiment import ProgramSource  # noqa: E402
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, messagebox_confirm  # noqa: E402
from nanofactorysystem.plane_fitting import PlaneFitMode  # noqa: E402
from nanofactorysystem.resin_drop import ellipse_through  # noqa: E402

# =================================================================================================
# MODEL: the values you have to set
# =================================================================================================
MODEL_PATH = Path(r"C:\Users\Nanofactory\Desktop\Hannes\mdl_lens.stl")  # LAB: STL, OBJ, GLB, ...
MODEL_UNIT = "um"              # unit of the coordinates in the model file: "nm", "um", "mm", "cm", "m"
POWER_MW = 0.5                 # laser power of the structure
SLICER = {
    "velocity": 10_000,                # µm/s; IFOV writes with the fixed IFOV speed, kept for the time estimate
    "unit": MODEL_UNIT,
    "hatch_size": 0.2,                 # distance of hatch lines in µm (63x; 0.125 for the 20x)
    "slice_size": 0.2,                 # distance of slice planes in µm (63x; 0.15 for the 20x)
    "hatch_strategy": "alternating",   # "alternating", "linear_x", "linear_y", "cross", "concentric"
    "hatch_angle_deg": 0.0,            # base direction of the hatch lines (0 = along x)
    "contour_offset_um": 0.0,          # inward offset of the outline (half the voxel width)
    "num_contour_lines": 0,            # perimeter lines before the infill
}
SUBSTRATE_DEPTH_UM = 0.5       # the model starts this far inside the substrate (adhesion)

# =================================================================================================
# Where and how
# =================================================================================================
SUBSTRATE_LABEL: Optional[str] = None  # None: a single experiment in OUTPUT_ROOT of main.py
CENTER: Optional[Point2D] = None       # None: the center of the resin drop of main.RESIN_EDGES
MARGIN_AROUND_UM = 100.0               # free space around the model inside the experiment area
CAMERA_CAPTURE = True                  # camera image after the structure
ASK_EACH_STEP = True                   # message boxes before plane fit and printing
SHOW_PLOTS = True                      # layout plot windows (must be closed to continue)


def model_size_um(path: Path = None, unit: str = None) -> tuple[float, float, float]:
    """ Extent of the model in x, y and z in µm.

    Parameters
    ----------
    path : Path, optional
        Model file (default ``MODEL_PATH``).
    unit : str, optional
        Unit of the model coordinates (default ``MODEL_UNIT``).

    Returns
    -------
    tuple of float
        Width, length and height in µm.

    Raises
    ------
    FileNotFoundError
        If the model file does not exist.
    """

    import trimesh

    from nanofactorysystem.aerobasic.slicer.units import scale_to_um

    path = Path(path or MODEL_PATH)
    if not path.is_file():
        raise FileNotFoundError(f"Model file {path} not found; set MODEL_PATH in main_3D_model.py.")
    mesh = trimesh.load(str(path), force="mesh")
    extent = (mesh.bounds[1] - mesh.bounds[0]) * scale_to_um(unit or MODEL_UNIT)
    return float(extent[0]), float(extent[1]), float(extent[2])


def experiment_center() -> Point2D:
    """ ``CENTER``, or the center of the resin drop of ``main.RESIN_EDGES``. """

    if CENTER is not None:
        return CENTER
    drop = ellipse_through(settings.RESIN_EDGES)
    return Point2D(round(drop.cx), round(drop.cy))


def experiment_spec() -> ExperimentSpec:
    """ One IFOV experiment with the sliced model as its only structure.

    Returns
    -------
    ExperimentSpec
    """

    width, length, height = model_size_um()
    slicer = dict(SLICER, center=Point3D(0, 0, -SUBSTRATE_DEPTH_UM))
    return ExperimentSpec(
        name=f"model3d_{MODEL_PATH.stem}",
        objective=settings.OBJECTIVE,
        center=experiment_center(),
        grid=(1, 1),
        structure_size_um=max(width, length) + MARGIN_AROUND_UM,
        program_source=ProgramSource.SLICER,
        setup="IFOV_on",                 # required for SLICER
        plane_fit_mode=PlaneFitMode.CORNERS,
        dhm_usage=False,
        camera_capture=CAMERA_CAPTURE,
        default_power_mw=POWER_MW,
        materials={"resin": "SZ2080"},
        description=f"3D model {MODEL_PATH.name}: {width:.1f} x {length:.1f} x {height:.2f} µm, hatch "
                    f"{SLICER['hatch_size']} µm, slice {SLICER['slice_size']} µm, {SLICER['hatch_strategy']}",
        tags=["model3d", "slicer", "ifov"],
        structures=[StructureSpec(MODEL_PATH.stem, height_data=MODEL_PATH, power_mw=POWER_MW, slicer=slicer)],
    )


def execute(spec: ExperimentSpec, session) -> Path:
    """ Run the experiment on the substrate ``SUBSTRATE_LABEL``, or alone in ``OUTPUT_ROOT``.

    Parameters
    ----------
    spec : ExperimentSpec
        The experiment (see :func:`experiment_spec`).
    session : main.Session
        Backend, plane, confirmation, plots, data root and material registry.

    Returns
    -------
    Path
        The experiment folder.
    """

    if SUBSTRATE_LABEL is None:
        return session.run(spec)
    from nanofactorysystem.substrate_plan import SubstrateExperiment, run_substrate

    substrate = dataclasses.replace(settings.substrate_spec(), label=SUBSTRATE_LABEL)
    if session.data_root is not None:
        substrate = dataclasses.replace(substrate, data_root=session.data_root)
    [folder] = run_substrate(substrate, [SubstrateExperiment(spec)], backend=session.backend, plane=session.plane,
                             confirm=session.confirm, show_plot=session.show_plot,
                             material_registry=session.material_registry)
    session.last_experiment = Path(folder)
    return session.last_experiment


def run(*, dry: bool = False, workdir: Optional[Path] = None) -> Path:
    """ Slice the model and run the experiment.

    Parameters
    ----------
    dry : bool
        Simulated hardware; output in ``workdir`` (default: a temporary folder).
    workdir : Path, optional
        Folder of a dry run.

    Returns
    -------
    Path
        The experiment folder.
    """

    if dry:
        import matplotlib
        matplotlib.use("Agg")  # no plot windows in a dry run
    spec = experiment_spec()
    if not dry:
        return execute(spec, settings.Session(confirm=messagebox_confirm if ASK_EACH_STEP else None,
                                              show_plot=SHOW_PLOTS))

    from nanofactorysystem.backends.dummy.dry_run import dry_run

    with dry_run(settings.USER, workdir=workdir) as simulated:
        session = settings.Session(backend=simulated.backend, plane=simulated.plane,
                                   output_root=simulated.workdir / "out", data_root=simulated.workdir / "data_root",
                                   show_plot=False, material_registry=settings.dry_run_registry(simulated.workdir))
        session.output_root.mkdir(parents=True, exist_ok=True)
        print(f"DRY RUN on simulated hardware, output in {simulated.workdir}")
        try:
            return execute(spec, session)
        finally:
            session.material_registry.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print a 3D model with the slicer in IFOV mode")
    parser.add_argument("--dry-run", action="store_true", help="simulated hardware")
    folder = run(dry=parser.parse_args().dry_run)
    print(f"Experiment written to {folder}")
