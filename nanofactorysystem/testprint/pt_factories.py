"""Named structure factories of the parameter tests (T158–T161, design docs/design/PARAMETER_TESTS.md).

Factories ``quick_pt.walls``, ``quick_pt.pads``, ``full_pt01.f1`` … ``full_pt01.f7`` and ``voxel_pt01.gap``.
Their arguments are JSON values only (the material start file as dict, the sub-field or the gap-test
parameters), so ``experiment_spec.json`` holds the complete parameter set and a restart rebuilds the same
field. Every factory builds the field with its pure builder (:mod:`.parameter_tests`), checks all powers
against the attenuator calibration range **when it is known** (offline builds have no range) and returns a
:class:`~.structure.ParameterFieldStructure` with the objective of the running experiment.
"""
from __future__ import annotations

from typing import Callable

from nanofactorysystem.structure_factories import BuildContext, structure_factory

from . import parameter_tests as pt
from .ordering import DEFAULT_ORDERING
from .structure import ParameterFieldStructure

__all__ = ["quick_walls", "quick_pads", "full_f1", "full_f2", "full_f3", "full_f4", "full_f5", "full_f6", "full_f7",
           "voxel_gap", "QUICK_FACTORIES", "FULL_FACTORIES", "DEFAULT_OBJECTIVE"]

DEFAULT_OBJECTIVE = "Zeiss 63x"


def _structure(name: str, builder: Callable, context: BuildContext, arguments: dict,
               dwell_after_power_s: float) -> ParameterFieldStructure:
    field = builder(**arguments)
    if context.power_min_mw is not None and context.power_max_mw is not None:
        context.check_power(*field.powers_mw())
    structure = ParameterFieldStructure(name, arguments, objective=context.objective or DEFAULT_OBJECTIVE,
                                        power_mw=field.label_power_mw, dwell_after_power_s=dwell_after_power_s)
    structure._built = field  # same pure function of the same arguments
    return structure


def _sub_field_factory(name: str, builder: Callable, doc: str):
    def factory(context: BuildContext, *, inputs: dict, half: str, order: str = DEFAULT_ORDERING,
                dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
        return _structure(name, builder, context, {"inputs": dict(inputs), "half": half, "order": order},
                          dwell_after_power_s)
    factory.__name__ = factory.__qualname__ = name.replace(".", "_")
    factory.__doc__ = f""" {doc}

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment (objective, attenuator range).
    inputs : dict
        Material start file (``ParameterTestInputs`` JSON).
    half : {{"a", "b"}}
        Sub-field: first or second half of the power ladder.
    order : str
        In-layer ordering strategy.
    dwell_after_power_s : float
        Dwell after every power change (D9 / T148).

    Returns
    -------
    ParameterFieldStructure

    Raises
    ------
    ValueError
        If a power lies outside the known attenuator range.
    """
    return structure_factory(name)(factory)


quick_walls = _sub_field_factory("quick_pt.walls", pt.quick_walls, "Quick PT Q1 walls (one sub-field).")
quick_pads = _sub_field_factory("quick_pt.pads", pt.quick_pads, "Quick PT Q2 pads (one sub-field).")
full_f1 = _sub_field_factory("full_pt01.f1", pt.full_f1, "Full PT-01 F1 line test (one sub-field).")
full_f2 = _sub_field_factory("full_pt01.f2", pt.full_f2, "Full PT-01 F2 bridges (one sub-field).")
full_f3 = _sub_field_factory("full_pt01.f3", pt.full_f3, "Full PT-01 F3 line pairs (one sub-field).")
full_f4 = _sub_field_factory("full_pt01.f4", pt.full_f4, "Full PT-01 F4 squares (one sub-field).")
full_f5 = _sub_field_factory("full_pt01.f5", pt.full_f5, "Full PT-01 F5 layer test (one sub-field).")
full_f6 = _sub_field_factory("full_pt01.f6", pt.full_f6, "Full PT-01 F6 crossings (one sub-field).")
full_f7 = _sub_field_factory("full_pt01.f7", pt.full_f7, "Full PT-01 F7 pillars (one sub-field).")


@structure_factory("voxel_pt01.gap")
def voxel_gap(context: BuildContext, *, inputs: dict, power_mw: float, gap_um: float, order: str = DEFAULT_ORDERING,
              dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ Voxel PT-01 gap cell (base, gap, lid at ``power_mw``).

    Parameters
    ----------
    context : BuildContext
    inputs : dict
        Material start file (JSON).
    power_mw : float
        Tested power (lid).
    gap_um : float
        Gap between the base top layer and the first lid layer.
    order : str
    dwell_after_power_s : float

    Returns
    -------
    ParameterFieldStructure

    Raises
    ------
    ValueError
        If a power lies outside the known attenuator range.
    """

    return _structure("voxel_pt01.gap", pt.voxel_gap_cell, context,
                      {"inputs": dict(inputs), "power_mw": float(power_mw), "gap_um": float(gap_um), "order": order},
                      dwell_after_power_s)


QUICK_FACTORIES = {1: quick_walls, 2: quick_pads}
FULL_FACTORIES = {1: full_f1, 2: full_f2, 3: full_f3, 4: full_f4, 5: full_f5, 6: full_f6, 7: full_f7}
