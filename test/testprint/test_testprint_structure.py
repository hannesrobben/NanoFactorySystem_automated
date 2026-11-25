"""ParameterFieldStructure: toolpath IR → IFOV layer programs (T137)."""
import json
import re

import numpy as np
import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json  # noqa: E402
from nanofactorysystem.aerobasic.slicer import JobParameters  # noqa: E402
from nanofactorysystem.aerobasic.slicer.toolpath import (  # noqa: E402
    KIND_LAYER, ROLE_CONTOUR, ElementGroup, PathElement, ToolpathJob)
from nanofactorysystem.backends.dummy.attenuator import write_calibration_file  # noqa: E402
from nanofactorysystem.backends.dummy.world import SimulatedWorld  # noqa: E402
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Unit  # noqa: E402
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration  # noqa: E402
from nanofactorysystem.testprint.structure import (  # noqa: E402
    ParameterFieldStructure, merge_groups_by_z, register_field_builder)


@pytest.fixture(autouse=True)
def synthetic_calibration(tmp_path):
    path = write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(path)):
        yield


def _line(x, y, z, power=None):
    return PathElement.from_segment_2d(x, y, x + 2.0, y, z, power_mw=power)


@register_field_builder("test.three_powers")
def three_powers(*, with_structure_power: bool = True):
    """ Two layers, three powers: layer z=0 has 1.0, 1.0, 2.0 mW lines; layer z=0.5 has 2.0 and 3.0 mW. """

    groups = [
        ElementGroup(kind=KIND_LAYER, z_um=0.5, elements=[_line(0, 0, 0.5, 2.0), _line(0, 1, 0.5, 3.0)]),
        ElementGroup(kind=KIND_LAYER, z_um=0.0, elements=[_line(0, 0, 0.0, 1.0), _line(0, 1, 0.0, 1.0),
                                                          _line(0, 2, 0.0, 2.0)]),
    ]
    return ToolpathJob(params=JobParameters(), groups=groups)


@register_field_builder("test.mixed_kinds")
def mixed_kinds():
    ring = PathElement.from_polyline_2d(np.array([[0, 0], [1, 0], [1, 1]]), 0.0, closed=True, role=ROLE_CONTOUR,
                                        power_mw=1.0)
    groups = [ElementGroup(kind=KIND_LAYER, z_um=0.0, elements=[_line(0, 0, 0.0, 1.0), ring, _line(0, 2, 0.0, 1.0),
                                                               _line(0, 3, 0.0)])]
    return ToolpathJob(params=JobParameters(), groups=groups)


def programs(structure):
    coordinate_system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system)]


def power_comments(text):
    return re.findall(r"Power set to ([0-9.]+) mW", text)


def test_one_block_per_power_run_and_layers_in_ascending_z():
    structure = ParameterFieldStructure("test.three_powers", {}, power_mw=0.5)
    texts = programs(structure)
    assert len(texts) == 2                                      # z = 0.0 first, then z = 0.5
    assert [power_comments(t) for t in texts] == [["1.0", "2.0"], ["2.0", "3.0"]]
    assert all(t.count("IFOV ON") == len(power_comments(t)) for t in texts)  # one IFOV block per power run
    assert structure.element_powers_mw == [1.0, 2.0, 3.0]
    stats = structure.statistics()
    assert stats["n_layers"] == 2 and stats["n_blocks"] == 4 and stats["z_levels_um"] == [0.0, 0.5]
    assert stats["n_elements"] == 5


def test_set_power_values_follow_the_calibration():
    texts = programs(ParameterFieldStructure("test.three_powers", {}, power_mw=0.5))
    values = re.findall(r"\$AO\[0\]\.A=([0-9.eE+-]+)", texts[0])
    assert len(values) == 2 and float(values[0]) < float(values[1])  # 1 mW below 2 mW on the attenuator


def test_leaf_kinds_and_element_order_are_kept():
    texts = programs(ParameterFieldStructure("test.mixed_kinds", {}, power_mw=0.5))
    # line (1.0) | ring (1.0, polyline leaf) | line (1.0) | line (structure power 0.5)
    assert power_comments(texts[0]) == ["1.0", "1.0", "1.0", "0.5"]


def test_dwell_only_after_power_changes():
    plain = programs(ParameterFieldStructure("test.three_powers", {}, power_mw=0.5))
    assert all("DWELL" not in t for t in plain)
    texts = programs(ParameterFieldStructure("test.three_powers", {}, power_mw=0.5, dwell_after_power_s=0.05))
    for text in texts:
        lines = text.splitlines()
        power_lines = [i for i, line in enumerate(lines) if line.startswith("$AO[0].A=")]
        dwell_lines = [i for i, line in enumerate(lines) if line.startswith("DWELL")]
        assert dwell_lines == [i + 2 for i in power_lines]      # comment + DWELL right after each change
        assert all(lines[i] == "DWELL 0.050" for i in dwell_lines)
    # mixed_kinds: four blocks, but the power changes only once (1.0 → 0.5) after the first block of the layer
    text = programs(ParameterFieldStructure("test.mixed_kinds", {}, power_mw=0.5, dwell_after_power_s=0.05))[0]
    assert text.count("DWELL") == 2


def test_per_element_powers_need_a_structure_power():
    with pytest.raises(ValueError, match="power of the structure"):
        programs(ParameterFieldStructure("test.three_powers", {}))


def test_json_round_trip_rebuilds_the_same_programs():
    structure = ParameterFieldStructure("test.three_powers", {"with_structure_power": True}, power_mw=0.5,
                                        objective="Zeiss 63x", dwell_after_power_s=0.01)
    data = json.loads(json.dumps(structure.to_json()))
    assert "__missing__" not in data and data["statistics"]["n_blocks"] == 4
    again = structure_from_json(data)
    assert isinstance(again, ParameterFieldStructure)
    assert programs(again) == programs(structure)


def test_objective_and_dwell_are_checked():
    with pytest.raises(ValueError, match="not supported"):
        ParameterFieldStructure("test.three_powers", {}, objective="Nikon 20x")
    with pytest.raises(ValueError, match="dwell"):
        ParameterFieldStructure("test.three_powers", {}, dwell_after_power_s=-1)
    with pytest.raises(KeyError, match="not registered"):
        ParameterFieldStructure("test.unknown", {}, builder_module="").field


def test_merge_groups_by_z_rounds_to_one_nanometre():
    groups = [ElementGroup(kind=KIND_LAYER, z_um=0.3000004, elements=[_line(0, 0, 0.3)]),
              ElementGroup(kind=KIND_LAYER, z_um=-0.0, elements=[_line(0, 1, 0.0)]),
              ElementGroup(kind=KIND_LAYER, z_um=0.29999996, elements=[_line(0, 2, 0.3)])]
    merged = merge_groups_by_z(groups)
    assert [g.z_um for g in merged] == [0.0, 0.3]
    assert [len(g) for g in merged] == [1, 2]
    assert str(merged[0].z_um) == "0.0"
