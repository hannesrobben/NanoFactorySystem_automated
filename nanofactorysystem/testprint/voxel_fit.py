"""Fitted voxel models w(P), l(P) (T150, design docs/design/TEST_PRINT_PTD01.md §4.4).

A :class:`VoxelFitModel` evaluates a voxel width and length over the laser power at one writing
velocity. It is the result of a fit (analysis code, T151); this module only evaluates it. The
normalised axes of PTD-01 use it at the power of every cell: ``h = h_rel · w(P)``,
``Δz = dz_rel · l(P)``.

Model kinds are registered by name, so a new kind needs no change of the class:

- ``threshold_ln``: ``d(P) = d_scale · sqrt(n_eff · ln(P / P_th))`` = ``d_scale · sqrt(ln((P/P_th)^n_eff))``
  for the width (``w_scale_um``) and the length (``l_scale_um``), parameters ``p_th_mw``, ``n_eff``.
- ``power_law``: ``d(P) = a · (P - P_th)^b``, parameters ``p_th_mw``, ``w_a``, ``w_b``, ``l_a``, ``l_b``.
- ``tabulated``: piecewise linear between measured points ``power_mw``, ``width_um``, ``length_um``.

No extrapolation: every evaluation outside ``valid_power_mw`` (or at another velocity) raises.
``voxel_size(power_mw, velocity_um_s)`` satisfies the slicer protocol
``aerobasic.slicer.voxel.VoxelModel``, so the model can be passed to ``Model3D_Slicer(voxel_model=…)``.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from nanofactorysystem.experiment_spec import SpecSerialisationError
from nanofactorysystem.voxel.database import VoxelSize
from nanofactorysystem.voxel.materials import MissingPropertyError

__all__ = ["VoxelFitModel", "ModelKind", "register_model_kind", "model_kinds", "SCHEMA", "VELOCITY_TOLERANCE"]

SCHEMA = "nanofactory.voxel_fit_model/1"
# Relative difference between the requested and the fitted velocity that still counts as the same velocity
VELOCITY_TOLERANCE = 0.01


@dataclass(frozen=True)
class ModelKind:
    """ One registered model kind.

    Parameters
    ----------
    name : str
    required : tuple of str
        Parameter names the kind needs.
    width, length : callable
        ``f(params, power_mw) -> µm``.
    check : callable, optional
        ``check(params, valid_power_mw)`` raising ``ValueError`` for inconsistent parameters.
    """

    name: str
    required: tuple[str, ...]
    width: Callable[[dict, float], float]
    length: Callable[[dict, float], float]
    check: Optional[Callable[[dict, tuple[float, float]], None]] = None


_KINDS: dict[str, ModelKind] = {}


def register_model_kind(kind: ModelKind) -> ModelKind:
    """ Register a model kind under ``kind.name`` (replaces an earlier one of the same name). """

    _KINDS[kind.name] = kind
    return kind


def model_kinds() -> list[str]:
    """ Names of the registered model kinds. """

    return sorted(_KINDS)


def _threshold_ln(scale_key: str) -> Callable[[dict, float], float]:
    def evaluate(params: dict, power_mw: float) -> float:
        return params[scale_key] * math.sqrt(params["n_eff"] * math.log(power_mw / params["p_th_mw"]))
    return evaluate


def _check_threshold(params: dict, valid: tuple[float, float]) -> None:
    if params["p_th_mw"] <= 0 or params["n_eff"] <= 0:
        raise ValueError("threshold_ln needs p_th_mw > 0 and n_eff > 0")
    if valid[0] <= params["p_th_mw"]:
        raise ValueError(f"valid_power_mw must start above p_th_mw = {params['p_th_mw']} mW (zero size at P_th)")


def _power_law(prefix: str) -> Callable[[dict, float], float]:
    def evaluate(params: dict, power_mw: float) -> float:
        return params[f"{prefix}_a"] * (power_mw - params["p_th_mw"]) ** params[f"{prefix}_b"]
    return evaluate


def _check_power_law(params: dict, valid: tuple[float, float]) -> None:
    if valid[0] <= params["p_th_mw"]:
        raise ValueError(f"valid_power_mw must start above p_th_mw = {params['p_th_mw']} mW")


def _tabulated(key: str) -> Callable[[dict, float], float]:
    def evaluate(params: dict, power_mw: float) -> float:
        return float(np.interp(power_mw, params["power_mw"], params[key]))
    return evaluate


def _check_tabulated(params: dict, valid: tuple[float, float]) -> None:
    powers = np.asarray(params["power_mw"], dtype=float)
    if len(powers) < 2 or len(params["width_um"]) != len(powers) or len(params["length_um"]) != len(powers):
        raise ValueError("tabulated needs at least 2 points and as many widths and lengths as powers")
    if np.any(np.diff(powers) <= 0):
        raise ValueError("tabulated powers must be strictly ascending")
    if valid[0] < powers[0] or valid[1] > powers[-1]:
        raise ValueError("valid_power_mw must lie inside the tabulated powers (no extrapolation)")


register_model_kind(ModelKind("threshold_ln", ("w_scale_um", "l_scale_um", "p_th_mw", "n_eff"),
                              _threshold_ln("w_scale_um"), _threshold_ln("l_scale_um"), _check_threshold))
register_model_kind(ModelKind("power_law", ("p_th_mw", "w_a", "w_b", "l_a", "l_b"),
                              _power_law("w"), _power_law("l"), _check_power_law))
register_model_kind(ModelKind("tabulated", ("power_mw", "width_um", "length_um"),
                              _tabulated("width_um"), _tabulated("length_um"), _check_tabulated))


@dataclass(frozen=True)
class VoxelFitModel:
    """ A fitted voxel model w(P), l(P) at one writing velocity.

    Parameters
    ----------
    kind : str
        Registered model kind (:func:`model_kinds`).
    params : dict
        Parameters of the kind.
    valid_power_mw : (float, float)
        Power range of the data the fit is based on; evaluations outside raise.
    velocity_um_s : float
        Writing velocity of the data (IFOV 63x: 5000 µm/s).
    source : str
        Experiment UUIDs, fit date, residuals file, …
    residuals : dict
        E.g. RMS and maximum residual of w and l in µm.

    Raises
    ------
    MissingPropertyError
        For a missing parameter of the kind (no silent default, G7).
    ValueError
        For an unknown kind, an empty range or inconsistent parameters.
    """

    kind: str
    params: dict
    valid_power_mw: tuple[float, float]
    velocity_um_s: float
    source: str = ""
    residuals: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in _KINDS:
            raise ValueError(f"Unknown voxel model kind {self.kind!r}; registered: {model_kinds()}")
        kind = _KINDS[self.kind]
        missing = [name for name in kind.required if self.params.get(name) is None]
        if missing:
            raise MissingPropertyError(f"Voxel model {self.kind!r} lacks the parameters {missing}.")
        low, high = (float(v) for v in self.valid_power_mw)
        if not 0 < low < high:
            raise ValueError(f"valid_power_mw must be 0 < low < high, got {self.valid_power_mw}")
        if not self.velocity_um_s or self.velocity_um_s <= 0:
            raise MissingPropertyError("Voxel model lacks the writing velocity velocity_um_s.")
        object.__setattr__(self, "valid_power_mw", (low, high))
        object.__setattr__(self, "params", {k: (list(map(float, v)) if isinstance(v, (list, tuple, np.ndarray))
                                                else float(v)) for k, v in self.params.items()})
        if kind.check is not None:
            kind.check(self.params, self.valid_power_mw)

    # ------------------------------------------------------------------------------------------
    def _check_power(self, power_mw: float) -> float:
        low, high = self.valid_power_mw
        power = float(power_mw)
        if not low - 1e-12 <= power <= high + 1e-12:
            raise ValueError(f"Power {power:g} mW lies outside the validity range {low:g} - {high:g} mW of the "
                             f"voxel model ({self.kind}); no extrapolation.")
        return power

    def contains(self, power_mw: float) -> bool:
        """ True if ``power_mw`` lies inside ``valid_power_mw``. """

        low, high = self.valid_power_mw
        return low - 1e-12 <= float(power_mw) <= high + 1e-12

    def width_um(self, power_mw: float) -> float:
        """ Voxel width at ``power_mw``.

        Raises
        ------
        ValueError
            Outside ``valid_power_mw``.
        """

        return float(_KINDS[self.kind].width(self.params, self._check_power(power_mw)))

    def length_um(self, power_mw: float) -> float:
        """ Voxel length (axial size) at ``power_mw``.

        Raises
        ------
        ValueError
            Outside ``valid_power_mw``.
        """

        return float(_KINDS[self.kind].length(self.params, self._check_power(power_mw)))

    def voxel_size(self, power_mw: float, velocity_um_s: float) -> VoxelSize:
        """ Slicer protocol ``VoxelModel``: width and height (= length) at the laser parameters.

        Raises
        ------
        ValueError
            Outside ``valid_power_mw`` or at another velocity than the fitted one.
        """

        if abs(float(velocity_um_s) - self.velocity_um_s) > VELOCITY_TOLERANCE * self.velocity_um_s:
            raise ValueError(f"The voxel model was fitted at {self.velocity_um_s:g} um/s, not at "
                             f"{velocity_um_s:g} um/s; no extrapolation.")
        method = f"fit-{self.kind}"
        return VoxelSize(self.width_um(power_mw), self.length_um(power_mw), method, method, 0)

    def describe(self) -> dict[str, Any]:
        """ Slicer protocol ``VoxelModel``: JSON description for the metadata (= :meth:`to_json`). """

        return self.to_json()

    # ------------------------------------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        """ JSON form with schema ``nanofactory.voxel_fit_model/1``. """

        return {"schema": SCHEMA, "kind": self.kind, "params": dict(self.params),
                "valid_power_mw": list(self.valid_power_mw), "velocity_um_s": self.velocity_um_s,
                "source": self.source, "residuals": dict(self.residuals)}

    @classmethod
    def from_json(cls, data: dict) -> "VoxelFitModel":
        """ Rebuild a model from :meth:`to_json`.

        Raises
        ------
        SpecSerialisationError
            For another schema.
        MissingPropertyError
            For a missing field or parameter.
        """

        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            raise SpecSerialisationError(f"Unsupported voxel model schema {data.get('schema') if isinstance(data, dict) else data!r}; "
                                         f"expected {SCHEMA!r}.")
        lacking = [k for k in ("kind", "params", "valid_power_mw", "velocity_um_s") if data.get(k) is None]
        if lacking:
            raise MissingPropertyError(f"Voxel model JSON lacks {lacking}.")
        return cls(kind=data["kind"], params=dict(data["params"]), valid_power_mw=tuple(data["valid_power_mw"]),
                   velocity_um_s=float(data["velocity_um_s"]), source=data.get("source", ""),
                   residuals=dict(data.get("residuals", {})))

    def save(self, path) -> Path:
        """ Write the JSON form to ``path``. """

        path = Path(path)
        path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path) -> "VoxelFitModel":
        """ Read a model written by :meth:`save`. """

        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
