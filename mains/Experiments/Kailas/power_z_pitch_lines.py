##########################################################################
# Copyright (c) 2022-2026 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Line cells on a base pad: power (rows) x line pitch zipped with the line z offset (columns).

Described by ``experiment_spec()`` (T64); ``testprint()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem import getLogger
from nanofactorysystem.aerobasic.programs.drawings.cell_lines_on_base_02192026 import CellLinesOnBase
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode, sample_points

PAD_SIZE = 100.0         # um
EDGE_MARGIN = 3.0        # um
Z_B = -2.0               # um

BASE_POWER = 0.5         # mW
BASE_HEIGHT = 4.0        # um
BASE_HATCH = 0.3         # um
BASE_SLICE = 0.25        # um

VELOCITY = 5000.0        # um/s (IFOV writes with the fixed speed of the objective)

POWERS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]                  # mW
PITCHES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]        # um
Z_OFFSETS = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0]   # um

DROP_DIRECTION = DropDirection.DOWN
PLANE_FIT_MODE = PlaneFitMode.CORNERS
SECONDS_PER_PLANE_POINT = 32.0   # measured on the 2026-07-30 dot run

OBJECTIVES = {
    "Zeiss 20x": dict(fov_um=500.0, z_max_um=25700.0, margin_um=200.0, padding_um=100.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    "Zeiss 63x": dict(fov_um=150.0, z_max_um=25480.0, margin_um=180.0, padding_um=100.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {"OffsetFocusDetection": [120, -80], "minCircularity": 0.6, "exposureValue": 120},
        "layer": {"dzFineDefault": 25.0, "laserPower": 0.7},
        "plane": {},
    }


def _z_note(dz: float) -> str:
    if dz < 0:
        return "buried in pad"
    if dz == 0:
        return "coplanar with pad top"
    return "proud of pad"


def cell(power, pitch, dz, objective):
    """ Factory of one line cell; checks the powers against the attenuator calibration of the experiment. """

    def build(experiment):
        attenuator = experiment.system.controller.attenuator
        power_min, power_max = attenuator["powerMin"], attenuator["powerMax"]
        out_of_range = [p for p in (power, BASE_POWER) if not power_min <= p <= power_max]
        if out_of_range:
            raise ValueError(f"Powers {out_of_range} mW lie outside the attenuator calibration range "
                             f"({power_min:.4f} - {power_max:.4f} mW).")
        return CellLinesOnBase(center=Point3D(0, 0, Z_B), cellsize=PAD_SIZE, distance_between_lines=pitch,
                               line_z_offset=dz, edge_margin=EDGE_MARGIN, velocity=VELOCITY, line_power=power,
                               base_power=BASE_POWER, base_height=BASE_HEIGHT, base_hatch=BASE_HATCH,
                               base_slice=BASE_SLICE, objective=objective)
    return build


def experiment_spec(objective="Zeiss 63x", absolute_center=Point2D(0, 0), dhm_usage=True,
                    setup="IFOV_on") -> ExperimentSpec:
    """ One row per power, one column per (pitch, z offset); the checks run before anything is printed. """

    # Checked before the plane fit: a bad configuration cost a sample.
    if len(PITCHES) != len(Z_OFFSETS):
        raise ValueError(f"PITCHES has {len(PITCHES)} values but Z_OFFSETS has {len(Z_OFFSETS)}. They are zipped, "
                         f"and zip() truncates to the shorter list silently. POWERS is independent.")
    if DROP_DIRECTION is not DropDirection.DOWN:
        raise ValueError("This experiment requires DropDirection.DOWN. The reversed layer order is what makes the "
                         "line layer run before the pad, so the lines are always written into virgin resin and only "
                         "their burial changes across the Z_OFFSETS sweep.")
    if BASE_HEIGHT + min(Z_OFFSETS) < 0:
        raise ValueError(f"Z_OFFSETS minimum {min(Z_OFFSETS)} um puts the line plane below the pad bottom "
                         f"(pad is {BASE_HEIGHT} um thick).")
    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    fov = OBJECTIVES[objective]["fov_um"]
    if PAD_SIZE > fov:
        raise ValueError(f"Pad {PAD_SIZE} um exceeds the {fov} um field of view.")
    structures = [
        StructureSpec(f"cell_p{power}_d{pitch}_z{dz:+}", factory=cell(power, pitch, dz, objective), power_mw=power,
                      axes="XYZ", structure_type=StructureType.IFOV)
        for power in POWERS for pitch, dz in zip(PITCHES, Z_OFFSETS)]
    return ExperimentSpec(
        name="power_z_pitch_lines", objective=objective, center=absolute_center, grid=(len(POWERS), len(PITCHES)),
        structures=structures, setup=setup, drop_direction=DROP_DIRECTION, plane_fit_mode=PLANE_FIT_MODE,
        dhm_usage=dhm_usage, camera_capture=True, structure_size_um=PAD_SIZE, default_power_mw=0.7,
        low_speed_um_s=1000, high_speed_um_s=10_000, opl_start_um=350.0, sys_args=runtime_arguments(),
        **OBJECTIVES[objective])


def plane_points(spec: ExperimentSpec) -> int:
    """ Number of plane-fit points of the experiment (same layout as ``Experiment``). """

    spec = spec.resolved()
    rows, cols = spec.grid
    step = spec.structure_size_um + spec.padding_um
    width = cols * step - spec.padding_um + 2 * spec.margin_um
    height = rows * step - spec.padding_um + 2 * spec.margin_um
    top_left = (spec.center.X - width / 2, spec.center.Y - height / 2)
    return len(sample_points(spec.plane_fit_mode, top_left, spec.margin_um, spec.padding_um, spec.structure_size_um,
                             spec.grid))


def testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=True, path=None,
              objective="Zeiss 63x", user="Kailas", dhm_usage=True, setup="IFOV_on", backend=None, plane=None):
    """ Run the experiment.

    Parameters
    ----------
    absolute_center : Point2D
        Center of the experiment in µm.
    resin_dimension : list
        Edges of the resin drop in µm: [[right], [left], [near], [far]].
    ask_continue_box : bool
        Confirm every step in a message box.
    path : Path or str, optional
        Root folder; the data go into its subfolder ``power_z_pitch_lines``, without it into ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center, dhm_usage, setup)
    root, spec.name = script_output(
        path, Path(f".output/large_z_pitch_vs_power/power_z_pitch_linesv2_{datetime.datetime.now():%Y%m%d}"),
        "power_z_pitch_lines")
    (root / spec.name).mkdir(parents=True, exist_ok=True)
    logger = getLogger(logfile=root / spec.name / "console.log")

    # Resolved geometry, logged so console.log can be checked against the .pgm files
    resolved = spec.resolved()
    rows, cols = resolved.grid
    step = resolved.structure_size_um + resolved.padding_um
    pad_top = Z_B + BASE_HEIGHT
    n_base_layers = abs(round(BASE_HEIGHT / BASE_SLICE)) + 1
    logger.info(f"Grid {rows}x{cols} = {rows * cols} slots, pad {PAD_SIZE} um, "
                f"{cols * step - resolved.padding_um + 2 * resolved.margin_um:.0f} x "
                f"{rows * step - resolved.padding_um + 2 * resolved.margin_um:.0f} um footprint")
    logger.info(f"Pad {Z_B} -> {pad_top} um, {n_base_layers} layers at {BASE_HEIGHT / (n_base_layers - 1):.3f} um, "
                f"hatch {BASE_HATCH} um, power {BASE_POWER} mW (VELOCITY is inert on the IFOV path)")
    logger.info(f"Rows (+Y): power {POWERS} mW")
    logger.info("Columns (+X): pitch zipped with z offset")
    for j, (pitch, dz) in enumerate(zip(PITCHES, Z_OFFSETS)):
        logger.info(f"  col {j}: pitch {pitch:4.1f} um, z {dz:+.2f} um -> lines at {pad_top + dz:+.2f} um "
                    f"({_z_note(dz)})")
    if min(Z_OFFSETS) < 0:
        logger.warning(f"Columns with z offset < 0 are buried in the {BASE_HEIGHT} um pad and are optically "
                       f"invisible from above; read them by confocal cross-section.")
    # Announce the cost: a silent focus-detection phase of half an hour looks like a hang
    n_points = plane_points(spec)
    logger.info(f"Plane fit mode {PLANE_FIT_MODE.name}: {n_points} probe points, roughly "
                f"{n_points * SECONDS_PER_PLANE_POINT / 60:.0f} min.")

    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=backend is None)


if __name__ == '__main__':
    testprint(
        absolute_center=Point2D(X=1000, Y=22000),
        resin_dimension=[[900, 17500], [1000, 26700], [-3700, 22000], [5500, 22200]],
        ask_continue_box=True,
        objective="Zeiss 63x",
        user="Kailas",
        dhm_usage=False,
    )
