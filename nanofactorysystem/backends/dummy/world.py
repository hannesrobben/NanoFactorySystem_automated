"""Shared state of all simulated devices of the dummy backend."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from nanofactorysystem.backends.dummy.calllog import CallLog
from nanofactorysystem.devices.coordinate_system import Plane

AXES = ("X", "Y", "Z", "A", "B")


class VirtualClock:
    """ Deterministic clock in seconds, advanced only by simulated actions.

    Parameters
    ----------
    start : float
        Start time in seconds.
    """

    def __init__(self, start: float = 0.0):
        self.now = float(start)

    def advance(self, dt: float) -> float:
        """ Advance the clock.

        Parameters
        ----------
        dt : float
            Time step in seconds. Negative values are ignored.

        Returns
        -------
        float
            The new time.
        """

        if dt > 0:
            self.now += float(dt)
        return self.now

    def sleep(self, dt: float) -> None:
        """ Drop-in replacement for :func:`time.sleep` that advances the clock. """

        self.advance(dt)


@dataclass
class SampleModel:
    """ Known substrate surface of the simulated sample.

    The surface is ``z(x, y) = c + a*x + b*y`` with all values in µm. It is
    not used to simulate plane detection; it is the plane that a dry run
    passes to ``Experiment.plane_fit(plane=...)``.

    Attributes
    ----------
    c : float
        Height at x = y = 0 in µm.
    a : float
        Slope in x direction.
    b : float
        Slope in y direction.
    """

    c: float = 20000.0
    a: float = 0.0
    b: float = 0.0

    def z(self, x: float, y: float) -> float:
        """ Return the surface height in µm at the given position in µm. """

        return self.c + self.a * x + self.b * y

    def plane(self) -> Plane:
        """ Return the surface as a z function for coordinate systems.

        Returns
        -------
        Plane
            Plane with parameters ``[a, b, c]`` in µm.
        """

        return Plane(np.array([self.a, self.b, self.c], dtype=float))


@dataclass(frozen=True)
class Exposure:
    """ Straight segment written with the laser switched on.

    Coordinates are stage coordinates in mm (controller units).
    """

    start: tuple[float, float, float]
    end: tuple[float, float, float]
    power: float
    t: float


@dataclass
class TaskSim:
    """ Simulated state of one controller task. """

    task_id: int
    state: int = 2  # TaskState.idle
    program_path: Optional[str] = None
    line_number: int = 0
    error_code: int = 0
    error_location: int = 0
    running_polls: int = 0  # TaskState queries answered with "running" before the actual state


@dataclass
class SimulatedWorld:
    """ State shared by all simulated devices of one dummy backend.

    Parameters
    ----------
    seed : int
        Seed of the random number generator used for image noise.
    stage : dict, optional
        Initial positions of the axes X, Y, Z, A, B in mm.
    sample : SampleModel, optional
        Known substrate surface.
    max_power : float
        Laser power in mW at attenuator value 10 of the synthetic calibration.
    opl_optimum : float
        DHM OPL motor position in µm with maximum interference contrast.

    Attributes
    ----------
    rng : numpy.random.Generator
        Seeded generator; the only source of randomness.
    clock : VirtualClock
        Deterministic simulated time.
    calllog : CallLog
        Every call to any simulated device.
    exposures : list of Exposure
        Segments written with the laser on.
    """

    seed: int = 0
    stage: dict = field(default_factory=lambda: {"X": 0.0, "Y": 0.0, "Z": 20.0, "A": 0.0, "B": 0.0})
    sample: SampleModel = field(default_factory=SampleModel)
    max_power: float = 20.0
    opl_optimum: float = 1000.0

    def __post_init__(self):
        self.rng = np.random.Generator(np.random.PCG64(self.seed))
        self.clock = VirtualClock()
        self.calllog = CallLog()
        self.stage = {axis: float(self.stage.get(axis, 0.0)) for axis in AXES}
        self.absolute = True
        self.enabled = set(AXES)
        self.laser_on = False
        self.attenuator_value = 0.0
        self.ifov = False
        self.variables: dict[str, float] = {}
        self.exposures: list[Exposure] = []
        self.tasks: dict[int, TaskSim] = {}

    # Laser

    def power_of(self, value: float) -> float:
        """ Return the laser power in mW for an attenuator value (0..10).

        This is the curve used for the synthetic calibration file:
        ``P = max_power * (value / 10)**2``.
        """

        value = min(max(float(value), 0.0), 10.0)
        return self.max_power * (value / 10.0) ** 2

    @property
    def power(self) -> float:
        """ Current laser power in mW. """

        return self.power_of(self.attenuator_value)

    # Motion

    def move(self, target: dict[str, float], feed: Optional[float] = None, *, incremental: Optional[bool] = None) -> None:
        """ Move the stage instantly and record an exposure if the laser is on.

        Parameters
        ----------
        target : dict
            Axis name → position (absolute) or distance (incremental) in mm.
        feed : float, optional
            Feed rate in mm/s, used to advance the virtual clock.
        incremental : bool, optional
            Override of the current programming mode.
        """

        if incremental is None:
            incremental = not self.absolute
        start = tuple(self.stage[a] for a in "XYZ")
        for axis, value in target.items():
            axis = axis.upper()
            if axis not in self.stage:
                continue
            self.stage[axis] = self.stage[axis] + value if incremental else float(value)
        end = tuple(self.stage[a] for a in "XYZ")

        distance = math.dist(start, end)
        if feed:
            self.clock.advance(distance / abs(feed))
        if self.laser_on and distance > 0:
            self.exposures.append(Exposure(start, end, self.power, self.clock.now))

    def task(self, task_id: int) -> TaskSim:
        """ Return the simulated task, creating it if necessary. """

        if task_id not in self.tasks:
            self.tasks[task_id] = TaskSim(task_id)
        return self.tasks[task_id]
