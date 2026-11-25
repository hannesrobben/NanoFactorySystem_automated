"""Material start file of the parameter tests (T158, design docs/design/PARAMETER_TESTS.md §3).

One JSON file per material holds every value the three parameter tests (Quick PT, Full PT-01, Voxel PT-01)
need: the power ladder, label and support power, the anchoring depth and the axis lists of every test. No
calibration, fit model or voxel database is needed to print (the tests measure P_th, w and l). The file is
read by the scripts in ``mains/parametertest/``; its content is passed to the structure factories as JSON, so
it is stored in ``/spec`` of every experiment.

Schema ``nanofactory.parameter_tests/1``. Missing sections are filled with the defaults of this module
(the decided values of the design); unknown keys raise ``SpecSerialisationError``.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nanofactorysystem.experiment_spec import SpecSerialisationError
from nanofactorysystem.voxel.materials import MissingPropertyError

__all__ = ["ParameterTestInputs", "SCHEMA", "DEFAULT_POWERS_MW", "DEFAULT_SUPPORT", "DEFAULT_QUICK", "DEFAULT_FULL",
           "DEFAULT_VOXEL", "as_inputs"]

SCHEMA = "nanofactory.parameter_tests/1"

# Power ladder 0.1 … 1.0 mW, linear (decided 2026-11-25); sub-field a = first half, b = second half
DEFAULT_POWERS_MW = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
# Pedestals, bases, REF pad, gap-test bases: one safe setting (decided)
DEFAULT_SUPPORT = {"power_mw": 0.5, "hatch_um": 0.2, "slice_um": 0.25}

DEFAULT_QUICK = {
    # Q1 walls: lines written in layers from z_from to z_to (1 µm in the substrate, 1 µm above)
    "walls": {"groups": 2, "walls_per_group": 3, "length_um": 8.0, "pitch_um": 1.5, "z_from_um": -1.0,
              "z_to_um": 1.0, "slice_um": 0.25},
    # Q2 pads: 5 × 5 µm from z_from to z_to, hatch per column
    "pads": {"size_um": 5.0, "hatch_um": [0.1, 0.2, 0.4, 0.6], "z_from_um": -1.0, "z_to_um": 1.0,
             "slice_um": 0.25},
}

DEFAULT_FULL = {
    "f1": {"passes": [1, 2, 3, 4], "line_length_um": 7.0, "line_pitch_um": 2.5},
    "f2": {"spans_um": [2.0, 4.0, 7.0, 10.0], "pedestal_um": [2.0, 3.0, 3.0], "line_below_top_um": 0.5,
           "gap_um": 2.0},
    "f3": {"spacing_um": [0.2, 0.4, 0.6, 0.8, 1.0, 1.2], "line_length_um": 6.0, "group_gap_um": 1.5},
    "f4": {"hatch_um": [0.1, 0.2, 0.4, 0.6], "pad_um": 6.0, "ramp_um": 1.6, "layers": 3, "slice_um": 0.3},
    "f5": {"slice_um": [0.1, 0.2, 0.3, 0.5], "hatch_um": 0.2, "wedge_um": [8.0, 4.0, 3.0], "cap_um": [8.0, 2.0]},
    "f6": {"line_length_um": 6.0, "grid_pitch_um": 2.5, "rod_pitch_um": 1.5, "woodpile_layers": 4,
           "woodpile_dz_um": 0.4},
    "f7": {"heights_um": [2.0, 4.0, 6.0, 8.0, 10.0], "pillar_diameter_um": 1.5, "base_um": [6.0, 6.0, 1.4],
           "hatch_um": 0.2, "slice_um": 0.25},
}

DEFAULT_VOXEL = {
    # gap test: base, gap, lid at the tested power; every cell its own structure, 100 µm apart, 3 × 4 grid
    "base_um": 20.0, "base_height_um": 2.0, "slice_um": 0.25, "hatch_um": 0.2,
    "gaps_um": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0], "lid_layers": 4,
    "cell_pitch_um": 100.0, "grid": [3, 4],
}


def _merge(defaults: dict, given: dict, where: str) -> dict:
    unknown = sorted(set(given) - set(defaults))
    if unknown:
        raise SpecSerialisationError(f"Unknown keys {unknown} in {where}; allowed: {sorted(defaults)}.")
    merged = copy.deepcopy(defaults)
    for key, value in given.items():
        if isinstance(defaults[key], dict):
            merged[key] = _merge(defaults[key], dict(value), f"{where}.{key}")
        else:
            merged[key] = copy.deepcopy(value)
    return merged


@dataclass(frozen=True)
class ParameterTestInputs:
    """ The material start file of the parameter tests.

    Parameters
    ----------
    material : str
        Registry name of the resin.
    powers_mw : list of float
        Power ladder (even number of levels): sub-field a takes the first half, b the second half.
    label_power_mw : float
        Power of the header marks (L mark, id dots).
    support : dict
        ``power_mw``, ``hatch_um``, ``slice_um`` of pedestals, bases, REF pad and gap-test bases.
    anchor_depth_um : float
        Depth below the interface down to which the first layer of volume cells is repeated.
    quick, full, voxel : dict
        Axis values of the three tests (defaults: the decided values of the design).
    source : str
        Where the values come from.

    Raises
    ------
    MissingPropertyError
        Without material or powers.
    ValueError
        For an odd number of powers, non-positive values or unsorted powers.
    """

    material: str
    powers_mw: list = field(default_factory=lambda: list(DEFAULT_POWERS_MW))
    label_power_mw: float = 0.5
    support: dict = field(default_factory=lambda: dict(DEFAULT_SUPPORT))
    anchor_depth_um: float = 1.0
    quick: dict = field(default_factory=dict)
    full: dict = field(default_factory=dict)
    voxel: dict = field(default_factory=dict)
    source: str = ""

    def __post_init__(self):
        if not self.material:
            raise MissingPropertyError("Parameter-test inputs lack the material.")
        powers = [round(float(p), 6) for p in (self.powers_mw or [])]
        if not powers:
            raise MissingPropertyError("Parameter-test inputs lack the power ladder.")
        if len(powers) % 2:
            raise ValueError(f"The power ladder needs an even number of levels (sub-fields a and b), got {len(powers)}.")
        if any(p <= 0 for p in powers) or powers != sorted(powers):
            raise ValueError("Powers must be positive and ascending.")
        if self.label_power_mw <= 0 or self.anchor_depth_um < 0:
            raise ValueError("label_power_mw must be > 0 and anchor_depth_um >= 0.")
        object.__setattr__(self, "powers_mw", powers)
        object.__setattr__(self, "support", _merge(DEFAULT_SUPPORT, dict(self.support), "support"))
        object.__setattr__(self, "quick", _merge(DEFAULT_QUICK, dict(self.quick), "quick"))
        object.__setattr__(self, "full", _merge(DEFAULT_FULL, dict(self.full), "full"))
        object.__setattr__(self, "voxel", _merge(DEFAULT_VOXEL, dict(self.voxel), "voxel"))
        if any(float(v) <= 0 for v in self.support.values()):
            raise ValueError("Support power, hatch and slice must be > 0.")

    # ------------------------------------------------------------------------------------------
    def powers_of(self, half: str) -> list[float]:
        """ The powers of sub-field ``"a"`` (first half of the ladder) or ``"b"`` (second half).

        Raises
        ------
        ValueError
            For another half.
        """

        n = len(self.powers_mw) // 2
        if half == "a":
            return self.powers_mw[:n]
        if half == "b":
            return self.powers_mw[n:]
        raise ValueError(f"half must be 'a' or 'b', got {half!r}")

    def to_json(self) -> dict[str, Any]:
        """ JSON form with schema ``nanofactory.parameter_tests/1`` (all values, defaults included). """

        return {"schema": SCHEMA, "material": self.material, "powers_mw": list(self.powers_mw),
                "label_power_mw": self.label_power_mw, "support": copy.deepcopy(self.support),
                "anchor_depth_um": self.anchor_depth_um, "quick": copy.deepcopy(self.quick),
                "full": copy.deepcopy(self.full), "voxel": copy.deepcopy(self.voxel), "source": self.source}

    @classmethod
    def from_json(cls, data: dict) -> "ParameterTestInputs":
        """ Read the JSON form.

        Raises
        ------
        SpecSerialisationError
            For another schema or unknown keys.
        """

        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            found = data.get("schema") if isinstance(data, dict) else type(data).__name__
            raise SpecSerialisationError(f"Unsupported schema {found!r}; expected {SCHEMA!r}.")
        unknown = sorted(set(data) - set(cls.__dataclass_fields__) - {"schema"})
        if unknown:
            raise SpecSerialisationError(f"Unknown keys {unknown} in the parameter-test inputs.")
        return cls(**{k: v for k, v in data.items() if k != "schema"})

    def save(self, path) -> Path:
        """ Write the JSON form to ``path``. """

        path = Path(path)
        path.write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path) -> "ParameterTestInputs":
        """ Read a file written by :meth:`save` (or by hand). """

        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def as_inputs(value) -> ParameterTestInputs:
    """ ``ParameterTestInputs`` from itself or its JSON dict (factory arguments are dicts). """

    return value if isinstance(value, ParameterTestInputs) else ParameterTestInputs.from_json(value)
