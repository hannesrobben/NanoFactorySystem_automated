"""Field builders F0–F7 of the test print PTD-01 (T141, T142, T143)."""
import dataclasses
import logging

import numpy as np
import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from conftest import EXAMPLE_CALIBRATION, EXAMPLE_STAGE_A  # noqa: E402
from nanofactorysystem.aerobasic.programs.split import MAX_PROGRAM_LINES  # noqa: E402
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Unit  # noqa: E402
from nanofactorysystem.testprint import ptd01  # noqa: E402
from nanofactorysystem.testprint.field import FieldLayoutError  # noqa: E402
from nanofactorysystem.testprint.structure import ParameterFieldStructure  # noqa: E402
from nanofactorysystem.testprint.voxel_fit import VoxelFitModel  # noqa: E402

log = logging.getLogger(__name__)
CAL = EXAMPLE_CALIBRATION.to_json()
LABEL_MW = 0.7

# Upper bounds of the number of layer programs (each costs layer_overhead_s); the example calibration
# gives F4 29, F5 229, F7 127 layers (logged by test_layer_counts)
MAX_LAYERS = {0: 9, 1: 10, 2: 20, 3: 10, 4: 35, 5: 260, 6: 15, 7: 140}

_FIELDS = {}


def built(field_id):
    """ Each field is built once per test session (F5 and F7 take seconds). """

    if field_id not in _FIELDS:
        arguments = {"stage_a": EXAMPLE_STAGE_A.to_json()} if field_id == 0 else \
            {"calibration": CAL, "label_power_mw": LABEL_MW}
        _FIELDS[field_id] = (ptd01.BUILDERS[field_id](**arguments), arguments)
    return _FIELDS[field_id]


def programs(structure):
    coordinate_system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system)]


def cell_powers(field):
    return {c.cell_id: sorted({e.power_mw for g in c.groups for e in g.elements}) for c in field.cells}


@pytest.mark.parametrize("field_id, n_cells", [(0, 80), (1, 24), (2, 24), (3, 30), (4, 16), (5, 16), (6, 15),
                                               (7, 20)])
def test_cell_counts_and_validation(field_id, n_cells):
    field, _ = built(field_id)
    assert len(field.cells) == n_cells
    assert field.problems() == []
    assert field.name == ptd01.FIELD_NAMES[field_id] and field.field_id == field_id
    assert field.label_power_mw == pytest.approx(EXAMPLE_STAGE_A.label_power_mw if field_id == 0 else LABEL_MW)


def test_f0_axes_layers_and_blocks(synthetic_attenuator):
    field, arguments = built(0)
    levels = EXAMPLE_STAGE_A.levels_mw()
    assert field.meta["powers_mw"] == levels and field.meta["z_offsets_um"] == list(EXAMPLE_STAGE_A.z_offsets_um)
    for cell in field.cells:
        assert cell.params["power_mw"] == levels[cell.row]
        assert cell.params["z_offset_um"] == EXAMPLE_STAGE_A.z_offsets_um[cell.col]
        assert EXAMPLE_STAGE_A.p_min_mw <= cell.params["power_mw"] <= EXAMPLE_STAGE_A.p_max_mw
    stats = ParameterFieldStructure("ptd01.f0", arguments).statistics()
    assert stats["n_layers"] == 8                       # one layer per z offset, the header shares z = 0
    assert stats["n_blocks"] == 81                      # 10 powers per layer + the header block


def test_f1_lines_and_passes():
    field, _ = built(1)
    for cell in field.cells:
        rel, n = ptd01.F1_P_REL[cell.row], ptd01.F1_PASSES[cell.col]
        assert cell.params_rel["p_rel"] == rel and cell.params["passes"] == n
        elements = [e for g in cell.groups for e in g.elements]
        assert len(elements) == 4 * n                  # 2 x-lines + 2 y-lines, n passes each
        assert [e.power_mw for e in elements] == pytest.approx([EXAMPLE_CALIBRATION.power_mw(rel)] * len(elements))
        assert all(g.z_um == EXAMPLE_CALIBRATION.z0_um for g in cell.groups)


def test_f2_bridge_inside_the_pedestal_top():
    field, _ = built(2)
    line_z = round(3.0 - EXAMPLE_CALIBRATION.l0_um / 2, 3)
    assert field.meta["line_z_um"] == line_z
    for cell in field.cells:
        parts = {e.meta["part"]: e for g in cell.groups for e in g.elements}
        assert set(parts) == {"pedestal", "anchor", "bridge"}
        bridge = [e for g in cell.groups for e in g.elements if e.meta["part"] == "bridge"]
        assert len(bridge) == 1 and bridge[0].points[0, 2] == line_z
        span = ptd01.F2_SPANS_UM[cell.col]
        assert bridge[0].length_um == pytest.approx(span + ptd01.F2_PEDESTAL_UM[0])  # to the pedestal centres
        assert bridge[0].power_mw == pytest.approx(EXAMPLE_CALIBRATION.power_mw(ptd01.F2_P_REL[cell.row]))
        pedestal_powers = [e.power_mw for g in cell.groups for e in g.elements if e.meta["part"] != "bridge"]
        assert pedestal_powers == pytest.approx([EXAMPLE_CALIBRATION.p_ref_mw] * len(pedestal_powers))
        assert min(g.z_um for g in cell.groups) <= -1.5 and cell.min_gap_um == 2.0   # anchored (D15), gap (D11)


def test_f3_spacing_follows_the_width_at_the_cell_power():
    field, _ = built(3)
    model = EXAMPLE_CALIBRATION.voxel_model
    for cell in field.cells:
        power = EXAMPLE_CALIBRATION.power_mw(ptd01.F3_P_REL[cell.row])
        s = ptd01.F3_S_REL[cell.col] * model.width_um(power)
        assert cell.params["spacing_um"] == pytest.approx(s, abs=1e-6)
        group = sorted(e.points[0, 1] for g in cell.groups for e in g.elements if e.meta["part"] == "group")
        assert len(group) == 5 and np.allclose(np.diff(group), s, atol=1e-6)
    assert field.power_range_mw == model.valid_power_mw


def test_f4_pads_have_three_layers_above_the_anchor():
    field, _ = built(4)
    for cell in field.cells:
        power = EXAMPLE_CALIBRATION.power_mw(ptd01.F4_P_REL[cell.row])
        assert cell.params["hatch_um"] == pytest.approx(ptd01.F4_H_REL[cell.col]
                                                        * EXAMPLE_CALIBRATION.voxel_model.width_um(power), abs=1e-6)
        layers = [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "pad"]
        assert len(layers) == ptd01.F4_LAYERS and layers[0] == 0.0
        x0, _, x1, _ = cell.bounds_um()
        assert x1 - x0 == pytest.approx(ptd01.F4_PAD_UM + ptd01.F4_RAMP_UM, abs=0.15)


@pytest.mark.slow
def test_f5_wedges_and_caps():
    field, _ = built(5)
    caps = [c for c in field.cells if c.params["shape"] == "cap"]
    assert len(caps) == 4 and all(c.row == 3 for c in caps)
    assert all(c.params["power_mw"] == pytest.approx(EXAMPLE_CALIBRATION.p_ref_mw) for c in caps)
    for cell in field.cells:
        power = cell.params["power_mw"]
        dz = ptd01.F5_DZ_REL[cell.col] * EXAMPLE_CALIBRATION.voxel_model.length_um(power)
        assert cell.params["slice_um"] == pytest.approx(dz, abs=1e-6)


def test_f6_crossings():
    field, _ = built(6)
    types = {c.row: c.params["type"] for c in field.cells}
    assert types == {0: "star", 1: "grid", 2: "woodpile"}
    star = next(c for c in field.cells if c.params["type"] == "star")
    assert sum(len(g.elements) for g in star.groups) == 4
    woodpile = next(c for c in field.cells if c.params["type"] == "woodpile")
    zs = [g.z_um for g in woodpile.groups]
    assert len(zs) == 4 and zs[1] - zs[0] == pytest.approx(0.6 * EXAMPLE_CALIBRATION.l0_um, abs=1e-3)


@pytest.mark.slow
def test_f7_pillars_on_bases():
    field, _ = built(7)
    for cell in field.cells:
        height = ptd01.F7_HEIGHTS_UM[cell.col]
        pillar = [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "pillar"]
        base = [g.z_um for g in cell.groups if g.elements[0].meta["part"] == "base"]
        assert min(pillar) >= 1.4 and max(base) < 1.4
        assert max(pillar) == pytest.approx(1.4 + height, abs=cell.params["slice_um"] + 1e-3)
        assert height < ptd01.F7_BASE_UM[0] + 4.5          # lower than the pitch (D10)


@pytest.mark.slow
@pytest.mark.parametrize("field_id", range(8))
def test_layer_counts_and_program_lines(field_id, synthetic_attenuator):
    field, arguments = built(field_id)
    structure = ParameterFieldStructure(f"ptd01.f{field_id}", arguments)
    texts = programs(structure)
    log.info("%s: %d layer programs, %d IFOV blocks", field.name, len(texts), structure.statistics()["n_blocks"])
    assert len(texts) == len(field.z_levels_um()) <= MAX_LAYERS[field_id]
    assert max(len(t.splitlines()) for t in texts) < MAX_PROGRAM_LINES


def test_every_power_inside_the_given_range():
    field, _ = built(0)
    assert all(EXAMPLE_STAGE_A.p_min_mw <= p <= EXAMPLE_STAGE_A.p_max_mw
               for powers in cell_powers(field).values() for p in powers)
    for field_id in (1, 2, 3, 4, 6):
        field, _ = built(field_id)
        rel = max(r for c in field.cells for r in [c.params_rel.get("p_rel", 0)])
        assert max(p for powers in cell_powers(field).values() for p in powers) <= \
               EXAMPLE_CALIBRATION.power_mw(max(rel, EXAMPLE_CALIBRATION.p_ref_factor)) + 1e-9


def test_cell_power_outside_the_model_range_is_reported():
    narrow = dataclasses.replace(EXAMPLE_CALIBRATION, voxel_model=VoxelFitModel(
        "threshold_ln", EXAMPLE_CALIBRATION.voxel_model.params, (0.33, 0.6), 5000.0))
    with pytest.raises(ValueError, match="no extrapolation"):   # w(P) cannot be evaluated for 2.25 P_th
        ptd01.field_f3(calibration=narrow.to_json(), label_power_mw=LABEL_MW)
    field = ptd01.field_f3(calibration=narrow.to_json(), label_power_mw=LABEL_MW, p_rel=[1.25, 1.5, 1.75, 2.0])
    assert field.problems() == []
    wide_cells = dataclasses.replace(field, power_range_mw=(0.4, 0.6))
    with pytest.raises(FieldLayoutError, match="outside the voxel model range"):
        wide_cells.to_toolpath_job()


def test_builds_are_deterministic(synthetic_attenuator):
    for field_id in (2, 3):
        _, arguments = built(field_id)
        first = programs(ParameterFieldStructure(f"ptd01.f{field_id}", arguments))
        again = programs(ParameterFieldStructure(f"ptd01.f{field_id}", dict(arguments)))
        assert first == again


def test_f3_golden_program(synthetic_attenuator, golden):
    """ Decision D6: a program reference of the small single-layer field F3. """

    _, arguments = built(3)
    golden("ptd01_f3", "\n".join(programs(ParameterFieldStructure("ptd01.f3", arguments))) + "\n")
