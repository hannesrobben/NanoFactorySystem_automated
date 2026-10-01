##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Refractive index study: rectangles, power (rows) x velocity (columns).

Described by ``experiment_spec()`` (T51); ``print_file()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem.aerobasic.programs.drawings import Rectangle3D
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode

OBJECTIVES = {
    "Zeiss 20x": dict(drop_direction=DropDirection.UP, fov_um=500.0, z_max_um=24550.0, margin_um=200.0,
                      padding_um=100.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    # zMax could possibly be up to 25550 µm; margin outside the grid, padding between the structures
    "Zeiss 63x": dict(drop_direction=DropDirection.DOWN, fov_um=150.0, z_max_um=25480.0, margin_um=150.0,
                      padding_um=50.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}
PARAMETERS = {
    "Zeiss 20x": {"hatch size": 0.125, "slice size": 0.15, "power": [], "velocity": []},
    "Zeiss 63x": {"hatch size": 0.2, "slice size": 0.2,
                  "power": [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7],
                  "velocity": [1_000, 2_000, 3_000, 4_000, 5_000, 6_000, 7_000, 8_000, 9_000, 10_000]},
}
AXES = "ABZ"


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {"OffsetFocusDetection": [130, -15], "minCircularity": 0.55, "exposureValue": 120},
        "layer": {"dzFineDefault": 25.0, "laserPower": 0.7},
        "plane": {},
    }


def rectangle(hatch, slice_size, velocity):
    """ Factory of one rectangle; the acceleration is read from the running experiment. """

    def build(experiment):
        return Rectangle3D(center=Point3D(0, 0, -2), width=50, length=50, height=3, hatch_size=hatch,
                           slice_size=slice_size, velocity=velocity, acceleration=experiment.accel_a_um)
    return build


def experiment_spec(objective="Zeiss 20x", absolute_center=Point2D(0, 0), dhm_usage=False,
                    setup="IFOV_off") -> ExperimentSpec:
    """ One row per power, one column per velocity. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    parameters = PARAMETERS[objective]
    if not parameters["power"] or not parameters["velocity"]:
        raise ValueError(f"No power and velocity lists are defined for {objective}.")
    structures = [
        StructureSpec(f"rect_{AXES}_{objective}_P_{power}_v_{velocity}",
                      factory=rectangle(parameters["hatch size"], parameters["slice size"], velocity),
                      power_mw=power, axes=AXES)
        for power in parameters["power"] for velocity in parameters["velocity"]]
    return ExperimentSpec(
        name="refractive_Index_power_velocity", objective=objective, center=absolute_center,
        grid=(len(parameters["power"]), len(parameters["velocity"])), structures=structures, setup=setup,
        plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=dhm_usage, camera_capture=True, default_power_mw=0.7,
        low_speed_um_s=1000, high_speed_um_s=5000, opl_start_um=350.0, sys_args=runtime_arguments(),
        **OBJECTIVES[objective])


def print_file(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
               objective="Zeiss 20x", user="Hannes", dhm_usage=False, substrate=None, setup="IFOV_off",
               backend=None, plane=None):
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
        Root folder; the data go into its subfolder ``refractive_Index_power_velocity``, without it into
        ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center, dhm_usage, setup)
    root, spec.name = script_output(
        path, Path(f".output/tomography/testprint{datetime.datetime.now():%Y%m%d}"),
        "refractive_Index_power_velocity")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=backend is None,
                          substrate_information=substrate)
