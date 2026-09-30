##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Surface quality of aspherical lenses for several [hatch, slice, power, velocity] sets.

Described by ``experiment_spec()`` (T51); ``print_file()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem import getLogger
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode

OBJECTIVES = {
    "Zeiss 20x": dict(drop_direction=DropDirection.UP, fov_um=500.0, z_max_um=24550.0, margin_um=300.0,
                      padding_um=50.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    # zMax could possibly be up to 25550 µm
    "Zeiss 63x": dict(drop_direction=DropDirection.DOWN, fov_um=150.0, z_max_um=25480.0, margin_um=250.0,
                      padding_um=100.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}
# [hatch, slice, power, velocity] per column
PARAMETER_SETS = {
    "Zeiss 20x": [],
    "Zeiss 63x": [
        [0.2, 0.2, 0.2, 2000],  # baseline - printed quite often
        [0.15, 0.2, 0.2, 2000],  # finer hatching - should not be needed for a better surface quality
        [0.2, 0.15, 0.2, 2000],  # finer slicing - should show an advantage over the other structures
        [0.2, 0.1, 0.2, 2000],  # even finer slicing
        [0.1, 0.1, 0.2, 2000],  # combination of very fine hatching and slicing
    ],
}


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "DHM Print", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {"OffsetFocusDetection": [130, -15], "minCircularity": 0.6, "exposureValue": 120},
        "layer": {"beta": 0.7, "dzCoarseDefault": 50.0, "dzFineDefault": 50.0, "laserPower": 0.7},
        "plane": {},
    }


def lens(hatch, slice_size, velocity):
    """ Factory of one lens; the acceleration is read from the running experiment. """

    def build(experiment):
        return AsphericalLens(Point3D(0, 0, -1), height=4, length=50, width=50, sphere_radius=515,
                              conic_constant=-2.3, hatch_size=hatch, slice_size=slice_size, velocity=velocity,
                              acceleration=experiment.accel_a_um)
    return build


def experiment_spec(objective="Zeiss 20x", absolute_center=Point2D(0, 0), repeat=5, dhm_usage=False,
                    setup="IFOV_off") -> ExperimentSpec:
    """ ``repeat`` rows, one column per parameter set. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    parameter_sets = PARAMETER_SETS[objective]
    if not parameter_sets:
        raise ValueError(f"No parameter sets are defined for {objective}.")
    structures = [
        StructureSpec(f"lens_param_{str(parameters)}_{j}", factory=lens(*parameters[:2], parameters[3]),
                      power_mw=parameters[2], axes="ABZ")
        for j in range(repeat) for parameters in parameter_sets]
    return ExperimentSpec(
        name="lenses_surface_5_parametersets", objective=objective, center=absolute_center,
        grid=(repeat, len(parameter_sets)), structures=structures, setup=setup,
        plane_fit_mode=PlaneFitMode.GRID, dhm_usage=dhm_usage, camera_capture=True, default_power_mw=0.7,
        low_speed_um_s=1000, high_speed_um_s=10_000, opl_start_um=350.0, sys_args=runtime_arguments(),
        **OBJECTIVES[objective])


def print_file(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
               objective="Zeiss 20x", user="Hannes", repeat=5, dhm_usage=False, substrate=None, setup="IFOV_off",
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
        Root folder; the data go into its subfolder ``lenses_surface_5_parametersets``, without it into ``.output``.
    repeat : int
        Number of rows (repetitions of every parameter set).
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center, repeat, dhm_usage, setup)
    root, spec.name = script_output(
        path, Path(f".output/dhm_paper/DHM_Justage_{datetime.datetime.now():%Y%m%d}_{objective}"),
        "lenses_surface_5_parametersets")
    (root / spec.name).mkdir(parents=True, exist_ok=True)
    getLogger(logfile=root / spec.name / "console.log").info(
        f"Surface quality investigation with the parameter sets [hatching, slicing, power, velocity]: "
        f"{PARAMETER_SETS[objective]}")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=False,
                          substrate_information=substrate)
