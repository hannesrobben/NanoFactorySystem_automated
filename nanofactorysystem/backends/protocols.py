"""Protocols of the device roles and of the hardware seams.

*Role* protocols describe what ``System``, ``Experiment`` and ``tools`` use
from a device facade. *Seam* protocols describe what a backend has to
provide so that the facades can run on it. Both are derived from the
call sites in the package (see ``docs/design/DUMMY_BACKEND.md``, §3).
"""
from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

import numpy as np


# Seams


@runtime_checkable
class ControllerTransport(Protocol):
    """ Socket-like connection to the A3200 ASCII command interface. """

    def connect(self, address: tuple[str, int]) -> None: ...

    def send(self, data: bytes) -> int: ...

    def recv(self, bufsize: int) -> bytes: ...

    def settimeout(self, value: Optional[float]) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class CameraDriver(Protocol):
    """ Camera driver, replaces ``camera.CameraDevice``. """

    opened: bool

    def __getitem__(self, key: str) -> Any: ...

    def __setitem__(self, key: str, value: Any) -> None: ...

    def keys(self) -> list[str]: ...

    def property(self, key: str) -> Any: ...

    def getimage(self) -> np.ndarray: ...

    def close(self) -> None: ...


@runtime_checkable
class DhmDriver(Protocol):
    """ DHM client, replaces ``dhm.DhmClient``.

    Besides these methods, the attributes of ``DhmClient._commands``
    (``ConfigList``, ``Config``, ``CameraImage``, ``CameraShutter``,
    ``MotorPos``, ...) must be readable, and writeable where the real
    client has a set command.
    """

    def set_keys(self) -> list[str]: ...

    def keys(self) -> list[str]: ...

    def parameters(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


# Roles


@runtime_checkable
class LegacyMotionController(Protocol):
    """ Role of ``devices.A3200`` as used by System, tools and Experiment. """

    socket: Any
    attenuator: Any

    def __getitem__(self, key: str) -> Any: ...

    def parameters(self) -> dict[str, Any]: ...

    def moveabs(self, speed: float, **axes: float) -> None: ...

    def position(self, axes: str) -> Any: ...

    def wait(self, axes: str, pause: Optional[float] = None) -> None: ...

    def power(self, power: float) -> None: ...

    def laseron(self, power: float) -> None: ...

    def laseroff(self) -> None: ...

    def pulse(self, power: float, duration: float) -> None: ...

    def init_zline(self, fn: Optional[str] = None) -> Optional[int]: ...

    def zline(self, power: float, fast: float, slow: float, dz: float) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class TaskController(Protocol):
    """ Role of ``devices.aerotech.Aerotech3200`` as used by Experiment.

    ``api`` is an ``AerotechAsciiInterface`` (``LINEAR``, ``AXISSTATUS``,
    ``STATUS``, ``PROGRAM_*``, ``send``, ``__call__``).
    """

    api: Any

    @property
    def xyz(self) -> Any: ...

    def run_program_as_task(self, program: PathLike | Any, *, task_id: Optional[int] = None,
                            program_ready_timeout: float = 10,
                            program_start_running_timeout: float = 10) -> Any: ...

    def save_log(self, folder: Path | str = ".") -> str: ...

    def connect(self) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class AttenuatorRole(Protocol):
    """ Role of ``devices.Attenuator``. """

    data: np.ndarray

    def ptoa(self, power: float) -> float: ...

    def atop(self, value: float) -> float: ...

    def __getitem__(self, key: str) -> Any: ...

    def parameters(self) -> dict[str, Any]: ...


@runtime_checkable
class CameraRole(Protocol):
    """ Role of ``devices.Camera`` as used by System, tools and Experiment. """

    opened: bool

    def getimage(self) -> np.ndarray: ...

    def optexpose(self, level: int = 127) -> Any: ...

    def container(self, loc=None, config=None, **kwargs) -> Any: ...

    def parameters(self) -> dict[str, Any]: ...

    def __setitem__(self, key: str, value: Any) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class DhmRole(Protocol):
    """ Role of ``devices.Dhm`` as used by System and Experiment. """

    device: Any
    opened: bool

    def getimage(self, opt: bool = True) -> Any: ...

    def motorscan(self, m0: Optional[float] = None) -> float: ...

    def container(self, opt=True, loc=None, config=None, image_count=0, **kwargs) -> Any: ...

    def parameters(self) -> dict[str, Any]: ...

    def close(self) -> None: ...
