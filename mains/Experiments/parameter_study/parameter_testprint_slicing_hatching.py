##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Parameter search with stairs, aspherical lenses and rectangles: hatch size (rows) x slice size (columns).

Three blocks (stairs, lenses, rectangles) of hatch x slice cells; the cells with the two smallest hatch or
slice sizes stay empty. Described by ``experiment_spec()`` (T51); ``testprint()`` keeps the former call
signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem import getLogger
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens
from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D, Stair
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
    "Zeiss 20x": {"hatch size": [0.125], "slice size": [0.15], "power": 0.7, "velocity": None},
    "Zeiss 63x": {"hatch size": [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],
                  "slice size": [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5],
                  "power": 0.3, "velocity": 10_000},
}
AXES = "ABZ"


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {},
        "layer": {"beta": 0.7, "dzCoarseDefault": 50.0, "dzFineDefault": 10.0, "laserPower": 0.4},
        "plane": {},
    }


def stair(hatch, slice_size, velocity):
    def build(experiment):
        return Stair(Point3D(0, 0, -2), n_steps=5, step_height=0.6, step_length=20, step_width=50, hatch_size=hatch,
                     slice_size=slice_size, socket_height=5, velocity=velocity, acceleration=experiment.accel_a_um)
    return build


def lens(hatch, slice_size, velocity):
    def build(experiment):
        return AsphericalLens(Point3D(0, 0, -2), height=5, length=80, width=60, sphere_radius=1030,
                              conic_constant=-2.3, hatch_size=hatch, slice_size=slice_size, velocity=velocity,
                              acceleration=experiment.accel_a_um)
    return build


def rectangle(hatch, slice_size, velocity):
    def build(experiment):
        return Rectangle3D(center=Point3D(0, 0, -2), width=40, length=75, height=5, hatch_size=hatch,
                           slice_size=slice_size, velocity=velocity, acceleration=experiment.accel_a_um)
    return build


def experiment_spec(objective="Zeiss 20x", absolute_center=Point2D(0, 0), dhm_usage=True) -> ExperimentSpec:
    """ Three blocks (stair, lens, rectangle) of hatch x slice cells. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    parameters = PARAMETERS[objective]
    hatches, slices = parameters["hatch size"], parameters["slice size"]
    structures = []
    for prefix, factory in (("stair", stair), ("lens", lens), ("rect", rectangle)):
        for i, hatch in enumerate(hatches):
            for j, slice_size in enumerate(slices):
                if i in (0, 1) or j in (0, 1):
                    structures.append(StructureSpec.empty())
                else:
                    structures.append(StructureSpec(
                        f"{prefix}{i + j}_{AXES}_h_{hatch}_l_{slice_size}",
                        factory=factory(hatch, slice_size, parameters["velocity"]),
                        power_mw=parameters["power"], axes=AXES))
    return ExperimentSpec(
        name="parameter_testprint", objective=objective, center=absolute_center,
        grid=(3 * len(hatches), len(slices)), structures=structures, drop_direction=DropDirection.DOWN,
        plane_fit_mode=PlaneFitMode.GRID, dhm_usage=dhm_usage, camera_capture=True,
        default_power_mw=parameters["power"], low_speed_um_s=1000, high_speed_um_s=10_000, opl_start_um=350.0,
        sys_args=runtime_arguments(), **OBJECTIVES[objective])


def testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
              objective="Zeiss 20x", user="Hannes", dhm_usage=True, backend=None, plane=None):
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

    spec = experiment_spec(objective, absolute_center, dhm_usage)
    root, spec.name = script_output(
        path, Path(f".output/parameter_study/Parameter_hatch_slice_SZ2080_yellow_"
                   f"{datetime.datetime.now():%Y%m%d}_{objective}"),
        "parameter_testprint")
    (root / spec.name).mkdir(parents=True, exist_ok=True)
    parameters = PARAMETERS[objective]
    getLogger(logfile=root / spec.name / "console.log").info(
        f"Parameter search with the structures stair, aspherical lens and rectangle. \nThe parameter set is: "
        f"\nHatch size: {parameters['hatch size']} \nLayer height: {parameters['slice size']}")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=False)
