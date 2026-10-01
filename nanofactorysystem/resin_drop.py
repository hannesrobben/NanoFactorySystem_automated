##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Outline of the resin drop from its four edge points (T62).

The drop is described by an axis-parallel ellipse through the four edge
points measured by hand (right, left, near, far; maintainer decision
2026-10-01). Experiment areas are checked against it instead of against the
bounding box of the points. Automatic detection of the outline is F9; for
dip-in there is no drop boundary and no check (F8).
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ellipse:
    """ Axis-parallel ellipse ((x - cx) / a)^2 + ((y - cy) / b)^2 <= 1, in µm. """

    cx: float
    cy: float
    a: float
    b: float

    def contains(self, points, tolerance: float = 1e-9) -> np.ndarray:
        """ True for every (x, y) point on or inside the ellipse. """

        points = np.atleast_2d(np.asarray(points, dtype=float))
        value = ((points[:, 0] - self.cx) / self.a) ** 2 + ((points[:, 1] - self.cy) / self.b) ** 2
        return value <= 1 + tolerance


def ellipse_through(edges) -> Ellipse:
    """ The axis-parallel ellipse through four edge points of a resin drop.

    Solves ``A x^2 + C y^2 + D x + E y = 1`` for the four points. If the
    points do not define an ellipse (e.g. three on a line, or a hyperbola
    through them), the ellipse inscribed in their bounding box is used and a
    warning is logged.

    Parameters
    ----------
    edges : sequence of (x, y)
        Four edge points in µm.

    Returns
    -------
    Ellipse
    """

    points = np.asarray(edges, dtype=float)
    if points.shape != (4, 2):
        raise ValueError(f"Four edge points (x, y) are needed for the drop outline, got shape {points.shape}")
    x, y = points[:, 0], points[:, 1]
    # Shift to the bounding-box center for a well-conditioned system
    x0, y0 = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
    u, v = x - x0, y - y0
    try:
        A, C, D, E = np.linalg.solve(np.column_stack([u ** 2, v ** 2, u, v]), np.ones(4))
        if A > 0 and C > 0:
            cu, cv = -D / (2 * A), -E / (2 * C)
            scale = 1 + A * cu ** 2 + C * cv ** 2
            return Ellipse(float(x0 + cu), float(y0 + cv), float(np.sqrt(scale / A)), float(np.sqrt(scale / C)))
    except np.linalg.LinAlgError:
        pass
    log.warning("The edge points %s define no ellipse; the ellipse inscribed in their bounding box is used",
                points.tolist())
    return Ellipse(float(x0), float(y0), float((x.max() - x.min()) / 2), float((y.max() - y.min()) / 2))


def has_drop_boundary(drop_direction) -> bool:
    """ False for dip-in (no drop boundary, F8), else True. """

    return getattr(drop_direction, "name", "") != "DIP_IN"


def rectangle_inside(ellipse: Ellipse, lower, upper) -> bool:
    """ True if the axis-parallel rectangle ``lower``–``upper`` lies inside the ellipse (all four corners). """

    (x0, y0), (x1, y1) = lower, upper
    return bool(np.all(ellipse.contains([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])))


def drop_outline(edges) -> Optional[Ellipse]:
    """ The ellipse for four edge points, None for fewer points (only a bounding box can be used then). """

    if edges is None or len(edges) != 4:
        return None
    return ellipse_through(edges)
