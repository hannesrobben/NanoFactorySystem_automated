##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Orientation test: three rectangles in the corner cells (0, 0), (1, 0) and (1, 1) of the power-speed grid.

Described by ``experiment_spec()`` (T51); ``testprint()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode

OBJECTIVES = {
    "Zeiss 20x": dict(fov_um=500.0, z_max_um=25700.0, margin_um=200.0, padding_um=100.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    # zMax could possibly be up to 25550 µm
    "Zeiss 63x": dict(fov_um=150.0, z_max_um=25480.0, margin_um=50.0, padding_um=100.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}
PARAMETERS = {
    "Zeiss 20x": {"hatch size": 0.125, "slice size": 0.15, "power": [0.7], "velocity": [], "default power": 0.7},
    "Zeiss 63x": {"hatch size": 0.1, "slice size": 0.2,  # earlier: 0.05 ... 0.2 and 0.1
                  "power": [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7],
                  "velocity": [1_000, 2_000, 3_000, 4_000, 5_000, 7_500, 10_000],
                  "default power": 0.7},
}
PRINTED_CELLS = ((0, 0), (1, 0), (1, 1))  # (velocity index, power index); all other cells stay empty


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment (DHM on by default). """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {"OffsetFocusDetection": [120, -80], "minCircularity": 0.6, "exposureValue": 120},
        "layer": {"dzFineDefault": 25.0, "laserPower": 0.7},
        "plane": {},
    }


def rectangle(hatch, slice_size):
    """ Factory of one rectangle (10 mm/s); the acceleration is read from the running experiment. """

    def build(experiment):
        return Rectangle3D(center=Point3D(0, 0, -2), width=50, length=50, height=3, hatch_size=hatch,
                           slice_size=slice_size, velocity=10_000, acceleration=experiment.accel_a_um)
    return build


def experiment_spec(objective="Zeiss 20x", absolute_center=Point2D(0, 0)) -> ExperimentSpec:
    """ Grid of the power-speed study with rectangles only in ``PRINTED_CELLS``. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    parameters = PARAMETERS[objective]
    if not parameters["velocity"]:
        raise ValueError(f"No velocities are defined for {objective}.")
    structures = []
    for i in range(len(parameters["velocity"])):
        for j in range(len(parameters["power"])):
            if (i, j) in PRINTED_CELLS:
                structures.append(StructureSpec(f"rect_{i}_{10_000}_{j}_{0.7}",
                                                factory=rectangle(parameters["hatch size"], parameters["slice size"]),
                                                power_mw=0.7, axes="ABZ"))
            else:
                structures.append(StructureSpec.empty())
    return ExperimentSpec(
        name="parameter_testprint", objective=objective, center=absolute_center,
        grid=(len(parameters["velocity"]), len(parameters["power"])), structures=structures,
        drop_direction=DropDirection.DOWN, plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=True, camera_capture=True,
        default_power_mw=parameters["default power"], low_speed_um_s=1000, high_speed_um_s=10_000,
        opl_start_um=350.0, sys_args=runtime_arguments(), **OBJECTIVES[objective])


def testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
              objective="Zeiss 20x", user="Hannes", backend=None, plane=None):
    """ Run the experiment.

    Parameters
    ----------
    absolute_center : Point2D
        Center of the experiment in µm.
    resin_dimension : list
        Edges of the resin drop in µm: [[right], [left], [near], [far]].
    ask_continue_box : bool
        Confirm every step in a message box.
    path : Path, optional
        Root folder; the data go into its subfolder ``parameter_testprint``, without it into ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center)
    root, spec.name = script_output(
        path,
        Path(f".output/parameter_study/Orientation_test_TL_MARK_{datetime.datetime.now():%Y%m%d}_{objective}"),
        "parameter_testprint")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=False)
