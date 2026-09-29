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
        # "dzCoarseDefault": 50.0,
        "dzFineDefault": 25.0,
        "laserPower": 0.7
    },
    "plane": {},
}



def binary_testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                     objective="Zeiss 20x", user="Hannes", dhm_usage=False, substrate=None, setup="IFOV_off",
                     backend=None, plane=None):
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
        backend: Hardware backend passed to Experiment/System. None (default) uses the lab hardware;
                "dummy" or a DummyBackend object runs the experiment on simulated devices (dry run).
        plane: Optional known substrate plane (ZFunction). If given, plane_fit() uses it instead of
                measuring the substrate, e.g. DummyBackend().world.sample.plane() for a dry run.
    """

    if path is None:
        path = Path(mkdir(f".output/dhm_paper/testprint{datetime.datetime.now():%Y%m%d}", clean=False))
    else:
        path = Path(path)  # accept str or Path
        path = Path(mkdir(os.path.join(path, "testprint_dhm"), clean=False))
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
        margin = 200  # outside
        padding = 100  # inside
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
        drop_direction = DropDirection.DOWN
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

    sys_args.update({"controller": {
        "zMax": zmax, }
    })
    # Option to not use DHM
    if "dhm" in sys_args.keys():
        sys_args["dhm"].update({"usage": dhm_usage})
    else:
        sys_args.update({"dhm": {"usage": dhm_usage}})

    structure_size = fov  # because structure is smaller than fov
    grid=(2, 3)
    with Experiment(
            path=path,
            user=user,
            objective=objective,
            logger=logger,
            sys_args=sys_args,
            default_power=0.7,
            low_speed_um=1000,
            high_speed_um=5000,
            resin_corner_tr=resin_corner_tr,
            resin_corner_bl=resin_corner_bl,
            structure_size=structure_size,
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=grid,
            n_mid_points=0,
            drop_direction=drop_direction,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            fov_dim = (fov, fov),
            plane_fit_mode=1,
            skip_corner=False,
            setup = setup,
            substrate_information=substrate,
            backend=backend) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=True)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False, plane=plane)

        # Optical path length for DHM
        if dhm_usage:
            if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
            experiment.opl_scan(m0=350.0, force=False)

        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Add structures
        # experiment.skip_structure()
        # experiment.add_structure(
        #     structure_type=StructureType.NORMAL,
        #     name="stacked_lens_1",
        #     axes="ABZ",
        #     power=parameterset['power'],
        #     structure=Stair(
        #         Point3D(0, 0, -2),
        #         n_steps=6,
        #         step_height=0.6,
        #         step_length=20,
        #         step_width=50,
        #         hatch_size=parameterset['hatch size'],
        #         slice_size=parameterset['slice size'],
        #         socket_height=7,
        #         velocity=parameterset['velocity'],
        #         acceleration=experiment.accel_a_um))
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
