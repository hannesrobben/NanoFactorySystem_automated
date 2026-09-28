
import datetime
import os
from pathlib import Path
from tkinter import messagebox

import numpy as np

from nanofactorysystem import mkdir, getLogger
from nanofactorysystem.aerobasic.programs.drawings.cell_lines_on_base_02192026 import CellLinesOnBase
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType

PAD_SIZE = 100.0         # um
EDGE_MARGIN = 3.0        # um
Z_B = -2.0               # um

BASE_POWER = 0.5         # mW
BASE_HEIGHT = 4.0        # um
BASE_HATCH = 0.3         # um
BASE_SLICE = 0.25        # um

VELOCITY = 5000.0        # um/s

POWERS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]                  # mW
PITCHES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]        # um
Z_OFFSETS = [-3.0,-2.0, -1.0, 0.0, 1.0, 2.0,3.0, 4.0, 5.0]     # um

DROP_DIRECTION = DropDirection.DOWN


PLANE_FIT_MODE = 1
SECONDS_PER_PLANE_POINT = 32.0   # measured on the 2026-07-30 dot run

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


def _z_note(dz: float) -> str:
    if dz < 0:
        return "buried in pad"
    if dz == 0:
        return "coplanar with pad top"
    return "proud of pad"


def testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=True, path=None,
                        objective="Zeiss 63x", user="Kailas", dhm_usage=True, setup="IFOV_on"):


    # Checked before the plane fit: a bad configuration cost a sample.
    if len(PITCHES) != len(Z_OFFSETS):
        raise ValueError(
            f"PITCHES has {len(PITCHES)} values but Z_OFFSETS has {len(Z_OFFSETS)}. They are "
            f"zipped, and zip() truncates to the shorter list silently. POWERS is independent."
        )

    if DROP_DIRECTION is not DropDirection.DOWN:
        raise ValueError(
            "This experiment requires DropDirection.DOWN. The reversed layer order is what makes "
            "the line layer run before the pad, so the lines are always written into virgin resin "
            "and only their burial changes across the Z_OFFSETS sweep."
        )

    if BASE_HEIGHT + min(Z_OFFSETS) < 0:
        raise ValueError(
            f"Z_OFFSETS minimum {min(Z_OFFSETS)} um puts the line plane below the pad bottom "
            f"(pad is {BASE_HEIGHT} um thick)."
        )


    if path is None:
        path = Path(mkdir(f".output/large_z_pitch_vs_power/power_z_pitch_linesv2_{datetime.datetime.now():%Y%m%d}",
                          clean=False))
    else:
        if isinstance(path,str):
            path=Path(path)
        assert isinstance(path,Path)
        path = Path(mkdir(os.path.join(path, "power_z_pitch_lines"), clean=False))
    logger = getLogger(logfile=f"{path}/console.log")

    # Size of (oval) resin drop in micrometres
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
        write_speed_mm_s = 10.0

    elif objective == "Zeiss 63x":
        fov = 150
        zmax = 25480.0
        c_width = 30
        c_length = 120
        c_height = 7
        c_hatch = 0.3
        c_slice = 0.75
        margin = 180
        padding = 100
        write_speed_mm_s = 5.0

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

    structure_size = float(PAD_SIZE)
    grid_size = (len(POWERS), len(PITCHES))

    # Resolved geometry, logged so console.log can be checked against the .pgm files.
    pad_top = Z_B + BASE_HEIGHT
    n_base_layers = abs(round(BASE_HEIGHT / BASE_SLICE)) + 1
    logger.info(
        f"Grid {grid_size[0]}x{grid_size[1]} = {grid_size[0] * grid_size[1]} slots, pad {PAD_SIZE} um, "
        f"{grid_size[1] * (structure_size + padding) - padding + 2 * margin:.0f} x "
        f"{grid_size[0] * (structure_size + padding) - padding + 2 * margin:.0f} um footprint"
    )
    logger.info(
        f"Pad {Z_B} -> {pad_top} um, {n_base_layers} layers at "
        f"{BASE_HEIGHT / (n_base_layers - 1):.3f} um, hatch {BASE_HATCH} um, power {BASE_POWER} mW; "
        f"write speed {write_speed_mm_s} mm/s (VELOCITY is inert on the IFOV path)"
    )
    logger.info(f"Rows (+Y): power {POWERS} mW")
    logger.info("Columns (+X): pitch zipped with z offset")
    for j, (pitch, dz) in enumerate(zip(PITCHES, Z_OFFSETS)):
        logger.info(
            f"  col {j}: pitch {pitch:4.1f} um, z {dz:+.2f} um -> lines at {pad_top + dz:+.2f} um "
            f"({_z_note(dz)})"
        )
    if min(Z_OFFSETS) < 0:
        logger.warning(
            f"Columns with z offset < 0 are buried in the {BASE_HEIGHT} um pad and are optically "
            f"invisible from above; read them by confocal cross-section."
        )

    with Experiment(
            path=path,
            user=user,
            objective=objective,
            logger=logger,
            sys_args=sys_args,
            default_power=0.7,   # corners and the QR code fall back to this
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
            drop_direction=DROP_DIRECTION,
            corner_z=-2,
            corner_width=c_width,
            corner_length=c_length,
            corner_height=c_height,
            corner_hatch=c_hatch,
            corner_slice=c_slice,
            fov_dim=(fov, fov),
            plane_fit_mode=PLANE_FIT_MODE,
            setup=setup,
            skip_corner=False) as experiment:


        attenuator = experiment.system.controller.attenuator
        power_min, power_max = attenuator["powerMin"], attenuator["powerMax"]
        out_of_range = [p for p in POWERS + [BASE_POWER] if not power_min <= p <= power_max]
        if out_of_range:
            raise ValueError(
                f"Powers {out_of_range} mW lie outside the attenuator calibration range "
                f"({power_min:.4f} - {power_max:.4f} mW)."
            )

        experiment.plot_experiment(show=True)

        # Announce the cost: a silent 35-minute focus-detection phase looks like a hang.
        n_plane_points = len(experiment.sample_points_for_plane_fitting())
        plane_minutes = n_plane_points * SECONDS_PER_PLANE_POINT / 60
        logger.info(
            f"Plane fit mode {PLANE_FIT_MODE}: {n_plane_points} probe points, roughly "
            f"{plane_minutes:.0f} min. The z reference is therefore not the 4-corner fit the "
            f"printed dot runs used -- only z relative to this run's own pad top is comparable."
        )
        if ask_continue_box and not messagebox.askyesno(
                message=f"Run plane fitting? {n_plane_points} probe points, roughly "
                        f"{plane_minutes:.0f} min."):
            return

        experiment.plane_fit(force=False)

        if dhm_usage:
            if ask_continue_box and not messagebox.askyesno(message="Run OPL motor scan?"):
                return
            experiment.opl_scan(m0=350.0, force=False)


        for power in POWERS:
            for pitch, dz in zip(PITCHES, Z_OFFSETS):
                experiment.add_structure(
                    structure_type=StructureType.IFOV,
                    name=f"cell_p{power}_d{pitch}_z{dz:+}",
                    axes="XYZ",
                    power=power,
                    structure=CellLinesOnBase(
                        center=Point3D(0, 0, Z_B),
                        cellsize=PAD_SIZE,
                        distance_between_lines=pitch,
                        line_z_offset=dz,
                        edge_margin=EDGE_MARGIN,
                        velocity=VELOCITY,
                        line_power=power,
                        base_power=BASE_POWER,
                        base_height=BASE_HEIGHT,
                        base_hatch=BASE_HATCH,
                        base_slice=BASE_SLICE,
                        objective=objective,
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
    power_z_pitch_lines(
        absolute_center=Point2D(X=1000, Y=22000),
        resin_dimension=[[900, 17500], [1000, 26700], [-3700, 22000], [5500, 22200]],
        ask_continue_box=True,
        objective="Zeiss 63x",
        user="Kailas",
        dhm_usage=False,
    )
