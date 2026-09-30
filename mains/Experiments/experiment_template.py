##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Template for experiment scripts (T51).

An experiment is described by one ExperimentSpec instead of values edited in the
script: objective, center, grid, structures, program source, plane-fit mode, DHM and
camera usage, power and speeds. Objective-specific values (FOV, drop direction, zMax,
margins, corner sizes) come from ``nanofactorysystem.experiment_spec.OBJECTIVE_DEFAULTS``
and can be overridden in the spec.

Copy this file for a new experiment and change the spec functions. Run it with
``mains/`` as the working directory (``cd mains && python -m Experiments.experiment_template``).
A dry run on simulated hardware: ``main(backend="dummy")``.
"""
from pathlib import Path

import numpy as np

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D, Stair
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, run_experiment
from nanofactorysystem.plane_fitting import PlaneFitMode

# Substrate of the current print: resin drop edges and experiment center in µm (from main.py)
RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]
CENTER = Point2D(1310, 19500)


def drawing_spec(objective: str = "Zeiss 20x", center: Point2D = CENTER) -> ExperimentSpec:
    """ Example: structures of the drawing classes (program source DRAWING). """

    return ExperimentSpec(
        name="template_drawing",
        objective=objective,
        center=center,
        grid=(1, 3),
        plane_fit_mode=PlaneFitMode.CORNERS,
        dhm_usage=False,
        camera_capture=True,
        structures=[
            StructureSpec(
                "stair",
                Stair(Point3D(0, 0, -2), n_steps=6, step_height=0.6, step_length=20, step_width=50,
                      hatch_size=0.125, slice_size=0.15, socket_height=7, velocity=10_000, acceleration=500_000),
                power_mw=0.7, axes="ABZ"),
            StructureSpec(
                "rectangle",
                Rectangle3D(Point3D(0, 0, -1), 50, 50, 3, hatch_size=0.5, slice_size=0.5, velocity=1000,
                            acceleration=500),
                power_mw=0.7, axes="XYZ", repeat=1),
        ],
    )


def slicer_spec(objective: str = "Zeiss 63x", center: Point2D = CENTER) -> ExperimentSpec:
    """ Example: a height map sliced by the slicer (program source SLICER, IFOV setup). """

    height_map = np.zeros((40, 40))
    height_map[10:30, 10:30] = 2.0  # 20 x 20 µm block, 2 µm high, 1 µm pixels
    return ExperimentSpec(
        name="template_slicer",
        objective=objective,
        center=center,
        grid=(1, 1),
        program_source=ProgramSource.SLICER,
        setup="IFOV_on",
        structures=[StructureSpec("block", height_data=height_map, power_mw=0.3,
                                  slicer={"velocity": 5, "hatch_size": 0.1, "slice_size": 0.1,
                                          "pixel_size": 1.0, "unit": "um"})],
    )


def main(spec: ExperimentSpec = None, *, user: str = "Hannes", path: Path = Path(".output/experiments"),
         backend=None, plane=None):
    """ Run the experiment; on the lab PC every step is confirmed in a message box.

    Parameters
    ----------
    spec : ExperimentSpec, optional
        Default: :func:`drawing_spec`.
    user : str
        User key of the configuration.
    path : Path
        Root folder of the experiment output.
    backend : {"real", "dummy"}, optional
        ``"dummy"`` for a dry run on simulated hardware (no questions, known plane).
    plane : ZFunction, optional
        Known substrate plane for dry runs.
    """

    spec = spec or drawing_spec()
    if backend is None:
        from tkinter import messagebox

        def confirm(question):
            return messagebox.askyesno(message=question)
        show_plot = True
    else:
        confirm, show_plot = None, False
    return run_experiment(spec, user=user, resin_edges=RESIN_EDGES, path=path, backend=backend, plane=plane,
                          confirm=confirm, show_plot=show_plot)


if __name__ == "__main__":
    main()
