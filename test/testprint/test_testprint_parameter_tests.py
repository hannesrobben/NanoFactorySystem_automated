"""Parameter tests version 2: material start file, Quick PT, Full PT-01, Voxel PT-01 (T158–T161)."""
import json

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json  # noqa: E402
from nanofactorysystem.aerobasic.programs.split import MAX_PROGRAM_LINES  # noqa: E402
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Unit  # noqa: E402
from nanofactorysystem.experiment import ProgramSource, StructureType  # noqa: E402
from nanofactorysystem.experiment_spec import ExperimentSpec, SpecSerialisationError, StructureSpec  # noqa: E402
from nanofactorysystem.structure_factories import BuildContext, factory_names  # noqa: E402
from nanofactorysystem.testprint import ParameterTestInputs, pt_factories  # noqa: E402
from nanofactorysystem.testprint import parameter_tests as pt  # noqa: E402
from nanofactorysystem.testprint.field import build_header  # noqa: E402
from nanofactorysystem.testprint.structure import ParameterFieldStructure  # noqa: E402
from nanofactorysystem.voxel.materials import MissingPropertyError  # noqa: E402

INPUTS = ParameterTestInputs("SZ2080", source="tests").to_json()
CONTEXT = BuildContext(objective="Zeiss 63x", setup="IFOV_on", power_min_mw=0.05, power_max_mw=2.0)
SUB_FIELDS = [(name, half) for name in ["quick_pt.walls", "quick_pt.pads"] + [f"full_pt01.f{i}" for i in range(1, 8)]
              for half in "ab"]
_BUILT = {}


def built(name, half):
    if (name, half) not in _BUILT:
        _BUILT[(name, half)] = ParameterFieldStructure(name, {"inputs": INPUTS, "half": half})
    return _BUILT[(name, half)]


def programs(structure):
    coordinate_system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system)]


def elements(cell, part=None):
    return [e for g in cell.groups for e in g.elements if part is None or e.meta["part"] == part]


# ---------------------------------------------------------------------------------------------- inputs
def test_inputs_defaults_halves_and_round_trip(tmp_path):
    inputs = ParameterTestInputs("SZ2080")
    assert inputs.powers_mw == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert inputs.powers_of("a") == [0.1, 0.2, 0.3, 0.4, 0.5] and inputs.powers_of("b")[0] == 0.6
    assert inputs.label_power_mw == 0.5 and inputs.anchor_depth_um == 1.0
    assert inputs.support == {"power_mw": 0.5, "hatch_um": 0.2, "slice_um": 0.25}
    assert inputs.full["f3"]["spacing_um"] == [0.2, 0.4, 0.6, 0.8, 1.0, 1.2]
    assert ParameterTestInputs.load(inputs.save(tmp_path / "parameter_tests_SZ2080.json")) == inputs
    partial = ParameterTestInputs("IP-Dip", full={"f4": {"hatch_um": [0.1, 0.3]}})
    assert partial.full["f4"]["hatch_um"] == [0.1, 0.3] and partial.full["f4"]["pad_um"] == 6.0


def test_inputs_errors():
    with pytest.raises(MissingPropertyError):
        ParameterTestInputs("")
    with pytest.raises(ValueError, match="even number"):
        ParameterTestInputs("SZ2080", powers_mw=[0.1, 0.2, 0.3])
    with pytest.raises(SpecSerialisationError, match="Unknown keys"):
        ParameterTestInputs("SZ2080", full={"f9": {}})
    with pytest.raises(SpecSerialisationError, match="schema"):
        ParameterTestInputs.from_json({"schema": "nanofactory.parameter_tests/9", "material": "x"})
    with pytest.raises(ValueError, match="half"):
        ParameterTestInputs("SZ2080").powers_of("c")


def test_header_has_the_sub_field_bit():
    parts_a = {e.meta["part"] for g in build_header(3, label_power_mw=0.5, half="a") for e in g.elements}
    parts_b = {e.meta["part"] for g in build_header(3, label_power_mw=0.5, half="b") for e in g.elements}
    assert "half_bit" not in parts_a and parts_b - parts_a == {"half_bit"}
    with pytest.raises(ValueError, match="half"):
        build_header(3, label_power_mw=0.5, half="c")


# ---------------------------------------------------------------------------------------------- all sub-fields
@pytest.mark.parametrize("name, half", SUB_FIELDS)
def test_every_sub_field_is_valid_and_uses_its_half_of_the_ladder(name, half):
    field = built(name, half).field
    assert field.problems() == []
    assert field.size_um == 60.0 and field.half == half and field.label_power_mw == 0.5
    powers = ParameterTestInputs.from_json(INPUTS).powers_of(half)
    cell_powers = {c.params["power_mw"] for c in field.cells}
    if name == "full_pt01.f5":
        cell_powers.discard(0.5)  # caps at the support power
        if half == "a":
            cell_powers.add(0.5)
    assert cell_powers <= set(powers) | {0.5}
    assert set(powers) <= cell_powers | {0.5}
    assert all(row["half"] == half for row in field.cell_table())


@pytest.mark.parametrize("name, n_cells", [("quick_pt.walls", 10), ("quick_pt.pads", 20), ("full_pt01.f1", 20),
                                           ("full_pt01.f2", 20), ("full_pt01.f3", 30), ("full_pt01.f4", 20),
                                           ("full_pt01.f5", 24), ("full_pt01.f6", 15), ("full_pt01.f7", 25)])
def test_cell_counts(name, n_cells):
    assert len(built(name, "a").field.cells) == n_cells


# ---------------------------------------------------------------------------------------------- geometry
def test_quick_walls_are_stacked_lines_from_minus_one_to_plus_one():
    cell = built("quick_pt.walls", "a").field.cells[0]
    assert [g.z_um for g in cell.groups] == [-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0]
    assert all(len(g.elements) == 3 for g in cell.groups)          # three walls 1.5 µm apart
    ys = sorted(e.points[0, 1] for e in cell.groups[0].elements)
    assert ys[1] - ys[0] == pytest.approx(1.5) and cell.groups[0].elements[0].length_um == pytest.approx(8.0)
    assert {c.col for c in built("quick_pt.walls", "a").field.cells} == {0, 1}   # two groups per power


def test_quick_pads_reach_one_micrometre_into_the_substrate():
    field = built("quick_pt.pads", "b").field
    cell = field.cells[0]
    zs = [g.z_um for g in cell.groups]
    assert zs[0] == -1.0 and zs[-1] == 1.0 and len(zs) == 9
    assert [c.params["hatch_um"] for c in field.cells[:4]] == [0.1, 0.2, 0.4, 0.6]


def test_full_f2_line_below_the_pedestal_top_and_supports_at_the_support_power():
    field = built("full_pt01.f2", "a").field
    for cell in field.cells:
        [bridge] = elements(cell, "bridge")
        assert bridge.points[0, 2] == 2.5 and cell.min_gap_um == 2.0
        assert {e.power_mw for e in elements(cell, "pedestal")} == {0.5}
        assert min(g.z_um for g in cell.groups) <= -1.0


def test_full_f3_spacings_and_f4_layers():
    f3 = built("full_pt01.f3", "a").field
    assert sorted({c.params["spacing_um"] for c in f3.cells}) == [0.2, 0.4, 0.6, 0.8, 1.0, 1.2]
    f4 = built("full_pt01.f4", "a").field
    for cell in f4.cells:
        assert [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "pad"] == [0.0, 0.3, 0.6]


def test_full_f5_caps_and_f7_pillars():
    f5 = built("full_pt01.f5", "b").field
    caps = [c for c in f5.cells if c.params["shape"] == "cap"]
    assert len(caps) == 4 and {c.params["power_mw"] for c in caps} == {0.5}
    assert sorted({c.params["slice_um"] for c in f5.cells}) == [0.1, 0.2, 0.3, 0.5]
    f7 = built("full_pt01.f7", "b").field
    for cell in f7.cells:
        pillar = [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "pillar"]
        assert min(pillar) >= 1.4 and max(pillar) == pytest.approx(1.4 + cell.params["pillar_height_um"], abs=0.26)


def test_voxel_gap_cell_lid_positions():
    for gap in (0.0, 0.4, 2.0):
        field = pt.voxel_gap_cell(inputs=INPUTS, power_mw=0.7, gap_um=gap)
        [cell] = field.cells
        lid = [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "lid"]
        base = [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "base"]
        assert base[-1] == 2.0 and lid == [round(2.0 + gap + k * 0.25, 3) for k in range(4)]
        assert {e.power_mw for e in elements(cell, "lid")} == {0.7}
        assert {e.power_mw for e in elements(cell, "base")} == {0.5}
        assert field.problems() == []
    # gap 0: the first lid layer is written on the top base layer again (double exposure)
    job = ParameterFieldStructure("voxel_pt01.gap", {"inputs": INPUTS, "power_mw": 0.7, "gap_um": 0.0}).toolpath_job
    top = next(g for g in job.groups if g.z_um == 2.0)
    assert {e.meta["part"] for e in top.elements} == {"base", "lid"}
    with pytest.raises(ValueError, match="gap_um"):
        pt.voxel_gap_cell(inputs=INPUTS, power_mw=0.7, gap_um=-0.2)


# ---------------------------------------------------------------------------------------------- factories
def test_factories_registered_and_spec_round_trip(test_config, synthetic_attenuator):
    names = set(factory_names())
    assert {"quick_pt.walls", "quick_pt.pads", "voxel_pt01.gap"} | {f"full_pt01.f{i}" for i in range(1, 8)} <= names
    call = pt_factories.full_f3(inputs=INPUTS, half="b", dwell_after_power_s=0.02)
    spec = ExperimentSpec(name="full_pt01_test", objective="Zeiss 63x", center=Point2D(0, 0), grid=(1, 1),
                          structures=[StructureSpec("F3_b", factory=call, power_mw=0.5, axes="XYZ",
                                                    structure_type=StructureType.IFOV)],
                          program_source=ProgramSource.DRAWING, setup="IFOV_on")
    again = ExperimentSpec.from_json(json.loads(json.dumps(spec.to_json())))
    built_structures = [s.structures[0].drawable(s.program_source, s.objective, CONTEXT) for s in (spec, again)]
    assert programs(built_structures[0]) == programs(built_structures[1])
    rebuilt = structure_from_json(json.loads(json.dumps(built_structures[0].to_json())))
    assert programs(rebuilt) == programs(built_structures[0])


def test_factory_power_check_only_with_a_known_range():
    narrow = BuildContext(objective="Zeiss 63x", setup="IFOV_on", power_min_mw=0.05, power_max_mw=0.8)
    with pytest.raises(ValueError, match="outside the attenuator calibration range"):
        pt_factories.quick_walls(inputs=INPUTS, half="b").build(narrow)
    offline = pt_factories.quick_walls(inputs=INPUTS, half="b").build(BuildContext())
    assert offline.objective == "Zeiss 63x" and len(offline.field.cells) == 10
    gap = pt_factories.voxel_gap(inputs=INPUTS, power_mw=0.3, gap_um=0.6).build(CONTEXT)
    assert gap.field.cells[0].params["gap_um"] == 0.6


@pytest.mark.slow
@pytest.mark.parametrize("name, half", SUB_FIELDS)
def test_program_lines_and_layer_counts(name, half, synthetic_attenuator):
    texts = programs(built(name, half))
    assert max(len(t.splitlines()) for t in texts) < MAX_PROGRAM_LINES
    assert len(texts) <= 60                                          # absolute slice distances share layers
