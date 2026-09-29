"""Tests for Experiment (experiment.py) on the dummy backend."""
import json

import matplotlib
import pytest

from nanofactorysystem.aerobasic.programs.drawings import Rectangle3D
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType
from nanofactorysystem.runtime import getLogger


def make_experiment(path, backend, *, dhm_usage=False, skip_corner=True, substrate=None, setup="IFOV_off"):
    """ Small 20x experiment with one grid cell, as in the experiment template. """

    matplotlib.use("Agg")
    sys_args = {
        "attenuator": {"fitKind": "quadratic"},
        "controller": {"zMax": 24550.0},
        "dhm": {"usage": dhm_usage, "oplStep": 100.0},
    }
    return Experiment(
        path=path, user="Test", objective="Zeiss 20x", logger=getLogger(logfile=path / "console.log"),
        sys_args=sys_args,
        default_power=0.7, low_speed_um=1000, high_speed_um=5000,
        resin_corner_tr=Point2D(5720, 27190), resin_corner_bl=Point2D(-3333, 17212),
        structure_size=500, margin=200, padding=100, absolute_grid_center=Point2D(1310, 19500),
        grid=(1, 1), n_mid_points=0, drop_direction=DropDirection.UP,
        corner_z=-2, corner_width=50, corner_length=300, corner_height=7, corner_hatch=0.5, corner_slice=0.75,
        fov_dim=(500, 500), skip_corner=skip_corner, setup=setup, backend=backend,
        substrate_information=substrate)


@pytest.fixture
def experiment(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        yield experiment


def add_rectangle(experiment, name="rect"):
    experiment.add_structure(
        StructureType.NORMAL, name, axes="XYZ", power=0.7,
        structure=Rectangle3D(Point3D(0, 0, -1), 10, 10, 3, hatch_size=1.0, slice_size=1.0,
                              velocity=1000, acceleration=500))


def progress(experiment):
    return json.loads((experiment.path / "print_progress.json").read_text())


def test_print_experiment_runs_all_layers(experiment, dummy_backend):
    add_rectangle(experiment)
    experiment.build_programs()

    experiment.print_experiment()

    runs = dummy_backend.calllog.filter(device="program")
    layers = experiment.structure_configs[0]["layer_files"]
    assert len(runs) == len(layers) > 1
    data = progress(experiment)
    assert data["error log"] == []
    assert [s["name"] for s in data["finished_structures"]] == ["rect"]


def test_failed_layer_is_logged_and_printing_continues(experiment, dummy_backend):
    add_rectangle(experiment)
    experiment.build_programs()
    dummy_backend.transport.program_error_next(error_code=42, running_polls=1)

    experiment.print_experiment()

    data = progress(experiment)
    assert len(data["error log"]) == 1
    assert "42" in data["error log"][0]["error"]
    # The failed task was stopped and all layers were attempted
    assert "PROGRAM 1 STOP" in dummy_backend.calllog.commands()
    layers = experiment.structure_configs[0]["layer_files"]
    assert len(dummy_backend.calllog.filter(device="program")) == len(layers)
    assert [s["name"] for s in data["finished_structures"]] == ["rect"]


def test_experiment_dictionary(experiment):
    data = json.loads((experiment.path / "experiment_dictionary.json").read_text())

    assert data["objective"] == "Zeiss 20x"
    assert data["logger"] == str(experiment.path / "console.log")


def test_structure_without_layers(experiment):
    experiment.print_structure([], x=1310.0, y=19500.0, name="empty", power=0.7)

    data = progress(experiment)
    assert data["finished_structures"][-1] == {"name": "empty", "finished layer": None}


def test_opl_scan_uses_dhm_motor_scan(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, dhm_usage=True) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())

        m = experiment.opl_scan(m0=800.0)

        assert m == pytest.approx(dummy_backend.world.opl_optimum, abs=100.0)
        assert experiment.system.dhm.device.MotorPos == pytest.approx(m)
        assert float((path / "oplscan" / "opl.txt").read_text()) == pytest.approx(m)
        # A second call reads the stored result instead of scanning again
        assert experiment.opl_scan(m0=0.0) == pytest.approx(m)


def test_substrate_information_is_merged(test_config, dummy_backend, no_sleep, tmp_path):
    for i, info in enumerate([{"name": "S1", "drops": 1}, {"drops": 2, "used drop": "center"}]):
        path = tmp_path / f"experiment{i}"
        path.mkdir()
        with make_experiment(path, dummy_backend, substrate=info):
            pass

    data = json.loads((tmp_path / "substrate_information.json").read_text())
    assert data == {"name": "S1", "drops": 2, "used drop": "center"}


def test_restart_from_stored_dictionary(test_config, dummy_backend, no_sleep, tmp_path):
    import importlib.util
    from pathlib import Path

    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.build_programs()
        layers = experiment.structure_configs[0]["layer_files"]
    layer_ids = sorted(int(str(f).split(".")[-2]) for f in layers)
    # Simulate a print aborted after the second layer (drop direction up: ascending order)
    (path / "print_progress.json").write_text(json.dumps({
        "current_structure": {"name": "rect", "finished layer": layer_ids[1], "order": 1},
        "finished_structures": [], "error log": []}))

    params = Experiment.parameters_from_dictionary(path)
    assert params["objective"] == "Zeiss 20x" and params["grid"] == (1, 1)
    assert params["drop_direction"] == DropDirection.UP
    assert params["resin_corner_tr"].as_tuple() == (5720.0, 27190.0)
    assert params["sys_args"]["controller"]["zMax"] == 24550.0

    script = Path(__file__).parents[1] / "mains" / "restart_experiment.py"
    spec = importlib.util.spec_from_file_location("restart_experiment", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # does not start a restart on import
    dummy_backend.calllog.clear()

    module.restart(path, backend=dummy_backend)

    assert len(dummy_backend.calllog.filter(device="program")) == len(layers) - 2
    assert [s["name"] for s in progress(experiment)["finished_structures"]] == ["rect"]
