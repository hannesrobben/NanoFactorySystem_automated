"""Dummy backend: simulated Laser Nanofactory hardware.

Example
-------
>>> from nanofactorysystem import System
>>> from nanofactorysystem.backends import DummyBackend
>>> backend = DummyBackend(seed=1)
>>> with System("Test", "Zeiss 20x", backend=backend, controller={"zMax": 25000.0}) as system:  # doctest: +SKIP
...     system.moveabs(x=100.0)
>>> backend.calllog.commands()  # doctest: +SKIP
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from nanofactorysystem.backends.dummy.a3200 import FakeA3200Transport
from nanofactorysystem.backends.dummy.attenuator import write_calibration_file
from nanofactorysystem.backends.dummy.calllog import CallLog, CallRecord
from nanofactorysystem.backends.dummy.camera import DummyCameraDriver
from nanofactorysystem.backends.dummy.dhm import DummyDhmClient
from nanofactorysystem.backends.dummy.world import Exposure, SampleModel, SimulatedWorld, VirtualClock

__all__ = [
    "DummyBackend", "SimulatedWorld", "SampleModel", "Exposure", "VirtualClock", "CallLog", "CallRecord",
    "FakeA3200Transport", "DummyCameraDriver", "DummyDhmClient", "write_calibration_file",
]


class DummyBackend:
    """ Backend with simulated devices sharing one :class:`SimulatedWorld`.

    Parameters
    ----------
    seed : int
        Seed of the image noise. Ignored if ``world`` is given.
    world : SimulatedWorld, optional
        Shared state to use; a new one is created by default.
    workdir : str or Path, optional
        Directory for the synthetic calibration file and for program files
        written by the controller classes. Default: a new temporary
        directory.
    strict : bool
        Answer unknown controller commands with INVALID instead of success.
    decimal_comma : bool
        Let the controller format numbers with a decimal comma.
    camera_size : tuple of int
        Sensor width and height of the simulated camera.

    Attributes
    ----------
    transport : FakeA3200Transport
        Simulated controller connection shared by both controller facades.
    """

    name = "dummy"

    def __init__(self, seed: int = 0, *, world: Optional[SimulatedWorld] = None,
                 workdir: Optional[str | Path] = None, strict: bool = False, decimal_comma: bool = False,
                 camera_size: tuple[int, int] = (1280, 1024)):
        self.world = world if world is not None else SimulatedWorld(seed=seed)
        if workdir is None:
            workdir = tempfile.mkdtemp(prefix="nanofactory_dummy_")
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.camera_size = camera_size
        self.transport = FakeA3200Transport(self.world, strict=strict, decimal_comma=decimal_comma)

    def __repr__(self) -> str:
        return f"DummyBackend(seed={self.world.seed}, workdir={str(self.workdir)!r})"

    @property
    def calllog(self) -> CallLog:
        """ Call log of all simulated devices. """

        return self.world.calllog

    def controller_transport(self) -> FakeA3200Transport:
        """ Return the shared simulated controller connection. """

        return self.transport

    def camera_driver(self, product: Optional[str], device_id: Optional[Any]) -> DummyCameraDriver:
        """ Return a new simulated camera. """

        width, height = self.camera_size
        return DummyCameraDriver(self.world, width=width, height=height)

    def dhm_driver(self, objective: dict[str, Any]) -> DummyDhmClient:
        """ Return a new simulated DHM client with the objective's configuration selected. """

        return DummyDhmClient(self.world, config_id=int(objective.get("dhmId", 178)))

    def attenuator_args(self) -> dict[str, Any]:
        """ Write the synthetic calibration file and return its path as attenuator argument. """

        path = write_calibration_file(self.workdir / "calibration.dat", self.world)
        return {"calibrationFile": str(path)}

    def program_dir(self) -> Path:
        """ Return the directory for program files. """

        return self.workdir
