##########################################################################
# Copyright (c) 2022-2026 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""One large binary IFOV grating (2 mm) on a big substrate.

Described by ``experiment_spec()`` (T64); ``print_file()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem.aerobasic.programs.drawings import BinaryGrating_IFOV
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode

STRUCTURE_SIZE = 2000.0  # um
# Margin and padding are twice the usual values of the objective (extra large on purpose)
OBJECTIVES = {
    "Zeiss 20x": dict(drop_direction=DropDirection.UP, fov_um=500.0, z_max_um=24550.0, margin_um=600.0,
                      padding_um=200.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    # zMax could possibly be up to 25550 µm
    "Zeiss 63x": dict(drop_direction=DropDirection.DOWN, fov_um=150.0, z_max_um=25480.0, margin_um=100.0,
                      padding_um=200.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}
PARAMETERS = {
    "Zeiss 20x": {"hatch size": 0.2, "slice size": 0.2, "power": 0.7, "velocity": 10_000},
    "Zeiss 63x": {"hatch size": 0.2, "slice size": 0.2, "power": 0.5, "velocity": 5_000},
}


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass, the thick glass, ISO 8037/1",
                   "substrateThickness": 1000, "material": "SZ2080", "materialThickness": 175.0},
        "focus": {"OffsetFocusDetection": [130, -15], "minCircularity": 0.8, "exposureValue": 120},
        "layer": {"dzFineDefault": 25.0, "laserPower": 0.7},
        "plane": {},
    }


def experiment_spec(objective="Zeiss 20x", absolute_center=Point2D(0, 0), dhm_usage=False,
                    setup="IFOV_off") -> ExperimentSpec:
    """ One binary IFOV grating of 2 mm x 2 mm, without corner markers. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    parameters = PARAMETERS[objective]
    grating = BinaryGrating_IFOV(
        center=Point3D(0, 0, -1), x_dim=STRUCTURE_SIZE, y_dim=STRUCTURE_SIZE, period=20, height=3, duty_cycle=0.5,
        grating_angle_deg=0.0, base_height=4.0, hatch_size=parameters["hatch size"],
        slice_size=parameters["slice size"], velocity=parameters["velocity"], power=None,
        start_hatching_direction=HatchingDirection.X, alternating_hatch=True)
    name = (f"binaryIFOV_s{parameters['slice size']}_h_{parameters['hatch size']}_p_{parameters['power']}"
            f"_v_{parameters['velocity']}_Obj_{objective}")
    return ExperimentSpec(
        name="grating_after_debugging", objective=objective, center=absolute_center, grid=(1, 1),
        structures=[StructureSpec(name, grating, power_mw=parameters["power"], axes="XYZ",
                                  structure_type=StructureType.IFOV)],
        setup=setup, plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=dhm_usage, camera_capture=True,
        structure_size_um=STRUCTURE_SIZE, skip_corner=True, default_power_mw=0.7, low_speed_um_s=1000,
        high_speed_um_s=10_000, opl_start_um=350.0, sys_args=runtime_arguments(), **OBJECTIVES[objective])


def binary_testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
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
    path : Path or str, optional
        Root folder; the data go into its subfolder ``grating_after_debugging`` (before T64:
        ``grating_nach_debuggen``), without it into ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center, dhm_usage, setup)
    root, spec.name = script_output(
        path, Path(f".output/ifov/binary_grating1{datetime.datetime.now():%Y%m%d}"), "grating_after_debugging")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=backend is None,
                          substrate_information=substrate)


# The entry function was named print_file in this script, while main_IFOV.py imports binary_testprint
print_file = binary_testprint
