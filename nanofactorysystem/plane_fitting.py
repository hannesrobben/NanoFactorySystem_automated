##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Plane fitting of the substrate surface: sample points, measurement and checks.

The functions work without an :class:`~nanofactorysystem.experiment.Experiment`,
so that a single plane fit can be run from a script (N079); ``Experiment.plane_fit``
uses them as well. The fitting algorithms (``tools.plane.Plane``,
``PlaneFit.from_points``) are unchanged.
"""
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
from scidatacontainer import Container

from .devices.coordinate_system import DropDirection, PlaneFit, ZFunction
from .runtime import mkdir


class PlaneFitMode(Enum):
    """ Where the substrate surface is measured, relative to the structure grid.

    The points lie on the grid lines, i.e. half a padding before, between and
    after the structure cells; for ``rows × cols`` cells there are
    ``rows + 1`` horizontal and ``cols + 1`` vertical grid lines.

    Members
    -------
    GRID (0)
        Every crossing of the grid lines: ``(rows + 1) × (cols + 1)`` points,
        between all structures and around them.
    CORNERS (1)
        The four outer corners of the grid.
    BORDER (2)
        The crossings on the border of the grid: ``2 × (rows + cols)`` points
        (``GRID`` without the inner points).
    """

    GRID = 0
    CORNERS = 1
    BORDER = 2

    @classmethod
    def parse(cls, value) -> "PlaneFitMode":
        """ Return the mode for a member, its name (any case) or its integer value (older files). """

        if isinstance(value, cls):
            return value
        if isinstance(value, str) and not value.isdigit():
            return cls[value.upper()]
        return cls(int(value))


def sample_points(mode: PlaneFitMode, top_left, margin: float, padding: float, structure_size: float,
                  grid) -> list[tuple[float, float]]:
    """ Return the sample points of a plane fit in µm.

    Parameters
    ----------
    mode : PlaneFitMode or int or str
        Where to measure.
    top_left : sequence of float
        (x, y) of the top-left corner of the experiment rectangle.
    margin, padding, structure_size : float
        Layout of the experiment in µm (margin around the grid, gap between
        cells, cell size).
    grid : sequence of int
        (rows, cols).

    Returns
    -------
    list of (float, float)
    """

    mode = PlaneFitMode.parse(mode)
    rows, cols = int(grid[0]), int(grid[1])
    pitch = structure_size + padding
    x0 = float(top_left[0]) + margin - 0.5 * padding
    y0 = float(top_left[1]) + margin - 0.5 * padding
    # rows + 1 and cols + 1 grid lines: before, between and after the cells (N078)
    crossings = [(i, j) for i in range(rows + 1) for j in range(cols + 1)]
    if mode == PlaneFitMode.CORNERS:
        crossings = [(0, 0), (rows, 0), (0, cols), (rows, cols)]
    elif mode == PlaneFitMode.BORDER:
        crossings = [(i, j) for i, j in crossings if i in (0, rows) or j in (0, cols)]
    return [(x0 + j * pitch, y0 + i * pitch) for i, j in crossings]


def measure_plane(system, points, drop_direction: DropDirection, path: Path, logger=None, *,
                  sys_args: Optional[dict] = None, force: bool = False) -> tuple[PlaneFit, Container, str]:
    """ Measure the substrate surface at the given points and fit a plane.

    The resin interfaces are detected at every point with
    :class:`~nanofactorysystem.tools.plane.Plane`; the plane is fitted through
    the "low" interface points for a drop facing down and through the "high"
    ones for a drop facing up. The measurement is written to
    ``<path>/plane.zdc`` (plus the background image ``back.zdc`` and the layer
    detections). An existing ``plane.zdc`` is loaded instead unless ``force``.

    Parameters
    ----------
    system : System
        Open system.
    points : list of (float, float)
        Sample points in µm, e.g. from :func:`sample_points`.
    drop_direction : DropDirection
    path : Path
        Folder for the measurement files.
    logger : logging.Logger, optional
    sys_args : dict, optional
        Runtime arguments (sections ``layer``, ``focus``, ``plane``, …) for the
        detection tools.
    force : bool
        Measure again although ``plane.zdc`` exists.

    Returns
    -------
    tuple
        The fitted ``PlaneFit``, the plane container and the source
        (``"measured"`` or ``"loaded"``).
    """

    from .tools.plane import Plane

    log = logger or logging.getLogger(__name__)
    path = Path(path)
    mkdir(path, clean=False)
    plane_dc_path = path / "plane.zdc"
    if not force and plane_dc_path.exists():
        log.info("Load plane detection results...")
        dc = Container(file=str(plane_dc_path))
        source = "loaded"
    else:
        # The 63x objective scans from z0 upwards only
        if system.objective["magnification"] == 63.0:
            zlo, zup = system.z0, None
        else:
            zlo = zup = system.z0
        plane = Plane(zlo, zup, system, log, **(sys_args or {}))

        log.info("Store background image...")
        plane.layer.focus.imgBack.write(str(path / "back.zdc"))

        log.info("Run plane detection...")
        for x, y in points:
            plane.run(x, y, path=path)

        log.info("Store plane detection results...")
        dc = plane.container()
        dc.write(str(plane_dc_path))
        source = "measured"

    interface = interface_for(drop_direction)
    fit = PlaneFit.from_points(np.asarray(dc["meas/result.json"][interface]["points"]))
    log.info(str(fit))
    return fit, dc, source


def interface_for(drop_direction: DropDirection) -> str:
    """ Interface of the resin layer on the substrate: ``"low"`` for a drop facing down, else ``"high"``. """

    return "low" if drop_direction == DropDirection.DOWN else "high"


def structure_tilt(z_function: ZFunction, center, size: float) -> tuple[float, float, float]:
    """ Height difference of the substrate under a square structure.

    Parameters
    ----------
    z_function : ZFunction
        Substrate surface.
    center : sequence of float
        (x, y) of the structure center in µm.
    size : float
        Edge length of the structure in µm.

    Returns
    -------
    tuple of float
        (deviation, z_min, z_max) of the surface at the four corners in µm.
    """

    x, y = float(center[0]), float(center[1])
    half = 0.5 * size
    z = [float(z_function(x + dx, y + dy)) for dx in (-half, half) for dy in (-half, half)]
    return max(z) - min(z), min(z), max(z)
