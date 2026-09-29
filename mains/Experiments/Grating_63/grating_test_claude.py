##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################

"""
Grating_63 Experiment Script
=========================
Test experiment for various grating structures:
- BlazedGrating (sawtooth)
- BinaryGrating (step grating)
- SinusoidalGrating
- FresnelLens

All structures exceed the FOV of 150 µm with:
- Height difference ≥ 2 µm between peak and valley
- Base height of 2-3 µm
"""

import datetime
import os
from pathlib import Path
from tkinter import messagebox
import numpy as np

from nanofactorysystem import mkdir, getLogger
from nanofactorysystem.aerobasic.programs.drawings.height_function_structures.structures import (
    BlazedGrating,
    BinaryGrating,
    SinusoidalGrating,
    FresnelLens
)
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
        "OffsetFocusDetection": [80, 0],
        "minCircularity": 0.6,
        "exposureValue": 120
    },
    "layer": {
        "dzFineDefault": 25.0,
        "laserPower": 0.7
    },
    "plane": {},
}


def gratings_testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                       objective="Zeiss 63x", user="Hannes", dhm_usage=True):
    """
    Grating_63 test experiment with BlazedGrating, BinaryGrating, SinusoidalGrating, and FresnelLens.

    Args:
        absolute_center: Point2D with x- and y-coordinate of the center of this experiment
        resin_dimension: list of the coordinates of the edges of the resin
                [[right edge],   Example:   [[100, 18550],
                [left edge],                [200, 26300],
                [near edge],                [-3500, 22400],
                [far edge]]                 [4000, 22400]]
        ask_continue_box: bool -> controls the asking box
        path: Path argument for root directory where the experimental data will be saved
        objective: Microscope objective to use
        user: User name for logging
        dhm_usage: Whether to use DHM
    """

    if path is None:
        path = Path(mkdir(f".output/gratings_test/print_{datetime.datetime.now():%Y%m%d}", clean=False))
    else:
        path = Path(path)  # accept str or Path
        path = Path(mkdir(os.path.join(path, "grating_function_test_2"), clean=False))
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
        parameterset = {
            "hatch size": [0.2],
            "slice size": [0.2],
            "power": [0.7],
            "velocity": [10_000]
        }

    elif objective == "Zeiss 63x":
        fov = 150
        zmax = 25480.0
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
        parameterset = {
            "hatch size": [0.2],
            "slice size": [0.2],
            "power": [0.4],
            "velocity": [5_000]
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

    # ==================================================================================
    # STRUCTURE PARAMETERS
    # ==================================================================================
    # All structures exceed FOV of 150 µm
    # Height difference ≥ 2 µm
    # Base height ~ 2-3 µm

    structure_width = 100  # µm - exceeds 150 µm FOV
    structure_length = 50  # µm - exceeds 150 µm FOV
    grating_height = 2.5  # µm - height difference peak to valley
    base_height = 2.5  # µm - base/socket height
    grating_period = 5.0  # µm - period for gratings

    # FresnelLens specific parameters
    fresnel_focal_length = 500  # µm
    fresnel_wavelength = 0.78  # µm (780 nm - typical 2PP wavelength)
    fresnel_height = 2.5  # µm

    # ==================================================================================

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
            structure_size=150,
            fov_dim=(fov, fov),
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=(2, 2),  # 4 structures: BlazedGrating, BinaryGrating, SinusoidalGrating, FresnelLens
            n_mid_points=0,
            drop_direction=DropDirection.DOWN,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            plane_fit_mode=1,
            skip_corner=False) as experiment:

        # Visualize experiment
        experiment.plot_experiment(show=True)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path length for DHM
        if dhm_usage:
            if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
            experiment.opl_scan(m0=350.0, force=False)

        # ------------------------------------------------------------------------------
        # ADD STRUCTURES
        # ------------------------------------------------------------------------------

        # Structure 1: Blazed Grating_63 (Sawtooth)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"blazed_grating_p{grating_period}_h{grating_height}_b{base_height}",
            axes="ABZ",
            power=parameterset['power'][0],
            structure=BlazedGrating(
                center=Point3D(0, 0, -base_height),
                width=structure_width,
                length=structure_length,
                period=grating_period,
                height=grating_height,
                grating_angle_deg=0.0,
                phase_deg=0.0,
                base_height=base_height,
                hatch_size=parameterset['hatch size'][0],
                slice_size=parameterset['slice size'][0],
                velocity=parameterset['velocity'][0],
                acceleration=experiment.accel_a_um,
                fov_size=(fov, fov),
                usable_fov_fraction=0.85
            )
        )

        # Structure 2: Binary Grating_63 (Step Grating_63)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"binary_grating_p{grating_period}_h{grating_height}_b{base_height}",
            axes="ABZ",
            power=parameterset['power'][0],
            structure=BinaryGrating(
                center=Point3D(0, 0, -base_height),
                width=structure_width,
                length=structure_length,
                period=grating_period,
                height=grating_height,
                duty_cycle=0.5,  # 50% duty cycle
                grating_angle_deg=0.0,
                phase_deg=0.0,
                base_height=base_height,
                hatch_size=parameterset['hatch size'][0],
                slice_size=parameterset['slice size'][0],
                velocity=parameterset['velocity'][0],
                acceleration=experiment.accel_a_um,
                fov_size=(fov, fov),
                usable_fov_fraction=0.85
            )
        )

        # Structure 3: Sinusoidal Grating_63
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name=f"sinus_grating_p{grating_period}_h{grating_height}_b{base_height}",
            axes="ABZ",
            power=parameterset['power'][0],
            structure=SinusoidalGrating(
                center=Point3D(0, 0, -base_height),
                width=structure_width,
                length=structure_length,
                period=grating_period,
                height=grating_height,
                grating_angle_deg=0.0,
                phase_deg=0.0,
                base_height=base_height,
                hatch_size=parameterset['hatch size'][0],
                slice_size=parameterset['slice size'][0],
                velocity=parameterset['velocity'][0],
                acceleration=experiment.accel_a_um,
                fov_size=(fov, fov),
                usable_fov_fraction=0.85
            )
        )

        # Structure 4: Fresnel Lens
        # experiment.add_structure(
        #     structure_type=StructureType.NORMAL,
        #     name=f"fresnel_lens_f{fresnel_focal_length}_h{fresnel_height}_b{base_height}",
        #     axes="ABZ",
        #     power=parameterset['power'][0],
        #     structure=FresnelLens(
        #         center=Point3D(0, 0, -base_height),
        #         width=structure_width,
        #         length=structure_length,
        #         focal_length=fresnel_focal_length,
        #         wavelength=fresnel_wavelength,
        #         height=fresnel_height,
        #         base_height=base_height,
        #         hatch_size=parameterset['hatch size'][0],
        #         slice_size=parameterset['slice size'][0],
        #         velocity=parameterset['velocity'][0],
        #         acceleration=experiment.accel_a_um,
        #         fov_size=(fov, fov),
        #         usable_fov_fraction=0.85
        #     )
        # )

        # ------------------------------------------------------------------------------
        # END STRUCTURES
        # ------------------------------------------------------------------------------

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


# Example usage:
if __name__ == '__main__':
    print("use main.py")
    # Example coordinates - adjust to your setup
    # absolute_center = Point2D(0, 22400)  # Center of experiment
    # resin_dimension = [
    #     [100, 18550],  # right edge
    #     [200, 26300],  # left edge
    #     [-3500, 22400],  # near edge
    #     [4000, 22400]  # far edge
    # ]
    #
    # gratings_testprint(
    #     absolute_center=absolute_center,
    #     resin_dimension=resin_dimension,
    #     ask_continue_box=True,
    #     objective="Zeiss 63x",
    #     user="Hannes",
    #     dhm_usage=True
    # )