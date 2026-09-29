##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################

import datetime
import os
from pathlib import Path
from tkinter import messagebox
import numpy as np

from nanofactorysystem import mkdir, getLogger
from nanofactorysystem.aerobasic.programs.drawings.DOE import DOEstep
from nanofactorysystem.aerobasic.programs.drawings.lines import Stair, Rectangle3D
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

sys_args = {
    "attenuator": {
        "fitKind": "quadratic",
    },
    "sample": {
        "name": "DHM Print",
        "orientation": "down",
        "substrate": "boro-silicate glass",
        "substrateThickness": 700.0,
        "material": "SZ2080",
        "materialThickness": 75.0,
    },
    "focus": {
        "OffsetFocusDetection": [130, -15],
        "minCircularity": 0.6,
        "exposureValue": 120
    },
    "layer": {
        "beta": 0.7,
        "dzCoarseDefault": 50.0,
        "dzFineDefault": 50.0,
        "laserPower": 0.7,
    },
    "plane": {},
}


def print_file(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
               objective="Zeiss 20x", user="Hannes", repeat=12, dhm_usage=False, substrate=None, setup="IFOV_off"):
    """
        absolute_center: Point2D with x- and y-coordinate of the center of this experiment
        resin_dimension: list of the coordinates of the edges of the resin
                [[right edge],   Example:   [[100, 18550],
                [left edge],                [200, 26300],
                [near edge],                [-3500, 22400],
                [far edge]]                 [4000, 22400]]
        ask_continue_box: bool -> controls the asking box
        path: Path argument for root directory where the experimental data will be safe in a subdirectory called ...
                If nothing is given, the export_path will be in the subdirectory .output
    """

    if path is None:
        path = Path(mkdir(f".output/dhm_paper/DHM_Justage_{datetime.datetime.now():%Y%m%d}_{objective}", clean=False))
    else:
        path = Path(path)  # accept str or Path
        path = Path(mkdir(os.path.join(path, f"padding_test_5µm"), clean=False))
    logger = getLogger(logfile=f"{path}/console.log")

    # Size of (oval) resin drop in micrometres
    edges = np.asarray(resin_dimension)
    resin_corner_tr = Point2D(*np.max(edges, axis=0))
    resin_corner_bl = Point2D(*np.min(edges, axis=0))
    absolute_grid_center = absolute_center

    if objective == "Zeiss 20x":
        drop_direction = DropDirection.UP
        fov = 500
        zmax = 24550.0
        # Corner settings
        c_width = 50
        c_length = 300
        c_height = 7
        c_hatch = 0.5
        c_slice = 0.75
        # printing area settings
        margin = 300
        padding = 50
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameterset = {
            "hatch size": 0.2,  # hatch size
            "slice size": 0.2,  # slice size/ layer height
            "power": 0.7,
            "velocity": 10_000
        }

    elif objective == "Zeiss 63x":
        drop_direction = DropDirection.DOWN
        fov = 150
        zmax = 25480.0  # could possibly be up to 25550 µm
        # Corner settings
        c_width = 30
        c_length = 120
        c_height = 7
        c_hatch = 0.3
        c_slice = 0.75
        # printing area settings
        margin = 150
        # padding = 100
        padding = 5
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameterset = {
            "hatch size": 0.2,  # [0.1, 0.2, 0.5],  # hatch size
            "slice size": 0.2,  # [0.1, 0.2, 0.5],  # slice size/ layer height
            "power": 0.5,
            "velocity": 5_000
        }

    else:
        raise Exception(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")

    sys_args.update({"controller": {
        "zMax": zmax, }
    })
    # Option to not use DHM
    if "dhm" in sys_args.keys():
        sys_args["dhm"].update({"usage": dhm_usage})
    else:
        sys_args.update({"dhm": {"usage": dhm_usage}})

    structure_size = 50
    grid_size = (3, 3)  # number of repetitions
    with Experiment(
            path=path,
            user=user,
            objective=objective,
            logger=logger,
            sys_args=sys_args,
            default_power=0.7,
            low_speed_um=1000,
            high_speed_um=10_000,
            resin_corner_tr=resin_corner_tr,
            resin_corner_bl=resin_corner_bl,
            structure_size=structure_size,
            margin=margin,
            padding=padding ,
            absolute_grid_center=absolute_grid_center,
            grid=grid_size,
            n_mid_points=0,
            drop_direction=drop_direction,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            fov_dim=(fov, fov),
            plane_fit_mode=1,
            skip_corner=False,
            setup=setup) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=False)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path max_length for DHM
        if dhm_usage:
            if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
            experiment.opl_scan(m0=350.0, force=False)

        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Adding Stair Structure
        for i in range(grid_size[0] * grid_size[1]):
            # Adding aspherical lens structure
            experiment.add_structure(
                structure_type=StructureType.NORMAL,
                name=f"rect_{i + 1}",
                axes=movement_axis[0],
                power=parameterset["power"],
                structure=Rectangle3D(
                    center=Point3D(X=0, Y=0, Z=-2),
                    width=50,
                    length=50,
                    height=5,
                    hatch_size=parameterset["hatch size"],
                    slice_size=parameterset["slice size"],
                    velocity=parameterset["velocity"],
                    acceleration=experiment.accel_a_um))

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------

        # Build corner and structure programs
        if ask_continue_box:
            if messagebox.askyesno(message="Create programs for all structures?"):
                experiment.build_programs()
            else:
                if messagebox.askyesno(message="Programs already created?"):
                    experiment.retrieve_programs()
        else:
            experiment.build_programs()

        # Print corners and structures
        if ask_continue_box and not messagebox.askyesno(message="FINAL STEP: Print experiment?"): return
        experiment.print_experiment()

        # experiment.measure(coordinate=center, name="after")

# if __name__ == '__main__':
