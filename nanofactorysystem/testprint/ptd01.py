"""Field builders of the standard test print PTD-01 (T141–T143, design docs/design/TEST_PRINT_PTD01.md §5).

Every builder is a pure function of JSON arguments (the stage-A axes or the process calibration as a
dict) and returns a :class:`~nanofactorysystem.testprint.field.ParameterField`. It is registered as a
field builder ``"ptd01.f<n>"``, so ``ParameterFieldStructure("ptd01.f3", arguments)`` and the
evaluation (T147) rebuild exactly the same field. No builder depends on a ``BuildContext``.

Axis levels are module constants (one place for a later revision). The y axis of every field is the
laser power (row 0 = lowest power, at the bottom), the x axis the parameter under test.

Conventions (decisions of 2026-11-25):

- Line fields are written at the interface working point ``z0`` of the calibration.
- Volume cells (pads, wedges, caps, pedestals, bases, REF pad) are anchored ``ANCHOR_DEPTH_UM`` = 1.5 µm
  into the substrate (D15).
- Supporting volumes (F2 pedestals, F7 bases, REF pad) are written at ``P_ref`` with hatch and slice
  distance ``VOLUME_H_REL · w(P_ref)`` and ``VOLUME_DZ_REL · l(P_ref)``.
- Fields that need the voxel size at the cell power (F3, F4, F5, F7) start at ``p_rel = 1.25``: the
  threshold model has zero size at ``P_th``, so the fit model is only valid above it. Their cell
  powers must lie inside the validity range of the model (checked by the field validation).
"""
from __future__ import annotations

from typing import Optional

from nanofactorysystem.aerobasic.slicer import SlicingParameters

from . import cells
from .calibration import ProcessCalibration, as_calibration, as_stage_a
from .field import LINE, VOLUME, CellSpec, ParameterField, build_header, grid_centers, packed_centers
from .ordering import DEFAULT_ORDERING
from .structure import register_field_builder

__all__ = ["field_f0", "field_f1", "field_f2", "field_f3", "field_f4", "field_f5", "field_f6", "field_f7",
           "FIELD_NAMES", "BUILDERS"]

FIELD_SIZE_UM = 50.0
HEADER_UM = 5.0
ANCHOR_DEPTH_UM = 1.5                    # D15
VOLUME_H_REL = 0.5                       # supporting volumes at P_ref: hatch = 0.5 w(P_ref)
VOLUME_DZ_REL = 0.5                      # supporting volumes at P_ref: slice = 0.5 l(P_ref)
REF_PAD_UM = (4.0, 4.0, 1.0)             # REF pad x, y, height
PIXEL_UM = cells.DEFAULT_PIXEL_UM
EDGE_UM = 2 * PIXEL_UM                   # sliced edges are interpolated over one pixel: pack volumes with this margin

# F0 interface & threshold: powers and z offsets come from the stage-A file (D8)
F0_LINE_LENGTH_UM = 4.0

# F1 line test: 2 x-lines + 2 y-lines per cell, written n times
F1_P_REL = (1.0, 1.3, 1.6, 1.9, 2.2, 2.5)
F1_PASSES = (1, 2, 3, 4)
F1_LINE_LENGTH_UM = 5.0                  # the concept's ~7 µm does not fit 6 rows (7.5 µm pitch)
F1_LINE_PITCH_UM = 2.5

# F2 bridges (D11)
F2_P_REL = (1.0, 1.3, 1.6, 1.9, 2.2, 2.5)
F2_SPANS_UM = (2.0, 4.0, 7.0, 10.0)
F2_PEDESTAL_UM = (2.0, 3.0, 3.0)         # x, y, height
F2_GAP_UM = 2.0

# F3 line pairs: a pair above a group of five lines, centre distance s = s_rel · w(P)
F3_P_REL = (1.25, 1.5, 1.75, 2.0, 2.25)
F3_S_REL = (0.5, 0.8, 1.1, 1.4, 1.7, 2.0)
F3_LINE_LENGTH_UM = 6.0
F3_GROUP_GAP_UM = 1.5                    # free distance between the pair and the group

# F4 squares: 6 × 6 µm pads, 3 layers of dz = 0.5 l(P), ramp on +x, hatch along x
F4_P_REL = (1.25, 1.5, 1.75, 2.0)
F4_H_REL = (0.3, 0.5, 0.75, 1.0)
F4_PAD_UM = 6.0
F4_RAMP_UM = 1.6
F4_LAYERS = 3
F4_DZ_REL = 0.5

# F5 layer test: wedges (rows of p_rel) and caps at P_ref (top row), slice distance per column
F5_P_REL = (1.25, 1.5, 1.75)
F5_DZ_REL = (0.15, 0.25, 0.4, 0.6)
F5_H_REL = 0.5
F5_WEDGE_UM = (8.0, 6.0, 3.0)            # length x, width y, height (20.6°)
F5_CAP_UM = (8.0, 2.0)                   # diameter, height

# F6 crossings: star / 3 × 3 grid / woodpile (rows), p_rel (columns)
F6_P_REL = (1.0, 1.25, 1.5, 1.75, 2.0)
F6_TYPES = ("star", "grid", "woodpile")
F6_LINE_LENGTH_UM = 6.0
F6_GRID_PITCH_UM = 2.5
F6_ROD_PITCH_UM = 1.5
F6_WOODPILE_LAYERS = 4
F6_WOODPILE_DZ_REL = 0.6                 # dz = 0.6 l0

# F7 pillars on bases (D10)
F7_P_REL = (1.25, 1.5, 1.75, 2.0)
F7_HEIGHTS_UM = (2.0, 4.0, 6.0, 8.0, 10.0)
F7_PILLAR_DIAMETER_UM = 1.5
F7_BASE_UM = (6.0, 6.0, 1.4)
F7_H_REL = 0.5
F7_DZ_REL = 0.5

FIELD_NAMES = {0: "F0_interface", 1: "F1_lines", 2: "F2_bridges", 3: "F3_line_pairs", 4: "F4_squares",
               5: "F5_layers", 6: "F6_crossings", 7: "F7_pillars"}


# ----------------------------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------------------------
def _mw(power_mw: float) -> float:
    """ Powers are rounded to 1 nW, so programs and tables show 0.45 instead of 0.44999999999999996. """

    return round(float(power_mw), 6)


def _slicing(hatch_um: float, dz_um: float, strategy: str = "linear_x") -> SlicingParameters:
    return SlicingParameters(layer_height_um=round(dz_um, 6), hatch_spacing_um=round(hatch_um, 6),
                             hatch_strategy=strategy, num_contour_lines=0, contour_offset_um=0.0)


def _support_slicing(cal: ProcessCalibration) -> SlicingParameters:
    p_ref = cal.p_ref_mw
    return _slicing(cal.hatch_um(VOLUME_H_REL, p_ref), cal.slice_um(VOLUME_DZ_REL, p_ref), "alternating")


def _ref_pad(cal: ProcessCalibration) -> list:
    x, y, h = REF_PAD_UM
    return cells.sliced("header", height_map_um=cells.pad_map(x, y, h), pixel_um=PIXEL_UM,
                        slicing=_support_slicing(cal), power_mw=_mw(cal.p_ref_mw), anchor_depth_um=ANCHOR_DEPTH_UM,
                        part="ref_pad")


def _cell_id(field_id: int, row: int, col: int) -> str:
    return f"F{field_id}-r{row}c{col}"


def _stage_b_field(field_id: int, cal: ProcessCalibration, field_cells: list, label_power_mw: float, *,
                   uses_model_at_cell_power: bool, order: str, meta: dict) -> ParameterField:
    header = build_header(field_id, label_power_mw=label_power_mw, z_um=cal.z0_um, ref_pad=_ref_pad(cal))
    meta = {"stage": "B", "p_th_mw": cal.p_th_mw, "p_ref_mw": cal.p_ref_mw, "z0_um": cal.z0_um,
            "w0_um": round(cal.w0_um, 6), "l0_um": round(cal.l0_um, 6), "calibration_source": cal.source, **meta}
    return ParameterField(field_id, FIELD_NAMES[field_id], tuple(field_cells), float(label_power_mw),
                          header_groups=header, order=order,
                          power_range_mw=cal.voxel_model.valid_power_mw if uses_model_at_cell_power else None,
                          meta=meta)


def _row_centers(heights: list[float], gap_um: float) -> list[float]:
    """ y centres of rows of the given heights, packed with ``gap_um`` and centred in the cell area. """

    area_center = -HEADER_UM / 2
    return [area_center + y for y in packed_centers(heights, gap_um)]


# ----------------------------------------------------------------------------------------------
# F0 – F2 (T141)
# ----------------------------------------------------------------------------------------------
@register_field_builder("ptd01.f0")
def field_f0(*, stage_a: dict, line_length_um: float = F0_LINE_LENGTH_UM,
             order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F0 interface & threshold: log power ladder (rows) × z offset (columns), one line per cell.

    Every z offset is its own layer program; every power its own IFOV block in it (10 × 8: 8 layers
    + header, 80 blocks).

    Parameters
    ----------
    stage_a : dict
        ``StageAAxes`` JSON (powers, z offsets, label power, label z).
    line_length_um : float
    order : str
        In-layer ordering strategy.

    Returns
    -------
    ParameterField
    """

    axes = as_stage_a(stage_a)
    levels, offsets = axes.levels_mw(), axes.z_offsets_um
    centers = grid_centers(len(levels), len(offsets), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    field_cells = []
    for r, power in enumerate(levels):
        for c, z in enumerate(offsets):
            cid = _cell_id(0, r, c)
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)], {"power_mw": power, "z_offset_um": z},
                                        {}, "line",
                                        groups=tuple(cells.line(cid, length_um=line_length_um, power_mw=power,
                                                                z_um=z))))
    header = build_header(0, label_power_mw=axes.label_power_mw, z_um=axes.label_z_um)
    return ParameterField(0, FIELD_NAMES[0], tuple(field_cells), axes.label_power_mw, header_groups=header,
                          order=order, meta={"stage": "A", "material": axes.material, "powers_mw": levels,
                                             "z_offsets_um": list(offsets), "line_length_um": line_length_um})


@register_field_builder("ptd01.f1")
def field_f1(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             passes: Optional[list] = None, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F1 line test: p_rel (rows) × number of passes (columns); 2 x-lines and 2 y-lines per cell at z0.

    Parameters
    ----------
    calibration : dict
        ``ProcessCalibration`` JSON.
    label_power_mw : float
        Power of the header marks.
    p_rel, passes : list, optional
        Axis levels (default ``F1_P_REL``, ``F1_PASSES``).
    order : str

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F1_P_REL if p_rel is None else p_rel)
    passes = [int(n) for n in (F1_PASSES if passes is None else passes)]
    centers = grid_centers(len(p_rel), len(passes), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    half = F1_LINE_LENGTH_UM / 2
    x_pair = -(half + F1_LINE_PITCH_UM / 4)       # x-lines left, y-lines right of the cell centre
    y_pair = F1_LINE_PITCH_UM / 2 + F1_LINE_PITCH_UM / 4
    field_cells = []
    for r, rel in enumerate(p_rel):
        power = _mw(cal.power_mw(rel))
        for c, n in enumerate(passes):
            cid = _cell_id(1, r, c)
            groups = cells.line_set(cid, n=2, pitch_um=F1_LINE_PITCH_UM, length_um=F1_LINE_LENGTH_UM,
                                    power_mw=power, direction="x", z_um=cal.z0_um, passes=n,
                                    offset_um=(x_pair, 0.0), part="x_lines")
            groups += cells.line_set(cid, n=2, pitch_um=F1_LINE_PITCH_UM, length_um=F1_LINE_LENGTH_UM,
                                     power_mw=power, direction="y", z_um=cal.z0_um, passes=n,
                                     offset_um=(y_pair, 0.0), part="y_lines")
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)],
                                        {"power_mw": round(power, 6), "passes": n, "z_um": cal.z0_um,
                                         "line_length_um": F1_LINE_LENGTH_UM}, {"p_rel": rel}, "line_set",
                                        groups=tuple(groups)))
    return _stage_b_field(1, cal, field_cells, label_power_mw, uses_model_at_cell_power=False, order=order,
                          meta={"p_rel": p_rel, "passes": passes})


@register_field_builder("ptd01.f2")
def field_f2(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             spans_um: Optional[list] = None, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F2 bridges: p_rel (rows) × span (columns); a line between two pedestals written at P_ref.

    The line lies inside the pedestal top, ``z = pedestal height - l0/2`` (design §9.1: with the
    descending print order of the 63x the line is written first and the pedestals grow into it), and
    reaches to the pedestal centres. Pedestals 2 × 3 × 3 µm, gap 2 µm between cells (D11).

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F2_P_REL if p_rel is None else p_rel)
    spans = [float(s) for s in (F2_SPANS_UM if spans_um is None else spans_um)]
    px, py, ph = F2_PEDESTAL_UM
    line_z = round(ph - cal.l0_um / 2, 3)
    support = _support_slicing(cal)
    x_centers = packed_centers([s + 2 * px + EDGE_UM for s in spans], F2_GAP_UM)
    y_centers = _row_centers([py] * len(p_rel), (FIELD_SIZE_UM - HEADER_UM - py * len(p_rel)) / len(p_rel))
    field_cells = []
    for r, rel in enumerate(p_rel):
        power = _mw(cal.power_mw(rel))
        for c, span in enumerate(spans):
            cid = _cell_id(2, r, c)
            groups = []
            for side in (-1, 1):
                pedestal = cells.sliced(cid, height_map_um=cells.pedestal_map(px, py, ph), pixel_um=PIXEL_UM,
                                        slicing=support, power_mw=_mw(cal.p_ref_mw), anchor_depth_um=ANCHOR_DEPTH_UM,
                                        offset_um=(side * (span + px) / 2, 0.0), part="pedestal")
                groups += pedestal
            groups += cells.suspended_line(cid, span_um=span, z_um=line_z, power_mw=power, extend_um=px / 2)
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": round(power, 6), "span_um": span, "line_z_um": line_z,
                                         "pedestal_power_mw": round(cal.p_ref_mw, 6)}, {"p_rel": rel},
                                        "sliced+suspended_line", groups=tuple(groups), kind=VOLUME,
                                        min_gap_um=F2_GAP_UM, anchor_depth_um=ANCHOR_DEPTH_UM))
    return _stage_b_field(2, cal, field_cells, label_power_mw, uses_model_at_cell_power=False, order=order,
                          meta={"p_rel": p_rel, "spans_um": spans, "line_z_um": line_z})


# ----------------------------------------------------------------------------------------------
# F3 – F5 (T142)
# ----------------------------------------------------------------------------------------------
@register_field_builder("ptd01.f3")
def field_f3(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             s_rel: Optional[list] = None, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F3 line pairs: p_rel (rows) × s_rel (columns); a line pair above a group of five lines.

    The centre distance of neighbouring lines is ``s = s_rel · w(P)`` at the power of the cell; all
    lines along x, 6 µm long, at z0. One layer.

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F3_P_REL if p_rel is None else p_rel)
    s_rel = list(F3_S_REL if s_rel is None else s_rel)
    centers = grid_centers(len(p_rel), len(s_rel), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    field_cells = []
    for r, rel in enumerate(p_rel):
        power = _mw(cal.power_mw(rel))
        width = cal.voxel_model.width_um(power)
        for c, srel in enumerate(s_rel):
            cid = _cell_id(3, r, c)
            s = round(srel * width, 6)
            total = 5 * s + F3_GROUP_GAP_UM
            groups = cells.line_set(cid, n=2, pitch_um=s, length_um=F3_LINE_LENGTH_UM, power_mw=power,
                                    z_um=cal.z0_um, offset_um=(0.0, total / 2 - s / 2), part="pair")
            groups += cells.line_set(cid, n=5, pitch_um=s, length_um=F3_LINE_LENGTH_UM, power_mw=power,
                                     z_um=cal.z0_um, offset_um=(0.0, -total / 2 + 2 * s), part="group")
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)],
                                        {"power_mw": round(power, 6), "spacing_um": s, "model_width_um": round(width, 6),
                                         "z_um": cal.z0_um}, {"p_rel": rel, "s_rel": srel}, "line_set",
                                        groups=tuple(groups)))
    return _stage_b_field(3, cal, field_cells, label_power_mw, uses_model_at_cell_power=True, order=order,
                          meta={"p_rel": p_rel, "s_rel": s_rel})


@register_field_builder("ptd01.f4")
def field_f4(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             h_rel: Optional[list] = None, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F4 squares: p_rel (rows) × h_rel (columns); 6 × 6 µm pads of 3 layers with a 1.6 µm ramp on +x.

    Hatch ``h = h_rel · w(P)`` along x (``linear_x``), slice ``dz = 0.5 · l(P)`` at the cell power;
    anchored 1.5 µm.

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F4_P_REL if p_rel is None else p_rel)
    h_rel = list(F4_H_REL if h_rel is None else h_rel)
    x_centers = packed_centers([F4_PAD_UM + F4_RAMP_UM + EDGE_UM] * len(h_rel), 4.5)
    y_centers = _row_centers([F4_PAD_UM + EDGE_UM] * len(p_rel), 4.5)
    field_cells = []
    for r, rel in enumerate(p_rel):
        power = _mw(cal.power_mw(rel))
        dz = cal.slice_um(F4_DZ_REL, power)
        height = (F4_LAYERS - 0.5) * dz
        pad = cells.pad_map(F4_PAD_UM, F4_PAD_UM, height, ramp_um=F4_RAMP_UM)
        for c, hrel in enumerate(h_rel):
            cid = _cell_id(4, r, c)
            hatch = cal.hatch_um(hrel, power)
            groups = cells.sliced(cid, height_map_um=pad, pixel_um=PIXEL_UM, slicing=_slicing(hatch, dz, "linear_x"),
                                  power_mw=power, anchor_depth_um=ANCHOR_DEPTH_UM, part="pad")
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": round(power, 6), "hatch_um": round(hatch, 6),
                                         "slice_um": round(dz, 6), "layers": F4_LAYERS,
                                         "pad_height_um": round(F4_LAYERS * dz, 6)},
                                        {"p_rel": rel, "h_rel": hrel, "dz_rel": F4_DZ_REL}, "sliced",
                                        groups=tuple(groups), kind=VOLUME, anchor_depth_um=ANCHOR_DEPTH_UM))
    return _stage_b_field(4, cal, field_cells, label_power_mw, uses_model_at_cell_power=True, order=order,
                          meta={"p_rel": p_rel, "h_rel": h_rel, "dz_rel": F4_DZ_REL})


@register_field_builder("ptd01.f5")
def field_f5(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             dz_rel: Optional[list] = None, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F5 layer test: wedges (rows of p_rel) and a row of caps at P_ref (top) × dz_rel (columns).

    Slice ``dz = dz_rel · l(P)``, hatch ``h = 0.5 · w(P)`` at the power of the cell; wedge 8 × 6 × 3 µm
    (20.6°), cap Ø 8 µm × 2 µm; anchored 1.5 µm. Cells with the same slice distance share layers.

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F5_P_REL if p_rel is None else p_rel)
    dz_rel = list(F5_DZ_REL if dz_rel is None else dz_rel)
    wx, wy, wh = F5_WEDGE_UM
    cap_d, cap_h = F5_CAP_UM
    x_centers = packed_centers([max(wx, cap_d) + EDGE_UM] * len(dz_rel), 4.5)
    y_centers = _row_centers([wy + EDGE_UM] * len(p_rel) + [cap_d + EDGE_UM], 4.5)
    rows = [("wedge", rel, _mw(cal.power_mw(rel))) for rel in p_rel] + [("cap", cal.p_ref_factor, _mw(cal.p_ref_mw))]
    wedge, cap = cells.wedge_map(wx, wy, wh), cells.cap_map(cap_d, cap_h)
    field_cells = []
    for r, (shape, rel, power) in enumerate(rows):
        hatch = cal.hatch_um(F5_H_REL, power)
        for c, drel in enumerate(dz_rel):
            cid = _cell_id(5, r, c)
            dz = cal.slice_um(drel, power)
            groups = cells.sliced(cid, height_map_um=wedge if shape == "wedge" else cap, pixel_um=PIXEL_UM,
                                  slicing=_slicing(hatch, dz, "linear_x"), power_mw=power,
                                  anchor_depth_um=ANCHOR_DEPTH_UM, part=shape)
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"shape": shape, "power_mw": round(power, 6), "hatch_um": round(hatch, 6),
                                         "slice_um": round(dz, 6)}, {"p_rel": rel, "dz_rel": drel, "h_rel": F5_H_REL},
                                        "sliced", groups=tuple(groups), kind=VOLUME,
                                        anchor_depth_um=ANCHOR_DEPTH_UM))
    return _stage_b_field(5, cal, field_cells, label_power_mw, uses_model_at_cell_power=True, order=order,
                          meta={"p_rel": p_rel, "dz_rel": dz_rel, "h_rel": F5_H_REL})


# ----------------------------------------------------------------------------------------------
# F6 – F7 (T143)
# ----------------------------------------------------------------------------------------------
@register_field_builder("ptd01.f6")
def field_f6(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F6 crossings: structure type (rows: star 0/45/90/135°, 3 × 3 grid, 4-layer woodpile) × p_rel.

    Lines are written once at z0; the woodpile starts at z0 with ``dz = 0.6 · l0``.

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F6_P_REL if p_rel is None else p_rel)
    centers = grid_centers(len(F6_TYPES), len(p_rel), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    woodpile_dz = round(F6_WOODPILE_DZ_REL * cal.l0_um, 6)
    field_cells = []
    for r, kind in enumerate(F6_TYPES):
        for c, rel in enumerate(p_rel):
            cid = _cell_id(6, r, c)
            power = _mw(cal.power_mw(rel))
            if kind == "star":
                groups = []
                for angle in (0.0, 45.0, 90.0, 135.0):
                    groups += cells.line(cid, length_um=F6_LINE_LENGTH_UM, power_mw=power, direction=angle,
                                         z_um=cal.z0_um, part=f"star_{angle:g}")
                params = {"angles_deg": [0, 45, 90, 135]}
            elif kind == "grid":
                groups = cells.line_set(cid, n=3, pitch_um=F6_GRID_PITCH_UM, length_um=F6_LINE_LENGTH_UM,
                                        power_mw=power, direction="x", z_um=cal.z0_um, part="grid_x")
                groups += cells.line_set(cid, n=3, pitch_um=F6_GRID_PITCH_UM, length_um=F6_LINE_LENGTH_UM,
                                         power_mw=power, direction="y", z_um=cal.z0_um, part="grid_y")
                params = {"pitch_um": F6_GRID_PITCH_UM}
            else:
                groups = cells.woodpile(cid, n_layers=F6_WOODPILE_LAYERS, rod_pitch_um=F6_ROD_PITCH_UM,
                                        rod_length_um=F6_LINE_LENGTH_UM, dz_um=woodpile_dz, power_mw=power,
                                        z0_um=cal.z0_um)
                params = {"rod_pitch_um": F6_ROD_PITCH_UM, "layers": F6_WOODPILE_LAYERS, "dz_um": woodpile_dz}
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)],
                                        {"type": kind, "power_mw": round(power, 6), "z_um": cal.z0_um, **params},
                                        {"p_rel": rel}, kind, groups=tuple(groups), kind=LINE))
    return _stage_b_field(6, cal, field_cells, label_power_mw, uses_model_at_cell_power=False, order=order,
                          meta={"p_rel": p_rel, "types": list(F6_TYPES), "woodpile_dz_um": woodpile_dz})


@register_field_builder("ptd01.f7")
def field_f7(*, calibration: dict, label_power_mw: float, p_rel: Optional[list] = None,
             heights_um: Optional[list] = None, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F7 pillars on bases: p_rel (rows) × pillar height above the base (columns).

    Base 6 × 6 × 1.4 µm at P_ref, anchored 1.5 µm; pillar Ø 1.5 µm at the cell power with
    ``h = 0.5 · w(P)``, ``dz = 0.5 · l(P)``, starting at the base top (D10). The highest pillars are
    in the rightmost column, at the field edge; all are lower than the 10.5 µm pitch.

    Returns
    -------
    ParameterField
    """

    cal = as_calibration(calibration)
    p_rel = list(F7_P_REL if p_rel is None else p_rel)
    heights = [float(h) for h in (F7_HEIGHTS_UM if heights_um is None else heights_um)]
    bx, by, bh = F7_BASE_UM
    x_centers = packed_centers([bx + EDGE_UM] * len(heights), 4.5)
    y_centers = _row_centers([by + EDGE_UM] * len(p_rel), 4.5)
    support = _support_slicing(cal)
    base_map = cells.pad_map(bx, by, bh)
    field_cells = []
    for r, rel in enumerate(p_rel):
        power = _mw(cal.power_mw(rel))
        hatch, dz = cal.hatch_um(F7_H_REL, power), cal.slice_um(F7_DZ_REL, power)
        for c, height in enumerate(heights):
            cid = _cell_id(7, r, c)
            groups = cells.sliced(cid, height_map_um=base_map, pixel_um=PIXEL_UM, slicing=support,
                                  power_mw=_mw(cal.p_ref_mw), anchor_depth_um=ANCHOR_DEPTH_UM, part="base")
            pillar = cells.pillar_map(F7_PILLAR_DIAMETER_UM, bh + height, extent_um=F7_PILLAR_DIAMETER_UM + 0.5)
            groups += cells.sliced(cid, height_map_um=pillar, pixel_um=PIXEL_UM,
                                   slicing=_slicing(hatch, dz, "alternating"), power_mw=power, min_z_um=bh,
                                   part="pillar")
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": round(power, 6), "pillar_height_um": height,
                                         "aspect_ratio": round(height / F7_PILLAR_DIAMETER_UM, 3),
                                         "hatch_um": round(hatch, 6), "slice_um": round(dz, 6),
                                         "base_power_mw": round(cal.p_ref_mw, 6)},
                                        {"p_rel": rel, "h_rel": F7_H_REL, "dz_rel": F7_DZ_REL}, "sliced",
                                        groups=tuple(groups), kind=VOLUME, anchor_depth_um=ANCHOR_DEPTH_UM))
    return _stage_b_field(7, cal, field_cells, label_power_mw, uses_model_at_cell_power=True, order=order,
                          meta={"p_rel": p_rel, "heights_um": heights})


BUILDERS = {0: field_f0, 1: field_f1, 2: field_f2, 3: field_f3, 4: field_f4, 5: field_f5, 6: field_f6, 7: field_f7}
