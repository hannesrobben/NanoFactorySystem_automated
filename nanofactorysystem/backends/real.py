"""Backend for the real Laser Nanofactory hardware (the default)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


class RealBackend:
    """ Creates exactly the hardware connections the package used before.

    Every factory method returns None, which tells the device classes to
    open their hardware themselves (TCP socket, ``CameraDevice``,
    ``DhmClient``, configured calibration file, current working directory).
    """

    name = "real"

    def controller_transport(self) -> Optional[Any]:
        """ Return None: ``A3200`` opens its own TCP socket. """

        return None

    def camera_driver(self, product: Optional[str], device_id: Optional[Any]) -> Optional[Any]:
        """ Return None: ``Camera`` opens the MatrixVision device. """

        return None

    def dhm_driver(self, objective: dict[str, Any]) -> Optional[Any]:
        """ Return None: ``Dhm`` connects to the DHM server. """

        return None

    def attenuator_args(self) -> dict[str, Any]:
        """ Return no overrides: the configured calibration file is used. """

        return {}

    def program_dir(self) -> Optional[Path]:
        """ Return None: program files go to the current working directory. """

        return None

    def restart_ascii_interface(self) -> str:
        """ Terminate ``A3200AsciiInterface.exe`` for recovery level R1 (T133); the A3200 software restarts it. """

        from nanofactorysystem.devices.aerotech.health import terminate_ascii_interface
        return terminate_ascii_interface()

    def program_loader(self, dll: Optional[str] = None):
        """ Return a :class:`LibraryLoader` (A3200 C library, T129); raises if the library is not usable. """

        from nanofactorysystem.devices.aerotech.library import DEFAULT_DLL
        from nanofactorysystem.devices.aerotech.loader import LibraryLoader
        return LibraryLoader(dll or DEFAULT_DLL)

    def __repr__(self) -> str:
        return "RealBackend()"
