"""Test field: cells, header, merge by z, validation, cell table (T139, design §4.3).

A :class:`ParameterField` is a 50 × 50 µm area (field coordinates centred on the field, x right,
y up). The cells lie in ``y < size/2 - header``; the header strip ``y ≥ size/2 - header`` holds the
L mark, the 3-bit field id and (stage B) the REF pad. Row 0 is the lowest row (y axis = power).

``to_toolpath_job()`` moves the cells into field coordinates, merges all groups of equal z (rounded
to 1 nm) into one layer and orders the elements of every layer with the field's ordering strategy
(:mod:`.ordering`). ``cell_table()`` lists every cell with its absolute and normalised parameters;
it is a pure function of the field, so the evaluation (T147) regenerates it from the factory
arguments stored in ``/spec``.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from nanofactorysystem.aerobasic.slicer import JobParameters, LaserParameters
from nanofactorysystem.aerobasic.slicer.toolpath import ElementGroup, ToolpathJob

from . import cells as _cells
from .ordering import DEFAULT_ORDERING, ordering
from .structure import merge_groups_by_z

__all__ = ["CellSpec", "ParameterField", "FieldLayoutError", "build_header", "grid_centers", "packed_centers",
           "LINE", "VOLUME"]

LINE = "line"
VOLUME = "volume"
HEADER_CELL = "header"


class FieldLayoutError(ValueError):
    """ The field layout is invalid; ``problems`` lists every problem found. """

    def __init__(self, name: str, problems: list[str]):
        self.problems = list(problems)
        super().__init__(f"Field {name}: {len(problems)} layout problem(s):\n  - " + "\n  - ".join(problems))


@dataclass(frozen=True)
class CellSpec:
    """ One parameter combination of a field.

    Parameters
    ----------
    cell_id : str
        E.g. ``"F3-r2c4"``.
    row, col : int
        Grid position (row 0 = lowest y).
    center_um : (float, float)
        Cell centre in field coordinates.
    params : dict
        Absolute parameters, e.g. ``{"power_mw": …, "spacing_um": …}``.
    params_rel : dict
        Normalised parameters, e.g. ``{"p_rel": 1.5, "s_rel": 1.0}`` (empty in stage A).
    primitive : str
        Name of the cell primitive(s).
    groups : tuple of ElementGroup
        Geometry in cell-local µm (not compared, not in the cell table).
    kind : {"line", "volume"}
        Decides the default minimum gap to other cells (decision D5).
    min_gap_um : float, optional
        Minimum gap to other cells instead of the field default of ``kind``.
    anchor_depth_um : float
        Substrate anchoring of the cell (decision D15), for the cell table.
    """

    cell_id: str
    row: int
    col: int
    center_um: tuple
    params: dict
    params_rel: dict
    primitive: str
    groups: tuple = field(default=(), compare=False, repr=False)
    kind: str = LINE
    min_gap_um: Optional[float] = None
    anchor_depth_um: float = 0.0

    def bounds_um(self) -> tuple[float, float, float, float]:
        """ Bounding box ``(x_min, y_min, x_max, y_max)`` of the cell's elements in field coordinates. """

        x0, y0, x1, y1 = _cells.groups_bounds(self.groups)
        cx, cy = self.center_um
        return x0 + cx, y0 + cy, x1 + cx, y1 + cy

    def field_groups(self) -> list[ElementGroup]:
        """ Copies of the groups in field coordinates, elements tagged with ``row`` and ``col``. """

        moved = _cells.translate_groups(self.groups, float(self.center_um[0]), float(self.center_um[1]))
        for group in moved:
            for element in group.elements:
                element.meta.update(cell=self.cell_id, row=int(self.row), col=int(self.col))
        return moved


def grid_centers(n_rows: int, n_cols: int, *, size_um: float = 50.0, header_um: float = 5.0) -> dict:
    """ Centres of an evenly spaced ``n_rows × n_cols`` grid in the cell area of a field.

    Returns
    -------
    dict
        ``(row, col) -> (x, y)``; row 0 is the lowest row.
    """

    height = size_um - header_um
    return {(r, c): (-size_um / 2 + (c + 0.5) * size_um / n_cols, -size_um / 2 + (r + 0.5) * height / n_rows)
            for r in range(n_rows) for c in range(n_cols)}


def packed_centers(widths: Sequence[float], gap_um: float) -> list[float]:
    """ Centres of items of the given widths placed side by side with ``gap_um``, centred on 0. """

    total = sum(widths) + gap_um * (len(widths) - 1)
    centers, position = [], -total / 2
    for width in widths:
        centers.append(position + width / 2)
        position += width + gap_um
    return centers


def build_header(field_id: int, *, label_power_mw: float, size_um: float = 50.0, header_um: float = 5.0,
                 z_um: float = 0.0, ref_pad: Optional[list[ElementGroup]] = None, mark_um: float = 3.0,
                 dot_pitch_um: float = 1.5, half: str = "") -> tuple[ElementGroup, ...]:
    """ Header of a field in field coordinates: L mark, 3-bit field id and optional REF pad.

    The L mark (one polyline, legs of ``mark_um``) sits at the left of the header strip. The field id
    is written most significant bit first as dots to the right of it: a dot for a 1, nothing for a 0
    (field 0 has no dot). With ``half`` (parameter tests, version 2) a fourth bit follows: 0 for
    sub-field ``"a"``, 1 for ``"b"``. The REF pad (cell-local groups, e.g. a sliced 4 × 4 × 1 µm pad at P_ref)
    is centred at the right end of the strip.

    Parameters
    ----------
    field_id : int
        0 … 7.
    label_power_mw : float
        Power of the L mark and the dots.
    size_um, header_um : float
        Field size and header height.
    z_um : float
        z of the L mark and the dots.
    ref_pad : list of ElementGroup, optional
        REF pad in cell-local coordinates (stage B).
    mark_um, dot_pitch_um : float
        Leg length of the L mark and dot distance.
    half : {"", "a", "b"}
        Sub-field; empty: no fourth bit.

    Returns
    -------
    tuple of ElementGroup
        Elements tagged ``cell="header"``, ``row=col=-1``.

    Raises
    ------
    ValueError
        For a field id outside 0 … 7.
    """

    if not 0 <= int(field_id) <= 7:
        raise ValueError(f"field_id must be 0 ... 7 (3 bits), got {field_id}")
    if half not in ("", "a", "b"):
        raise ValueError(f"half must be '', 'a' or 'b', got {half!r}")
    x0 = -size_um / 2 + 1.0
    y0 = size_um / 2 - header_um + 1.0
    groups = _cells.polyline(HEADER_CELL, points=[(x0, y0 + mark_um), (x0, y0), (x0 + mark_um, y0)],
                             power_mw=label_power_mw, z_um=z_um, part="L_mark")
    for i in range(3):
        if (int(field_id) >> (2 - i)) & 1:
            groups += _cells.dot(HEADER_CELL, x_um=x0 + mark_um + dot_pitch_um * (i + 1), y_um=y0 + mark_um / 2,
                                 power_mw=label_power_mw, z_um=z_um, part=f"id_bit{2 - i}")
    if half == "b":
        groups += _cells.dot(HEADER_CELL, x_um=x0 + mark_um + dot_pitch_um * 4, y_um=y0 + mark_um / 2,
                             power_mw=label_power_mw, z_um=z_um, part="half_bit")
    if ref_pad:
        pad_x0, _, pad_x1, _ = _cells.groups_bounds(ref_pad)
        groups += _cells.translate_groups(ref_pad, size_um / 2 - 1.0 - pad_x1, size_um / 2 - header_um / 2)
        for group in groups[-len(ref_pad):]:
            for element in group.elements:
                element.meta.update(cell=HEADER_CELL, part="anchor" if element.meta.get("part") == "anchor"
                                    else "ref_pad")
    for group in groups:
        for element in group.elements:
            element.meta.update(row=-1, col=-1)
    return tuple(groups)


@dataclass(frozen=True)
class ParameterField:
    """ A test field: cells with their own parameters plus a header.

    Parameters
    ----------
    field_id : int
        0 … 7, written as 3-bit dots.
    name : str
        E.g. ``"F3_line_pairs"``.
    cells : tuple of CellSpec
    label_power_mw : float
        Power of the header elements; the structure power of the field.
    header_groups : tuple of ElementGroup
        Header in field coordinates (:func:`build_header`).
    size_um, header_um : float
        Field size (50 µm) and header strip height (5 µm).
    order : str
        In-layer ordering strategy (decision D16: ``"row_by_row"``).
    min_gap_line_um, min_gap_volume_um : float
        Minimum gaps between cell bounding boxes (decision D5: 2 / 4.5 µm).
    z_min_um, z_max_um : float
        Allowed z range of all elements.
    power_range_mw : (float, float), optional
        Validity range of the voxel model; every cell power must lie inside (stage B).
    meta : dict
        Axis levels and other field information (JSON values).
    half : {"", "a", "b"}
        Sub-field of the parameter tests (version 2); column ``half`` of the cell table.
    """

    field_id: int
    name: str
    cells: tuple
    label_power_mw: float
    header_groups: tuple = field(default=(), compare=False, repr=False)
    size_um: float = 50.0
    header_um: float = 5.0
    order: str = DEFAULT_ORDERING
    min_gap_line_um: float = 2.0
    min_gap_volume_um: float = 4.5
    z_min_um: float = -3.0
    z_max_um: float = 30.0
    power_range_mw: Optional[tuple] = None
    meta: dict = field(default_factory=dict)
    half: str = ""

    # ------------------------------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------------------------------
    def _required_gap(self, cell: CellSpec) -> float:
        if cell.min_gap_um is not None:
            return float(cell.min_gap_um)
        return self.min_gap_volume_um if cell.kind == VOLUME else self.min_gap_line_um

    def problems(self) -> list[str]:
        """ Every layout problem of the field (empty list: valid).

        Checks: unique cell ids, every element inside the field, cells below the header strip and
        header elements inside it, the gap between cell bounding boxes, the z range, cell powers
        inside ``power_range_mw`` and a known ordering strategy.
        """

        found: list[str] = []
        half, header_y = self.size_um / 2, self.size_um / 2 - self.header_um
        ids = [c.cell_id for c in self.cells]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            found.append(f"duplicate cell ids {duplicates}")
        try:
            ordering(self.order)
        except ValueError as error:
            found.append(str(error))
        boxes = {}
        for cell in self.cells:
            if not cell.groups:
                found.append(f"cell {cell.cell_id} has no elements")
                continue
            x0, y0, x1, y1 = boxes[cell.cell_id] = cell.bounds_um()
            if x0 < -half - 1e-9 or x1 > half + 1e-9 or y0 < -half - 1e-9 or y1 > half + 1e-9:
                found.append(f"cell {cell.cell_id} lies outside the field ({x0:.2f}, {y0:.2f}) - ({x1:.2f}, {y1:.2f})")
            elif y1 > header_y + 1e-9:
                found.append(f"cell {cell.cell_id} reaches into the header strip (y up to {y1:.2f} > {header_y:.2f})")
            for group in cell.groups:
                if not self.z_min_um <= group.z_um <= self.z_max_um:
                    found.append(f"cell {cell.cell_id}: z = {group.z_um} outside {self.z_min_um} ... {self.z_max_um}")
                    break
            if self.power_range_mw is not None:
                low, high = self.power_range_mw
                outside = sorted({e.power_mw for g in cell.groups for e in g.elements
                                  if not low - 1e-12 <= e.power_mw <= high + 1e-12})
                if outside:
                    found.append(f"cell {cell.cell_id}: powers {outside} mW outside the voxel model range "
                                 f"{low:g} - {high:g} mW")
        if self.header_groups:
            x0, y0, x1, y1 = _cells.groups_bounds(self.header_groups)
            if x0 < -half - 1e-9 or x1 > half + 1e-9 or y0 < header_y - 1e-9 or y1 > half + 1e-9:
                found.append(f"header elements leave the header strip ({x0:.2f}, {y0:.2f}) - ({x1:.2f}, {y1:.2f})")
        placed = [c for c in self.cells if c.cell_id in boxes]
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                ax0, ay0, ax1, ay1 = boxes[a.cell_id]
                bx0, by0, bx1, by1 = boxes[b.cell_id]
                gap = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1)
                required = max(self._required_gap(a), self._required_gap(b))
                if gap < required - 1e-9:
                    found.append(f"cells {a.cell_id} and {b.cell_id}: gap {gap:.2f} um < {required:g} um")
        return found

    def validate(self) -> None:
        """ Raise :class:`FieldLayoutError` listing every problem, if there is one. """

        found = self.problems()
        if found:
            raise FieldLayoutError(self.name, found)

    # ------------------------------------------------------------------------------------------
    # Toolpath
    # ------------------------------------------------------------------------------------------
    def to_toolpath_job(self, objective: Optional[str] = None) -> ToolpathJob:
        """ All cells and the header as one job in field coordinates.

        Groups of equal z (rounded to 1 nm) are merged into one layer; the elements of every layer
        are ordered with the strategy ``order``.

        Parameters
        ----------
        objective : str, optional
            Stored in ``job.meta`` (the IFOV configuration is chosen by the structure).

        Returns
        -------
        ToolpathJob

        Raises
        ------
        FieldLayoutError
            If the layout is invalid.
        """

        self.validate()
        groups = list(_cells.translate_groups(self.header_groups))
        for cell in sorted(self.cells, key=lambda c: (c.row, c.col)):
            groups += cell.field_groups()
        strategy = ordering(self.order)
        layers = merge_groups_by_z(groups)
        for layer in layers:
            layer.elements = strategy(layer.elements)
        params = JobParameters(laser=LaserParameters(power_mw=float(self.label_power_mw)))
        return ToolpathJob(params=params, groups=layers, source_file=self.name,
                           recipe=[{"step": "parameter_field", "field_id": self.field_id, "order": self.order}],
                           meta={"field": self.name, "field_id": self.field_id, "objective": objective,
                                 "n_cells": len(self.cells)})

    def powers_mw(self) -> list[float]:
        """ All distinct element powers of the field (cells and header), sorted. """

        groups = list(self.header_groups) + [g for c in self.cells for g in c.groups]
        return sorted({float(e.power_mw) for g in groups for e in g.elements if e.power_mw is not None})

    def z_levels_um(self) -> list[float]:
        """ The distinct z levels (= layer programs) of the field. """

        groups = list(self.header_groups) + [g for c in self.cells for g in c.groups]
        return [g.z_um for g in merge_groups_by_z(groups)]

    # ------------------------------------------------------------------------------------------
    # Cell table and plot
    # ------------------------------------------------------------------------------------------
    def cell_table(self) -> list[dict[str, Any]]:
        """ One row per cell: field, cell id, grid position, centre, kind, anchoring, bounding box,
        absolute and normalised parameters.

        Returns
        -------
        list of dict
        """

        rows = []
        for cell in sorted(self.cells, key=lambda c: (c.row, c.col)):
            x0, y0, x1, y1 = cell.bounds_um() if cell.groups else (None,) * 4
            row = {"field_id": self.field_id, "field": self.name, "half": self.half, "cell_id": cell.cell_id,
                   "row": cell.row,
                   "col": cell.col, "x_um": round(float(cell.center_um[0]), 4),
                   "y_um": round(float(cell.center_um[1]), 4), "primitive": cell.primitive, "kind": cell.kind,
                   "anchor_depth_um": cell.anchor_depth_um,
                   "bbox_x_min_um": None if x0 is None else round(x0, 4),
                   "bbox_y_min_um": None if y0 is None else round(y0, 4),
                   "bbox_x_max_um": None if x1 is None else round(x1, 4),
                   "bbox_y_max_um": None if y1 is None else round(y1, 4)}
            row.update(cell.params)
            row.update(cell.params_rel)
            rows.append(row)
        return rows

    def write_cell_table(self, path, extra_columns: Sequence[str] = ()) -> Path:
        """ Write :meth:`cell_table` as CSV (UTF-8), optionally with empty extra columns.

        Parameters
        ----------
        path : path-like
        extra_columns : sequence of str
            Empty columns appended for measured values (e.g. ``width_um``).

        Returns
        -------
        Path
        """

        rows = self.cell_table()
        return write_rows(path, rows, extra_columns)

    def plot(self, ax=None):
        """ Top view of the field: elements coloured by power, cell ids, header strip.

        Returns
        -------
        matplotlib.axes.Axes
        """

        import matplotlib.pyplot as plt
        from matplotlib import cm, colors

        if ax is None:
            _, ax = plt.subplots(figsize=(7, 7))
        powers = self.powers_mw()
        norm = colors.Normalize(min(powers), max(powers) if max(powers) > min(powers) else min(powers) + 1)
        half = self.size_um / 2
        ax.plot([-half, half, half, -half, -half], [-half, -half, half, half, -half], color="0.5", lw=0.8)
        ax.axhline(half - self.header_um, color="0.7", lw=0.6, ls="--")
        groups = list(self.header_groups) + [g for c in self.cells for g in c.field_groups()]
        for group in groups:
            for element in group.elements:
                points = element.points
                if element.closed:
                    points = list(points) + [points[0]]
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                ax.plot(xs, ys, color=cm.viridis(norm(element.power_mw)), lw=0.6)
        for cell in self.cells:
            ax.text(cell.center_um[0], cell.center_um[1], cell.cell_id.split("-")[-1], fontsize=5, ha="center",
                    va="center", color="crimson")
        ax.set_aspect("equal")
        ax.set_title(f"{self.name} (field {self.field_id})")
        ax.set_xlabel("x / µm")
        ax.set_ylabel("y / µm")
        return ax


def write_rows(path, rows: list[dict[str, Any]], extra_columns: Sequence[str] = ()) -> Path:
    """ Write table rows (dicts) as CSV; the columns are the union of all keys in first-seen order. """

    columns: list[str] = []
    for row in rows:
        columns += [k for k in row if k not in columns]
    columns += [c for c in extra_columns if c not in columns]
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})
    return path
