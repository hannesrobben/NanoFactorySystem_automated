##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Lab check of the features added in phases 1-4 and B on one substrate with two small experiments.

Run it with ``mains/`` as the working directory (``cd mains && python -m lab_checks.new_features_check``).
Set RESIN_EDGES and the two centers for the current substrate first. A dry run on simulated hardware:
``main(backend="dummy", plane=..., data_root=...)``.

What is exercised (check the points in CHECKLIST after the run):

- substrate plan: layout check of both experiments against each other and the resin-drop ellipse (T52, T62),
  substrate label and index ``substrate.json`` (T48)
- experiment "drawing": plane fit with ``PlaneFitMode.CORNERS`` and the tilt warning (T44), camera images
  after every structure with commanded and actual position (T45, T46, T58), the stitched camera overview
  before and after printing with the single images (T28), a power per layer (T31), a repetition (T50),
  the expected and the actual printing time (T28), the summary (T49)
- experiment "slicer": a height map sliced in IFOV mode (``ProgramSource.SLICER``, T51)
- storage: everything in ``experiment.h5`` with JSON copies, console and command log (T47, T55), unpacked
  into ``<experiment>/unpacked`` with the analysis tools (T66)
- restart: abort the drawing experiment during printing (Ctrl+C) and resume it with
  ``mains/restart_experiment.py`` (T50)
"""
import dataclasses
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, messagebox_confirm
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec, run_substrate

OBJECTIVE = "Zeiss 63x"
# Edges of the resin drop in µm: right, left, near, far (values of the last main.py run; change them)
RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]
DRAWING_CENTER = Point2D(1200, 21600)
SLICER_CENTER = Point2D(1200, 23200)

POWER_MW = 0.7                          # rectangles and plane fit
LAYER_POWERS_MW = [0.6, 0.7, 0.8, 0.9]  # one value per layer of the "ramp" rectangle (4 layers)
SLICER_POWER_MW = 0.3

SUBSTRATE = SubstrateSpec(
    user="Hannes",
    objective=OBJECTIVE,
    resin_edges=RESIN_EDGES,
    label=None,                         # None: the next free label of the user
    material={"substrate": "boro-silicate glass", "thickness_um": 700.0, "resin": "SZ2080",
              "resin_thickness_um": 75.0},
    notes="Lab check of the new features (mains/lab_checks/new_features_check.py)",
)

CHECKLIST = """
After the run, check in each experiment folder:
 1. overview_before.png / overview_after.png: in focus? Corners, QR code and structures in the right place?
    (The overview does not move Z: 'before' is taken at the Z the plane fit ended at.)
 2. console.log: plane-fit points (CORNERS), possible tilt warning, 'Expected printing time' and the actual time.
 3. experiment_summary.json: one row per structure; 'ramp' with layer power 0.6-0.9, 'rect_rep1' as repetition.
 4. unpacked/tables/captures.csv: commanded vs. actual stage position of every camera image.
 5. unpacked/: camera images as PNG, layer programs as TXT, logs; substrate.json lists both experiments.
 6. Restart: run again, abort the drawing experiment with Ctrl+C while printing, then set exp_path in
    restart_experiment.py to its folder and run it; only the missing layers are printed.
"""


def drawing_spec(center: Point2D = DRAWING_CENTER) -> ExperimentSpec:
    """ Small rectangles in a 2x2 grid with camera images, overview, power per layer and a repetition. """

    def rectangle():
        return Rectangle3D(Point3D(0, 0, -1), 30, 30, 3, hatch_size=0.5, slice_size=1.0, velocity=1000,
                           acceleration=500)

    return ExperimentSpec(
        name="check_drawing",
        objective=OBJECTIVE,
        center=center,
        grid=(2, 2),
        plane_fit_mode=PlaneFitMode.CORNERS,
        camera_capture=True,
        overview_capture=True,
        overview_single_images=True,
        default_power_mw=POWER_MW,
        structures=[
            StructureSpec("rect", rectangle(), power_mw=POWER_MW, axes="XYZ", repeat=1),
            StructureSpec("ramp", rectangle(), power_mw=POWER_MW, axes="XYZ", layer_power=LAYER_POWERS_MW),
            StructureSpec.empty(),
        ],
    )


def slicer_spec(center: Point2D = SLICER_CENTER) -> ExperimentSpec:
    """ A 20 x 20 x 2 µm block from a height map, sliced and printed in IFOV mode. """

    height_map = np.zeros((40, 40))
    height_map[10:30, 10:30] = 2.0      # 1 µm pixels
    return ExperimentSpec(
        name="check_slicer",
        objective=OBJECTIVE,
        center=center,
        grid=(1, 1),
        program_source=ProgramSource.SLICER,
        setup="IFOV_on",
        camera_capture=True,
        default_power_mw=POWER_MW,
        structures=[StructureSpec("block", height_data=height_map, power_mw=SLICER_POWER_MW,
                                  slicer={"velocity": 5, "hatch_size": 0.1, "slice_size": 0.1,
                                          "pixel_size": 1.0, "unit": "um"})],
    )


def unpack(folder: Path) -> Optional[Path]:
    """ Unpack ``experiment.h5`` of an experiment into ``<folder>/unpacked`` with the analysis tools (T66). """

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "analysis"))
    try:
        from experiment_analysis import unpack_experiment
    except ImportError as error:
        print(f"Analysis tools not found, {folder} is not unpacked: {error}")
        return None
    return unpack_experiment(folder, folder / "unpacked", overwrite=True)


def main(*, backend=None, plane=None, data_root: Optional[Path] = None) -> list[Path]:
    """ Check the layout, run both experiments and unpack their files.

    On the lab PC every step and every further experiment is confirmed in a message box.

    Parameters
    ----------
    backend : {"real", "dummy"}, optional
        ``"dummy"`` for a dry run on simulated hardware (no questions, no plots).
    plane : ZFunction, optional
        Known substrate plane for dry runs.
    data_root : Path, optional
        Data root instead of the user's default location.

    Returns
    -------
    list of Path
        The experiment folders.
    """

    substrate = dataclasses.replace(SUBSTRATE, data_root=data_root) if data_root is not None else SUBSTRATE
    interactive = backend is None
    folders = run_substrate(substrate, [SubstrateExperiment(drawing_spec()), SubstrateExperiment(slicer_spec())],
                            backend=backend, plane=plane,
                            confirm=messagebox_confirm if interactive else None,
                            confirm_between=messagebox_confirm if interactive else None, show_plot=interactive)
    for folder in folders:
        unpack(folder)
    print(CHECKLIST)
    return folders


if __name__ == "__main__":
    main()
