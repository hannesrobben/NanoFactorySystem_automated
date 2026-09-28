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
from nanofactorysystem.aerobasic.programs.drawings.lines import Stair, Rectangle3D
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

"""
 # ONLY FOR ONE TIME USE FOR OFFSET INVESTIGATION
 """

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
    "focus": {},
    "layer": {
            "beta": 0.7,
            "dzCoarseDefault": 50.0,
            "dzFineDefault": 10.0,
            "laserPower": 0.4,
        },
    "plane": {},
}


# ToDo(HR): how do i transfer a dict or other system arguments to this function?
def dhm_testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                  objective="Zeiss 20x", user="Hannes"):
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
        path = Path(mkdir(f".output/dhm_paper/print4paper_no_z_Offset_{datetime.datetime.now():%Y%m%d}_dhm_{objective}", clean=False))
    else:
        assert (path, Path)
        path = Path(mkdir(os.path.join(path, "testprint_dhm")))
    logger = getLogger(logfile=f"{path}/console.log")

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
        power = 0.7

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
        power = 0.3

    else:
        raise Exception(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")

    sys_args.update({"controller": {
        "zMax": zmax, }
    })

    with Experiment(
            path=path,
            user=user,
            objective=objective,
            logger=logger,
            sys_args=sys_args,
            default_power=power,
            low_speed_um=1000,
            high_speed_um=5000,
            resin_corner_tr=resin_corner_tr,
            resin_corner_bl=resin_corner_bl,
            structure_size=fov,
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=(3, 5),
            n_mid_points=0,  # ToDo changing depending on experiment
            drop_direction=DropDirection.DOWN,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            skip_corner=True) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=False)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path length for DHM
        if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
        experiment.opl_scan(m0=3847.0, force=False)

        # TODO: Take image of whole scene
        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Add structures
        experiment.skip_structure()
        experiment.skip_structure()
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="stair_galvo3",
            axes="ABZ",
            power=power,
            structure=Stair(
                Point3D(0, 0, 0),
                n_steps=6,
                step_height=0.6,
                step_length=20,
                step_width=50,
                hatch_size=0.1,
                slice_size=0.3,
                socket_height=7,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="stair_galvo4",
            axes="ABZ",
            power=power,
            structure=Stair(
                Point3D(0, 0, 0),
                n_steps=6,
                step_height=0.6,
                step_length=20,
                step_width=50,
                hatch_size=0.1,
                slice_size=0.3,
                socket_height=7,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="stair_galvo5",
            axes="ABZ",
            power=power,
            structure=Stair(
                Point3D(0, 0, 0),
                n_steps=6,
                step_height=0.6,
                step_length=20,
                step_width=50,
                hatch_size=0.1,
                slice_size=0.3,
                socket_height=7,
                velocity=5000,
                acceleration=experiment.accel_a_um))

        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="lens_galvo1",
            axes="ABZ",
            power=power,
            structure=AsphericalLens(
                Point3D(0, 0, 0),
                height=7,
                length=100,
                width=75,
                sphere_radius=1030,
                conic_constant=-2.3,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="lens_galvo2",
            axes="ABZ",
            power=power,
            structure=AsphericalLens(
                Point3D(0, 0, 0),
                height=7,
                length=100,
                width=75,
                sphere_radius=1030,
                conic_constant=-2.3,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="lens_galvo3",
            axes="ABZ",
            power=power,
            structure=AsphericalLens(
                Point3D(0, 0, 0),
                height=7,
                length=100,
                width=75,
                sphere_radius=1030,
                conic_constant=-2.3,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="lens_galvo4",
            axes="ABZ",
            power=power,
            structure=AsphericalLens(
                Point3D(0, 0, 0),
                height=7,
                length=100,
                width=75,
                sphere_radius=1030,
                conic_constant=-2.3,
                hatch_size=0.125,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="lens_galvo5",
            axes="ABZ",
            power=power,
            structure=AsphericalLens(
                Point3D(0, 0, 0),
                height=7,
                length=100,
                width=75,
                sphere_radius=1030,
                conic_constant=-2.3,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))

        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="rect_galvo1",
            axes="ABZ",
            power=power,
            structure=Rectangle3D(
                center=Point3D(0, 0, 0),
                width=50,
                length=125,
                height=7,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="rect_galvo2",
            axes="ABZ",
            power=power,
            structure=Rectangle3D(
                center=Point3D(0, 0, 0),
                width=50,
                length=125,
                height=7,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="rect_galvo3",
            axes="ABZ",
            power=power,
            structure=Rectangle3D(
                center=Point3D(0, 0, 0),
                width=50,
                length=125,
                height=7,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="rect_galvo4",
            axes="ABZ",
            power=power,
            structure=Rectangle3D(
                center=Point3D(0, 0, 0),
                width=50,
                length=125,
                height=7,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="rect_galvo5",
            axes="ABZ",
            power=power,
            structure=Rectangle3D(
                center=Point3D(0, 0, 0),
                width=50,
                length=125,
                height=7,
                hatch_size=0.1,
                slice_size=0.15,
                velocity=5000,
                acceleration=experiment.accel_a_um))

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------

        # Build corner and structure programs
        if ask_continue_box:
            if messagebox.askyesno(message="Create programs for all structures?"):
                experiment.build_programs()
            else:
                if not messagebox.askyesno(message="Programs already created?"): return
        else:
            experiment.build_programs()

        # Print corners and structures
        if ask_continue_box and not messagebox.askyesno(message="FINAL STEP: Print experiment?"): return
        experiment.print_experiment()

        # TODO: Take image of whole scene
        # experiment.measure(coordinate=center, name="after")

# if __name__ == '__main__':
