"""Simulated MatrixVision camera driver."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from nanofactorysystem.backends.dummy.world import SimulatedWorld


@dataclass(frozen=True)
class PropertyInfo:
    """ Value range of a camera property, like ``camera.Property``. """

    minValue: float
    maxValue: float
    choices: Optional[tuple] = None


class DummyCameraDriver:
    """ Drop-in replacement for ``nanofactorysystem.camera.CameraDevice``.

    Images have a flat background whose level is proportional to the
    exposure time (127 at ``reference_exposure``), clipped to 0..255, plus
    seeded Gaussian noise. They contain no exposure spots.

    Parameters
    ----------
    world : SimulatedWorld
        Shared state; provides the random generator, clock and call log.
    width, height : int
        Sensor size in pixels.
    noise_sigma : float
        Standard deviation of the image noise in counts.
    reference_exposure : float
        Exposure time in µs that yields a mean value of 127.
    """

    _keys = ("family", "product", "serial", "deviceID", "Width", "Height", "OffsetX", "OffsetY",
             "AcquisitionMode", "ExposureMode", "ExposureTime", "ExposureAuto", "mvGainMode",
             "GainSelector", "Gain", "GainAuto")

    def __init__(self, world: SimulatedWorld, *, width: int = 1280, height: int = 1024,
                 noise_sigma: float = 2.0, reference_exposure: float = 20000.0):
        self.world = world
        self.sensor = (int(width), int(height))
        self.noise_sigma = float(noise_sigma)
        self.reference_exposure = float(reference_exposure)
        self.opened = True
        self._values: dict[str, Any] = {
            "family": "mvBlueFOX3 (simulated)",
            "product": "DummyCamera",
            "serial": "SIM00001",
            "deviceID": 0,
            "Width": int(width),
            "Height": int(height),
            "OffsetX": 0,
            "OffsetY": 0,
            "AcquisitionMode": "Continuous",
            "ExposureMode": "Timed",
            "ExposureTime": 20000.0,
            "ExposureAuto": 0,
            "mvGainMode": "Default",
            "GainSelector": "AnalogAll",
            "Gain": 0.0,
            "GainAuto": 0,
        }
        self._ranges = {
            "Width": PropertyInfo(8, width),
            "Height": PropertyInfo(8, height),
            "OffsetX": PropertyInfo(0, width - 8),
            "OffsetY": PropertyInfo(0, height - 8),
            "ExposureTime": PropertyInfo(10.0, 1_000_000.0),
            "Gain": PropertyInfo(0.0, 24.0),
        }

    def __str__(self) -> str:
        return f"{self._values['family']} {self._values['product']} (S/N {self._values['serial']})"

    def _log(self, call: str, args: tuple = (), result: Any = None) -> None:
        self.world.calllog.record("camera", call, args, result, self.world.clock.now)

    def keys(self) -> list[str]:
        """ Return all property names. """

        return list(self._keys)

    def __getitem__(self, key: str) -> Any:
        if key not in self._values:
            raise KeyError(f"Unknown camera property {key}!")
        return self._values[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self._values:
            raise KeyError(f"Unknown camera property {key}!")
        if key in self._ranges:
            rng = self._ranges[key]
            value = type(self._values[key])(min(max(value, rng.minValue), rng.maxValue))
        self._values[key] = value
        self._log("set", (key, value))

    def property(self, key: str) -> PropertyInfo:
        """ Return the value range of a numeric property. """

        if key not in self._ranges:
            raise AttributeError(f"Component '{key}' has no min value!")
        return self._ranges[key]

    def getimage(self) -> np.ndarray:
        """ Return a synthetic 8-bit camera image.

        Returns
        -------
        numpy.ndarray
            Array of shape (Height, Width) and dtype uint8.
        """

        shape = (int(self._values["Height"]), int(self._values["Width"]))
        gain = 10 ** (float(self._values["Gain"]) / 20)
        level = 127.0 * float(self._values["ExposureTime"]) / self.reference_exposure * gain
        img = level + self.world.rng.normal(0.0, self.noise_sigma, shape)
        img = np.clip(np.rint(img), 0, 255).astype(np.uint8)
        self._log("getimage", (), shape)
        return img

    def close(self) -> None:
        """ Close the simulated device. """

        self.opened = False
        self._log("close")
