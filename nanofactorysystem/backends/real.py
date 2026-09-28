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

    def __repr__(self) -> str:
        return "RealBackend()"
