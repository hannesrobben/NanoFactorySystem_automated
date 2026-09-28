"""Synthetic calibration file for the laser attenuator."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from nanofactorysystem.backends.dummy.world import SimulatedWorld


def write_calibration_file(path: str | Path, world: SimulatedWorld, points: int = 101) -> Path:
    """ Write a binary attenuator calibration file.

    The format is the one read by ``devices.Attenuator``: pairs of
    little-endian doubles (attenuator value 0..10, laser power in mW). The
    power follows ``world.power_of``.

    Parameters
    ----------
    path : str or Path
        Output file.
    world : SimulatedWorld
        Provides the power curve.
    points : int
        Number of calibration points.

    Returns
    -------
    Path
        The written file.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.linspace(0.0, 10.0, points)
    data = []
    for value in values:
        data += [float(value), world.power_of(value)]
    path.write_bytes(struct.pack("<" + "d" * len(data), *data))
    return path
