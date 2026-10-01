##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Cell geometry: power (rows) x velocity (columns).

Described by ``experiment_spec()`` (T51); ``print_file()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem.aerobasic.programs.drawings.cell import CellGeometry
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode

OBJECTIVES = {
    "Zeiss 20x": dict(fov_um=500.0, z_max_um=25700.0, margin_um=200.0, padding_um=100.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    "Zeiss 63x": dict(fov_um=150.0, z_max_um=25480.0, margin_um=150.0, padding_um=100.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}
PARAMETERS = {
    "Zeiss 20x": {"power": [0.3, 0.5, 0.7], "velocity": [3_000, 5_000, 10_000]},  # velocity in µm/s
    "Zeiss 63x": {"power": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7], "velocity": [5_000]},
}
STRUCTURE_SIZE = 300.0


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {"OffsetFocusDetection": [120, -80], "minCircularity": 0.6, "exposureValue": 120},
        "layer": {"dzFineDefault": 25.0, "laserPower": 0.7},
        "plane": {},
    }


def experiment_spec(objective="Zeiss 63x", absolute_center=Point2D(0, 0), dhm_usage=True,
                    setup="IFOV_on") -> ExperimentSpec:
    """ Grid of cell geometries: one row per power, one column per velocity. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    parameters = PARAMETERS[objective]
    structures = [
        StructureSpec(
            f"cell_p{power}_v{velocity}",
            CellGeometry(center=Point3D(0, 0, -2), fov=STRUCTURE_SIZE, velocity=velocity, distance_between_lines=10.0,
                         edge_margin=0.5, objective=objective, height=3.0, slice_size=0.2),
            power_mw=power, axes="XYZ")
        for power in parameters["power"] for velocity in parameters["velocity"]]
    return ExperimentSpec(
        name="power_test_1", objective=objective, center=absolute_center,
        grid=(len(parameters["power"]), len(parameters["velocity"])), structures=structures, setup=setup,
        drop_direction=DropDirection.DOWN, plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=dhm_usage,
        camera_capture=True, structure_size_um=STRUCTURE_SIZE, default_power_mw=0.7, low_speed_um_s=1000,
        high_speed_um_s=10_000, opl_start_um=350.0, sys_args=runtime_arguments(), **OBJECTIVES[objective])


def print_file(absolute_center: Point2D, resin_dimension: list, ask_continue_box=True, path=None,
               objective="Zeiss 63x", user="Hannes", dhm_usage=True, setup="IFOV_on", substrate: dict = None,
               backend=None, plane=None):
    """ Run the experiment.

    Parameters
    ----------
    absolute_center : Point2D
        Center of the experiment in µm.
    resin_dimension : list
        Edges of the resin drop in µm: [[right], [left], [near], [far]], e.g.
        [[100, 18550], [200, 26300], [-3500, 22400], [4000, 22400]].
    ask_continue_box : bool
        Confirm every step in a message box.
    path : Path, optional
        Root folder; the data go into its subfolder ``power_test_1``, without it into ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center, dhm_usage, setup)
    root, spec.name = script_output(
        path, Path(f".output/cell_geometry/power_velocity_{datetime.datetime.now():%Y%m%d}"), "power_test_1")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=backend is None,
                          substrate_information=substrate)


if __name__ == '__main__':
    print_file(
        absolute_center=Point2D(X=0, Y=0),
        resin_dimension=[[100, 18550], [200, 26300], [-3500, 22400], [4000, 22400]],
        ask_continue_box=True,
        objective="Zeiss 63x",
        user="Hannes",
        dhm_usage=False,
    )
