"""PTD-01 field scripts in mains/Experiments/ptd01/ (T145)."""
import importlib
import logging
from pathlib import Path

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.experiment import StructureType  # noqa: E402
from nanofactorysystem.storage import ExperimentStore  # noqa: E402
from nanofactorysystem.substrate_plan import check_layout  # noqa: E402

MAINS = Path(__file__).parents[2] / "mains"
SCRIPTS = {0: "f0_interface", 1: "f1_lines", 2: "f2_bridges", 3: "f3_line_pairs", 4: "f4_squares", 5: "f5_layers",
           6: "f6_crossings", 7: "f7_pillars"}
# Fewer axis levels for the heavy volume fields, to keep the dry run short; the full fields are built
# and checked (layers, program lines) in test/testprint/test_testprint_ptd01.py
QUICK_AXES = {4: {"p_rel": [1.25], "h_rel": [0.5, 1.0]}, 5: {"p_rel": [1.5], "dz_rel": [0.4, 0.6]},
              7: {"p_rel": [1.5], "heights_um": [2.0, 4.0]}, 2: {"p_rel": [1.0, 2.5]}}
log = logging.getLogger(__name__)


@pytest.fixture
def ptd(monkeypatch):
    monkeypatch.syspath_prepend(str(MAINS))  # the scripts import Experiments.… from mains/
    common = importlib.import_module("Experiments.ptd01.common")
    monkeypatch.setattr(common, "USER", "Test")
    return common


def script(field_id):
    return importlib.import_module(f"Experiments.ptd01.{SCRIPTS[field_id]}")


def test_every_field_is_one_ifov_experiment(ptd, test_config):
    for field_id in range(8):
        spec = script(field_id).experiment_spec(calibration_path=ptd.EXAMPLE_CALIBRATION_FILE,
                                               allow_example=True).resolved()
        assert spec.objective == "Zeiss 63x" and spec.setup == "IFOV_on" and spec.grid == (1, 1)
        assert spec.tags == ["ptd01", f"F{field_id}", "stage_A" if field_id == 0 else "stage_B"]
        assert spec.corner == ptd.FIELD_CORNER and not spec.skip_corner        # reduced corners with QR (D2)
        assert spec.camera_capture and spec.overview_capture and not spec.dhm_usage
        [structure] = spec.structures
        assert structure.factory.name == f"ptd01.f{field_id}" and structure.structure_type == StructureType.IFOV
        assert structure.axes == "XYZ" and structure.repeat == 0


def test_replicates_use_repeat(ptd, test_config):
    spec = script(3).experiment_spec(calibration_path=ptd.EXAMPLE_CALIBRATION_FILE, allow_example=True,
                                     replicates=3)
    assert spec.grid == (1, 3) and spec.structures[0].repeat == 2


def test_stage_b_refuses_missing_and_example_calibrations(ptd, tmp_path):
    with pytest.raises(FileNotFoundError, match="evaluate stage A"):
        ptd.load_calibration(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="example values"):
        ptd.load_calibration(ptd.EXAMPLE_CALIBRATION_FILE)
    assert ptd.load_calibration(ptd.EXAMPLE_CALIBRATION_FILE, allow_example=True).material == ptd.RESIN
    assert ptd.load_stage_a().material == ptd.RESIN


def test_single_field_layout(ptd, test_config):
    areas = check_layout(ptd.substrate_spec(), ptd.experiments([3], calibration=ptd.load_calibration(
        ptd.EXAMPLE_CALIBRATION_FILE, allow_example=True)))
    assert [a.name for a in areas] == ["ptd01_F3_line_pairs"]


@pytest.mark.slow
@pytest.mark.parametrize("field_id", range(8))
def test_field_dry_run(ptd, field_id, test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    folders = script(field_id).main(backend=dummy_backend, plane=dummy_backend.world.sample.plane(),
                                    data_root=tmp_path / "data", calibration_path=ptd.EXAMPLE_CALIBRATION_FILE,
                                    axes=QUICK_AXES.get(field_id), allow_example=True)
    assert len(folders) == 1
    record = ExperimentStore.open(folders[0]).read()
    assert record.status == "finished"
    assert [s.name for s in record.structures if s.type == "IFOV"] == [script(field_id).common.ptd01.FIELD_NAMES[field_id]]
    log.info("F%d: estimated printing time %.0f s", field_id, record.time_estimate["total_s"])
    assert record.time_estimate["total_s"] > 0
    if field_id:
        assert (folders[0] / ptd.EXAMPLE_CALIBRATION_FILE.name).is_file()  # calibration copied (stage B)
