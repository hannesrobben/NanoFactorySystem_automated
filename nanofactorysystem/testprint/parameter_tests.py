"""Field builders of the parameter tests Quick PT, Full PT-01 and Voxel PT-01 (T159–T161, design
docs/design/PARAMETER_TESTS.md, version 2).

Single-stage tests on **absolute axes**: nothing about the material (threshold, voxel size) is needed
before printing; the relative quantities are computed in the evaluation. Every builder is a pure function
of the material start file (``inputs``, the JSON form of :class:`~.inputs.ParameterTestInputs`) and the
sub-field, registered as a field builder, so a restart and the evaluation rebuild the same field.

Common layout (design §3): 60 × 60 µm fields with a 5 µm header strip (L mark, 3-bit field number, sub-field
bit, REF pad at the support power); sub-field ``"a"`` holds the first five powers of the ladder (0.1–0.5 mW),
``"b"`` the last five (0.6–1.0 mW), one power per row, row 0 = lowest power. Volume cells are anchored
``anchor_depth_um`` (1 µm) into the substrate. Supports (pedestals, bases, REF pad, caps, gap-test bases) use
the support power, hatch and slice of the inputs.

Field numbers in the header: Quick PT Q1 walls = 1, Q2 pads = 2; Full PT-01 F1 … F7 = 1 … 7. The test is
identified by the experiment (QR code). Voxel PT-01 cells have no header (one 20 µm cell per structure,
identified by their grid position).
"""
from __future__ import annotations

from nanofactorysystem.aerobasic.slicer import SlicingParameters

from . import cells
from .field import LINE, VOLUME, CellSpec, ParameterField, build_header, grid_centers, packed_centers
from .inputs import ParameterTestInputs, as_inputs
from .ordering import DEFAULT_ORDERING
from .structure import register_field_builder

__all__ = ["FIELD_SIZE_UM", "HEADER_UM", "VOLUME_GAP_UM", "QUICK_FIELDS", "FULL_FIELDS", "quick_walls", "quick_pads",
           "full_f1", "full_f2", "full_f3", "full_f4", "full_f5", "full_f6", "full_f7", "voxel_gap_cell",
           "FULL_BUILDERS", "QUICK_BUILDERS"]

FIELD_SIZE_UM = 60.0
HEADER_UM = 5.0
VOLUME_GAP_UM = 4.5                     # D5
PIXEL_UM = cells.DEFAULT_PIXEL_UM
EDGE_UM = 2 * PIXEL_UM                  # sliced edges are interpolated over one pixel
REF_PAD_UM = (4.0, 4.0, 1.0)

QUICK_FIELDS = {1: "Q1_walls", 2: "Q2_pads"}
FULL_FIELDS = {1: "F1_lines", 2: "F2_bridges", 3: "F3_line_pairs", 4: "F4_squares", 5: "F5_layers",
               6: "F6_crossings", 7: "F7_pillars"}


# ----------------------------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------------------------
def _slicing(hatch_um: float, slice_um: float, strategy: str = "linear_x") -> SlicingParameters:
    return SlicingParameters(layer_height_um=float(slice_um), hatch_spacing_um=float(hatch_um),
                             hatch_strategy=strategy, num_contour_lines=0, contour_offset_um=0.0)


def _support_slicing(inputs: ParameterTestInputs, strategy: str = "alternating") -> SlicingParameters:
    return _slicing(inputs.support["hatch_um"], inputs.support["slice_um"], strategy)


def _ref_pad(inputs: ParameterTestInputs) -> list:
    x, y, h = REF_PAD_UM
    return cells.sliced("header", height_map_um=cells.pad_map(x, y, h), pixel_um=PIXEL_UM,
                        slicing=_support_slicing(inputs), power_mw=inputs.support["power_mw"],
                        anchor_depth_um=inputs.anchor_depth_um, part="ref_pad")


def _cell_id(prefix: str, half: str, row: int, col: int) -> str:
    return f"{prefix}{half}-r{row}c{col}"


def _height_map(size_x_um: float, size_y_um: float, top_um: float, slice_um: float, **kwargs):
    """ A pad whose top layer lies exactly at ``top_um`` on the grid ``k · slice`` (slicer planes are below
    the surface, so the map is half a slice higher). """

    return cells.pad_map(size_x_um, size_y_um, top_um + slice_um / 2, **kwargs)


def _sub_field(field_id: int, name: str, half: str, inputs: ParameterTestInputs, field_cells: list, meta: dict,
               order: str) -> ParameterField:
    header = build_header(field_id, label_power_mw=inputs.label_power_mw, size_um=FIELD_SIZE_UM, header_um=HEADER_UM,
                          z_um=0.0, ref_pad=_ref_pad(inputs), half=half)
    meta = {"material": inputs.material, "powers_mw": inputs.powers_of(half), "support": dict(inputs.support),
            "anchor_depth_um": inputs.anchor_depth_um, **meta}
    return ParameterField(field_id, f"{name}_{half}", tuple(field_cells), float(inputs.label_power_mw),
                          header_groups=header, size_um=FIELD_SIZE_UM, header_um=HEADER_UM, order=order,
                          z_min_um=-3.0, meta=meta, half=half)


def _row_centers(heights: list[float], gap_um: float) -> list[float]:
    return [-HEADER_UM / 2 + y for y in packed_centers(heights, gap_um)]


# ----------------------------------------------------------------------------------------------
# Quick PT (T159)
# ----------------------------------------------------------------------------------------------
@register_field_builder("quick_pt.walls")
def quick_walls(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ Quick PT Q1: walls of stacked lines per power (rows) in two identical groups (columns).

    Every wall is a line written in layers from ``z_from_um`` to ``z_to_um`` (1 µm in the substrate, 1 µm
    above, slice 0.25 µm); a group holds three walls 1.5 µm apart. Gives the polymerisation threshold,
    damage, the wall width and whether neighbours at 1.5 µm merge.

    Parameters
    ----------
    inputs : dict
        Material start file (JSON).
    half : {"a", "b"}
        Sub-field (first or second half of the power ladder).
    order : str
        In-layer ordering strategy.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    walls = data.quick["walls"]
    powers = data.powers_of(half)
    n_layers = int(round((walls["z_to_um"] - walls["z_from_um"]) / walls["slice_um"])) + 1
    zs = [round(walls["z_from_um"] + k * walls["slice_um"], 3) for k in range(n_layers)]
    centers = grid_centers(len(powers), int(walls["groups"]), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    field_cells = []
    for r, power in enumerate(powers):
        for c in range(int(walls["groups"])):
            cid = _cell_id("Q1", half, r, c)
            groups = []
            for z in zs:
                groups += cells.line_set(cid, n=int(walls["walls_per_group"]), pitch_um=walls["pitch_um"],
                                         length_um=walls["length_um"], power_mw=power, direction="x", z_um=z,
                                         part="wall")
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)],
                                        {"power_mw": power, "group": c, "walls": int(walls["walls_per_group"]),
                                         "wall_length_um": walls["length_um"], "wall_pitch_um": walls["pitch_um"],
                                         "z_from_um": walls["z_from_um"], "z_to_um": walls["z_to_um"],
                                         "slice_um": walls["slice_um"]}, {}, "line_set", groups=tuple(groups)))
    return _sub_field(1, QUICK_FIELDS[1], half, data, field_cells, {"walls": dict(walls)}, order)


@register_field_builder("quick_pt.pads")
def quick_pads(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ Quick PT Q2: 5 × 5 µm pads from z = −1 to +1 µm, power (rows) × hatch distance (columns).

    The pad is sliced from 0 to ``z_to_um`` and its first layer repeated down to ``z_from_um`` (the same
    as anchoring). Gives the surface formation over hatch and power.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    pads = data.quick["pads"]
    powers = data.powers_of(half)
    hatches = [float(h) for h in pads["hatch_um"]]
    size, dz = float(pads["size_um"]), float(pads["slice_um"])
    pad_map = _height_map(size, size, float(pads["z_to_um"]), dz)
    x_centers = packed_centers([size + EDGE_UM] * len(hatches), VOLUME_GAP_UM)
    y_centers = _row_centers([size + EDGE_UM] * len(powers), (FIELD_SIZE_UM - HEADER_UM - size * len(powers))
                             / len(powers))
    field_cells = []
    for r, power in enumerate(powers):
        for c, hatch in enumerate(hatches):
            cid = _cell_id("Q2", half, r, c)
            groups = cells.sliced(cid, height_map_um=pad_map, pixel_um=PIXEL_UM, slicing=_slicing(hatch, dz),
                                  power_mw=power, anchor_depth_um=-float(pads["z_from_um"]), part="pad")
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": power, "hatch_um": hatch, "pad_um": size, "slice_um": dz,
                                         "z_from_um": pads["z_from_um"], "z_to_um": pads["z_to_um"]}, {}, "sliced",
                                        groups=tuple(groups), kind=VOLUME, anchor_depth_um=-float(pads["z_from_um"])))
    return _sub_field(2, QUICK_FIELDS[2], half, data, field_cells, {"pads": dict(pads)}, order)


# ----------------------------------------------------------------------------------------------
# Full PT-01 (T160)
# ----------------------------------------------------------------------------------------------
@register_field_builder("full_pt01.f1")
def full_f1(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F1 line test: power (rows) × passes (columns); 2 x-lines and 2 y-lines of 7 µm, 2.5 µm apart, at z = 0.

    Gives the width over power and repetitions, the x/y difference (polarisation) and line end vs. middle.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f1 = data.full["f1"]
    powers, passes = data.powers_of(half), [int(n) for n in f1["passes"]]
    length, pitch = float(f1["line_length_um"]), float(f1["line_pitch_um"])
    centers = grid_centers(len(powers), len(passes), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    # x-lines left, y-lines right (pitch / 2 apart), the whole cell content centred on the cell centre
    x_pair = -(length / 2 + pitch / 4)
    y_pair = pitch / 2 + pitch / 4
    shift = -((x_pair - length / 2) + (y_pair + pitch / 2)) / 2
    x_pair, y_pair = x_pair + shift, y_pair + shift
    field_cells = []
    for r, power in enumerate(powers):
        for c, n in enumerate(passes):
            cid = _cell_id("F1", half, r, c)
            groups = cells.line_set(cid, n=2, pitch_um=pitch, length_um=length, power_mw=power, direction="x", z_um=0.0,
                                    passes=n, offset_um=(x_pair, 0.0), part="x_lines")
            groups += cells.line_set(cid, n=2, pitch_um=pitch, length_um=length, power_mw=power, direction="y",
                                     z_um=0.0, passes=n, offset_um=(y_pair, 0.0), part="y_lines")
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)],
                                        {"power_mw": power, "passes": n, "line_length_um": length,
                                         "line_pitch_um": pitch}, {}, "line_set", groups=tuple(groups)))
    return _sub_field(1, FULL_FIELDS[1], half, data, field_cells, {"f1": dict(f1)}, order)


@register_field_builder("full_pt01.f2")
def full_f2(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F2 bridges: power (rows) × span (columns); a line between two pedestals (2 × 3 × 3 µm, support
    power), 0.5 µm below the pedestal top, reaching to the pedestal centres; 2 µm between cells (D11).

    Gives width and length of a free-standing line (SEM under 45°), sag and the largest span.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f2 = data.full["f2"]
    powers, spans = data.powers_of(half), [float(s) for s in f2["spans_um"]]
    px, py, ph = (float(v) for v in f2["pedestal_um"])
    line_z = round(ph - float(f2["line_below_top_um"]), 3)
    support = _support_slicing(data)
    x_centers = packed_centers([s + 2 * px + EDGE_UM for s in spans], float(f2["gap_um"]))
    y_centers = _row_centers([py] * len(powers), (FIELD_SIZE_UM - HEADER_UM - py * len(powers)) / len(powers))
    pedestal = _height_map(px, py, ph - support.layer_height_um, support.layer_height_um)
    field_cells = []
    for r, power in enumerate(powers):
        for c, span in enumerate(spans):
            cid = _cell_id("F2", half, r, c)
            groups = []
            for side in (-1, 1):
                groups += cells.sliced(cid, height_map_um=pedestal, pixel_um=PIXEL_UM, slicing=support,
                                       power_mw=data.support["power_mw"], anchor_depth_um=data.anchor_depth_um,
                                       offset_um=(side * (span + px) / 2, 0.0), part="pedestal")
            groups += cells.suspended_line(cid, span_um=span, z_um=line_z, power_mw=power, extend_um=px / 2)
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": power, "span_um": span, "line_z_um": line_z,
                                         "pedestal_power_mw": data.support["power_mw"]}, {}, "sliced+suspended_line",
                                        groups=tuple(groups), kind=VOLUME, min_gap_um=float(f2["gap_um"]),
                                        anchor_depth_um=data.anchor_depth_um))
    return _sub_field(2, FULL_FIELDS[2], half, data, field_cells, {"f2": dict(f2), "line_z_um": line_z}, order)


@register_field_builder("full_pt01.f3")
def full_f3(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F3 line pairs: power (rows) × centre distance (columns); a pair above a group of five 6 µm lines.

    The distances run from "certainly merged" (0.2 µm) to "certainly separate" (1.2 µm); gives the merge
    distance and the widening by neighbours.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f3 = data.full["f3"]
    powers, spacings = data.powers_of(half), [float(s) for s in f3["spacing_um"]]
    length, group_gap = float(f3["line_length_um"]), float(f3["group_gap_um"])
    centers = grid_centers(len(powers), len(spacings), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    field_cells = []
    for r, power in enumerate(powers):
        for c, s in enumerate(spacings):
            cid = _cell_id("F3", half, r, c)
            total = 5 * s + group_gap
            groups = cells.line_set(cid, n=2, pitch_um=s, length_um=length, power_mw=power,
                                    offset_um=(0.0, total / 2 - s / 2), part="pair")
            groups += cells.line_set(cid, n=5, pitch_um=s, length_um=length, power_mw=power,
                                     offset_um=(0.0, -total / 2 + 2 * s), part="group")
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)], {"power_mw": power, "spacing_um": s,
                                                                     "line_length_um": length}, {}, "line_set",
                                        groups=tuple(groups)))
    return _sub_field(3, FULL_FIELDS[3], half, data, field_cells, {"f3": dict(f3)}, order)


@register_field_builder("full_pt01.f4")
def full_f4(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F4 squares: power (rows) × hatch distance (columns); 6 × 6 µm pads of 3 layers of 0.3 µm with a
    1.6 µm ramp on +x, hatch along x; anchored. Gives the hatch window (dense surface vs. gaps).

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f4 = data.full["f4"]
    powers, hatches = data.powers_of(half), [float(h) for h in f4["hatch_um"]]
    pad, ramp, dz, layers = float(f4["pad_um"]), float(f4["ramp_um"]), float(f4["slice_um"]), int(f4["layers"])
    pad_map = _height_map(pad, pad, (layers - 1) * dz, dz, ramp_um=ramp)
    x_centers = packed_centers([pad + ramp + EDGE_UM] * len(hatches), VOLUME_GAP_UM)
    y_centers = _row_centers([pad + EDGE_UM] * len(powers), VOLUME_GAP_UM)
    field_cells = []
    for r, power in enumerate(powers):
        for c, hatch in enumerate(hatches):
            cid = _cell_id("F4", half, r, c)
            groups = cells.sliced(cid, height_map_um=pad_map, pixel_um=PIXEL_UM, slicing=_slicing(hatch, dz),
                                  power_mw=power, anchor_depth_um=data.anchor_depth_um, part="pad")
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": power, "hatch_um": hatch, "slice_um": dz, "layers": layers,
                                         "pad_um": pad, "ramp_um": ramp}, {}, "sliced", groups=tuple(groups),
                                        kind=VOLUME, anchor_depth_um=data.anchor_depth_um))
    return _sub_field(4, FULL_FIELDS[4], half, data, field_cells, {"f4": dict(f4)}, order)


@register_field_builder("full_pt01.f5")
def full_f5(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F5 layer test: wedges 8 × 4 × 3 µm (rows: power) and a row of caps Ø 8 µm × 2 µm at the support
    power (top row) × slice distance (columns); hatch 0.2 µm; anchored. Gives the layer window.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f5 = data.full["f5"]
    powers, slices = data.powers_of(half), [float(v) for v in f5["slice_um"]]
    wx, wy, wh = (float(v) for v in f5["wedge_um"])
    cap_d, cap_h = (float(v) for v in f5["cap_um"])
    hatch = float(f5["hatch_um"])
    x_centers = packed_centers([max(wx, cap_d) + EDGE_UM] * len(slices), VOLUME_GAP_UM)
    y_centers = _row_centers([wy + EDGE_UM] * len(powers) + [cap_d + EDGE_UM], VOLUME_GAP_UM)
    rows = [("wedge", p) for p in powers] + [("cap", float(data.support["power_mw"]))]
    wedge, cap = cells.wedge_map(wx, wy, wh), cells.cap_map(cap_d, cap_h)
    field_cells = []
    for r, (shape, power) in enumerate(rows):
        for c, dz in enumerate(slices):
            cid = _cell_id("F5", half, r, c)
            groups = cells.sliced(cid, height_map_um=wedge if shape == "wedge" else cap, pixel_um=PIXEL_UM,
                                  slicing=_slicing(hatch, dz), power_mw=power, anchor_depth_um=data.anchor_depth_um,
                                  part=shape)
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"shape": shape, "power_mw": power, "hatch_um": hatch, "slice_um": dz}, {},
                                        "sliced", groups=tuple(groups), kind=VOLUME,
                                        anchor_depth_um=data.anchor_depth_um))
    return _sub_field(5, FULL_FIELDS[5], half, data, field_cells, {"f5": dict(f5)}, order)


@register_field_builder("full_pt01.f6")
def full_f6(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F6 crossings: type (rows: star 0/45/90/135°, 3 × 3 grid, 4-layer woodpile) × power (columns).

    Lines once at z = 0; the woodpile has rods 1.5 µm apart and 0.4 µm between layers. Gives the width over
    the angle, the overdose at crossings and the merging of woodpile layers.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f6 = data.full["f6"]
    powers, types = data.powers_of(half), ("star", "grid", "woodpile")
    length = float(f6["line_length_um"])
    centers = grid_centers(len(types), len(powers), size_um=FIELD_SIZE_UM, header_um=HEADER_UM)
    field_cells = []
    for r, kind in enumerate(types):
        for c, power in enumerate(powers):
            cid = _cell_id("F6", half, r, c)
            if kind == "star":
                groups = []
                for angle in (0.0, 45.0, 90.0, 135.0):
                    groups += cells.line(cid, length_um=length, power_mw=power, direction=angle, part=f"star_{angle:g}")
                params = {"angles_deg": [0, 45, 90, 135]}
            elif kind == "grid":
                groups = cells.line_set(cid, n=3, pitch_um=f6["grid_pitch_um"], length_um=length, power_mw=power,
                                        direction="x", part="grid_x")
                groups += cells.line_set(cid, n=3, pitch_um=f6["grid_pitch_um"], length_um=length, power_mw=power,
                                         direction="y", part="grid_y")
                params = {"grid_pitch_um": f6["grid_pitch_um"]}
            else:
                groups = cells.woodpile(cid, n_layers=int(f6["woodpile_layers"]), rod_pitch_um=f6["rod_pitch_um"],
                                        rod_length_um=length, dz_um=f6["woodpile_dz_um"], power_mw=power)
                params = {"rod_pitch_um": f6["rod_pitch_um"], "layers": int(f6["woodpile_layers"]),
                          "dz_um": f6["woodpile_dz_um"]}
            field_cells.append(CellSpec(cid, r, c, centers[(r, c)], {"type": kind, "power_mw": power, **params}, {},
                                        kind, groups=tuple(groups), kind=LINE))
    return _sub_field(6, FULL_FIELDS[6], half, data, field_cells, {"f6": dict(f6)}, order)


@register_field_builder("full_pt01.f7")
def full_f7(*, inputs: dict, half: str, order: str = DEFAULT_ORDERING) -> ParameterField:
    """ F7 pillars on bases: power (rows) × pillar height above the base (columns).

    Base 6 × 6 × 1.4 µm at the support power, anchored; pillar Ø 1.5 µm at the row power, filled with hatch
    0.2 / slice 0.25 µm from the base top. Gives the largest aspect ratio per power and the adhesion.

    Returns
    -------
    ParameterField
    """

    data = as_inputs(inputs)
    f7 = data.full["f7"]
    powers, heights = data.powers_of(half), [float(h) for h in f7["heights_um"]]
    bx, by, bh = (float(v) for v in f7["base_um"])
    diameter = float(f7["pillar_diameter_um"])
    support = _support_slicing(data)
    pillar_slicing = _slicing(f7["hatch_um"], f7["slice_um"], "alternating")
    base_map = cells.pad_map(bx, by, bh)
    x_centers = packed_centers([bx + EDGE_UM] * len(heights), VOLUME_GAP_UM)
    y_centers = _row_centers([by + EDGE_UM] * len(powers), VOLUME_GAP_UM)
    field_cells = []
    for r, power in enumerate(powers):
        for c, height in enumerate(heights):
            cid = _cell_id("F7", half, r, c)
            groups = cells.sliced(cid, height_map_um=base_map, pixel_um=PIXEL_UM, slicing=support,
                                  power_mw=data.support["power_mw"], anchor_depth_um=data.anchor_depth_um, part="base")
            pillar = cells.pillar_map(diameter, bh + height, extent_um=diameter + 0.5)
            groups += cells.sliced(cid, height_map_um=pillar, pixel_um=PIXEL_UM, slicing=pillar_slicing, power_mw=power,
                                   min_z_um=bh, part="pillar")
            field_cells.append(CellSpec(cid, r, c, (x_centers[c], y_centers[r]),
                                        {"power_mw": power, "pillar_height_um": height,
                                         "aspect_ratio": round(height / diameter, 3), "hatch_um": f7["hatch_um"],
                                         "slice_um": f7["slice_um"], "base_power_mw": data.support["power_mw"]}, {},
                                        "sliced", groups=tuple(groups), kind=VOLUME,
                                        anchor_depth_um=data.anchor_depth_um))
    return _sub_field(7, FULL_FIELDS[7], half, data, field_cells, {"f7": dict(f7)}, order)


# ----------------------------------------------------------------------------------------------
# Voxel PT-01 (T161)
# ----------------------------------------------------------------------------------------------
@register_field_builder("voxel_pt01.gap")
def voxel_gap_cell(*, inputs: dict, power_mw: float, gap_um: float,
                   order: str = DEFAULT_ORDERING) -> ParameterField:
    """ Voxel PT-01 gap cell: base, gap, lid (design §6).

    The base (20 × 20 µm, layers of 0.25 µm up to 2.0 µm, support power, anchored) is followed by a lid of
    four layers at ``2.0 + gap + k · 0.25`` µm written with the tested power. Gap 0 writes the first lid layer
    on the top layer of the base again (double exposure). After development the lid is missing once the gap
    is larger than the voxel length can bridge.

    Parameters
    ----------
    inputs : dict
        Material start file (JSON).
    power_mw : float
        Power of the lid (the tested power).
    gap_um : float
        Distance between the top layer of the base and the first lid layer.
    order : str

    Returns
    -------
    ParameterField
        One cell, no header (identified by its grid position).

    Raises
    ------
    ValueError
        For a negative gap or a non-positive power.
    """

    data = as_inputs(inputs)
    voxel = data.voxel
    if gap_um < 0 or power_mw <= 0:
        raise ValueError(f"gap_um must be >= 0 and power_mw > 0, got {gap_um}, {power_mw}")
    size, top, dz = float(voxel["base_um"]), float(voxel["base_height_um"]), float(voxel["slice_um"])
    slicing = _slicing(voxel["hatch_um"], dz, "alternating")
    cid = f"V-g{gap_um:.2f}"
    base = cells.sliced(cid, height_map_um=_height_map(size, size, top, dz), pixel_um=PIXEL_UM, slicing=slicing,
                        power_mw=data.support["power_mw"], anchor_depth_um=data.anchor_depth_um, part="base")
    layers = [g for g in base if g.elements[0].meta["part"] == "base"]
    lid = []
    for k in range(int(voxel["lid_layers"])):
        template = layers[k % len(layers)]
        moved = cells.translate_groups([template], dz_um=round(top + gap_um + k * dz - template.z_um, 3))[0]
        for element in moved.elements:
            element.power_mw = float(power_mw)
            element.meta["part"] = "lid"
        lid.append(moved)
    cell = CellSpec(cid, 0, 0, (0.0, 0.0), {"power_mw": float(power_mw), "gap_um": float(gap_um),
                                            "base_um": size, "base_height_um": top, "slice_um": dz,
                                            "lid_layers": int(voxel["lid_layers"]),
                                            "lid_z_um": round(top + gap_um, 3),
                                            "base_power_mw": data.support["power_mw"]}, {}, "sliced+lid",
                    groups=tuple(base + lid), kind=VOLUME, anchor_depth_um=data.anchor_depth_um)
    return ParameterField(0, "V_gap", (cell,), float(data.support["power_mw"]), size_um=size + 2.0, header_um=0.0,
                          order=order, z_min_um=-3.0, z_max_um=top + gap_um + 2.0,
                          meta={"material": data.material, "power_mw": float(power_mw), "gap_um": float(gap_um)})


QUICK_BUILDERS = {1: quick_walls, 2: quick_pads}
FULL_BUILDERS = {1: full_f1, 2: full_f2, 3: full_f3, 4: full_f4, 5: full_f5, 6: full_f6, 7: full_f7}
