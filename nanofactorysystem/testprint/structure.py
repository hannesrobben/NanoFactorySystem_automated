"""Print a toolpath job as IFOV layer programs (T137, design docs/design/TEST_PRINT_PTD01.md §4.1).

``ParameterFieldStructure`` is the structure of one test field. It is built from a *field builder*
(a registered function name plus JSON arguments), so that ``to_json()`` / ``structure_from_json``
and a restart rebuild exactly the same field. The builder returns a
:class:`~nanofactorysystem.testprint.field.ParameterField` or a plain
:class:`~nanofactorysystem.aerobasic.slicer.toolpath.ToolpathJob`.

The translation toolpath IR → AeroBasic follows ``Model3D_Slicer.iterate_layers`` (T31) without
changing it (maintainer decision 2026-11-25; merging both is future todo F18):

- one layer program per z level, in ascending z (the experiment reverses the order for DOWN);
- inside a layer the element order of the job is kept (the order is decided by the field's
  ordering strategy); consecutive elements with the same power and the same leaf kind form one
  block: open two-point infill lines → ``IFOV_Lines``, everything else → ``IFOV_PolyLines``;
- every block sets its own power (``SET_POWER``), optionally followed by a dwell
  (``dwell_after_power_s``, decision D9 / lab check T148).
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Iterator, Optional

from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.base import DrawableAeroBasicProgram, DrawableObject
from nanofactorysystem.aerobasic.programs.drawings.lines import IFOV_Lines, ifov_writing_speed_mm_s
from nanofactorysystem.aerobasic.programs.drawings.model3d import IFOV_PolyLines
from nanofactorysystem.aerobasic.slicer.toolpath import ROLE_INFILL, ElementGroup, PathElement, ToolpathJob
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D

log = logging.getLogger(__name__)

__all__ = ["ParameterFieldStructure", "register_field_builder", "field_builder", "field_builder_names",
           "merge_groups_by_z", "Z_DECIMALS"]

# z levels are rounded to 1 nm (design §4.2): equal z = equal layer program
Z_DECIMALS = 3

_BUILDERS: dict[str, Callable[..., Any]] = {}


def register_field_builder(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """ Decorator that registers a field builder under ``name``.

    A field builder is a pure function of JSON keyword arguments that returns a ``ParameterField``
    or a ``ToolpathJob``. It must not depend on random numbers, the clock or hardware, so that a
    rebuild gives the same programs (design §9.4).

    Parameters
    ----------
    name : str
        Registry name, e.g. ``"ptd01.f3"``.

    Raises
    ------
    ValueError
        If ``name`` is registered for another function.
    """

    def register(function: Callable[..., Any]) -> Callable[..., Any]:
        existing = _BUILDERS.get(name)
        if existing is not None and existing.__qualname__ != function.__qualname__:
            raise ValueError(f"Field builder {name!r} is already registered for "
                             f"{existing.__module__}.{existing.__qualname__}.")
        _BUILDERS[name] = function
        return function

    return register


def field_builder(name: str, module: str = "") -> Callable[..., Any]:
    """ Return the builder registered under ``name``, importing ``module`` first if it is unknown.

    Raises
    ------
    KeyError
        If the builder is still unknown.
    """

    if name not in _BUILDERS and module:
        importlib.import_module(module)
    if name not in _BUILDERS:
        raise KeyError(f"Field builder {name!r} is not registered (module {module or '?'}).")
    return _BUILDERS[name]


def field_builder_names() -> list[str]:
    """ Names of all registered field builders. """

    return sorted(_BUILDERS)


def merge_groups_by_z(groups: list[ElementGroup]) -> list[ElementGroup]:
    """ Merge layer groups with the same z (rounded to 1 nm) and sort them by ascending z.

    The elements keep their order: first those of the earlier group, then those of the later one.
    Groups without z (shells) are not supported by the IFOV translation and raise.

    Parameters
    ----------
    groups : list of ElementGroup

    Returns
    -------
    list of ElementGroup
        One group per z level, ascending.

    Raises
    ------
    ValueError
        For a group without ``z_um``.
    """

    merged: dict[float, ElementGroup] = {}
    for group in groups:
        if group.z_um is None:
            raise ValueError("Shell groups (without z) cannot be printed as IFOV layers.")
        z = round(float(group.z_um), Z_DECIMALS) + 0.0  # + 0.0 turns -0.0 into 0.0
        if z not in merged:
            merged[z] = ElementGroup(kind=group.kind, elements=[], z_um=z, meta={})
        merged[z].elements.extend(group.elements)
    return [merged[z] for z in sorted(merged)]


def _is_line(element: PathElement) -> bool:
    return element.role == ROLE_INFILL and not element.closed and element.n_vertices == 2


class ParameterFieldStructure(DrawableObject):
    """ A test field (or any toolpath job) printed as IFOV layer programs with power per element.

    Parameters
    ----------
    builder : str
        Name of a registered field builder (:func:`register_field_builder`), e.g. ``"ptd01.f3"``.
    arguments : dict
        JSON keyword arguments of the builder. Stored by ``to_json()``; never a ``ToolpathJob``.
    objective : str
        Objective of the IFOV configuration. ``Experiment.build_programs()`` passes no objective to
        ``iterate_layers``, so it is a constructor argument (filled from ``BuildContext.objective``).
    power_mw : float, optional
        Structure power in mW for elements without their own power. Default: the label power of the
        field the builder returns. Per-element powers need a structure power (same rule as
        ``Model3D_Slicer``).
    center : Point3D, optional
        Structure-local centre (default origin). The field is placed by the experiment.
    dwell_after_power_s : float
        Dwell after every power change (decision D9, value from the lab check T148); 0 = none.
    builder_module : str
        Module that registers the builder; imported when the builder is not registered yet (e.g.
        when the structure is rebuilt from its JSON form). Default: ``nanofactorysystem.testprint``.

    Raises
    ------
    ValueError
        For a negative dwell or an unsupported objective.
    """

    def __init__(self, builder: str, arguments: dict, *, objective: str = "Zeiss 63x",
                 power_mw: Optional[float] = None, center: Optional[Point3D] = None,
                 dwell_after_power_s: float = 0.0, builder_module: str = "nanofactorysystem.testprint"):
        super().__init__()
        if dwell_after_power_s < 0:
            raise ValueError(f"dwell_after_power_s must be >= 0, got {dwell_after_power_s}")
        self.velocity = float(ifov_writing_speed_mm_s(objective))  # raises for an unsupported objective
        self.builder = str(builder)
        self.arguments = dict(arguments)
        self.objective = objective
        self.power_mw = None if power_mw is None else float(power_mw)
        if center is None:
            center = Point3D(0.0, 0.0, 0.0)
        elif not isinstance(center, Point3D):
            center = Point3D(X=center.X, Y=center.Y, Z=0.0)
        self.center = center
        self.dwell_after_power_s = float(dwell_after_power_s)
        self.builder_module = builder_module
        self._built: Any = None
        self._job: Optional[ToolpathJob] = None

    # ------------------------------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------------------------------
    @property
    def field(self):
        """ What the builder returned (a ``ParameterField`` or a ``ToolpathJob``), built once. """

        if self._built is None:
            self._built = field_builder(self.builder, self.builder_module)(**self.arguments)
        return self._built

    @property
    def structure_power_mw(self) -> Optional[float]:
        """ The power of elements without their own power: ``power_mw`` or the field's label power. """

        if self.power_mw is not None:
            return self.power_mw
        return getattr(self.field, "label_power_mw", None)

    @property
    def toolpath_job(self) -> ToolpathJob:
        """ The job in structure-local µm, layers merged by z and sorted ascending.

        Raises
        ------
        ValueError
            If elements carry their own power but there is no structure power, or for shell groups.
        """

        if self._job is None:
            built = self.field
            job = built if isinstance(built, ToolpathJob) else built.to_toolpath_job(self.objective)
            if self.structure_power_mw is None and any(e.power_mw is not None for g in job.groups for e in g):
                raise ValueError("Power per element needs the power of the structure (power_mw=...) for the "
                                 "elements without their own power.")
            job.groups = merge_groups_by_z(job.groups)
            self._job = job
        return self._job

    # ------------------------------------------------------------------------------------------
    # DrawableObject contract
    # ------------------------------------------------------------------------------------------
    @property
    def center_point(self) -> Point3D:
        """ Structure-local centre used by the experiment for placement. """

        return self.center

    def _runs(self, group: ElementGroup) -> list[tuple[str, Optional[float], list[PathElement]]]:
        """ Consecutive elements of the same leaf kind and power: ``(kind, power, elements)``. """

        runs: list[tuple[str, Optional[float], list[PathElement]]] = []
        for element in group.elements:
            kind = "lines" if _is_line(element) else "polylines"
            power = element.power_mw if element.power_mw is not None else self.structure_power_mw
            if not runs or runs[-1][0] != kind or runs[-1][1] != power:
                runs.append((kind, power, []))
            runs[-1][2].append(element)
        return runs

    def _block(self, coordinate_system: CoordinateSystem, reference_point: Point3D, kind: str,
               power: Optional[float], elements: list[PathElement]) -> AeroBasicProgram:
        if kind == "lines":
            leaf = IFOV_Lines(reference_point=reference_point,
                              lines=[[Point2D(X=float(e.points[0][0]), Y=float(e.points[0][1])),
                                      Point2D(X=float(e.points[1][0]), Y=float(e.points[1][1]))] for e in elements],
                              velocity=self.velocity, power=power)
        else:
            leaf = IFOV_PolyLines(reference_point=reference_point,
                                  polylines=[[Point2D(X=float(p[0]), Y=float(p[1])) for p in e.points]
                                             for e in elements],
                                  velocity=self.velocity, power=power, closed=[bool(e.closed) for e in elements])
        program = DrawableAeroBasicProgram(coordinate_system)
        for sub_program in leaf.iterate_layers(coordinate_system, objective=self.objective):
            program.add_programm(sub_program)
        return program

    def _insert_dwell(self, program: AeroBasicProgram) -> None:
        """ Insert ``DWELL`` right after the first power line (``$AO[0].A=…``) of a block. """

        dwell = AeroBasicProgram()
        dwell.DWELL(self.dwell_after_power_s)
        for index, line in enumerate(program.lines):
            if line.startswith("$AO[0].A="):
                program.lines[index + 1:index + 1] = [f"' Dwell after the power change (D9)", *dwell.lines]
                return

    def iterate_layers(self, coordinate_system: CoordinateSystem,
                       plot_name: Optional[str] = None) -> Iterator[DrawableAeroBasicProgram]:
        """ Yield one IFOV program per z level in ascending z.

        Parameters
        ----------
        coordinate_system : CoordinateSystem
            Coordinate system of the experiment.
        plot_name : str, optional
            Accepted for ``draw_on`` compatibility; unused.

        Yields
        ------
        DrawableAeroBasicProgram
            One program per layer, with one IFOV block per run of equal power and leaf kind.
        """

        del plot_name
        for group in self.toolpath_job.groups:
            runs = self._runs(group)
            if not runs:
                continue
            reference_point = Point3D(X=self.center.X, Y=self.center.Y, Z=self.center.Z + float(group.z_um))
            layer_program = DrawableAeroBasicProgram(coordinate_system)
            previous_power: Any = object()  # the power before the layer program is unknown
            for kind, power, elements in runs:
                block = self._block(coordinate_system, reference_point, kind, power, elements)
                if self.dwell_after_power_s > 0 and power is not None and power != previous_power:
                    self._insert_dwell(block)
                previous_power = power
                layer_program.add_programm(block)
            yield layer_program

    # ------------------------------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------------------------------
    @property
    def element_powers_mw(self) -> list[float]:
        """ Distinct laser powers the structure prints with, in mW. """

        powers = {e.power_mw if e.power_mw is not None else self.structure_power_mw
                  for g in self.toolpath_job.groups for e in g.elements}
        return sorted(float(p) for p in powers if p is not None)

    def statistics(self) -> dict[str, Any]:
        """ Layers, IFOV blocks, elements, mark length and powers of the structure.

        Returns
        -------
        dict
            ``n_layers``, ``n_blocks``, ``n_power_changes``, ``n_elements``, ``mark_length_um``,
            ``z_levels_um``, ``element_powers_mw``.
        """

        job = self.toolpath_job
        n_blocks = n_changes = 0
        for group in job.groups:
            previous: Any = object()
            for _, power, _ in self._runs(group):
                n_blocks += 1
                n_changes += power != previous
                previous = power
        return {"n_layers": len(job.groups), "n_blocks": n_blocks, "n_power_changes": n_changes,
                "n_elements": job.n_elements, "mark_length_um": round(job.mark_length_um, 3),
                "z_levels_um": [g.z_um for g in job.groups], "element_powers_mw": self.element_powers_mw}

    def to_json(self) -> dict[str, Any]:
        """ Constructor arguments (rebuildable with ``structure_from_json``) plus ``statistics``. """

        data = super().to_json()
        data["statistics"] = self.statistics()
        return data

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.builder!r}, {self.objective})"
