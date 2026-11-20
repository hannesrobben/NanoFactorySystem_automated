##########################################################################
# Copyright (c) 2022-2026 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Focal points for an AI classifier: axial lines (z-lines) with camera images before and after (T36).

At random points inside the structure grid of an experiment, an axial line of length ``dz`` is exposed at
the substrate interface (the z-line program writes it centred on z: from z - dz/2 to z + dz/2), with the
same routine as the focus detection of the plane fit (``tools.focus.Focus.run``). Every point gives one
``FocusDetect`` container (.zdc) with the background, pre- and post-exposure images, the exposure data and
the result of the classic focus detection, as training data for a classifier. Afterwards the corner markers
and the QR code are printed, so the field can be found again.

Nothing here changes the system or the plane fitting: the script only calls the existing focus routine.
"""
import datetime
import json
from pathlib import Path
from typing import Optional

import numpy as np

from nanofactorysystem import getLogger
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D
from nanofactorysystem.experiment import Experiment
from nanofactorysystem.experiment_spec import CornerSpec, ExperimentSpec, messagebox_confirm
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.tools.focus import Focus

# --- Exposure parameters (N018: all variables before the functions) ------------------------------------
N_POINTS = 50                   # number of z-lines
MIN_DISTANCE_UM = (20.0, 20.0)  # minimal (x, y) distance between two lines; a point is rejected if it lies
                                # closer than this in x AND in y to an earlier point
DZ_VALUES_UM = [10.0]           # line lengths, used in turn; 0 exposes a dot (laser pulse of DURATION_S)
DZ_NOISE_UM = 0.5               # uniform noise +/- on every length, so that no two lines are equal (N020)
POWER_MW = 0.7                  # as the layer detection (tools/layer.py laserPower)
SPEED_UM_S = 200.0              # writing speed of the line (tools/layer.py stageSpeed)
DURATION_S = 0.2                # minimal exposure duration (tools/layer.py duration)
SEED: Optional[int] = None      # random seed of the point positions (None: new positions every run)

OBJECTIVES = {
    "Zeiss 20x": dict(fov_um=500.0, z_max_um=25700.0,
                      corner=CornerSpec(width_um=50.0, length_um=300.0, height_um=7.0, hatch_um=0.5, slice_um=0.75)),
    # zMax could possibly be up to 25550 µm
    "Zeiss 63x": dict(fov_um=150.0, z_max_um=25500.0,
                      corner=CornerSpec(width_um=30.0, length_um=120.0, height_um=7.0, hatch_um=0.3, slice_um=0.75)),
}


def runtime_arguments() -> dict:
    """ Runtime sections for the devices and detection tools of this experiment. """

    return {
        "attenuator": {"fitKind": "quadratic"},
        "sample": {"name": "#1", "substrate": "boro-silicate glass", "substrateThickness": 700.0,
                   "material": "SZ2080", "materialThickness": 75.0},
        "focus": {},
        "layer": {"beta": 0.7},
        "plane": {},
    }


def experiment_spec(objective="Zeiss 20x", absolute_center=Point2D(0, 0), dhm_usage=False) -> ExperimentSpec:
    """ The field of the z-lines: a 2 x 3 grid of FOV-sized cells with corner markers, no structures. """

    if objective not in OBJECTIVES:
        raise ValueError(f"No implemented objective {objective}! Possible objectives are 'Zeiss 20x' and 'Zeiss 63x'.")
    return ExperimentSpec(
        name="focal_point", objective=objective, center=absolute_center, grid=(2, 3), margin_um=10.0,
        padding_um=10.0, drop_direction=DropDirection.DOWN, plane_fit_mode=PlaneFitMode.CORNERS,
        dhm_usage=dhm_usage, camera_capture=True, default_power_mw=0.7, low_speed_um_s=1000, high_speed_um_s=5000,
        opl_start_um=3847.0, sys_args=runtime_arguments(), **OBJECTIVES[objective])


def random_points(n_points: int, min_distance, boundary, rng: np.random.Generator,
                  max_attempts: int = 1000) -> list[tuple[float, float]]:
    """ Random points inside a boundary with a minimal distance (rejection sampling).

    Parameters
    ----------
    n_points : int
        Number of points.
    min_distance : (float, float)
        A new point is rejected if it lies closer than ``min_distance[0]`` in
        x and closer than ``min_distance[1]`` in y to an earlier point.
    boundary : ((float, float), (float, float))
        ``((x_min, x_max), (y_min, y_max))`` in µm.
    rng : numpy.random.Generator
    max_attempts : int
        Attempts per point.

    Returns
    -------
    list of (x, y)

    Raises
    ------
    ValueError
        If not all points fit into the boundary.
    """

    (x_min, x_max), (y_min, y_max) = boundary
    points: list[tuple[float, float]] = []
    for index in range(n_points):
        for _ in range(max_attempts):
            x, y = float(rng.uniform(x_min, x_max)), float(rng.uniform(y_min, y_max))
            if all(abs(x - px) >= min_distance[0] or abs(y - py) >= min_distance[1] for px, py in points):
                points.append((x, y))
                break
        else:
            raise ValueError(f"Only {index} of {n_points} points with a distance of {min_distance} um fit into "
                             f"{boundary}; use fewer points or a smaller distance.")
    return points


def line_lengths(n_points: int, rng: np.random.Generator) -> list[float]:
    """ Line length of every point: ``DZ_VALUES_UM`` in turn plus ``DZ_NOISE_UM`` noise (never below 0). """

    lengths = [DZ_VALUES_UM[i % len(DZ_VALUES_UM)] for i in range(n_points)]
    return [max(0.0, dz + float(rng.uniform(-DZ_NOISE_UM, DZ_NOISE_UM))) if dz > 0 else 0.0 for dz in lengths]


def new_folder(root: Path) -> Path:
    """ A new, empty result folder below ``root`` (N019: earlier results are never overwritten). """

    folder = Path(root) / f"z_lines_{datetime.datetime.now():%Y%m%d-%H%M%S}"
    index = 1
    while folder.exists():
        folder = Path(root) / f"z_lines_{datetime.datetime.now():%Y%m%d-%H%M%S}_{index}"
        index += 1
    folder.mkdir(parents=True)
    return folder


def z_line_matrix(experiment: Experiment, folder: Path, *, seed: Optional[int] = SEED,
                  n_points: int = N_POINTS) -> dict:
    """ Expose the z-lines inside the structure grid and store one FocusDetect container per point.

    Parameters
    ----------
    experiment : Experiment
        Experiment with a plane fit.
    folder : Path
        Result folder (``point_<nnn>.zdc`` and ``focal_points.json``).
    seed : int, optional
        Random seed of positions and length noise; stored in the result.
    n_points : int

    Returns
    -------
    dict
        Content of ``focal_points.json``: parameters and one entry per point.
    """

    seed = seed if seed is not None else int(np.random.SeedSequence().entropy % 2 ** 32)
    rng = np.random.default_rng(seed)
    lower = np.minimum(experiment.rectangle_tl, experiment.rectangle_br) + experiment.margin
    upper = np.maximum(experiment.rectangle_tl, experiment.rectangle_br) - experiment.margin
    boundary = ((float(lower[0]), float(upper[0])), (float(lower[1]), float(upper[1])))
    points = random_points(n_points, MIN_DISTANCE_UM, boundary, rng)
    lengths = line_lengths(n_points, rng)

    # The routine of the focus detection: background image, z-line or dot, images before and after
    experiment.a3200.api.LINEAR(A=0.0, B=0.0, F=20)
    focus = Focus(experiment.system, experiment.log, **experiment.sys_args)
    result = {
        "experiment_uuid": experiment.qr_text, "objective": experiment.objective, "seed": seed,
        "boundary_um": boundary, "min_distance_um": list(MIN_DISTANCE_UM), "dz_values_um": DZ_VALUES_UM,
        "dz_noise_um": DZ_NOISE_UM, "power_mw": POWER_MW, "speed_um_s": SPEED_UM_S, "duration_s": DURATION_S,
        "z_camera_offset_um": focus["zCameraOffset"], "plane_fit": str(experiment.plane_fit_function),
        "line_position": "centred on the substrate interface z (z - dz/2 to z + dz/2)",
        "points": [],
    }
    for index, ((x, y), dz) in enumerate(zip(points, lengths), start=1):
        z = float(experiment.plane_fit_function(x, y))
        focus.run(x, y, z, dz, POWER_MW, SPEED_UM_S, DURATION_S)
        file = folder / f"point_{index:03d}.zdc"
        focus.container().write(str(file))
        result["points"].append({"index": index, "x_um": x, "y_um": y, "z_um": z, "dz_um": dz, "file": file.name,
                                 "status": focus.result.get("status"),
                                 "focus_offset_px": focus.result.get("focusOffset")})
        experiment.log.info(f"z-line {index}/{n_points} at ({x:.1f}, {y:.1f}, {z:.2f}) um, dz {dz:.2f} um: "
                            f"{focus.result.get('statusString', '')}")
        (folder / "focal_points.json").write_text(json.dumps(result, indent=2, default=str))
    return result


def focal_point_matrix_maker(absolute_center: Point2D, resin_dimension: list, ask_continue_box=False, path=None,
                             objective="Zeiss 20x", user="Hannes", dhm_usage=False, backend=None, plane=None,
                             seed: Optional[int] = SEED, n_points: int = N_POINTS) -> Path:
    """ Plane fit, z-lines with camera images, then the corner markers and the QR code.

    Parameters
    ----------
    absolute_center : Point2D
        Center of the field in µm.
    resin_dimension : list
        Edges of the resin drop in µm: [[right], [left], [near], [far]].
    ask_continue_box : bool
        Confirm every step in a message box.
    path : Path or str, optional
        Root folder; the data go into its subfolder ``focal_point``, without it into ``.output``.
    backend, plane : optional
        Dummy backend and known plane for a dry run.
    seed, n_points : optional
        Random seed and number of z-lines.

    Returns
    -------
    Path
        The folder with the z-line results.
    """

    spec = experiment_spec(objective, absolute_center, dhm_usage)
    root = Path(path) if path is not None else Path(f".output/focal_point/{datetime.datetime.now():%Y%m%d}")
    folder = root / spec.name
    folder.mkdir(parents=True, exist_ok=True)
    logger = getLogger(logfile=folder / "console.log")
    ask = (lambda question: messagebox_confirm(question)) if ask_continue_box else (lambda question: True)

    arguments = spec.experiment_arguments(user=user, resin_edges=resin_dimension, logger=logger, backend=backend,
                                          path=folder)
    with Experiment(**arguments) as experiment:
        experiment.plot_experiment(show=backend is None)
        if not ask("Run plane fitting?"):
            return folder
        experiment.plane_fit(plane=plane)
        if dhm_usage:
            if not ask("Run OPL motor scan?"):
                return folder
            experiment.opl_scan(m0=spec.opl_start_um)
        if not ask(f"Expose {n_points} z-lines?"):
            return folder
        results = new_folder(folder)
        z_line_matrix(experiment, results, seed=seed, n_points=n_points)
        # Corner markers and QR code, so the field can be found again
        experiment.build_programs()
        if ask("Print the corner markers and the QR code?"):
            experiment.print_experiment()
    return results


if __name__ == '__main__':
    focal_point_matrix_maker(
        absolute_center=Point2D(X=1000, Y=22000),
        resin_dimension=[[900, 17500], [1000, 26700], [-3700, 22000], [5500, 22200]],
        ask_continue_box=True,
        objective="Zeiss 20x",
        user="Hannes",
    )
