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
from nanofactorysystem.aerobasic.programs.drawings.qr_code import QRCode, QrErrorCorrection
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

sys_args = {
    "attenuator": {
        "fitKind": "quadratic",
    },
    "sample": {
        "name": "qrcode_test",
        "orientation": "bottom",
        "substrate": "boro-silicate glass",
        "substrateThickness": 700.0,
        "material": "SZ2080",
        "materialThickness": 75.0,
    },
    "focus": {
        "OffsetFocusDetection": [110, -180]  # x|width, y|height  2064x1544 - 0,0 point in upper left corner
                                             # -- WIDTH 8,2/14,8->off 0,8=111,5 -- HEIGHT 6,8/11->off 1,3=182,4 --
    },
    "layer": {
        "beta": 0.7,
    },
    "plane": {},
}


# ToDo(HR): how do i transfer a dict or other system arguments to this function?
def qr_code_test(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                 objective="Zeiss 63x", user="Hannes"):
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
        path = Path(mkdir(f".output/qr_code_test/height_pitch_test{datetime.datetime.now():%Y%m%d}", clean=False))
    else:
        # ToDo(HR) make ist more controllable
        assert (path, Path)
        path = Path(mkdir(os.path.join(path, "testprint_qr_code")))
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

    sys_args.update({"controller": {
        "zMax": zmax, }
    })

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
            structure_size=fov,
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=(5, 2),  # ToDo: changing depending on experiment
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
        experiment.plot_experiment(show=True)

        # Get substrate surface plane
        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"): return
        experiment.plane_fit(force=False)

        # Optical path length for DHM
        if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"): return
        experiment.opl_scan(m0=75.0, force=False)

        # TODO: Take image of whole scene
        # center = experiment.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
        # experiment.measure(coordinate=center, name="before")

        # ----------------------------------------------------------------------------------------------------------------------
        # ----------------------------------------------------------------------------------------------------------------------
        # Add structures
        # experiment.skip_structure()
        reference_point = Point3D(0, 0, experiment.corner_z)
        text_qr_code = experiment.qr_text
        qrcode_pitch4_height2_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=4.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=2.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch4_height3_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=4.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=3.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch3_height1_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=3.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=1.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch3_height2_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=3.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=2.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch3_height3_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=3.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=3.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch2_height2_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=2.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=2.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch2_height3_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=2.0,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=3.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)
        qrcode_pitch2_height1_base5 = QRCode(
            reference_point,
            text=text_qr_code,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=2,
            base_height=5.0,
            anchor_height=2.0,
            pixel_height=1.0,
            slice_size=experiment.corner_slice,
            hatch_size=experiment.corner_hatch,
            horizontal_velocity=experiment.high_speed_um,
            horizontal_acceleration=experiment.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=experiment.accel_z_um)

        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch4_height2_base5",
            structure=qrcode_pitch4_height2_base5)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch4_height3_base5",
            structure=qrcode_pitch4_height3_base5)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch3_height1_base5",
            structure=qrcode_pitch3_height1_base5)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch3_height2_base5",
            structure=qrcode_pitch3_height2_base5)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch3_height3_base5",
            structure=qrcode_pitch3_height3_base5)
        experiment.skip_structure()
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch2_height2_base5",
            structure=qrcode_pitch2_height2_base5)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch2_height3_base5",
            structure=qrcode_pitch2_height3_base5)
        experiment.add_structure(
            structure_type=StructureType.NORMAL,
            name="qrcode_pitch2_height1_base5",
            structure=qrcode_pitch2_height1_base5)
        experiment.skip_structure()

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
