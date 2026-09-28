# units.py
"""Unit handling at the system boundary.

Policy (docs/03 §1): internally there is exactly one length unit — um,
float64. This module is the *only* place where conversions happen. Every
public function elsewhere documents its units; every dimensioned name
carries a suffix (_um, _um_s, _mw).
"""
from __future__ import annotations

import numpy as np

UM_PER_UNIT: dict[str, float] = {
    "nm": 1e-3,
    "um": 1.0, "µm": 1.0, "μm": 1.0,  # ascii, micro sign, greek mu
    "mm": 1e3,
    "cm": 1e4,
    "m": 1e6,
}

# Plausibility window for TPP structures (docs/03 §1, rule 3)
PLAUSIBLE_MAX_EXTENT_UM = 10_000.0   # 1 cm — larger smells like a unit slip
PLAUSIBLE_MIN_EXTENT_UM = 0.05       # below the diffraction limit


def scale_to_um(unit: str) -> float:
    """Conversion factor unit -> um. Raises on unknown units (no guessing)."""
    try:
        return UM_PER_UNIT[unit.strip()]
    except KeyError:
        raise ValueError(
            f"Unknown unit '{unit}'. Supported: {sorted(set(UM_PER_UNIT))}"
        ) from None


def to_um(value, unit: str):
    """Convert scalar or array from `unit` to um (arrays -> float64 copy)."""
    f = scale_to_um(unit)
    if isinstance(value, np.ndarray):
        return np.asarray(value, dtype=np.float64) * f
    return float(value) * f


def from_um(value, unit: str):
    """Convert scalar or array from um to `unit`."""
    f = scale_to_um(unit)
    if isinstance(value, np.ndarray):
        return np.asarray(value, dtype=np.float64) / f
    return float(value) / f


def plausibility_warnings(extents_um) -> list[str]:
    """Human-readable warnings when model dimensions look like a unit slip.

    Never silently corrects — warns with a suggestion (docs/03 §1).
    """
    extents = np.asarray(extents_um, dtype=np.float64)
    warnings: list[str] = []
    largest = float(extents.max()) if extents.size else 0.0
    if largest > PLAUSIBLE_MAX_EXTENT_UM:
        warnings.append(
            f"Largest extent is {largest:.0f} um "
            f"(> {PLAUSIBLE_MAX_EXTENT_UM:.0f} um) — unusually large for TPP. "
            f"Check the `unit` parameter: a mm/um mixup by factor 1000 would "
            f"make this a {largest / 1e3:.1f} um structure."
        )
    if 0 < largest < PLAUSIBLE_MIN_EXTENT_UM:
        warnings.append(
            f"Largest extent is only {largest:.4f} um — below realistic TPP "
            f"feature size. Check the input unit."
        )
    return warnings
