"""Named structure factories ``ptd01.f0`` … ``ptd01.f7`` (T144, design docs/design/TEST_PRINT_PTD01.md §4.5).

A factory is called with JSON keyword arguments only (the calibration as a dict), so
``experiment_spec.json`` holds the complete parameter set of the print and a restart rebuilds the same
field. When the experiment runs, the factory

1. builds the field with the pure builder of :mod:`.ptd01` (no ``BuildContext`` needed),
2. checks every power of the field against the attenuator calibration range **when it is known**
   (offline, e.g. ``--layout`` or the evaluation, the range is unknown and ``check_power`` would
   raise; pattern ``_check_power`` of ``mains/Experiments/chain_rectangle_doe_lens.py``),
3. returns a :class:`~.structure.ParameterFieldStructure` with the objective of the running
   experiment. Its constructor arguments are the builder arguments, never a ``ToolpathJob``.

Example::

    from nanofactorysystem.testprint.factories import f3_line_pairs
    StructureSpec("F3", factory=f3_line_pairs(calibration=cal.to_json(), label_power_mw=0.7), power_mw=0.7,
                  axes="XYZ", structure_type=StructureType.IFOV)
"""
from __future__ import annotations

from typing import Optional

from nanofactorysystem.structure_factories import BuildContext, structure_factory

from . import ptd01
from .calibration import as_stage_a
from .ordering import DEFAULT_ORDERING
from .structure import ParameterFieldStructure

__all__ = ["f0_interface", "f1_lines", "f2_bridges", "f3_line_pairs", "f4_squares", "f5_layers", "f6_crossings",
           "f7_pillars", "FACTORIES", "DEFAULT_OBJECTIVE"]

DEFAULT_OBJECTIVE = "Zeiss 63x"


def _range_known(context: BuildContext) -> bool:
    return context.power_min_mw is not None and context.power_max_mw is not None


def _structure(field_id: int, context: BuildContext, arguments: dict,
               dwell_after_power_s: float) -> ParameterFieldStructure:
    """ Build the field, check its powers (when the range is known) and wrap it as a structure. """

    field = ptd01.BUILDERS[field_id](**arguments)
    if _range_known(context):
        context.check_power(*field.powers_mw())
    structure = ParameterFieldStructure(f"ptd01.f{field_id}", arguments, objective=context.objective or DEFAULT_OBJECTIVE,
                                        power_mw=field.label_power_mw, dwell_after_power_s=dwell_after_power_s)
    structure._built = field  # already built: the same pure function of the same arguments
    return structure


def _stage_b_arguments(calibration: dict, label_power_mw: float, order: str, **axes) -> dict:
    arguments = {"calibration": dict(calibration), "label_power_mw": float(label_power_mw), "order": order}
    arguments.update({k: list(v) for k, v in axes.items() if v is not None})
    return arguments


@structure_factory("ptd01.f0")
def f0_interface(context: BuildContext, *, stage_a: dict, order: str = DEFAULT_ORDERING,
                 dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F0 interface & threshold (stage A).

    Parameters
    ----------
    context : BuildContext
        Values of the running experiment (objective, attenuator range).
    stage_a : dict
        ``StageAAxes`` JSON of the material (``stage_a_<material>.json``, D8).
    order : str
        In-layer ordering strategy (D16).
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

    if _range_known(context):
        as_stage_a(stage_a).check_range(context.power_min_mw, context.power_max_mw)
    return _structure(0, context, {"stage_a": dict(stage_a), "order": order}, dwell_after_power_s)


@structure_factory("ptd01.f1")
def f1_lines(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             passes: Optional[list] = None, order: str = DEFAULT_ORDERING,
             dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F1 line test (stage B); axes default to ``ptd01.F1_P_REL`` / ``F1_PASSES``. See :func:`f0_interface`. """

    return _structure(1, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel, passes=passes),
                      dwell_after_power_s)


@structure_factory("ptd01.f2")
def f2_bridges(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
               spans_um: Optional[list] = None, order: str = DEFAULT_ORDERING,
               dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F2 bridges (stage B). See :func:`f0_interface`. """

    return _structure(2, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel,
                                                     spans_um=spans_um), dwell_after_power_s)


@structure_factory("ptd01.f3")
def f3_line_pairs(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
                  s_rel: Optional[list] = None, order: str = DEFAULT_ORDERING,
                  dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F3 line pairs (stage B). See :func:`f0_interface`. """

    return _structure(3, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel, s_rel=s_rel),
                      dwell_after_power_s)


@structure_factory("ptd01.f4")
def f4_squares(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
               h_rel: Optional[list] = None, order: str = DEFAULT_ORDERING,
               dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F4 squares (stage B). See :func:`f0_interface`. """

    return _structure(4, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel, h_rel=h_rel),
                      dwell_after_power_s)


@structure_factory("ptd01.f5")
def f5_layers(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
              dz_rel: Optional[list] = None, order: str = DEFAULT_ORDERING,
              dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F5 layer test (stage B). See :func:`f0_interface`. """

    return _structure(5, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel, dz_rel=dz_rel),
                      dwell_after_power_s)


@structure_factory("ptd01.f6")
def f6_crossings(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
                 order: str = DEFAULT_ORDERING, dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F6 crossings (stage B). See :func:`f0_interface`. """

    return _structure(6, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel),
                      dwell_after_power_s)


@structure_factory("ptd01.f7")
def f7_pillars(context: BuildContext, *, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
               heights_um: Optional[list] = None, order: str = DEFAULT_ORDERING,
               dwell_after_power_s: float = 0.0) -> ParameterFieldStructure:
    """ F7 pillars on bases (stage B). See :func:`f0_interface`. """

    return _structure(7, context, _stage_b_arguments(calibration, label_power_mw, order, p_rel=p_rel,
                                                     heights_um=heights_um), dwell_after_power_s)


FACTORIES = {0: f0_interface, 1: f1_lines, 2: f2_bridges, 3: f3_line_pairs, 4: f4_squares, 5: f5_layers,
             6: f6_crossings, 7: f7_pillars}
