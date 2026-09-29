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
        backend=dummy_backend,
        plane=world.sample.plane(),
    )

    # Experiment output
    out = tmp_path / "out" / "testprint_dhm"
    for name in ("experiment_dictionary.json", "structures.json", "print_progress.json", "calibration_file.npy"):
        assert (out / name).is_file(), name
    structures = json.loads((out / "structures.json").read_text())
    layer_files = [Path(f) for s in structures for f in s["layer_files"]]
    assert structures and layer_files
    assert all(f.is_file() for f in layer_files)
    assert all(tmp_path in f.parents for f in layer_files)

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

    # Camera images before, during and after writing
    assert list((out / "structures").rglob("camera_*.zdc"))

    # Nothing was written outside tmp_path's output and backend folders
    assert set(os.listdir(tmp_path)) <= {"out", "dummy", "programs"}
