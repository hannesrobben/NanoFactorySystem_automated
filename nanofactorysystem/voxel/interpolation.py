##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Interpolation of one voxel quantity (width or height) between measurements (design §4).

1. Exact hit: mean of the measurements at the same power and velocity.
2. 2-D linear interpolation in (ln P, ln v) on the Delaunay triangulation,
   only inside the convex hull and with at least ``min_points`` points that
   are not collinear.
3. For collinear points: 1-D linear interpolation over ln(P²/v), only for a
   query on the measured line and within the measured dose range.
4. Otherwise None; there is no extrapolation.
"""
from typing import Optional

import numpy as np

REL_TOLERANCE = 1e-6  # same power/velocity for an exact hit
LINE_TOLERANCE = 1e-6  # distance in (ln P, ln v) of a query from a line of collinear points


def average_duplicates(power, velocity, value, weight) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """ Merge measurements at the same power and velocity into their weighted mean.

    Returns
    -------
    tuple of ndarray
        power, velocity, value and summed weight of the distinct points.
    """

    points: list[list[float]] = []
    for p, v, x, w in zip(power, velocity, value, weight):
        for point in points:
            if np.isclose(point[0], p, rtol=REL_TOLERANCE) and np.isclose(point[1], v, rtol=REL_TOLERANCE):
                point[2] += x * w
                point[3] += w
                break
        else:
            points.append([p, v, x * w, w])
    data = np.array(points, dtype=float).reshape(-1, 4)
    return data[:, 0], data[:, 1], data[:, 2] / data[:, 3], data[:, 3]


def _collinear(coords: np.ndarray) -> bool:
    if len(coords) < 3:
        return True
    singular = np.linalg.svd(coords - coords.mean(axis=0), compute_uv=False)
    return singular[1] <= 1e-9 * max(singular[0], 1.0)


def interpolate(power, velocity, value, weight, query_power: float, query_velocity: float, *,
                min_points: int = 3, min_points_1d: int = 2) -> tuple[Optional[float], str, int]:
    """ Interpolate one quantity at (query_power, query_velocity).

    Parameters
    ----------
    power, velocity, value, weight : sequence of float
        Measurements (weight: number of lines of each measurement).
    query_power, query_velocity : float
        Where the value is wanted.
    min_points : int
        Minimum number of distinct points for the 2-D interpolation.
    min_points_1d : int
        Minimum number of distinct doses for the 1-D dose fallback.

    Returns
    -------
    tuple
        (value or None, method, number of distinct points used); method is
        ``"exact"``, ``"interpolated-2d"``, ``"interpolated-dose"`` or ``""``.
    """

    if len(power) == 0:
        return None, "", 0
    power, velocity, value, weight = average_duplicates(power, velocity, value, weight)

    # 1. Exact hit
    same = np.isclose(power, query_power, rtol=REL_TOLERANCE) & np.isclose(velocity, query_velocity,
                                                                            rtol=REL_TOLERANCE)
    if np.any(same):
        return float(value[same][0]), "exact", 1

    coords = np.column_stack((np.log(power), np.log(velocity)))
    query = np.array([np.log(query_power), np.log(query_velocity)])

    # 2. 2-D interpolation inside the convex hull
    if not _collinear(coords):
        if len(coords) < min_points:
            return None, "", 0
        from scipy.interpolate import LinearNDInterpolator
        result = float(LinearNDInterpolator(coords, value)(query[None, :])[0])
        if np.isnan(result):
            return None, "", 0  # outside the convex hull
        return result, "interpolated-2d", len(coords)

    # 3. 1-D fallback over the dose for collinear points, only on their line
    if len(coords) >= 2:
        direction = coords[-1] - coords[0]
        for other in coords[1:]:
            if np.linalg.norm(other - coords[0]) > np.linalg.norm(direction):
                direction = other - coords[0]
        direction = direction / np.linalg.norm(direction)
        offset = query - coords[0]
        distance = abs(offset[0] * direction[1] - offset[1] * direction[0])
        if distance > LINE_TOLERANCE:
            return None, "", 0
    dose = 2 * np.log(power) - np.log(velocity)
    order = np.argsort(dose)
    dose, sorted_value = dose[order], value[order]
    if len(np.unique(dose)) < min_points_1d:
        return None, "", 0
    query_dose = 2 * np.log(query_power) - np.log(query_velocity)
    if not dose[0] <= query_dose <= dose[-1]:
        return None, "", 0
    return float(np.interp(query_dose, dose, sorted_value)), "interpolated-dose", len(dose)
