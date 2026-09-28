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
        "minCircularity": 0.6,
        "exposureValue": 90
    },
    "layer": {
        "beta": 0.7,
        "dzCoarseDefault": 50.0,
        "dzFineDefault": 10.0,
        "laserPower": 0.2,
    },
    "plane": {},
}


def dhm_paper(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
              objective="Zeiss 63x", user="Hannes", repeat=10):
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
    # ToDo: DropDirection noch mit übergeben und testen ob das funktioniert

    # ToDo: Has to be changed in future in order to allow more prints of the same experiment on one substrate without
    # deleting all the different data of previous prints
    if path is None:
        # ToDo(HR) Adjust referencing to another more suitable path
        path = Path(mkdir(f".output/dhm_paper/FINAL_print_{datetime.datetime.now():%Y%m%d}_{objective}", clean=False))
    else:
        assert (path, Path)
        path = Path(mkdir(os.path.join(path, "dhm"), clean=False))
    logger = getLogger(logfile=f"{path}/console.log")

    rand_mat = np.asarray([[2, 1, 4, 2, 1],
                           [3, 0, 2, 3, 0],
                           [0, 2, 4, 3, 0],
                           [3, 4, 0, 1, 1],
                           [4, 2, 4, 1, 1]])
    doe_height_profile = rand_mat * 0.6  # height of one step of the staircase - to be able to compare both

    # Size of (oval) resin drop in micrometres
    edges = np.asarray(resin_dimension)
    resin_corner_tr = Point2D(*np.max(edges, axis=0))
    resin_corner_bl = Point2D(*np.min(edges, axis=0))
    absolute_grid_center = absolute_center

    if objective == "Zeiss 20x":
        fov = 500
        zmax = 25700.0
        # Corner settings
        c_width = 50
        c_length = 300
        c_height = 7
        c_hatch = 0.5
        c_slice = 0.75
        # printing area settings
        margin = 200
        padding = 100
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameterset = {
            "hatch size": [0.125],  # hatch size
            "slice size": [0.15],  # slice size/ layer height
            "power": 0.7,
            "velocity": 10_000
        }

    elif objective == "Zeiss 63x":
        fov = 150
        zmax = 25480.0  # could possibly be up to 25550 µm
        # Corner settings
        c_width = 30
        c_length = 120
        c_height = 7
        c_hatch = 0.3
        c_slice = 0.75
        # printing area settings
        margin = 50
        padding = 100
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameterset = {
            "hatch size": 0.1,  # hatch size
            "slice size": 0.1,  # slice size/ layer height
            "power": 0.3,
            "velocity": 10_000
        }

    else:
        raise Exception(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")

    logger.info(f"Print for DHM paper. Structures are stair, aspherical lens, rectangle and 5x5 quadratic DOE with"
                f"feature sizes of 10x10 µm. DOE height array is as follows: {rand_mat}.")
    sys_args.update({"controller": {
        "zMax": zmax, }
    })
    grid_size = (3, 3)  # number of repetitions, number of structures

    with Experiment(
            path=path,
            user=user,
            objective=objective,
            logger=logger,
            sys_args=sys_args,
            default_power=parameterset["power"],
            low_speed_um=1000,
            high_speed_um=10_000,
            resin_corner_tr=resin_corner_tr,
            resin_corner_bl=resin_corner_bl,
            structure_size=fov,
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=grid_size,
            n_mid_points=0,  # ToDo changing depending on experiment
            drop_direction=DropDirection.DOWN,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            plane_fit_mode=1) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=False)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path length for DHM
        if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
        experiment.opl_scan(m0=350.0, force=False)

        # TODO: Take image of whole scene
        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Adding Stair Structure
        for i in range(grid_size[0]):
            experiment.add_structure(
                structure_type=StructureType.NORMAL,
                name=f"stair{i + 1}_{movement_axis[0]}_{objective}",
                axes=movement_axis[0],
                power=parameterset["power"],
                structure=Stair(
                    Point3D(0, 0, -2),
                    n_steps=5,
                    step_height=0.6,
                    step_length=10,
                    step_width=40,
                    hatch_size=0.1,
                    slice_size=0.2,
                    socket_height=5,
                    velocity=parameterset["velocity"],
                    acceleration=experiment.accel_a_um))

            # Adding aspherical lens structure
            experiment.add_structure(
                structure_type=StructureType.NORMAL,
                name=f"lens{i + 1}_{movement_axis[0]}_{objective}",
                axes=movement_axis[0],
                power=parameterset["power"],
                structure=AsphericalLens(
                    Point3D(0, 0, -2),
                    height=5,
                    length=65,
                    width=50,
                    sphere_radius=1030,
                    conic_constant=-2.3,
                    hatch_size=0.1,
                    slice_size=0.1,
                    velocity=parameterset["velocity"],
                    acceleration=experiment.accel_a_um))

            # Adding rectangle structure
            experiment.add_structure(
                structure_type=StructureType.NORMAL,
                name=f"rect{i + 1}_{movement_axis[0]}_{objective}",
                axes=movement_axis[0],
                power=parameterset["power"],
                structure=Rectangle3D(
                    center=Point3D(0, 0, -2),
                    width=50,
                    length=60,
                    height=5,
                    hatch_size=0.1,
                    slice_size=0.2,
                    velocity=parameterset["velocity"],
                    acceleration=experiment.accel_a_um))

            # Adding DOE structure
            experiment.add_structure(
                structure_type=StructureType.NORMAL,
                name=f"DOE{i + 1}_{movement_axis[0]}_{objective}",
                axes=movement_axis[0],
                power=parameterset["power"],
                structure=DOEstep(
                    Point3D(0, 0, -2),
                    feature_size=10.0,
                    height_profile=doe_height_profile,
                    socket_height=5,
                    hatch_size=0.1,
                    slice_size=0.2,
                    velocity=5000,
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

        # TODO: Take image of whole scene
        # experiment.measure(coordinate=center, name="after")

# if __name__ == '__main__':
