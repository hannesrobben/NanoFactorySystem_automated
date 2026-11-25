"""PTD-01 chain mains/Experiments/ptd01/chain_ptd01.py, stages A and B (T146)."""
import importlib
from pathlib import Path

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.storage import ExperimentStore  # noqa: E402
from nanofactorysystem.storage.substrate_store import find_experiments  # noqa: E402
from nanofactorysystem.substrate_plan import check_layout  # noqa: E402

MAINS = Path(__file__).parents[2] / "mains"
QUICK_AXES = {2: {"p_rel": [1.0, 2.5]}, 4: {"p_rel": [1.25], "h_rel": [0.5, 1.0]},
              5: {"p_rel": [1.5], "dz_rel": [0.4, 0.6]}, 7: {"p_rel": [1.5], "heights_um": [2.0, 4.0]}}


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.syspath_prepend(str(MAINS))
    common = importlib.import_module("Experiments.ptd01.common")
    monkeypatch.setattr(common, "USER", "Test")
    return importlib.import_module("Experiments.ptd01.chain_ptd01")


def tags_of(spec: dict) -> list:
    """ The tags stored somewhere in the spec dict. """

    if isinstance(spec, dict):
        if "tags" in spec:
            return spec["tags"]
        for value in spec.values():
            found = tags_of(value)
            if found:
                return found
    return []


def test_field_selection(chain):
    assert chain.field_ids("A") == [0]
    assert chain.field_ids("B") == [1, 2, 3, 4, 5, 6, 7]
    assert chain.field_ids("all") == list(range(8))
    assert chain.field_ids("B", "F5,f3") == [3, 5]               # print order, case-insensitive
    with pytest.raises(ValueError, match="do not belong to stage A"):
        chain.field_ids("A", "F3")
    with pytest.raises(ValueError, match="Unknown stage"):
        chain.field_ids("C")


def test_stage_b_needs_a_calibration_before_anything_moves(chain, tmp_path):
    with pytest.raises(ValueError, match="needs the calibration"):
        chain.main("B")
    with pytest.raises(FileNotFoundError):
        chain.main("B", calibration_path=tmp_path / "missing.json")
    with pytest.raises(ValueError, match="example values"):
        chain.main("B", calibration_path=chain.common.EXAMPLE_CALIBRATION_FILE)


def test_mismatching_calibration_is_refused(chain, tmp_path):
    calibration = chain.common.load_calibration(chain.common.EXAMPLE_CALIBRATION_FILE, allow_example=True)
    import dataclasses
    other = dataclasses.replace(calibration, material="IP-Dip", source="measured").save(tmp_path / "c.json")
    with pytest.raises(ValueError, match="IP-Dip"):
        chain.main("B", calibration_path=other)


def test_layout_of_all_eight_fields_on_the_t113_drop(chain, test_config):
    common = chain.common
    calibration = common.load_calibration(common.EXAMPLE_CALIBRATION_FILE, allow_example=True)
    areas = check_layout(common.substrate_spec(), common.experiments(chain.field_ids("all"), calibration=calibration,
                                                                     stage_a=common.load_stage_a()))
    assert len(areas) == 8 and areas[0].name == "ptd01_F0_interface"


@pytest.mark.slow
def test_stage_a_and_stage_b_dry_run(chain, test_config, dummy_backend, no_sleep, tmp_path, capsys):
    import matplotlib
    matplotlib.use("Agg")
    common = chain.common
    plane = dummy_backend.world.sample.plane()
    root = tmp_path / "data"
    stage_a = chain.main("A", backend=dummy_backend, plane=plane, data_root=root)
    stage_b = chain.main("B", calibration_path=common.EXAMPLE_CALIBRATION_FILE, axes=QUICK_AXES,
                         backend=dummy_backend, plane=plane, data_root=root, allow_example=True)
    assert "sum" in capsys.readouterr().out                    # summed time estimate printed
    folders = stage_a + stage_b
    assert len(folders) == 8
    index = find_experiments(root)
    assert len(index) == 8 and all(e["status"] == "finished" for e in index)
    for field_id, folder in enumerate(folders):
        record = ExperimentStore.open(folder).read()
        assert tags_of(record.spec) == ["ptd01", f"F{field_id}", "stage_A" if field_id == 0 else "stage_B"]
        assert (folder / common.EXAMPLE_CALIBRATION_FILE.name).is_file() == (field_id > 0)
