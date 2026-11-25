"""Parameter-test scripts in mains/parametertest/ (T162): Quick PT, Full PT-01, Voxel PT-01."""
import dataclasses
import importlib
from pathlib import Path

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.experiment import StructureType  # noqa: E402
from nanofactorysystem.storage import ExperimentStore  # noqa: E402
from nanofactorysystem.storage.substrate_store import find_experiments  # noqa: E402
from nanofactorysystem.substrate_plan import check_layout  # noqa: E402

MAINS = Path(__file__).parents[2] / "mains"


@pytest.fixture
def pt(monkeypatch):
    monkeypatch.syspath_prepend(str(MAINS))  # the scripts import parametertest.… from mains/
    common = importlib.import_module("parametertest.common")
    monkeypatch.setattr(common, "USER", "Test")
    return common


def all_specs(pt):
    inputs = pt.load_inputs()
    return [e.spec for test in pt.TESTS for e in pt.experiments(test, inputs)]


def test_inputs_file_and_experiments(pt, test_config):
    inputs = pt.load_inputs()
    assert inputs.material == pt.RESIN and inputs.powers_mw[0] == 0.1 and inputs.powers_mw[-1] == 1.0
    specs = all_specs(pt)
    assert len(specs) == 1 + 7 + 10
    for spec in specs:
        resolved = spec.resolved()
        assert resolved.objective == "Zeiss 63x" and resolved.setup == "IFOV_on" and resolved.margin_um == 90.0
        assert resolved.corner == pt.FIELD_CORNER and not resolved.skip_corner and not resolved.dhm_usage
        assert resolved.tags[0] == "parameter_test"
    quick, full = specs[0], specs[1]
    assert quick.grid == (2, 2) and [s.name for s in quick.structures] == ["Q1_walls_a", "Q1_walls_b", "Q2_pads_a",
                                                                          "Q2_pads_b"]
    assert full.grid == (1, 2) and [s.factory.arguments["half"] for s in full.structures] == ["a", "b"]
    voxel = specs[8]
    assert voxel.grid == (3, 4) and voxel.resolved().structure_size_um == 100.0 and voxel.resolved().padding_um == 0.0
    gaps = [s.factory.arguments["gap_um"] for s in voxel.structures if s.factory is not None]
    assert gaps == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
    assert voxel.structures[-1].structure_type == StructureType.DUMMY


def test_qr_code_and_corners_stay_out_of_the_grid(pt, test_config):
    for spec in all_specs(pt):
        pt.check_marker_clearance(spec)                     # 90 µm margin: QR code 20 µm away from the grid
    too_small = dataclasses.replace(all_specs(pt)[0], margin_um=50.0)
    with pytest.raises(ValueError, match="QR code"):
        pt.check_marker_clearance(too_small)


def test_layout_of_all_tests_on_the_drop(pt, test_config):
    areas = check_layout(pt.substrate_spec(), [e for test in pt.TESTS for e in pt.experiments(test, pt.load_inputs())])
    assert len(areas) == 18


def test_selection(pt, test_config):
    inputs = pt.load_inputs()
    assert [e.spec.name for e in pt.experiments("full", inputs, only=["F3", "5"])] == \
           ["full_pt01_F3_line_pairs", "full_pt01_F5_layers"]
    assert [e.spec.name for e in pt.experiments("voxel", inputs, only=["0.5"])] == ["voxel_pt01_p0.50"]
    with pytest.raises(ValueError, match="no fields"):
        pt.experiments("full", inputs, only=["F9"])
    with pytest.raises(ValueError, match="not in the power ladder"):
        pt.experiments("voxel", inputs, only=["0.55"])
    chain = importlib.import_module("parametertest.chain")
    assert chain.tests_of("all") == ["quick", "full", "voxel"]


@pytest.mark.slow
def test_dry_run_of_quick_full_and_voxel(pt, test_config, dummy_backend, no_sleep, tmp_path, capsys):
    import matplotlib
    matplotlib.use("Agg")
    plane = dummy_backend.world.sample.plane()
    root = tmp_path / "data"
    folders = pt.run(["quick"], backend=dummy_backend, plane=plane, data_root=root)
    folders += pt.run(["full"], only=["F3"], backend=dummy_backend, plane=plane, data_root=root)
    folders += pt.run(["voxel"], only=["0.5"], backend=dummy_backend, plane=plane, data_root=root)
    assert "sum" in capsys.readouterr().out
    assert len(folders) == 3 and len(find_experiments(root)) == 3
    for folder in folders:
        record = ExperimentStore.open(folder).read()
        assert record.status == "finished"
        assert (folder / pt.INPUTS_FILE.name).is_file()       # material start file copied
    names = [s.name for s in ExperimentStore.open(folders[2]).read().structures if s.type == "IFOV"]
    assert len(names) == 11 and names[0] == "V_p0.50_g0.00"
    # T163: the cell tables are regenerated from /spec with absolute values and the sub-field
    from experiment_analysis.ptd import cell_table
    quick_rows = cell_table(folders[0])
    assert len(quick_rows) == 10 + 10 + 20 + 20 and {r["half"] for r in quick_rows} == {"a", "b"}
    assert {r["material"] for r in quick_rows} == {pt.RESIN}
    voxel_rows = cell_table(folders[2])
    assert sorted(r["gap_um"] for r in voxel_rows) == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
