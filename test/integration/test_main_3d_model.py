"""The 3D-model script mains/main_3D_model.py on the experiment environment (T166)."""
import importlib.util
import sys
from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.experiment import ProgramSource  # noqa: E402
from nanofactorysystem.experiment_spec import ExperimentSpec  # noqa: E402
from nanofactorysystem.storage import ExperimentStore  # noqa: E402

MAINS = Path(__file__).parents[2] / "mains"
TEST_RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


@pytest.fixture
def model_script(monkeypatch, tmp_path):
    """ mains/main_3D_model.py with a 20 x 10 x 2 µm box as model and a lab-independent resin drop. """

    monkeypatch.syspath_prepend(str(MAINS))  # the script imports main.py from mains/
    monkeypatch.delitem(sys.modules, "main", raising=False)
    spec = importlib.util.spec_from_file_location("main_3D_model", MAINS / "main_3D_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "box.stl"
    trimesh.creation.box(extents=(20.0, 10.0, 2.0)).export(str(path))
    monkeypatch.setattr(module, "MODEL_PATH", path)
    monkeypatch.setattr(module, "MODEL_UNIT", "um")
    monkeypatch.setattr(module, "SUBSTRATE_LABEL", None)
    monkeypatch.setattr(module, "CENTER", None)
    monkeypatch.setattr(module.settings, "RESIN_EDGES", TEST_RESIN_EDGES)
    monkeypatch.setattr(module, "SLICER", dict(module.SLICER, hatch_size=1.0, slice_size=1.0))
    return module


def test_spec_is_one_sliced_model_in_the_drop_center(model_script, tmp_path):
    assert model_script.model_size_um() == pytest.approx((20.0, 10.0, 2.0))
    spec = model_script.experiment_spec()
    assert spec.name == "model3d_box" and spec.program_source == ProgramSource.SLICER and spec.setup == "IFOV_on"
    assert spec.structure_size_um == pytest.approx(20.0 + model_script.MARGIN_AROUND_UM)
    [structure] = spec.structures
    assert structure.height_data == model_script.MODEL_PATH and structure.slicer["center"].Z == -0.5
    # the spec is a project file: the model is stored with its SHA-256 and the spec reads back
    path = spec.save(tmp_path / "spec" / "experiment_spec.json")
    assert ExperimentSpec.load(path).structures[0].slicer["hatch_size"] == 1.0


def test_missing_model_file_is_named(model_script, tmp_path, monkeypatch):
    monkeypatch.setattr(model_script, "MODEL_PATH", tmp_path / "missing.stl")
    with pytest.raises(FileNotFoundError, match="missing.stl"):
        model_script.experiment_spec()


@pytest.mark.slow
def test_dry_run(model_script, test_config, tmp_path):
    folder = model_script.run(dry=True, workdir=tmp_path / "dry")
    record = ExperimentStore.open(folder).read()
    assert record.status == "finished"
    assert [s.name for s in record.structures if s.type == "IFOV"] == ["box"]
