"""Dry run of the lab check of the new features (mains/lab_checks/new_features_check.py)."""
import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from nanofactorysystem.storage import ExperimentStore
from nanofactorysystem.substrate_plan import check_layout

SCRIPT = Path(__file__).parents[2] / "mains" / "lab_checks" / "new_features_check.py"


def load():
    spec = importlib.util.spec_from_file_location("new_features_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lab_check_layout_is_valid(test_config):
    module = load()
    areas = check_layout(module.SUBSTRATE, [module.SubstrateExperiment(module.drawing_spec()),
                                            module.SubstrateExperiment(module.slicer_spec())])
    assert [a.name for a in areas] == ["check_drawing", "check_slicer"]


@pytest.mark.slow
def test_lab_check_dry_run(test_config, dummy_backend, no_sleep, tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use("Agg")
    module = load()
    monkeypatch.setattr(module, "SUBSTRATE", dataclasses.replace(module.SUBSTRATE, user="Test"))

    folders = module.main(backend=dummy_backend, plane=dummy_backend.world.sample.plane(),
                          data_root=tmp_path / "root")

    drawing, slicer = (ExperimentStore.open(f).read() for f in folders)
    assert drawing.status == slicer.status == "finished"
    assert [s.name for s in drawing.structures if s.type == "NORMAL"] == ["rect", "ramp"]
    assert drawing.structure("rect_rep1").repeat_of == "rect"
    assert drawing.structure("ramp").layer_powers_mw == module.LAYER_POWERS_MW
    assert {c.kind for c in drawing.captures} == {"camera"}
    store = ExperimentStore.open(folders[0])
    assert store.read_overview("before") is not None and store.read_overview("after") is not None
    assert [s.type for s in slicer.structures if s.name == "block"] == ["IFOV"]
    # Unpacked next to the experiment file (T66)
    for folder in folders:
        assert (folder / "unpacked" / "summary.txt").exists()
    assert json.loads((folders[0] / "experiment_summary.json").read_text())["structures"]
