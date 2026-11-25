"""ParameterField: layout, header, merge by z, in-layer ordering, validation, cell table (T139)."""
import csv
import dataclasses
import json

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json  # noqa: E402
from nanofactorysystem.aerobasic.slicer import SlicingParameters  # noqa: E402
from nanofactorysystem.backends.dummy.attenuator import write_calibration_file  # noqa: E402
from nanofactorysystem.backends.dummy.world import SimulatedWorld  # noqa: E402
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Unit  # noqa: E402
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration  # noqa: E402
from nanofactorysystem.testprint import cells  # noqa: E402
from nanofactorysystem.testprint.field import (  # noqa: E402
    VOLUME, CellSpec, FieldLayoutError, ParameterField, build_header, grid_centers, packed_centers)
from nanofactorysystem.testprint.ordering import ordering, ordering_names, register_ordering  # noqa: E402
from nanofactorysystem.testprint.structure import ParameterFieldStructure, register_field_builder  # noqa: E402

SLICING = SlicingParameters(layer_height_um=0.3, hatch_spacing_um=0.5, hatch_strategy="linear_x")


@pytest.fixture(autouse=True)
def synthetic_calibration(tmp_path):
    path = write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(path)):
        yield


def line_cell(row, col, center, power, z=0.0):
    return CellSpec(f"T-r{row}c{col}", row, col, center, {"power_mw": power, "z_um": z}, {"p_rel": power / 0.5},
                    "line", groups=tuple(cells.line(f"T-r{row}c{col}", length_um=4.0, power_mw=power, z_um=z)))


@register_field_builder("test.small_field")
def small_field(*, powers: list, order: str = "row_by_row", with_pad: bool = True):
    centers = grid_centers(2, 2)
    field_cells = [line_cell(r, c, centers[(r, c)], powers[r], z=0.3 * c) for r in range(2) for c in range(2)]
    if with_pad:
        pad = cells.sliced("T-pad", height_map_um=cells.pad_map(4, 4, 0.6), pixel_um=cells.DEFAULT_PIXEL_UM,
                           slicing=SLICING, power_mw=1.0, anchor_depth_um=0.6)
        field_cells.append(CellSpec("T-pad", 2, 0, (0.0, 10.0), {"power_mw": 1.0}, {}, "sliced", groups=tuple(pad),
                                    kind=VOLUME, anchor_depth_um=0.6))
    ref = cells.sliced("ref", height_map_um=cells.pad_map(4, 4, 0.3), pixel_um=cells.DEFAULT_PIXEL_UM,
                       slicing=SLICING, power_mw=0.8)
    header = build_header(5, label_power_mw=0.7, ref_pad=ref)
    return ParameterField(5, "test_field", tuple(field_cells), 0.7, header_groups=header, order=order,
                          meta={"powers": powers})


def programs(structure):
    coordinate_system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system)]


def test_grid_and_packed_centers():
    centers = grid_centers(10, 8)
    assert centers[(0, 0)] == pytest.approx((-25 + 3.125, -25 + 2.25))
    assert centers[(9, 7)][1] < 20.0                                   # below the header strip
    assert packed_centers([6, 8, 11, 14], 2.0) == pytest.approx([-19.5, -10.5, 1.0, 15.5])


def test_header_marks_and_id_bits():
    header = build_header(5, label_power_mw=0.7)                       # 0b101: bits 2 and 0
    parts = sorted({e.meta["part"] for g in header for e in g.elements})
    assert parts == ["L_mark", "id_bit0", "id_bit2"]
    assert all(e.meta["row"] == -1 and e.power_mw == 0.7 for g in header for e in g.elements)
    assert cells.groups_bounds(header)[1] >= 20.0
    assert [e.meta["part"] for g in build_header(0, label_power_mw=0.7) for e in g.elements] == ["L_mark"]
    with pytest.raises(ValueError, match="0 ... 7"):
        build_header(8, label_power_mw=0.7)


def test_merge_by_z_and_row_by_row_order():
    field = small_field(powers=[0.5, 0.6])
    job = field.to_toolpath_job("Zeiss 63x")
    zs = [g.z_um for g in job.groups]
    assert zs == sorted(zs) and zs == field.z_levels_um()
    assert -0.6 in zs and 0.0 in zs and 0.3 in zs                     # anchor, base layer, column-1 lines
    layer0 = next(g for g in job.groups if g.z_um == 0.0)
    keys = [(e.meta["row"], e.meta["col"]) for e in layer0.elements]
    assert keys == sorted(keys) and keys[0] == (-1, -1)                # header first, then row by row
    assert {e.meta["cell"] for e in layer0.elements} == {"header", "T-r0c0", "T-r1c0", "T-pad"}
    assert job.meta["n_cells"] == 5 and job.params.laser.power_mw == 0.7


def test_ordering_registry():
    assert "row_by_row" in ordering_names()
    with pytest.raises(ValueError, match="Unknown in-layer ordering"):
        ordering("spiral")

    @register_ordering("test_reverse")
    def reverse(elements):
        return list(reversed(elements))

    job = small_field(powers=[0.5, 0.6], order="test_reverse").to_toolpath_job()
    layer0 = next(g for g in job.groups if g.z_um == 0.0)
    assert layer0.elements[-1].meta["cell"] == "header"


def test_validation_reports_every_problem():
    good = small_field(powers=[0.5, 0.6])
    assert good.problems() == []
    outside = line_cell(0, 9, (24.5, 0.0), 0.5)
    in_header = line_cell(0, 8, (0.0, 22.0), 0.5)
    too_close = line_cell(0, 7, (good.cells[0].center_um[0], good.cells[0].center_um[1] + 1.0), 0.5)
    too_high = line_cell(0, 6, (0.0, -20.0), 0.5, z=40.0)
    bad = dataclasses.replace(good, cells=good.cells + (outside, in_header, too_close, too_high, good.cells[0]),
                              power_range_mw=(0.55, 2.0), order="spiral")
    problems = bad.problems()
    text = "\n".join(problems)
    assert "outside the field" in text and "header strip" in text and "gap" in text
    assert "z = 40.0" in text and "outside the voxel model range" in text
    assert "duplicate cell ids" in text and "Unknown in-layer ordering" in text
    with pytest.raises(FieldLayoutError) as error:
        bad.to_toolpath_job()
    assert error.value.problems == problems


def test_volume_cells_need_the_larger_gap():
    field = small_field(powers=[0.5, 0.6])
    pad = field.cells[-1]
    near = dataclasses.replace(pad, cell_id="T-pad2", center_um=(pad.center_um[0], pad.center_um[1] - 7.0))
    problems = dataclasses.replace(field, cells=field.cells + (near,)).problems()
    assert problems == ["cells T-pad and T-pad2: gap 3.00 um < 4.5 um"]
    relaxed = dataclasses.replace(near, min_gap_um=2.0)
    relaxed_pad = dataclasses.replace(pad, min_gap_um=2.0)
    assert dataclasses.replace(field, cells=field.cells[:-1] + (relaxed_pad, relaxed)).problems() == []


def test_cell_table_and_csv(tmp_path):
    field = small_field(powers=[0.5, 0.6])
    table = field.cell_table()
    assert [r["cell_id"] for r in table] == ["T-r0c0", "T-r0c1", "T-r1c0", "T-r1c1", "T-pad"]
    first = table[0]
    for column in ("field_id", "field", "row", "col", "x_um", "y_um", "primitive", "kind", "anchor_depth_um",
                   "bbox_x_min_um", "power_mw", "p_rel"):
        assert column in first
    assert table[-1]["anchor_depth_um"] == 0.6
    path = field.write_cell_table(tmp_path / "cells.csv", extra_columns=["width_um"])
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5 and rows[0]["width_um"] == "" and rows[0]["power_mw"] == "0.5"


def test_structure_round_trip_and_determinism():
    structure = ParameterFieldStructure("test.small_field", {"powers": [0.5, 0.6]})
    assert structure.structure_power_mw == 0.7                        # label power of the field
    first = programs(structure)
    second = programs(ParameterFieldStructure("test.small_field", {"powers": [0.5, 0.6]}))
    assert first == second
    again = structure_from_json(json.loads(json.dumps(structure.to_json())))
    assert programs(again) == first
    assert structure.element_powers_mw == [0.5, 0.6, 0.7, 0.8, 1.0]


def test_plot(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    ax = small_field(powers=[0.5, 0.6]).plot()
    ax.figure.savefig(tmp_path / "field.png")
    assert (tmp_path / "field.png").stat().st_size > 0
