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
from nanofactorysystem.aerobasic.programs.drawings import BinaryGrating, Apertures, BlazedGrating
from nanofactorysystem.aerobasic.programs.drawings.lines import Stair, Rectangle3D
from nanofactorysystem.aerobasic.programs.drawings.DOE import Binary_grating, DOEstep
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

sys_args = {
    "attenuator": {
        "fitKind": "quadratic",
    },
    "sample": {
        "name": "#1",
        "orientation": "top",
        "substrate": "boro-silicate glass",
        "substrateThickness": 700.0,
        "material": "SZ2080",
        "materialThickness": 75.0,
    },
    "focus": {
        "OffsetFocusDetection": [120, -80],
        "minCircularity": 0.6,
        "exposureValue": 120
    },
    "layer": {
        # "beta": 0.7,
        "dzFineDefault": 25.0,
        "laserPower": 0.7,
    },
    "plane": {},
}


def binary_testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                     objective="Zeiss 20x", user="Hannes", dhm_usage=False):
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
        path = Path(mkdir(f".output/grating/binary_grating1{datetime.datetime.now():%Y%m%d}", clean=False))
    else:
        path = Path(path)  # accept str or Path
        path = Path(mkdir(os.path.join(path, "program_cycle_test"), clean=False))
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
            "hatch size": 0.2,  # [0.1, 0.2, 0.5],  # hatch size
            "slice size": 0.2,  # [0.1, 0.2, 0.5],  # slice size/ layer height
            "power": 0.7,
            "velocity": 10_000
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

    structure_size = 200.0
    grid_size = (2, 2)
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
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=grid_size,
            n_mid_points=0,
            drop_direction=DropDirection.DOWN,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            fov_dim=(fov, fov),
            plane_fit_mode=1,
            skip_corner=False) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=True)

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
        # Add structures
        # experiment.skip_structure()

        # Experiment Binary no rotation

        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"stair_{movement_axis[0]}_{objective}",
            axes=movement_axis[0],
            power=parameterset["power"],
            structure=Stair(
                Point3D(0, 0, -2),
                n_steps=5,
                step_height=0.6,
                step_length=10,
                step_width=40,
                hatch_size=parameterset["hatch size"],
                slice_size=parameterset["slice size"],
                socket_height=5,
                velocity=parameterset["velocity"],
                acceleration=experiment.accel_a_um))

        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"binary_s{parameterset["slice size"]}_h_{parameterset["hatch size"]}",
            axes="ABZ",
            power=parameterset["power"],
            structure=BinaryGrating(
                center=Point3D(0, 0, -2),
                width=structure_size,  # µm
                length=structure_size,  # µm
                period=10,  # µm
                height=2,  # µm
                duty_cycle=5,  # µm
                grating_angle_deg=0.0,
                base_height=2.0,  # µm
                hatch_size=parameterset["hatch size"],
                slice_size=parameterset["slice size"],
                velocity=parameterset["velocity"],
                acceleration=experiment.accel_a_um,
                aperture=None,
                hatch_angle_deg=0.0,
                alternating_hatch=True,
                fov_size=(fov, fov),
                usable_fov_fraction=0.6,
                grid_resolution=10000)
        )

        # Adding DOE structure
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"DOE_{movement_axis[0]}_{objective}",
            axes=movement_axis[0],
            power=parameterset["power"],
            structure=DOEstep(
                Point3D(0, 0, -2),
                feature_size=10.0,
                height_profile=doe_height_profile,
                socket_height=5,
                hatch_size=parameterset["hatch size"],
                slice_size=parameterset["slice size"],
                velocity=parameterset["velocity"],
                acceleration=experiment.accel_a_um))

        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"blazed_grating_",
            axes="ABZ",
            power=parameterset['power'],
            structure=BlazedGrating(
                center=Point3D(0, 0, -2),
                width=structure_size,
                length=structure_size,
                period=10,
                height=2,
                grating_angle_deg=0.0,
                phase_deg=0.0,
                base_height=3,
                hatch_size=parameterset['hatch size'],
                slice_size=parameterset['slice size'],
                velocity=parameterset['velocity'],
                acceleration=experiment.accel_a_um,
                fov_size=(fov, fov),
                usable_fov_fraction=0.6
            )
        )
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
