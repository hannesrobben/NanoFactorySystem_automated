"""Process calibration of the test prints (T140, design TEST_PRINT_PTD01.md §4.4, §7).

- :class:`ProcessCalibration` holds the stage-A results of one material / objective / setup /
  velocity (P_th, P_dam, interface working point z0, the voxel fit model) and converts the
  normalised axes of stage B into absolute values: ``P = p_rel · P_th``,
  ``h = h_rel · w(P)``, ``Δz = dz_rel · l(P)`` with the voxel size **at the power of the cell**.
  JSON schema ``nanofactory.process_calibration/1``; the file is written after the evaluation of
  stage A (``provisional=True``) and refined after stage B (T151).

The stage-A start values of the two-stage PTD-01 (``StageAAxes``) were moved to the attic with version 1
(T164, ``docs/ATTIC_INDEX.md``); the parameter tests of version 2 use ``inputs.ParameterTestInputs``.

Missing physical values raise ``MissingPropertyError`` (no silent default, G7); a wrong schema
raises ``SpecSerialisationError``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from nanofactorysystem.experiment_spec import SpecSerialisationError
from nanofactorysystem.voxel.materials import MissingPropertyError

from .voxel_fit import VELOCITY_TOLERANCE, VoxelFitModel

__all__ = ["ProcessCalibration", "as_calibration", "CALIBRATION_SCHEMA"]

CALIBRATION_SCHEMA = "nanofactory.process_calibration/1"


def _check_schema(data: Any, schema: str) -> None:
    if not isinstance(data, dict) or data.get("schema") != schema:
        found = data.get("schema") if isinstance(data, dict) else type(data).__name__
        raise SpecSerialisationError(f"Unsupported schema {found!r}; expected {schema!r}.")


def _require(values: dict, what: str) -> None:
    missing = [name for name, value in values.items() if value is None or value == ""]
    if missing:
        raise MissingPropertyError(f"{what} lacks the values {missing} (no silent default).")


@dataclass(frozen=True)
class ProcessCalibration:
    """ Stage-A results of one material, objective, setup and velocity.

    Parameters
    ----------
    material, objective, setup : str
        Registry name of the resin, objective key (``"Zeiss 63x"``), setup (``"IFOV_on"``).
    velocity_um_s : float
        Writing velocity (IFOV 63x: 5000 µm/s); must match the voxel model.
    p_th_mw : float
        Polymerisation threshold at the interface working point.
    z0_um : float
        Interface working point: z of the line centre relative to the fitted plane.
    voxel_model : VoxelFitModel or dict
        Fitted voxel model (required; a dict is read with ``VoxelFitModel.from_json``).
    p_dam_mw : float, optional
        Damage threshold (unknown until evaluated).
    p_ref_factor : float
        Working point ``P_ref = p_ref_factor · P_th`` (decision D3: 1.5).
    plane_fit : dict
        Interface detection settings the z0 belongs to (plane-fit mode, interface power, exposure).
    polarisation_deg : float, optional
        Polarisation direction relative to the x axis (decision D13, measured before stage B).
    provisional : bool
        True while the model is fitted from F0 data only.
    source, date : str
        Origin (experiment UUIDs, evaluation) and date. A source starting with ``"example"`` marks a
        file with example values that must not be used for a real print.

    Raises
    ------
    MissingPropertyError
        For a missing physical value or model.
    ValueError
        For values out of range or a velocity that does not match the model.
    """

    material: str
    objective: str
    setup: str
    velocity_um_s: float
    p_th_mw: float
    z0_um: float
    voxel_model: VoxelFitModel
    p_dam_mw: Optional[float] = None
    p_ref_factor: float = 1.5
    plane_fit: dict = field(default_factory=dict)
    polarisation_deg: Optional[float] = None
    provisional: bool = True
    source: str = ""
    date: str = ""

    def __post_init__(self):
        _require({"material": self.material, "objective": self.objective, "setup": self.setup,
                  "velocity_um_s": self.velocity_um_s, "p_th_mw": self.p_th_mw, "z0_um": self.z0_um,
                  "voxel_model": self.voxel_model}, "Process calibration")
        if isinstance(self.voxel_model, dict):
            object.__setattr__(self, "voxel_model", VoxelFitModel.from_json(self.voxel_model))
        if not isinstance(self.voxel_model, VoxelFitModel):
            raise TypeError(f"voxel_model must be a VoxelFitModel, got {type(self.voxel_model).__name__}")
        if self.p_th_mw <= 0 or self.velocity_um_s <= 0 or self.p_ref_factor <= 0:
            raise ValueError("p_th_mw, velocity_um_s and p_ref_factor must be > 0")
        if self.p_dam_mw is not None and self.p_dam_mw <= self.p_th_mw:
            raise ValueError(f"p_dam_mw ({self.p_dam_mw}) must lie above p_th_mw ({self.p_th_mw})")
        if abs(self.velocity_um_s - self.voxel_model.velocity_um_s) > VELOCITY_TOLERANCE * self.velocity_um_s:
            raise ValueError(f"The voxel model was fitted at {self.voxel_model.velocity_um_s:g} um/s, the "
                             f"calibration is for {self.velocity_um_s:g} um/s.")

    # ------------------------------------------------------------------------------------------
    @property
    def p_ref_mw(self) -> float:
        """ Working point ``p_ref_factor · P_th`` in mW. """

        return self.p_ref_factor * self.p_th_mw

    @property
    def w0_um(self) -> float:
        """ Voxel width at ``P_ref``. """

        return self.voxel_model.width_um(self.p_ref_mw)

    @property
    def l0_um(self) -> float:
        """ Voxel length at ``P_ref``. """

        return self.voxel_model.length_um(self.p_ref_mw)

    @property
    def is_example(self) -> bool:
        """ True for a file with example values (``source`` starts with ``"example"``). """

        return self.source.strip().lower().startswith("example")

    def power_mw(self, p_rel: float) -> float:
        """ Absolute power ``p_rel · P_th`` in mW. """

        return float(p_rel) * self.p_th_mw

    def hatch_um(self, h_rel: float, power_mw: float) -> float:
        """ Hatch distance ``h_rel · w(P)`` at the power of the cell.

        Raises
        ------
        ValueError
            If ``power_mw`` lies outside the validity range of the voxel model.
        """

        return float(h_rel) * self.voxel_model.width_um(power_mw)

    def slice_um(self, dz_rel: float, power_mw: float) -> float:
        """ Slice distance ``dz_rel · l(P)`` at the power of the cell.

        Raises
        ------
        ValueError
            If ``power_mw`` lies outside the validity range of the voxel model.
        """

        return float(dz_rel) * self.voxel_model.length_um(power_mw)

    def matches(self, material: str, objective: str, setup: str) -> bool:
        """ True if the calibration was made for this material, objective and setup. """

        return (self.material, self.objective, self.setup) == (material, objective, setup)

    # ------------------------------------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        """ JSON form with schema ``nanofactory.process_calibration/1`` (voxel model included). """

        return {"schema": CALIBRATION_SCHEMA, "material": self.material, "objective": self.objective,
                "setup": self.setup, "velocity_um_s": self.velocity_um_s, "p_th_mw": self.p_th_mw,
                "p_dam_mw": self.p_dam_mw, "z0_um": self.z0_um, "p_ref_factor": self.p_ref_factor,
                "plane_fit": dict(self.plane_fit), "polarisation_deg": self.polarisation_deg,
                "provisional": self.provisional, "source": self.source, "date": self.date,
                "voxel_model": self.voxel_model.to_json()}

    @classmethod
    def from_json(cls, data: dict) -> "ProcessCalibration":
        """ Rebuild a calibration from :meth:`to_json`.

        Raises
        ------
        SpecSerialisationError
            For another schema or unknown keys.
        MissingPropertyError
            For a missing physical value or model.
        """

        _check_schema(data, CALIBRATION_SCHEMA)
        allowed = set(cls.__dataclass_fields__) | {"schema"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise SpecSerialisationError(f"Unknown keys {unknown} in the process calibration.")
        arguments = {k: v for k, v in data.items() if k != "schema"}
        if arguments.get("voxel_model") is None:
            raise MissingPropertyError("Process calibration lacks the voxel model (no silent default).")
        return cls(**arguments)

    def save(self, path) -> Path:
        """ Write the JSON form to ``path``. """

        path = Path(path)
        path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path) -> "ProcessCalibration":
        """ Read a calibration file written by :meth:`save`. """

        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def as_calibration(value) -> ProcessCalibration:
    """ A ``ProcessCalibration`` from itself or its JSON dict (factory arguments are dicts). """

    return value if isinstance(value, ProcessCalibration) else ProcessCalibration.from_json(value)
