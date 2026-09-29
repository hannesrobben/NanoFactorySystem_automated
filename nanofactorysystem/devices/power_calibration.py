"""Laser power calibration for program generation.

Drawing classes that set the laser power in their programs (``IFOV_Lines``
and the structures built on it) convert a power in mW into an attenuator
value. The calibration they use is resolved in this order:

1. a ``PowerCalibration`` passed to the structure explicitly,
2. the calibration activated with :func:`power_calibration` (e.g. by
   ``Experiment.build_programs()`` with the attenuator of the running system),
3. the file ``attenuator.calibrationFile`` of the active configuration.
"""
from __future__ import annotations

import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal, Optional

import numpy as np

FitKind = Literal["polynomial", "spline"]

_active: list["PowerCalibration"] = []


class PowerCalibration:
    """ Conversion between attenuator value and laser power.

    Parameters
    ----------
    data : array_like
        Calibration table of shape (n, 2): attenuator value (0..10), laser
        power in mW.
    fit_kind : {"polynomial", "spline"}
        ``"polynomial"``: 2nd order polynomial fits in both directions (they
        do not pass through the data points exactly). ``"spline"``:
        quadratic spline interpolation.
    """

    def __init__(self, data, fit_kind: FitKind = "polynomial"):
        self.data = np.asarray(data, dtype=float).reshape(-1, 2)
        self.fit_kind = fit_kind
        a = self.data[:, 0]
        p = self.data[:, 1]
        if fit_kind == "polynomial":
            order = 2
            self.atop = np.poly1d(np.polyfit(a, p, order))
            self.ptoa = np.poly1d(np.polyfit(p, a, order))
        elif fit_kind == "spline":
            from scipy.interpolate import interp1d
            self.atop = interp1d(a, p, kind="quadratic")
            self.ptoa = interp1d(p, a, kind="quadratic")
        else:
            raise NotImplementedError(f"Fit kind {fit_kind} is not implemented.")

    @classmethod
    def from_file(cls, path: str | Path, fit_kind: FitKind = "polynomial") -> "PowerCalibration":
        """ Read a binary calibration file (pairs of little-endian doubles).

        Parameters
        ----------
        path : str or Path
            Calibration file, as used by ``devices.Attenuator``.
        fit_kind : {"polynomial", "spline"}
            See :class:`PowerCalibration`.

        Returns
        -------
        PowerCalibration
            The calibration.
        """

        raw = Path(path).read_bytes()
        if len(raw) % 16:
            raise RuntimeError("File size must be a multiple of 16!")
        num = len(raw) // 16
        data = struct.unpack("<" + 2 * num * "d", raw)
        return cls(np.array(data).reshape(num, 2), fit_kind)

    @classmethod
    def from_config(cls, fit_kind: FitKind = "polynomial") -> "PowerCalibration":
        """ Read the file ``attenuator.calibrationFile`` of the active configuration.

        Raises
        ------
        RuntimeError
            If no calibration file is configured.
        """

        from nanofactorysystem.config import sysConfig
        path = sysConfig.section("attenuator").get("calibrationFile")
        if path is None:
            raise RuntimeError("No laser power calibration: pass calibration=..., use power_calibration(...), "
                               "or set attenuator.calibrationFile in the configuration.")
        return cls.from_file(path, fit_kind)

    def to_json(self) -> dict:
        """ Return a JSON-serialisable description. """

        return {"fit_kind": self.fit_kind, "data": self.data.tolist()}

    def __repr__(self) -> str:
        return f"PowerCalibration({len(self.data)} points, fit_kind={self.fit_kind!r})"


@contextmanager
def power_calibration(calibration: PowerCalibration) -> Iterator[PowerCalibration]:
    """ Activate a calibration for all structures generated inside the context.

    Parameters
    ----------
    calibration : PowerCalibration
        Calibration to use.
    """

    _active.append(calibration)
    try:
        yield calibration
    finally:
        _active.pop()


def active_power_calibration(fit_kind: FitKind = "polynomial") -> PowerCalibration:
    """ Return the active calibration or, without one, the configured calibration file.

    Parameters
    ----------
    fit_kind : {"polynomial", "spline"}
        Fit used when reading the configured file.
    """

    if _active:
        calibration = _active[-1]
        if calibration.fit_kind != fit_kind:
            calibration = PowerCalibration(calibration.data, fit_kind)
        return calibration
    return PowerCalibration.from_config(fit_kind)


def resolve_power_calibration(calibration: Optional[PowerCalibration],
                              fit_kind: FitKind = "polynomial") -> PowerCalibration:
    """ Return ``calibration`` if given, otherwise :func:`active_power_calibration`. """

    return calibration if calibration is not None else active_power_calibration(fit_kind)
