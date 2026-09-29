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
               objective="Zeiss 20x", user="Hannes", repeat=5, dhm_usage=False, substrate=None, setup="IFOV_off"):
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
        path = Path(mkdir(os.path.join(path, f"lenses_surface_5_parametersets"), clean=False))
    logger = getLogger(logfile=f"{path}/console.log")

    # Size of (oval) resin drop in micrometres
    edges = np.asarray(resin_dimension)
    resin_corner_tr = Point2D(*np.max(edges, axis=0))
    resin_corner_bl = Point2D(*np.min(edges, axis=0))
    absolute_grid_center = absolute_center

    parameter_combi = []
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
        margin = 250
        padding = 100
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameter_combi = [  # [hatch, slice, power, velocity]
            [0.2, 0.2, 0.2, 2000],  # baseline - printed quite often
            [0.15, 0.2, 0.2, 2000],  # better hatching - should not be needed for better surface quality
            [0.2, 0.15, 0.2, 2000],  # better slicing - should see an advantage over the other structures
            [0.2, 0.1, 0.2, 2000],  # even more narrow slicing
            [0.1, 0.1, 0.2, 2000],  # combination of very narrow things
        ]
        parameterset = {
            "hatch size": 0.2,  # [0.1, 0.2, 0.5],  # hatch size
            "slice size": 0.2,  # [0.1, 0.2, 0.5],  # slice size/ layer height
            "power": 0.5,
            "velocity": 5_000
        }

    else:
        raise Exception(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")

    logger.info(f"Surface Quality investigation with following parametersets [hatching, slicing, power, velocity]:"
                f"{parameter_combi}")
    sys_args.update({"controller": {
        "zMax": zmax, }
    })
    # Option to not use DHM
    if "dhm" in sys_args.keys():
        sys_args["dhm"].update({"usage": dhm_usage})
    else:
        sys_args.update({"dhm": {"usage": dhm_usage}})

    structure_size = fov
    grid_size = (repeat, len(parameter_combi))  # number of repetitions, number of structures

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
            margin=margin,  # note extra big margin and padding
            padding=padding,
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
            plane_fit_mode=0,
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
        for j in range(repeat):
            for i in range(len(parameter_combi)):
                # Adding aspherical lens structure
                experiment.add_structure(
                    structure_type=StructureType.NORMAL,
                    name=f"lens_param_{str(parameter_combi[i])}_{j}",
                    axes=movement_axis[0],
                    power=parameter_combi[i][2],
                    structure=AsphericalLens(
                        Point3D(0, 0, -1),
                        height=4,
                        length=50,
                        width=50,
                        sphere_radius=515,
                        conic_constant=-2.3,
                        hatch_size=parameter_combi[i][0],
                        slice_size=parameter_combi[i][1],
                        velocity=parameter_combi[i][3],
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
