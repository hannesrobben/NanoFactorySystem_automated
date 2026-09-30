##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Dot rows on a base pad: power (rows) x dwell time (columns); inside each pad one z offset per dot row.

Described by ``experiment_spec()`` (T51); ``testprint()`` keeps the former call signature.
"""
import datetime
from pathlib import Path

from nanofactorysystem import getLogger
from nanofactorysystem.aerobasic.programs.drawings.dots.cell_dot_grid_1 import grid_shape
from nanofactorysystem.aerobasic.programs.drawings.dots.dot_rows_on_base import DotGridOnBase
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.experiment_spec import (CornerSpec, ExperimentSpec, StructureSpec, messagebox_confirm,
                                               run_experiment, script_output)
from nanofactorysystem.plane_fitting import PlaneFitMode

VELOCITY = 5000.0        # um/s   jump speed between dots (dots are stationary)
PAD_SIZE = 100.0         # um     base pad footprint = structure size per grid slot
PITCH = 15.0             # um     dot-to-dot spacing inside the pad -> 6 rows of 6
EDGE_MARGIN = 10.0       # um     clearance from outermost dot to pad edge
BASE_POWER = 0.5         # mW     fixed base power, decoupled from the swept dot power
BASE_HEIGHT = 4.0        # um     pad thickness: 2 um of overlap + 2 um standing in the resin
BASE_HATCH = 0.3         # um     pad hatch spacing
BASE_SLICE = 0.25        # um     pad layer height -> 17 layers, matches both printed runs
Z_B = -2.0               # um     pad bottom (pad top = Z_B + BASE_HEIGHT = +2.0)
DROP_DIRECTION = DropDirection.DOWN

PARAMETERS = {
    "power": [0.15, 0.2, 0.25, 0.3, 0.35, 0.4],  # mW
    "dwell_ms": [1, 5, 10, 20, 30, 40, 50],  # ms
    "dot_z_offset": [0, 0.5, 1.0, 1.5, 2.0, 2.5],  # um, one per dot row, bottom row (most negative Y) first
}
OBJECTIVES = {
    "Zeiss 20x": dict(fov_um=500.0, z_max_um=25700.0, margin_um=200.0, padding_um=100.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    "Zeiss 63x": dict(fov_um=150.0, z_max_um=25480.0, margin_um=200.0, padding_um=100.0,
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


def experiment_spec(objective="Zeiss 63x", absolute_center=Point2D(0, 0), dhm_usage=True,
                    setup="IFOV_on") -> ExperimentSpec:
    """ One row per power, one column per dwell time; the checks run before anything is printed. """

    if DROP_DIRECTION is not DropDirection.DOWN:
        raise ValueError(
            "This experiment requires DropDirection.DOWN. The reversed layer order is what makes "
            "the dot program run before the base, so the dots inherit the swept structure power "
            "while the base sets BASE_POWER itself. With UP the base would run first and leave "
            "BASE_POWER on the controller for every dot.")
    # Check here rather than letting DotGridOnBase raise after the plane fit
    n_side, extent = grid_shape(PAD_SIZE, PITCH, EDGE_MARGIN)
    dot_z_offsets = PARAMETERS["dot_z_offset"]
    if len(dot_z_offsets) != n_side:
        raise ValueError(
            f"dot_z_offset has {len(dot_z_offsets)} entries but PAD_SIZE {PAD_SIZE} um with "
            f"PITCH {PITCH} um and EDGE_MARGIN {EDGE_MARGIN} um gives {n_side} dot rows. "
            f"Pass exactly one offset per row, bottom row (most negative Y) first.")
    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    fov = OBJECTIVES[objective]["fov_um"]
    if PAD_SIZE > fov:
        raise ValueError(f"Pad {PAD_SIZE} um exceeds the {fov} um field of view.")
    if extent > fov:
        raise ValueError(f"Dot extent {extent} um exceeds the {fov} um IFOV field.")
    structures = [
        StructureSpec(
            f"dots_p{power}_t{dwell_ms}ms_zrows",
            DotGridOnBase(center=Point3D(0, 0, Z_B), cellsize=PAD_SIZE, dwell_s=dwell_ms / 1000.0, pitch=PITCH,
                          edge_margin=EDGE_MARGIN, dot_z_offset=dot_z_offsets, velocity=VELOCITY,
                          base_power=BASE_POWER, base_height=BASE_HEIGHT, base_hatch=BASE_HATCH,
                          base_slice=BASE_SLICE),
            power_mw=power, axes="XYZ", structure_type=StructureType.IFOV)
        for power in PARAMETERS["power"] for dwell_ms in PARAMETERS["dwell_ms"]]
    return ExperimentSpec(
        name="dots_row_z_offset", objective=objective, center=absolute_center,
        grid=(len(PARAMETERS["power"]), len(PARAMETERS["dwell_ms"])), structures=structures, setup=setup,
        drop_direction=DROP_DIRECTION, plane_fit_mode=PlaneFitMode.GRID, dhm_usage=dhm_usage,
        camera_capture=True, structure_size_um=PAD_SIZE, default_power_mw=0.7, low_speed_um_s=1000,
        high_speed_um_s=10_000, opl_start_um=350.0, sys_args=runtime_arguments(), **OBJECTIVES[objective])


def testprint(absolute_center: Point2D, resin_dimension: list, ask_continue_box=True, path=None,
              objective="Zeiss 63x", user="Hannes", dhm_usage=True, setup="IFOV_on", backend=None, plane=None):
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
        Root folder; the data go into its subfolder ``dots_row_z_offset``, without it into ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    """

    spec = experiment_spec(objective, absolute_center, dhm_usage, setup)
    root, spec.name = script_output(
        path, Path(f".output/cell_geometry/power_dwell_dotgrid_{datetime.datetime.now():%Y%m%d}"),
        "dots_row_z_offset")
    (root / spec.name).mkdir(parents=True, exist_ok=True)
    logger = getLogger(logfile=root / spec.name / "console.log")
    rows, cols = spec.grid
    n_side, extent = grid_shape(PAD_SIZE, PITCH, EDGE_MARGIN)
    logger.info(f"Grid {rows}x{cols} = {rows * cols} slots, {n_side}x{n_side} = {n_side ** 2} dots per slot "
                f"({extent} um extent), {rows * cols * n_side ** 2} dots total")
    pad_top = Z_B + BASE_HEIGHT
    n_base_layers = abs(round(BASE_HEIGHT / BASE_SLICE)) + 1
    logger.info(f"Pad {Z_B} -> {pad_top} um ({BASE_HEIGHT} um thick, {pad_top} um above the interface), "
                f"{n_base_layers} layers at {BASE_HEIGHT / (n_base_layers - 1):.3f} um; ")
    logger.info(f"  z swept WITHIN each pad, one offset per dot row, identical in all {rows * cols} slots. "
                f"Row 0 = most negative Y = printed first.")
    for i, offset in enumerate(PARAMETERS["dot_z_offset"]):
        note = "  <- coplanar with pad top, buried control row" if offset == 0 else ""
        logger.info(f"    row {i} (y {-extent / 2 + i * PITCH:+.1f} um in pad) -> offset {offset:+.2f} um, "
                    f"dots at z = {pad_top + offset:+.2f} um{note}")
    return run_experiment(spec, user=user, resin_edges=resin_dimension, path=root, backend=backend, plane=plane,
                          confirm=messagebox_confirm if ask_continue_box else None, show_plot=backend is None)


if __name__ == '__main__':
    testprint(
        absolute_center=Point2D(X=1000, Y=22000),
        resin_dimension=[[900, 17500], [1000, 26700], [-3700, 22000], [5500, 22200]],
        ask_continue_box=True,
        objective="Zeiss 63x",
        user="Hannes",
        dhm_usage=False,
    )
