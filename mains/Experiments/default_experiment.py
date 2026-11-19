##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Default experiment: every setting of an experiment, with an explanation (T110).

Start here if you are new to the experiment environment. This file is a complete, runnable
experiment description. Every field of ``ExperimentSpec`` and ``StructureSpec`` is written out
with its default value and a comment, so you can see what can be set without reading the library.

How an experiment works
-----------------------
1. You describe the experiment as an ``ExperimentSpec`` (this file): objective, position on the
   substrate, structure grid, structures and how they are printed and measured.
2. ``run_experiment(spec, ...)`` runs the usual flow on the machine:
   plot -> plane fit -> OPL scan (DHM only) -> add structures -> build programs -> print.
   On the lab PC each step is confirmed in a message box.
3. Everything ends up in ONE file ``<experiment folder>/experiment.h5`` (plus JSON copies,
   console log, summary). The spec itself is stored as ``experiment_spec.json`` and can be
   loaded and run again (``ExperimentSpec.load(...)``).

Two ways to describe the geometry (``program_source``):

- ``ProgramSource.DRAWING``: Python drawing classes (``Rectangle3D``, ``Stair``, gratings, lenses,
  ...), see :func:`drawing_spec`.
- ``ProgramSource.SLICER``: a height map (2-D array in µm) or a mesh file (STL, ...) is sliced
  into layers and printed in IFOV mode, see :func:`slicer_spec`.

Run
---
- Normally through ``mains/main.py`` (TASK = "experiment"), which uses :func:`experiment_spec`.
- Directly: ``cd mains && python -m Experiments.default_experiment`` (lab PC).
- Dry run on simulated hardware, no lab PC needed:
  ``cd mains && python -m Experiments.default_experiment --dry-run``.

Copy this file for a new experiment (e.g. ``mains/Experiments/<topic>/<name>.py``), delete what
you do not need and change the values. Values marked "default" can simply be left out.
"""
import argparse
from pathlib import Path
from typing import Optional

import numpy as np

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D, Stair
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource
from nanofactorysystem.experiment_spec import (ExperimentSpec, StructureSpec, default_sys_args, messagebox_confirm,
                                               run_experiment)
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.structure_factories import BuildContext, structure_factory

# ------------------------------------------------------------------------------------------------
# Where on the substrate (all positions are absolute stage coordinates in µm)
# ------------------------------------------------------------------------------------------------
# Edges of the resin drop, measured with the camera: right, left, near, far.
# Four points define the ellipse that is the printable area (the experiment center must lie
# inside it); with fewer points their bounding box is used.
RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]
# Center of the structure grid.
CENTER = Point2D(1310, 21000)
# Objective key of the configuration: "Zeiss 20x" or "Zeiss 63x". It selects FOV, drop direction,
# zMax, margins and corner sizes (OBJECTIVE_DEFAULTS in nanofactorysystem/experiment_spec.py).
OBJECTIVE = "Zeiss 63x"
USER = "Hannes"  # user key "user:<name>" of ~/nanofactory.json


# ------------------------------------------------------------------------------------------------
# Structures that need values of the running experiment: named structure factories
# ------------------------------------------------------------------------------------------------
@structure_factory("default_experiment.rectangle")
def rectangle(context: BuildContext, *, size_um: float, height_um: float, hatch_um: float, slice_um: float,
              velocity_um_s: float, stages: bool) -> Rectangle3D:
    """ A rectangle that uses the acceleration of the controller axes it is printed with.

    Some structures need values that only exist once the experiment runs, here the acceleration
    read from the controller. A *named* factory is registered with ``@structure_factory(name)``
    and called with keyword arguments only; the call returns a ``FactoryCall`` that the
    experiment builds later with a ``BuildContext`` (objective, setup, accelerations, drop
    direction, power range and calibration of the attenuator). Unlike a plain
    ``lambda experiment: ...`` it can be stored in ``experiment_spec.json`` and rebuilt.

    Why the acceleration matters: line structures (``Rectangle3D``, ``XLines``, ...) start every
    line with a run-up of ``2 * v**2 / (2 * a)`` (v in µm/s, a in µm/s²). A small value such as
    ``acceleration=500`` (0.5 mm/s²) at 1000 µm/s gives a 2 mm run-up before every 50 µm line:
    on the stages a 50 x 50 x 3 µm block then takes about 50 minutes. The expected printing time
    in the log and the summary shows such cases before printing.

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment.
    size_um, height_um : float
        Edge length and height of the rectangle.
    hatch_um, slice_um : float
        Hatch distance and slice distance.
    velocity_um_s : float
        Writing speed.
    stages : bool
        True for a structure printed with the stages (``axes="XYZ"``): the X acceleration is used;
        False for the galvo (``axes="ABZ"``): the A acceleration.

    Returns
    -------
    Rectangle3D
    """

    acceleration = context.accel_x_um if stages else context.accel_a_um
    return Rectangle3D(Point3D(0, 0, -1), size_um, size_um, height_um, hatch_size=hatch_um, slice_size=slice_um,
                       velocity=velocity_um_s, acceleration=acceleration)


# ------------------------------------------------------------------------------------------------
# Example 1: structures from drawing classes (program source DRAWING)
# ------------------------------------------------------------------------------------------------
def drawing_structures() -> list[StructureSpec]:
    """ All kinds of structure entries, in print order (one grid cell each, row by row).

    Coordinates of a structure are local, in µm, relative to the center of its grid cell; z is
    relative to the substrate surface found by the plane fit (negative z = into the substrate,
    so that the structure is anchored).

    Returns
    -------
    list of StructureSpec
    """

    return [
        # A drawing class instance. Every field of StructureSpec is shown once here:
        StructureSpec(
            name="stair",                  # name in the experiment file; must be unique ("_(<i>)" is appended)
            structure=Stair(Point3D(0, 0, -2), n_steps=6, step_height=0.6, step_length=20, step_width=50,
                            socket_height=7, hatch_size=0.125, slice_size=0.15,
                            velocity=10_000, acceleration=500_000),  # µm/s, µm/s²
            height_data=None,              # SLICER only: height map / mesh file (see slicer_spec)
            slicer={},                     # SLICER only: arguments of Model3D_Slicer
            power_mw=0.7,                  # laser power in mW; None -> ExperimentSpec.default_power_mw
            axes="ABZ",                    # "ABZ" = galvo scanner (fast, inside the FOV), "XYZ" = stages
            repeat=0,                      # number of copies in the following grid cells
            structure_type=None,           # None -> NORMAL (DRAWING) / IFOV (SLICER); DUMMY = empty cell
            factory=None,                  # named factory instead of `structure` (see "rect" below)
            layer_power=None,              # one power per layer in mW (list), instead of one power_mw
        ),
        # Printed twice: "rect" and its repetition "rect_rep1" in the next grid cell. Built by the named
        # factory above once the experiment runs, with the stage acceleration of the controller.
        StructureSpec("rect", factory=rectangle(size_um=50, height_um=3, hatch_um=0.5, slice_um=0.5,
                                                velocity_um_s=1000, stages=True),
                      power_mw=0.7, axes="XYZ", repeat=1),
        # Power per layer (T31): Rectangle3D has round(height / slice) + 1 layers -> 3 / 1 + 1 = 4 layers,
        # so exactly 4 values. A wrong number of values stops build_programs() with an error.
        StructureSpec("power_ramp", factory=rectangle(size_um=50, height_um=3, hatch_um=0.5, slice_um=1.0,
                                                      velocity_um_s=1000, stages=True),
                      power_mw=0.6, axes="XYZ", layer_power=[0.6, 0.7, 0.8, 0.9]),
        # An empty grid cell (nothing is printed there, e.g. to keep a column free).
        StructureSpec.empty(),
        # The same factory for the galvo: the A-axis acceleration is used.
        StructureSpec("galvo_rect", factory=rectangle(size_um=40, height_um=2, hatch_um=0.3, slice_um=0.5,
                                                      velocity_um_s=5000, stages=False),
                      power_mw=0.7, axes="ABZ"),
    ]


def experiment_spec(objective: str = OBJECTIVE, center: Point2D = CENTER, *,
                    name: str = "default_experiment") -> ExperimentSpec:
    """ The complete experiment description with every setting written out.

    Parameters
    ----------
    objective : str
        Objective key, e.g. ``"Zeiss 63x"``.
    center : Point2D
        Absolute center of the structure grid in µm.
    name : str
        Experiment name (folder name when the experiment is stored below an explicit path).

    Returns
    -------
    ExperimentSpec
    """

    # Runtime parameters of the devices and measurement tools, one section per component.
    # default_sys_args() holds the values of the experiment template; change single values here.
    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"      # fit of the power calibration curve
    sys_args["sample"]["name"] = "#1"                    # free sample information, stored with the experiment
    sys_args["focus"]["exposureValue"] = 120             # camera exposure for focus detection
    sys_args["layer"]["laserPower"] = 0.7                # power in mW for the resin interface detection
    # Further sections: "controller" (zMax is set from z_max_um), "dhm" (usage is set from dhm_usage),
    # "camera", "plane" (plane-fit settings). The controller zMax is a safety limit: moves above it are refused.

    return ExperimentSpec(
        # --- identification -----------------------------------------------------------------
        name=name,                          # short name, used as folder name below an explicit path
        description="Default experiment showing every setting.",  # free text, stored with the experiment
        tags=["template", "example"],       # free keywords, e.g. for a library of standard experiments
        objective=objective,                # "Zeiss 20x" or "Zeiss 63x"

        # --- placement on the substrate -----------------------------------------------------
        center=center,                      # absolute center of the grid in µm
        grid=(2, 3),                        # (rows, cols); rows along y, cols along x; must hold all structures
        structure_size_um=None,             # size of one grid cell; default: the FOV of the objective
        fov_um=None,                        # galvo field of view; default: 500 (20x) / 150 (63x)
        margin_um=None,                     # space between the grid and the experiment border; 200 / 50
        padding_um=None,                    # gap between neighbouring grid cells; default 100
        drop_direction=None,                # DropDirection.UP (20x) / DOWN (63x): print order and interface
        z_max_um=None,                      # safety limit of the Z stage; default 24550 (20x) / 25480 (63x)

        # --- corner markers and QR code (for finding the experiment again) ------------------
        skip_corner=False,                  # True: no corner markers and no QR code (UUID of the experiment)
        corner=None,                        # CornerSpec(z_um, width_um, length_um, height_um, hatch_um, slice_um);
                                            # default: CornerSpec of the objective, e.g. CornerSpec(width_um=30.0,
                                            # length_um=120.0, hatch_um=0.3) for 63x

        # --- structures ---------------------------------------------------------------------
        structures=drawing_structures(),
        program_source=ProgramSource.DRAWING,  # DRAWING (drawing classes) or SLICER (height map / mesh)
        setup="IFOV_off",                   # "IFOV_off" (stages + galvo) or "IFOV_on" (Aerotech IFOV; SLICER needs it)

        # --- laser and speeds ---------------------------------------------------------------
        default_power_mw=0.7,               # power of structures without power_mw, and of the corner markers
        low_speed_um_s=1000.0,              # speed of the slow moves (e.g. near the substrate)
        high_speed_um_s=5000.0,             # speed of the fast moves between structures

        # --- plane fit (substrate surface) --------------------------------------------------
        plane_fit_mode=PlaneFitMode.CORNERS,  # where the surface is measured: CORNERS (4 corners of the
                                              # experiment), GRID (every grid cell), BORDER (along the border)
        n_mid_points=0,                     # additional measuring points between the corners
        tilt_warning_um=1.0,                # warn if the surface height under a structure varies more than this

        # --- measurements -------------------------------------------------------------------
        dhm_usage=False,                    # DHM holograms after every structure (needs the DHM-PC); then also
        opl_start_um=None,                  # start position of the OPL motor scan (None: automatic)
        camera_capture=True,                # camera image after every structure (with commanded/actual position)
        overview_capture=False,             # stitched camera mosaic of the experiment before and after printing
        overview_single_images=False,       # also store the single images of the mosaic

        # --- materials (information model) --------------------------------------------------
        materials={"resin": "SZ2080"},      # material registry names per role ("resin", "substrate", "medium");
                                            # a snapshot of each is stored with the experiment (refractive
                                            # indices etc.); unknown names are stored as "unregistered"
        voxel_material=None,                # SLICER only: resin name in the voxel database -> voxel-aware slicing
        voxel_database=None,                # voxel database file; default: system.voxelDatabase of the config

        # --- time estimate and runtime ------------------------------------------------------
        layer_overhead_s=5.0,               # assumed overhead per layer for the printing time estimate
        sys_args=sys_args,                  # runtime parameters of the devices (see above)
    )


# ------------------------------------------------------------------------------------------------
# Example 2: a height map sliced by the slicer (program source SLICER)
# ------------------------------------------------------------------------------------------------
def slicer_spec(objective: str = OBJECTIVE, center: Point2D = Point2D(1310, 23000), *,
                name: str = "default_slicer") -> ExperimentSpec:
    """ A height map sliced into layers and printed in IFOV mode, with every slicer option.

    Parameters
    ----------
    objective : str
        Objective key.
    center : Point2D
        Absolute center of the grid in µm.
    name : str
        Experiment name.

    Returns
    -------
    ExperimentSpec
    """

    # Height map in µm: a 20 x 20 µm block, 2 µm high, on a 40 x 40 µm area with 1 µm pixels.
    # Instead of an array, height_data can be the path of a mesh file (STL, OBJ, ...) or of an image.
    height_map = np.zeros((40, 40))
    height_map[10:30, 10:30] = 2.0
    slicer = {
        "velocity": 5,                     # mm/s (500-25000 is read as µm/s); IFOV prints with the fixed IFOV
                                           # speed of the objective, this value is kept for the time estimate
        "pixel_size": 1.0,                 # height maps: pixel size in `unit`
        "unit": "um",                      # unit of pixel size / mesh: "nm", "um", "mm", "cm", "m"
        "hatch_size": 0.1,                 # distance of hatch lines in µm
        "slice_size": 0.1,                 # distance of slice planes in µm
        "hatch_strategy": "alternating",   # "alternating", "linear_x", "linear_y", "cross", "concentric"
        "hatch_angle_deg": 0.0,            # base direction of the hatch lines (0 = along x)
        "contour_offset_um": 0.0,          # inward offset of the outline (half the voxel width)
        "num_contour_lines": 0,            # perimeter lines before the infill ("walls")
        "base_height": 0.0,                # height maps: constant added to every pixel, in `unit`
        # With voxel_material set in the spec (voxel-aware slicing, T54):
        # "spacing_mode": "voxel_overlap",  # spacing = voxel size x (1 - voxel_overlap); or "static_hatching"
        # "voxel_overlap": 0.3,             # overlap of neighbouring lines/layers, in [0, 1)
    }
    return ExperimentSpec(
        name=name,
        description="Height map sliced and printed in IFOV mode.",
        tags=["template", "slicer"],
        objective=objective,
        center=center,
        grid=(1, 1),
        program_source=ProgramSource.SLICER,
        setup="IFOV_on",                   # required for SLICER
        camera_capture=True,
        materials={"resin": "SZ2080"},
        structures=[StructureSpec("block", height_data=height_map, power_mw=0.3, slicer=slicer)],
    )


def main(spec: Optional[ExperimentSpec] = None, *, user: str = USER,
         path: Path = Path(".output/experiments"), backend=None, plane=None) -> Path:
    """ Run the experiment; on the lab PC every step is confirmed in a message box.

    Parameters
    ----------
    spec : ExperimentSpec, optional
        Default: :func:`experiment_spec`.
    user : str
        User key of the configuration.
    path : Path
        Root folder; the experiment is written to ``<path>/<spec.name>``.
    backend : {"real", "dummy"}, DummyBackend or None
        None: the lab hardware. A backend object for a dry run on simulated hardware (no
        questions, no plot window).
    plane : ZFunction, optional
        Known substrate plane for dry runs.

    Returns
    -------
    Path
        The experiment folder.
    """

    spec = spec or experiment_spec()
    interactive = backend is None
    return run_experiment(spec, user=user, resin_edges=RESIN_EDGES, path=path, backend=backend, plane=plane,
                          confirm=messagebox_confirm if interactive else None, show_plot=interactive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="run on simulated hardware")
    parser.add_argument("--slicer", action="store_true", help="run the slicer example instead")
    options = parser.parse_args()
    chosen = slicer_spec() if options.slicer else experiment_spec()
    if options.dry_run:
        from nanofactorysystem.backends.dummy.dry_run import dry_run
        with dry_run(USER) as simulated:
            folder = main(chosen, path=simulated.workdir / "experiments", backend=simulated.backend,
                          plane=simulated.plane)
        print(f"Dry run finished: {folder}")
    else:
        main(chosen)
