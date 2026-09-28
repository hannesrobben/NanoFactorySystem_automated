"""Simulated client of the LyncéeTec DHM server (HoloServ)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from nanofactorysystem.backends.dummy.world import SimulatedWorld
from nanofactorysystem.dhm.dhmclient import DhmClient


class DummyDhmClient:
    """ Drop-in replacement for ``nanofactorysystem.dhm.DhmClient``.

    All attributes of ``DhmClient._commands`` exist with their real types.
    ``CameraImage`` is an off-axis hologram (carrier fringes plus seeded
    noise). Its intensity scales with ``CameraShutter`` and saturates, and
    its fringe contrast is ``exp(-((MotorPos - opl_optimum) / opl_width)**2)``,
    so the exposure optimisation and the OPL motor scan converge.

    Parameters
    ----------
    world : SimulatedWorld
        Shared state; provides the random generator, clock, call log and
        ``opl_optimum``.
    config_id : int
        Initially selected objective configuration (``dhmId``).
    configs : list of tuple, optional
        Available configurations as (id, name) pairs.
    width, height : int
        Hologram size in pixels.
    opl_width : float
        Width of the contrast envelope in µm.
    """

    manufacturer = "LyncéeTec (simulated)"

    def __init__(self, world: SimulatedWorld, *, config_id: int = 178, configs=None,
                 width: int = 256, height: int = 256, opl_width: float = 400.0):
        state = {
            "ServerVersion": 3,
            "CmdVersion": 1,
            "Status": 0,
            "ConfigList": list(configs or [(178, "Zeiss 20x (simulated)"), (180, "Zeiss 63x (simulated)")]),
            "Config": int(config_id),
            "DhmSerial": "SIM-DHM",
            "ObjectiveName": "simulated",
            "ObjectiveDescription": "simulated objective",
            "ObjectiveMagnification": 20.0,
            "ObjectiveNumericalAperture": 0.8,
            "ObjectivePixelSizeXUm": 0.3,
            "ObjectivePixelSizeYUm": 0.3,
            "CameraSerial": "SIM-CAM",
            "CameraName": "Simulated camera",
            "CameraMaxWidth": width,
            "CameraMaxHeight": height,
            "CameraWidth": width,
            "CameraHeight": height,
            "CameraOffsetX": 0,
            "CameraOffsetY": 0,
            "CameraBitPerPixel": 8,
            "CameraStride": width,
            "CameraPixelSizeUm": 5.86,
            "CameraMinShutter": 1,
            "CameraMaxShutter": 4000,
            "CameraShutter": 100,
            "CameraMinShutterUs": 50.0,
            "CameraMaxShutterUs": 80030.0,
            "CameraShutterUs": 2030.0,
            "CameraMinGain": 0,
            "CameraMaxGain": 100,
            "CameraGain": 0,
            "CameraMinBrightness": 0,
            "CameraMaxBrightness": 100,
            "CameraBrightness": 0,
            "LaserWavelength": 6.66e-7,
            "LaserOutput": 1,
            "MotorMinCoderPos": 0,
            "MotorMaxCoderPos": 1000000,
            "MotorCoderPos": 0,
            "MotorMinPos": 0.0,
            "MotorMaxPos": 10000.0,
            "MotorPos": 800.0,
            "MotorUnitPos": "um",
        }
        object.__setattr__(self, "world", world)
        object.__setattr__(self, "opl_width", float(opl_width))
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "opened", True)

    def _log(self, call: str, args: tuple = (), result: Any = None) -> None:
        self.world.calllog.record("dhm", call, args, result, self.world.clock.now)

    def __str__(self) -> str:
        return f"{self.manufacturer} (S/N {self._state['DhmSerial']})"

    def __enter__(self):
        return self

    def __exit__(self, etype, value, traceback):
        self.close()

    def __getattr__(self, name: str):
        state = object.__getattribute__(self, "_state")
        if name == "CameraImage":
            return self._hologram()
        if name in state:
            value = state[name]
            self._log("get", (name,), value)
            return value
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in DhmClient._commands:
            if DhmClient._commands[name][0] is None:
                raise AttributeError(f"Attribute '{name}' is not writeable!")
            if name == "CameraShutter":
                value = int(min(max(value, self._state["CameraMinShutter"]), self._state["CameraMaxShutter"]))
                self._state["CameraShutterUs"] = value * 20.0 + 30.0
            if name == "CameraShutterUs":
                self._state["CameraShutter"] = int(round((value - 30.0) / 20.0))
            if name == "MotorPos":
                value = float(min(max(value, self._state["MotorMinPos"]), self._state["MotorMaxPos"]))
            self._state[name] = value
            self._log("set", (name, value))
        else:
            object.__setattr__(self, name, value)

    def _hologram(self) -> np.ndarray:
        s = self._state
        h, w = s["CameraHeight"], s["CameraWidth"]
        maxpixel = (1 << s["CameraBitPerPixel"]) - 1
        contrast = math.exp(-((s["MotorPos"] - self.world.opl_optimum) / self.opl_width) ** 2)
        y, x = np.mgrid[0:h, 0:w]
        fringes = np.cos(2 * np.pi * (x / 4.0 + y / 7.0))
        mean = 60.0 * s["CameraShutter"] / 100.0
        img = mean * (1.0 + 0.9 * contrast * fringes) + self.world.rng.normal(0.0, 1.5, (h, w))
        dtype = np.uint16 if s["CameraBitPerPixel"] > 8 else np.uint8
        img = np.clip(np.rint(img), 0, maxpixel).astype(dtype)
        self._log("get", ("CameraImage",), (h, w))
        return img

    def set_keys(self) -> list[str]:
        """ Return the names of all writeable attributes. """

        return list(sorted(k for k, v in DhmClient._commands.items() if v[0] is not None))

    def keys(self) -> list[str]:
        """ Return the names of all attributes. """

        return list(sorted(DhmClient._commands))

    def parameters(self) -> dict[str, Any]:
        """ Return the parameter dictionary with the structure of ``DhmClient.parameters``. """

        s = self._state
        return {
            "server": {"version": s["ServerVersion"], "commandVersion": s["CmdVersion"]},
            "dhm": {"manufacturer": self.manufacturer, "serial": s["DhmSerial"], "configId": s["Config"],
                    "configName": dict(s["ConfigList"])[s["Config"]]},
            "objective": {"name": s["ObjectiveName"], "description": s["ObjectiveDescription"],
                          "magnification": s["ObjectiveMagnification"],
                          "numericalAperture": s["ObjectiveNumericalAperture"],
                          "xPixelSizeUm": s["ObjectivePixelSizeXUm"], "yPixelSizeUm": s["ObjectivePixelSizeYUm"]},
            "camera": {"name": s["CameraName"], "width": s["CameraWidth"], "height": s["CameraHeight"],
                       "bitPerPixel": s["CameraBitPerPixel"], "shutter": s["CameraShutter"],
                       "shutterUs": s["CameraShutterUs"]},
            "laser": {"wavelengthUm": s["LaserWavelength"] * 1e6},
            "motor": {"minPos": s["MotorMinPos"], "maxPos": s["MotorMaxPos"], "pos": s["MotorPos"],
                      "unitPos": s["MotorUnitPos"]},
        }

    def close(self) -> None:
        """ Close the simulated connection. """

        object.__setattr__(self, "opened", False)
        self._log("close")
