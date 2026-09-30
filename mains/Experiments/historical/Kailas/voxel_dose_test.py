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
from nanofactorysystem.aerobasic.programs.drawings.dots.cell_dot_grid import grid_shape
from nanofactorysystem.aerobasic.programs.drawings.dots.dot_grid_on_base import DotGridOnBase
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D

from nanofactorysystem.experiment import Experiment, StructureType

# --- tunable parameters -------------------------------------------------
# Process constants that are never varied here (jump velocity, pad hatch) live as defaults on
# DotGridOnBase. What follows is what the sweep varies or what the z arithmetic below reports.
PAD_SIZE = 100.0         # um     base pad footprint = structure size per grid slot
PITCH = 20.0             # um     dot-to-dot spacing inside the pad
EDGE_MARGIN = 10.0       # um     clearance from outermost dot to pad edge
velocity=5000.0
BASE_POWER = 0.5         # mW     fixed base power, decoupled from the swept dot power
BASE_HEIGHT = 4.0        # um     pad thickness: 2 um of overlap + 2 um standing in the resin
BASE_SLICE = 0.25        # um     pad layer height
BASE_HATCH = 0.3             #Hatching
# z = 0 is the plane-fit substrate/resin interface; z < 0 overlaps into the substrate.
Z_B = -2.0               # um     pad bottom (pad top = Z_B + BASE_HEIGHT = +2.0)
DOT_Z_OFFSET = 1.5 #um     dot focus above pad top; must be non-zero, see DotGridOnBase

DROP_DIRECTION = DropDirection.DOWN

parameterset = {
    "power": [ 0.15, 0.2, 0.25, 0.3],      # mW   rows, advance upward in VHX
    "dwell_ms": [1, 5, 10, 20, 30, 40, 50],          # ms   cols, advance leftward in VHX
}
# ------------------------------------------------------------------------

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
        "dzFineDefault": 25.0,
        "laserPower": 0.7,
    },
    "plane": {},
}


def testprint(absolute_center: Point2D,resin_dimension: list, ask_continue_box=True, path=None,
              objective="Zeiss 63x", user="Hannes", substrate=None, dhm_usage=True, setup="IFOV_on"):
    """absolute_center: experiment centre (Point2D).
       resin_dimension: resin edge coordinates [[right], [left], [near], [far]]."""

    if DROP_DIRECTION is not DropDirection.DOWN:
        raise ValueError(
            "This experiment requires DropDirection.DOWN. The reversed layer order is what makes "
            "the dot program run before the base, so the dots inherit the swept structure power "
            "while the base sets BASE_POWER itself. With UP the base would run first and leave "
            "BASE_POWER on the controller for every dot."
        )

    if path is None:
        path = Path(mkdir(f".output/cell_geometry/power_dwell_dotgrid_new_{datetime.datetime.now():%Y%m%d}",
                          clean=False))
    else:
        path = Path(path)
        assert isinstance(path, Path)
        path = Path(mkdir(os.path.join(path, "dot_grid"), clean=False))
    logger = getLogger(logfile=f"{path}/console.log")

    edges = np.asarray(resin_dimension)
    resin_corner_tr = Point2D(*np.max(edges, axis=0))
    resin_corner_bl = Point2D(*np.min(edges, axis=0))
    absolute_grid_center = absolute_center

    if objective == "Zeiss 20x":
        fov = 500
        zmax = 25700.0
        c_width = 50
        c_length = 300
        c_height = 7
        c_hatch = 0.5
        c_slice = 0.75
        margin = 200
        padding = 100
    elif objective == "Zeiss 63x":
        fov = 150
        zmax = 25480.0
        c_width = 30
        c_length = 120
        c_height = 7
        c_hatch = 0.3
        c_slice = 0.75
        margin = 200
        padding = 100
    else:
        raise Exception(f"No implemented objective {objective}! Possible objectives are "
                        f"'Zeiss 20x' and 'Zeiss 63x'.")

    if PAD_SIZE > fov:
        raise ValueError(f"Pad {PAD_SIZE} um exceeds the {fov} um field of view.")

    sys_args.update({"controller": {"zMax": zmax}})
    if "dhm" in sys_args.keys():
        sys_args["dhm"].update({"usage": dhm_usage})
    else:
        sys_args.update({"dhm": {"usage": dhm_usage}})

    grid_size = (len(parameterset["power"]), len(parameterset["dwell_ms"]))
    n_side, extent = grid_shape(PAD_SIZE, PITCH, EDGE_MARGIN)
    logger.info(
        f"Grid {grid_size[0]}x{grid_size[1]} = {grid_size[0] * grid_size[1]} slots, "
        f"{n_side}x{n_side} = {n_side ** 2} dots per slot ({extent} um extent), "
        f"{grid_size[0] * grid_size[1] * n_side ** 2} dots total"
    )

    # Same slicing as Rectangle3D_IFOV.iterate_layers, logged so the resolved z geometry is in
    # console.log and can be checked against the .pgm files before printing.
    pad_top = Z_B + BASE_HEIGHT
    n_base_layers = abs(round(BASE_HEIGHT / BASE_SLICE)) + 1
    logger.info(
        f"Pad {Z_B} -> {pad_top} um ({BASE_HEIGHT} um thick, {pad_top} um above the interface), "
        f"{n_base_layers} layers at {BASE_HEIGHT / (n_base_layers - 1):.3f} um; "
        f"dots at z = {pad_top + DOT_Z_OFFSET} um ({DOT_Z_OFFSET} um above the pad top)"
    )

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
            structure_size=float(PAD_SIZE),
            margin=margin,
            padding=padding,
            absolute_grid_center=absolute_grid_center,
            grid=grid_size,
            n_mid_points=0,
            camera_capture=True,
            drop_direction=DROP_DIRECTION,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            fov_dim=(fov, fov),
            plane_fit_mode=0,
            setup=setup,
            skip_corner=False) as experiment:

        experiment.plot_experiment(show=True)

        if ask_continue_box and not messagebox.askyesno(message="Run plane fitting?"):
            return
        experiment.plane_fit(force=False)

        if dhm_usage:
            if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"):
                return
            experiment.opl_scan(m0=350.0, force=False)

        for power in parameterset["power"]:
            for dwell_ms in parameterset["dwell_ms"]:
                experiment.add_structure(
                    structure_type=StructureType.IFOV,
                    name=f"dots_p{power}_t{dwell_ms}ms",
                    axes="XYZ",
                    power=power,
                    structure=DotGridOnBase(
                        center=Point3D(0, 0, Z_B),
                        cellsize=PAD_SIZE,
                        dwell_s=dwell_ms / 1000.0,
                        pitch=PITCH,
                        edge_margin=EDGE_MARGIN,
                        dot_z_offset=DOT_Z_OFFSET,
                        base_power=BASE_POWER,
                        base_height=BASE_HEIGHT,
                        base_slice=BASE_SLICE,
                        base_hatch=BASE_HATCH,
                        velocity=velocity
                    ),
                )

        if ask_continue_box:
            if messagebox.askyesno(message="Create programs for all structures?"):
                experiment.build_programs()
            else:
                if messagebox.askyesno(message="Programs already created?"):
                    experiment.retrieve_programs()
        else:
            experiment.build_programs()

        if ask_continue_box and not messagebox.askyesno(message="FINAL STEP: Print experiment?"):
            return
        experiment.print_experiment()


if __name__ == '__main__':
    testprint(
        absolute_center=Point2D(X=1000, Y=22000),
        resin_dimension=[[900, 17500], [1000, 26700], [-3700, 22000], [5500, 22200]],
        ask_continue_box=True,
        objective="Zeiss 63x",
        user="Hannes",
        dhm_usage=False,
    )
