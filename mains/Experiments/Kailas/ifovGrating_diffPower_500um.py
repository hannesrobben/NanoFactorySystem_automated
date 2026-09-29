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
from nanofactorysystem.aerobasic.programs.drawings import BinaryGrating_IFOV
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

sys_args = {
    "attenuator": {
        "fitKind": "quadratic",
    },
    "sample": {
        "name": "#1",
        "orientation": "top",
        "substrate": "boro-silicate glass, aber das dicke glass, ISO 8037/1",
        "substrateThickness": 1000,
        "material": "SZ2080",
        "materialThickness": 175.0,
    },
    "focus": {
        "OffsetFocusDetection": [130, -15],
        # "OffsetFocusDetection": [120, -80],
        "minCircularity": 0.55,
        "exposureValue": 120
    },
    "layer": {
        # "beta": 0.7,
        "dzFineDefault": 25.0,
        "laserPower": 0.7,
    },
    "plane": {},
}


# ToDo(HR): how do i transfer a dict or other system arguments to this function?
def print_file(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                     objective="Zeiss 63x", user="Hannes", dhm_usage=False, substrate=None, setup="IFOV_on"):
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
        path = Path(mkdir(f".output/ifov/binary_grating1{datetime.datetime.now():%Y%m%d}", clean=False))
    else:
        # ToDo(HR) make ist more controllable
        path = Path(path)  # accept str or Path
        path = Path(mkdir(os.path.join(path, "ifov_grating_different_power_500um_big"), clean=False))
    logger = getLogger(logfile=f"{path}/console.log")

    # Size of (oval) resin drop in micrometres
    edges = np.asarray(resin_dimension)
    resin_corner_tr = Point2D(*np.max(edges, axis=0))
    resin_corner_bl = Point2D(*np.min(edges, axis=0))
    absolute_grid_center = absolute_center

    if objective == "Zeiss 20x":
        drop_direction =DropDirection.UP
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
        padding = 100
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameterset = {
            "hatch size": 0.2,  # hatch size
            "slice size": 0.2,  # slice size/ layer height
            "power": 0.7,
            "velocity": 10_000
        }

    elif objective == "Zeiss 63x":
        drop_direction =DropDirection.DOWN
        fov = 150
        zmax = 25480.0  # could possibly be up to 25550 µm
        # Corner settings
        c_width = 30
        c_length = 120
        c_height = 7
        c_hatch = 0.3
        c_slice = 0.75
        # printing area settings
        margin = 100
        padding = 100
        # printing settings
        movement_axis = ["ABZ", "XYZ"]
        parameterset = {
            "hatch size": 0.2,  # [0.1, 0.2, 0.5],  # hatch size
            "slice size": 0.2,  # [0.1, 0.2, 0.5],  # slice size/ layer height
            "power": [0.1, 0.15, 0.2, 0.25 , 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7],
            # "power": [0.15, 0.3, 0.5],
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

    structure_size = 500.0
    grid_size = (1, len(parameterset["power"]))

    substrate.update({"structure sizes": structure_size})
    # todo save substrate
    
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
            structure_size=structure_size,  # ToDo change fov to structure size and add fov to real
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=grid_size,
            # ToDo: changing depending on experiment - e.g. (number of repetitions, number of structures)
            n_mid_points=0,  # ToDo changing depending on experiment
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
        experiment.plot_experiment(show=True)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path max_length for DHM
        if dhm_usage:
            if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
            experiment.opl_scan(m0=350.0, force=False)

        # TODO: Take image of whole scene
        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Add structures
        # experiment.skip_structure()
        for j in range(1):
            for i in range(len(parameterset["power"])):
                experiment.add_structure(
                    structure_type=StructureType.IFOV,
                    name=f"binaryIFOV_Obj_{objective}_power{parameterset["power"][i]}_{j}",
                    axes="XYZ",
                    power=parameterset["power"][i],
                    structure=BinaryGrating_IFOV(
                        center=Point3D(0, 0, -1),
                        x_dim=structure_size,  # µm
                        y_dim=structure_size,  # µm
                        period=20,  # µm
                        height=2,  # µm
                        duty_cycle=0.5,  # ratio
                        grating_angle_deg=0.0,
                        base_height=2.0,  # µm
                        hatch_size=parameterset["hatch size"],
                        slice_size=parameterset["slice size"],
                        velocity=parameterset["velocity"],
                        power=parameterset["power"][i],
                        start_hatching_direction=HatchingDirection.X,
                        alternating_hatch=True,
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

        # TODO: Take image of whole scene
        # experiment.measure(coordinate=center, name="after")

# if __name__ == '__main__':
