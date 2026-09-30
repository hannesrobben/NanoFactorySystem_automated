"""Dry run of the experiment template mains/Experiments/default_exp_file.py on the dummy backend.

The whole flow runs as on the lab PC: System start-up, plane_fit() (with the
known plane of the simulated sample instead of a measurement),
build_programs() and print_experiment(), which loads and runs every layer
program as a controller task and takes camera images. Everything is written
to tmp_path.
"""
import importlib.util
import json
import os
from pathlib import Path

import matplotlib
import pytest

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.storage import ExperimentStore
from nanofactorysystem.storage.json_copies import experiment_dictionary, structures_list

TEMPLATE = Path(__file__).parents[2] / "mains" / "Experiments" / "default_exp_file.py"

# Resin drop edges and experiment center in µm, as in mains/main.py
RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]
CENTER = Point2D(X=1310, Y=19500)


def load_template():
    spec = importlib.util.spec_from_file_location("default_exp_file_dry_run", TEMPLATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.slow
def test_default_experiment_dry_run(test_config, dummy_backend, no_sleep, tmp_path, monkeypatch):
    matplotlib.use("Agg")
    monkeypatch.chdir(tmp_path)
    world = dummy_backend.world
    template = load_template()

    template.binary_testprint(
        absolute_center=CENTER,
        resin_dimension=RESIN_EDGES,
        path=tmp_path / "out",
        objective="Zeiss 20x",
        user="Test",
        dhm_usage=False,
        substrate={"Name": "dry-run substrate", "Number of drops": 1},
        backend=dummy_backend,
        plane=world.sample.plane(),
    )

    # Experiment output: the experiment file and its JSON copies
    out = tmp_path / "out" / "testprint_dhm"
    for name in ("experiment.h5", "experiment_dictionary.json", "structures.json", "print_progress.json"):
        assert (out / name).is_file(), name
    assert not (out / "experiment.lock").exists()
    record = ExperimentStore.open(out).read()
    structures = json.loads((out / "structures.json").read_text())
    assert structures == structures_list(record)
    assert json.loads((out / "experiment_dictionary.json").read_text()) == experiment_dictionary(record, out)
    assert record.status == "finished" and record.system["backend"] == "dummy"
    assert record.calibration["table"].shape[1] == 2
    assert record.plane_fit.source == "given"
    assert [s.status for s in record.structures] == ["printed"] * len(structures)
    assert record.layout.double_corner.name == "corner_tl"
    assert record.layout.qrcode_text == record.uuid
    # Paths are stored relative to the experiment folder (T57)
    assert all(not Path(f).is_absolute() for s in structures for f in s["layer_files"])
    layer_files = [out / f for s in structures for f in s["layer_files"]]
    assert structures and layer_files
    assert all(f.is_file() for f in layer_files)

    # Every layer program was loaded, run to completion and fully understood by the simulation.
    # If this fails after adding new AeroBasic commands, extend FakeA3200Transport.execute().
    runs = world.calllog.filter(device="program")
    assert len(runs) == len(layer_files)
    assert all(r.result["not_simulated"] == 0 for r in runs)
    assert all(task.state == 2 for task in world.tasks.values())  # idle after Task.finish()
    assert not [r for r in world.calllog.filter(device="controller") if not r.result.startswith("%")]
    assert dummy_backend.transport.unhandled == []

    # The structures were written on the given substrate plane
    assert world.exposures
    plane = world.sample.plane()
    for exposure in world.exposures:
        x_um, y_um, z_um = (1000 * v for v in exposure.end)
        assert abs(z_um - plane(x_um, y_um)) < 20.0

    # Substrate information is passed on to the experiment
    assert json.loads((tmp_path / "out" / "substrate_information.json").read_text())["Name"] == "dry-run substrate"

    # Camera images before, during and after writing, stored in the experiment file
    cameras = [c for c in record.captures if c.kind == "camera"]
    assert len(cameras) == len(layer_files) + 2 * len(structures)
    assert not list(out.rglob("*.zdc"))

    # Nothing was written outside tmp_path's output and backend folders
    assert set(os.listdir(tmp_path)) <= {"out", "dummy", "programs"}
