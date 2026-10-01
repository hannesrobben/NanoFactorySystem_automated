"""Tests for Experiment (experiment.py) on the dummy backend."""
import json
import re
from pathlib import Path

import matplotlib
import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings import Rectangle3D
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import Experiment, StructureType
from nanofactorysystem.runtime import getLogger
from nanofactorysystem.storage import ExperimentStore


def make_experiment(path, backend, *, dhm_usage=False, skip_corner=True, substrate=None, setup="IFOV_off",
                    grid=(1, 1), drop_direction=DropDirection.UP, center=Point2D(1310, 19500), camera_capture=True,
                    **kwargs):
    """ Small 20x experiment with one grid cell, as in the experiment template.

    path=None uses the default location of a substrate (pass substrate_label and data_root). Camera
    images are on by default here, as in the tests written before T45; Experiment's default is off.
    """

    matplotlib.use("Agg")
    sys_args = {
        "attenuator": {"fitKind": "quadratic"},
        "controller": {"zMax": 24550.0},
        "dhm": {"usage": dhm_usage, "oplStep": 100.0},
    }
    return Experiment(
        path=path, user="Test", objective="Zeiss 20x",
        logger=getLogger(logfile=path / "console.log") if path is not None else getLogger(),
        sys_args=sys_args,
        default_power=0.7, low_speed_um=1000, high_speed_um=5000,
        resin_corner_tr=Point2D(5720, 27190), resin_corner_bl=Point2D(-3333, 17212),
        structure_size=500, margin=200, padding=100, absolute_grid_center=center,
        grid=grid, n_mid_points=0, drop_direction=drop_direction,
        corner_z=-2, corner_width=50, corner_length=300, corner_height=7, corner_hatch=0.5, corner_slice=0.75,
        fov_dim=(500, 500), skip_corner=skip_corner, setup=setup, backend=backend, camera_capture=camera_capture,
        substrate_information=substrate, substrate=kwargs.pop("substrate_label", None), **kwargs)


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


def abort_after(experiment, n_layers):
    """ Let the controller fail with RuntimeError("abort") when the layer after ``n_layers`` layers is loaded. """

    run = experiment.a3200.run_program_as_task
    calls = []

    def run_or_abort(*args, **kwargs):
        calls.append(args)
        if len(calls) > n_layers:
            raise RuntimeError("abort")
        return run(*args, **kwargs)

    experiment.a3200.run_program_as_task = run_or_abort


def printed_layers(path, name="rect"):
    """ Layer ids printed successfully according to the experiment file, in order. """

    return [e["layer_id"] for e in ExperimentStore.open(path).read().progress[name] if e["status"] == "ok"]


def progress(experiment, name=None):
    """ print_progress.json of the experiment, or the entry of one structure. """

    data = json.loads((experiment.path / "print_progress.json").read_text())
    if name is None:
        return data
    return next(s for s in data["structures"] if s["name"] == name)


def test_print_experiment_runs_all_layers(experiment, dummy_backend):
    add_rectangle(experiment)
    experiment.build_programs()

    experiment.print_experiment()

    runs = dummy_backend.calllog.filter(device="program")
    layers = experiment.structure_configs[0]["layer_files"]
    assert len(runs) == len(layers) > 1
    rect = progress(experiment, "rect")
    assert (rect["status"], rect["printed_layers"], rect["failed_layers"]) == ("printed", len(layers), 0)


def test_failed_layer_is_logged_and_printing_continues(experiment, dummy_backend):
    add_rectangle(experiment)
    experiment.build_programs()
    dummy_backend.transport.program_error_next(error_code=42, running_polls=1)

    experiment.print_experiment()

    rect = progress(experiment, "rect")
    failed = [layer for layer in rect["layers"] if layer["status"] == "failed"]
    assert len(failed) == 1 and "42" in failed[0]["error"]
    # The failed task was stopped and all layers were attempted
    assert "PROGRAM 1 STOP" in dummy_backend.calllog.commands()
    layers = experiment.structure_configs[0]["layer_files"]
    assert len(dummy_backend.calllog.filter(device="program")) == len(layers)
    assert (rect["status"], rect["printed_layers"], rect["failed_layers"]) == ("failed", len(layers) - 1, 1)


def test_experiment_dictionary(experiment):
    data = json.loads((experiment.path / "experiment_dictionary.json").read_text())

    assert data["objective"] == "Zeiss 20x"
    # Paths are relative to the experiment folder (T57)
    assert data["logger"] == "console.log" and data["path"] == "."


def test_structure_without_layers(experiment):
    experiment.print_structure([], x=1310.0, y=19500.0, name="empty", power=0.7)

    empty = progress(experiment, "empty")
    assert (empty["status"], empty["printed_layers"], empty["layers"]) == ("printed", 0, [])


@pytest.mark.parametrize("drop_direction", [DropDirection.UP, DropDirection.DOWN])
def test_print_progress_counts_layers(drop_direction, test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with pytest.raises(RuntimeError, match="abort"):
        with make_experiment(path, dummy_backend, grid=(1, 2), drop_direction=drop_direction) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment, "done")
            add_rectangle(experiment, "aborted")
            experiment.build_programs()
            n = len(experiment.structure_configs[0]["layer_files"])
            abort_after(experiment, n + 2)  # the first structure completely, two layers of the second
            experiment.print_experiment()

    data = json.loads((path / "print_progress.json").read_text())
    assert data["schema"] == "nanofactory.print_progress/2" and data["current_structure"] == "aborted"
    done, aborted = data["structures"]
    assert (done["status"], done["printed_layers"], done["n_layers"]) == ("printed", n, n)
    assert (aborted["status"], aborted["printed_layers"]) == ("printing", 2)
    # Layers in print order: ascending for drop direction UP, descending for DOWN
    ids = [layer["layer_id"] for layer in done["layers"]]
    assert ids == sorted(ids, reverse=drop_direction == DropDirection.DOWN)
    assert [layer["layer_id"] for layer in aborted["layers"]] == ids[:2]
    assert done["started"] and done["ended"] and aborted["started"] and not aborted["ended"]
    assert all(layer["started"] and layer["ended"] for layer in done["layers"])


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


def test_substrate_information_is_stored_in_the_experiment(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, substrate={"name": "S1", "drops": 2}):
        pass

    assert ExperimentStore.open(path).read().substrate == {"information": {"name": "S1", "drops": 2}}
    assert json.loads((path / "experiment_dictionary.json").read_text())["substrate"]["information"]["drops"] == 2
    assert not (tmp_path / "substrate_information.json").exists()


def test_measure_stores_position_of_every_capture(test_config, dummy_backend, no_sleep, tmp_path):
    from scidatacontainer import Container

    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, dhm_usage=True) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())

        results = experiment.measure({"X": 1.31, "Y": 19.5}, structure="rect", layer_id=2, dhm_image_count=2,
                                     offsets_um=[(0.0, 0.0), (20.0, -10.0)])

    assert len(results) == 2
    store = ExperimentStore.open(path)
    captures = store.read().captures
    assert [(c.kind, c.image_index) for c in captures] == [("dhm", 0), ("camera", 0), ("dhm", 1), ("camera", 1)]
    for capture in captures:
        dx, dy = capture.offset_um
        assert capture.commanded_um[:2] == pytest.approx((1310.0 + dx, 19500.0 + dy))
        assert capture.commanded_um[2] is None  # measure() does not move Z (T58)
        # The dummy stage reaches the target, so the actual position equals the commanded one
        assert capture.actual_um["X"] == pytest.approx(1310.0 + dx)
        assert capture.actual_um["Y"] == pytest.approx(19500.0 + dy)
        assert set(capture.actual_um) == set("XYZAB")
        assert capture.structure == "rect" and capture.layer_id == 2 and capture.phase == "layer"
        assert capture.image_count == (2 if capture.kind == "dhm" else 1)
        assert capture.time.endswith("Z")
    # Image data: two holograms per DHM capture, one camera image
    _, holograms, _ = store.read_capture(captures[2].capture_id)
    _, image, camera = store.read_capture(captures[3].capture_id)
    assert holograms.ndim == 3 and holograms.shape[0] == 2 and image.ndim == 2
    assert "ExposureTime" in camera
    # The returned containers carry the same record, the DHM container also its location
    dhm_container, camera_container = results[1]
    assert dhm_container["data/capture.json"] == captures[2].to_dict()
    assert dhm_container["data/location.json"]["X"] == pytest.approx(1330.0)
    assert camera_container["data/capture.json"] == captures[3].to_dict()
    # A capture can still be exported as .zdc file
    exported = store.export_capture(captures[2].capture_id, tmp_path / "dhm.zdc")
    assert Container(file=str(exported))["data/capture.json"]["capture_id"] == captures[2].capture_id
    assert not list(path.rglob("*.zdc"))


def test_print_structure_records_captures(experiment):
    add_rectangle(experiment)
    experiment.build_programs()

    experiment.print_experiment()

    record = ExperimentStore.open(experiment.path).read()
    captures = record.captures
    n_layers = len(experiment.structure_configs[0]["layer_files"])
    assert [c.phase for c in captures] == ["before"] + ["layer"] * n_layers + ["after"]
    assert [c.layer_id for c in captures if c.phase == "layer"] == list(range(n_layers))
    assert {c.structure for c in captures} == {"rect"}
    assert [e["status"] for e in record.progress["rect"]] == ["ok"] * n_layers
    assert record.structure("rect").status == "printed" and record.status == "finished"


def test_exception_while_printing_leaves_readable_file(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with pytest.raises(RuntimeError, match="cable unplugged"):
        with make_experiment(path, dummy_backend) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            run = experiment.a3200.run_program_as_task
            calls = []

            def failing_run(*args, **kwargs):
                calls.append(args)
                if len(calls) == 2:
                    raise RuntimeError("cable unplugged")
                return run(*args, **kwargs)

            experiment.a3200.run_program_as_task = failing_run
            experiment.print_experiment()

    record = ExperimentStore.open(path).read()
    assert record.status == "failed"
    assert record.sessions[-1]["end_reason"] == "exception"
    assert [e["layer_id"] for e in record.progress["rect"]] == [0]
    assert record.structure("rect").status == "printing"
    assert not (path / "experiment.lock").exists()
    assert json.loads((path / "experiment_dictionary.json").read_text())["status"] == "failed"


def test_command_log_belongs_to_the_experiment(test_config, dummy_backend, no_sleep, tmp_path):
    paths = [tmp_path / "first", tmp_path / "second"]
    for i, path in enumerate(paths):
        path.mkdir()
        with make_experiment(path, dummy_backend) as experiment:
            experiment.system.moveabs(x=100.0 * (i + 1))

    for i, path in enumerate(paths):
        logs = ExperimentStore.open(path).read_logs("a3200")
        assert list(logs) == ["000"]
        assert f"X{0.1 * (i + 1):.10f}"[:5] in logs["000"]  # the move of this experiment
        # Same commands as A3200.log in the folder (the stored copy also has the close time)
        assert (path / "A3200.log").read_text().split("Commands:")[1] == logs["000"].split("Commands:")[1]
        console = ExperimentStore.open(path).read_logs("console")["000"]
        assert "Initializing system." in console and "System closed." in console
    # Each experiment has its own log; the second does not repeat the first one's session
    assert ExperimentStore.open(paths[1]).read_logs("console")["000"].count("Initializing system.") == 1
    assert not (tmp_path / "A3200.log").exists() and not (tmp_path / "dummy" / "A3200.log").exists()


def test_aborted_experiment_keeps_its_command_log(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with pytest.raises(KeyboardInterrupt):
        with make_experiment(path, dummy_backend):
            raise KeyboardInterrupt

    store = ExperimentStore.open(path)
    assert "Commands:" in store.read_logs("a3200")["000"]
    assert store.read().status == "aborted" and store.read().sessions[0]["end_reason"] == "aborted"


def test_moved_experiment_can_be_restarted(test_config, dummy_backend, no_sleep, tmp_path):
    import shutil

    old = tmp_path / "old" / "experiment"
    old.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="abort"):
        with make_experiment(old, dummy_backend) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            layers = experiment.structure_configs[0]["layer_files"]
            abort_after(experiment, 1)
            experiment.print_experiment()
    new = tmp_path / "new" / "experiment"
    getLogger(logfile=tmp_path / "other.log")  # release old/console.log, so that the folder can be moved
    shutil.move(old.parent, new.parent)
    dummy_backend.calllog.clear()

    with Experiment(**Experiment.parameters_from_dictionary(new), backend=dummy_backend) as restarted:
        assert restarted.path == new
        restarted.restart_experiment()

    # All remaining layers ran; they can only have been read from the new folder, the old one is gone
    assert len(dummy_backend.calllog.filter(device="program")) == len(layers) - 1
    assert not (tmp_path / "old").exists()
    assert ExperimentStore.open(new).read().status == "finished"


def test_two_experiments_on_one_substrate(test_config, dummy_backend, no_sleep, tmp_path):
    from nanofactorysystem.storage.substrate_store import SubstrateStore, find_experiments

    root = tmp_path / "Femtika_Experiment" / "Test"
    label = SubstrateStore(root).create("Test", "TU", material={"substrate": "glass"}).label
    folders = []
    for _ in range(2):  # the same experiment printed twice
        with make_experiment(None, dummy_backend, substrate_label=label, data_root=root,
                             skip_corner=False) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            folders.append(experiment.path)

    # Two folders next to each other; the repeated print did not overwrite the first one
    assert folders[0] != folders[1] and all(f.parent == root / label for f in folders)
    assert [f.name.rsplit("_", 1)[0] for f in folders] == [f"{label}-A", f"{label}-B"]
    records = [ExperimentStore.open(f).read() for f in folders]
    assert records[0].uuid != records[1].uuid
    assert all(r.substrate_label == label and r.substrate["material"] == {"substrate": "glass"} for r in records)
    assert [r.label for r in records] == [f"{label}-A", f"{label}-B"]
    assert (folders[0] / "console.log").is_file()

    index = find_experiments(root, substrate=label)
    assert [(e["label"], e["status"], e["objective"]) for e in index] == [
        (f"{label}-A", "built", "Zeiss 20x"), (f"{label}-B", "built", "Zeiss 20x")]
    assert [Path(e["folder"]) for e in index] == folders
    assert index[0]["uuid"] == records[0].uuid and index[0]["double_corner_um"] is not None
    assert index[0]["center_um"] == [1310.0, 19500.0]


def test_experiments_in_explicit_folders_are_labelled_on_their_substrate(test_config, dummy_backend, no_sleep,
                                                                         tmp_path):
    from nanofactorysystem.storage.substrate_store import SubstrateStore

    root = tmp_path / "root"
    substrates = SubstrateStore(root)
    label = substrates.create("Test", "TU").label
    for name in ("first", "second"):
        (tmp_path / name).mkdir()
        with make_experiment(tmp_path / name, dummy_backend, substrate_label=label, data_root=root):
            pass

    experiments = substrates.get(label).experiments
    assert [e["label"] for e in experiments] == [f"{label}-A", f"{label}-B"]
    assert [Path(e["path"]) for e in experiments] == [(tmp_path / n).resolve() for n in ("first", "second")]
    assert ExperimentStore.open(tmp_path / "second").read().label == f"{label}-B"


def test_restart_updates_the_substrate_index(test_config, dummy_backend, no_sleep, tmp_path):
    from nanofactorysystem.storage.substrate_store import SubstrateStore

    root = tmp_path / "root"
    substrates = SubstrateStore(root)
    label = substrates.create("Test", "TU").label
    with pytest.raises(RuntimeError):
        with make_experiment(None, dummy_backend, substrate_label=label, data_root=root) as experiment:
            path = experiment.path
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            raise RuntimeError("abort")
    assert substrates.get(label).experiments[0]["status"] == "failed"

    # Continue the stored experiment and print it: the index shows the new status
    with Experiment(**Experiment.parameters_from_dictionary(path), backend=dummy_backend) as restarted:
        restarted.plane_fit(plane=dummy_backend.world.sample.plane())
        restarted.retrieve_programs()
        restarted.print_experiment()

    experiments = substrates.get(label).experiments
    assert len(experiments) == 1 and experiments[0]["status"] == "finished"
    assert ExperimentStore.open(path).read().label == f"{label}-A"


def test_default_location_needs_a_substrate(test_config, dummy_backend, no_sleep):
    with pytest.raises(ValueError, match="substrate"):
        make_experiment(None, dummy_backend)


def test_summary_after_build_and_print(test_config, dummy_backend, no_sleep, tmp_path, caplog):
    from nanofactorysystem.aerobasic.programs.drawings.lines import Stair

    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, grid=(1, 2)) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.add_structure(StructureType.NORMAL, "stair", axes="ABZ", power=0.5,
                                 structure=Stair(Point3D(0, 0, -2), n_steps=2, step_height=0.6, step_length=20,
                                                 step_width=50, hatch_size=0.5, slice_size=0.6, socket_height=1,
                                                 velocity=10_000, acceleration=500_000))
        experiment.build_programs()

        built = json.loads((path / "experiment_summary.json").read_text())
        assert [(r["name"], r["status"]) for r in built["structures"]] == [("rect", "pending"), ("stair", "pending")]
        assert "Experiment summary" in caplog.text

        experiment.print_experiment()

    data = json.loads((path / "experiment_summary.json").read_text())
    assert data == ExperimentStore.open(path).read_summary()
    assert data["experiment_uuid"] == experiment.qr_text and data["status"] == "finished"
    rect, stair = data["structures"]
    assert (rect["name"], rect["slice_um"], rect["hatch_um"], rect["velocity"], rect["power_mw"]) == (
        "rect", 1.0, 1.0, 1000.0, 0.7)
    assert (stair["slice_um"], stair["hatch_um"], stair["power_mw"], stair["status"]) == (0.6, 0.5, 0.5, "printed")
    assert rect["printed_layers"] == rect["n_layers"] > 0 and not rect["ifov"] and not rect["dhm"]
    assert rect["x_um"] != stair["x_um"]


def test_experiment_plot_shows_corners_and_qr_code(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, skip_corner=False) as experiment:
        fig = experiment.plot_experiment(show=False)

        ax = fig.axes[0]
        labels = ax.get_legend_handles_labels()[1]
        assert {"Corners", "Double corner (orientation)", "QR code", "Resin Drop"} <= set(labels)
        assert experiment.qr_text in ax.get_title()
        assert sorted(t.get_text() for t in ax.texts if t.get_text() in ("TL", "TR", "BL", "BR")) == [
            "BL", "BR", "TL", "TR"]
    assert (path / "experiment.png").is_file()


def test_structure_plots_on_request(experiment):
    add_rectangle(experiment)
    experiment.build_programs()
    assert not (experiment.path / "structures" / "rect" / "plot_rect.png").exists()

    experiment.build_programs(plot_structures=True)

    assert (experiment.path / "structures" / "rect" / "plot_rect.png").is_file()


@pytest.mark.parametrize("camera_capture", [False, True])
def test_camera_images_only_on_request(camera_capture, test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, camera_capture=camera_capture) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.build_programs()
        dummy_backend.calllog.clear()
        results = experiment.measure({"X": 1.31, "Y": 19.5}, structure="rect")
        experiment.print_experiment()

    assert (results[0][1] is not None) == camera_capture
    record = ExperimentStore.open(path).read()
    cameras = [c for c in record.captures if c.kind == "camera"]
    assert bool(cameras) == camera_capture
    assert bool(dummy_backend.calllog.filter(device="camera", call="getimage")) == camera_capture
    assert record.parameters["camera_capture"] is camera_capture
    assert json.loads((path / "experiment_summary.json").read_text())["camera_capture"] is camera_capture
    # A restart uses the stored value
    assert Experiment.parameters_from_dictionary(path)["camera_capture"] is camera_capture


def test_captures_are_taken_with_the_galvo_at_zero(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        experiment.add_structure(  # written with the galvo (ABZ): the layers leave A and B displaced
            StructureType.NORMAL, "rect", axes="ABZ", power=0.7,
            structure=Rectangle3D(Point3D(0, 0, -1), 60, 60, 3, hatch_size=5.0, slice_size=1.0,
                                  velocity=1000, acceleration=500))
        experiment.build_programs()
        experiment.print_experiment()

    layer_programs = "\n".join(open(f).read() for f in experiment.structure_configs[0]["layer_files"])
    assert re.search(r"LINEAR[^\n]*A-?0\.0[1-9]", layer_programs)  # the layers move the galvo
    captures = ExperimentStore.open(path).read().captures
    assert captures and all(c.actual_um["A"] == 0.0 and c.actual_um["B"] == 0.0 for c in captures)
    assert all(c.commanded_um[2:] == (None, 0.0, 0.0) for c in captures)  # Z is not moved (T58)
    layer_captures = [c for c in captures if c.phase == "layer"]
    assert len({round(c.actual_um["Z"], 3) for c in layer_captures}) > 1  # Z stays where each layer ended


def test_experiment_default_takes_no_camera_images(test_config, dummy_backend, no_sleep, tmp_path):
    import inspect
    assert inspect.signature(Experiment).parameters["camera_capture"].default is False


def test_existing_experiment_is_not_overwritten(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend):
        pass

    with pytest.raises(FileExistsError):
        make_experiment(path, dummy_backend)


def test_restart_from_stored_dictionary(test_config, dummy_backend, no_sleep, tmp_path):
    import importlib.util
    from pathlib import Path

    path = tmp_path / "experiment"
    path.mkdir()
    # A print aborted after the second layer
    with pytest.raises(RuntimeError, match="abort"):
        with make_experiment(path, dummy_backend) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            layers = experiment.structure_configs[0]["layer_files"]
            abort_after(experiment, 2)
            experiment.print_experiment()

    params = Experiment.parameters_from_dictionary(path)  # read from experiment.h5
    assert params["resume"] and params["path"] == path
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
    assert progress(experiment, "rect")["status"] == "printed"
    stored = json.loads((path / "structures.json").read_text())
    assert not any(Path(f).is_absolute() for s in stored for f in s["layer_files"] + [s["program_file"]])
    # The restart continued the same experiment file and kept its UUID
    record = ExperimentStore.open(path).read()
    assert record.uuid == experiment.qr_text
    assert [s["kind"] for s in record.sessions] == ["new", "restart"]
    assert record.status == "finished"
    assert printed_layers(path) == sorted(int(str(f).split(".")[-2]) for f in layers)


def test_restart_after_two_aborts(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with pytest.raises(RuntimeError, match="abort"):
        with make_experiment(path, dummy_backend) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            experiment.add_structure(
                StructureType.NORMAL, "rect", axes="XYZ", power=0.7,
                structure=Rectangle3D(Point3D(0, 0, -1), 10, 10, 6, hatch_size=1.0, slice_size=1.0,
                                      velocity=1000, acceleration=500))
            experiment.build_programs()
            ids = sorted(int(str(f).split(".")[-2]) for f in experiment.structure_configs[0]["layer_files"])
            abort_after(experiment, 2)
            experiment.print_experiment()
    assert len(ids) >= 5 and printed_layers(path) == ids[:2]

    # Second run: aborted again after one more layer
    with pytest.raises(RuntimeError, match="abort"):
        with Experiment(**Experiment.parameters_from_dictionary(path), backend=dummy_backend) as experiment:
            abort_after(experiment, 1)
            experiment.restart_experiment()
    assert printed_layers(path) == ids[:3]

    # Third run: resumes at the fourth layer and finishes; every layer was printed exactly once
    dummy_backend.calllog.clear()
    with Experiment(**Experiment.parameters_from_dictionary(path), backend=dummy_backend) as experiment:
        experiment.restart_experiment()
    assert len(dummy_backend.calllog.filter(device="program")) == len(ids) - 3
    assert printed_layers(path) == ids
    record = ExperimentStore.open(path).read()
    assert [s["kind"] for s in record.sessions] == ["new", "restart", "restart"]
    assert [s["end_reason"] for s in record.sessions] == ["exception", "exception", "finished"]
    assert record.structure("rect").status == "printed" and record.status == "finished"


def test_old_json_folder_is_imported_on_restart(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with pytest.raises(RuntimeError, match="abort"):
        with make_experiment(path, dummy_backend) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            layers = experiment.structure_configs[0]["layer_files"]
            abort_after(experiment, 2)
            experiment.print_experiment()
    uuid = experiment.qr_text
    # Make it look like a folder written before the experiment file: no experiment.h5, absolute paths of the
    # lab PC in structures.json, and print_progress.json as the only progress record
    (path / "experiment.h5").unlink()
    ids = sorted(int(str(f).split(".")[-2]) for f in layers)
    (path / "print_progress.json").write_text(json.dumps({
        "current_structure": {"name": "rect", "finished layer": ids[1], "order": 1},
        "finished_structures": [], "error log": []}))
    structures = json.loads((path / "structures.json").read_text())
    for s in structures:
        s["layer_files"] = [f"C:/Users/Nanofactory/old/experiment/{f}" for f in s["layer_files"]]
    (path / "structures.json").write_text(json.dumps(structures))
    dummy_backend.calllog.clear()

    with Experiment(**Experiment.parameters_from_dictionary(path), backend=dummy_backend) as experiment:
        experiment.restart_experiment()

    assert len(dummy_backend.calllog.filter(device="program")) == len(layers) - 2
    record = ExperimentStore.open(path).read()
    assert record.uuid == uuid  # recovered from the log file
    assert [s["kind"] for s in record.sessions] == ["imported"]
    assert record.structure("rect").status == "printed" and record.status == "finished"
    assert len(printed_layers(path)) == len(layers)
    assert all(not Path(f).is_absolute() for f in record.structure("rect").layer_files)


def test_repeated_structure_is_printed_at_its_own_place(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, grid=(1, 3)) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        add_rectangle(experiment)  # same name: a second, different structure
        # REPEAT repeats the most recent structure; "_(1)" marks a duplicate name, "_rep1" a repetition
        assert experiment.add_structure(StructureType.REPEAT, "ignored") == "rect_(1)_rep1"
        with pytest.raises(ValueError, match="Too many"):
            experiment.add_structure(StructureType.REPEAT, "ignored")
        experiment.build_programs()
        experiment.print_experiment()

    record = ExperimentStore.open(path).read()
    assert [(s.name, s.repeat_of) for s in record.structures] == [("rect", ""), ("rect_(1)", ""),
                                                                  ("rect_(1)_rep1", "rect_(1)")]
    centers = [s.center_um[:2] for s in record.structures]
    assert len(set(centers)) == 3
    # The repeat was written at its own grid cell, not on top of the original
    repeat_x = record.structure("rect_(1)_rep1").center_um[0]
    assert any(abs(1000 * e.end[0] - repeat_x) < 10 for e in dummy_backend.world.exposures)
    assert record.structure("rect_(1)_rep1").status == "printed"


def exposure_powers(world, since=0):
    """ Laser powers (mW, rounded) of the exposures after index ``since``, grouped by z in um. """

    powers = {}
    for exposure in world.exposures[since:]:
        powers.setdefault(round(exposure.end[2] * 1000, 3), set()).add(round(exposure.power, 1))
    return powers


def test_power_per_structure(test_config, dummy_backend, no_sleep, tmp_path):
    # Parameter test prints: every structure prints with its own power (N012)
    world = dummy_backend.world
    with make_experiment(tmp_path, dummy_backend, grid=(1, 2)) as experiment:
        experiment.plane_fit(plane=world.sample.plane())
        for name, power in (("low", 1.0), ("high", 3.0)):
            experiment.add_structure(StructureType.NORMAL, name, axes="XYZ", power=power,
                                     structure=Rectangle3D(Point3D(0, 0, -1), 10, 10, 1, hatch_size=2.0,
                                                           slice_size=1.0, velocity=1000, acceleration=500))
        experiment.build_programs()
        experiment.print_experiment()

    powers = {p for ps in exposure_powers(world).values() for p in ps}
    assert powers == {1.0, 3.0}


def test_power_per_layer(test_config, dummy_backend, no_sleep, tmp_path):
    world = dummy_backend.world
    with make_experiment(tmp_path, dummy_backend, grid=(1, 2)) as experiment:
        experiment.plane_fit(plane=world.sample.plane())
        experiment.add_structure(StructureType.NORMAL, "rect", axes="XYZ", power=0.7, layer_power=[1.0, 2.0, 3.0, 4.0],
                                 structure=Rectangle3D(Point3D(0, 0, -1), 10, 10, 3, hatch_size=2.0, slice_size=1.0,
                                                       velocity=1000, acceleration=500))
        experiment.add_structure(StructureType.REPEAT, "rect")
        experiment.build_programs()
        experiment.print_experiment()

    # Each of the 4 layers of the structure and its repetition prints with its own power
    by_z = exposure_powers(world)
    assert sorted(p for ps in by_z.values() for p in ps) == [1.0, 2.0, 3.0, 4.0]
    assert all(len(ps) == 1 for ps in by_z.values())
    for power in (1.0, 2.0, 3.0, 4.0):  # in both grid cells (600 um apart)
        x_um = [e.end[0] * 1000 for e in world.exposures if round(e.power, 1) == power]
        assert max(x_um) - min(x_um) > 500
    record = ExperimentStore.open(tmp_path).read()
    assert record.structure("rect").layer_powers_mw == [1.0, 2.0, 3.0, 4.0]
    assert record.structure("rect_rep1").layer_powers_mw == [1.0, 2.0, 3.0, 4.0]
    program = ExperimentStore.open(tmp_path).read_program("rect", 1)
    assert "Layer power 2 mW" in program and "$AO[0].A=" in program
    from nanofactorysystem.storage.summary import summary
    assert summary(record)["structures"][0]["layer_power_mw"] == "1-4"
    assert json.loads((tmp_path / "structures.json").read_text())[0]["layer_powers"] == [1.0, 2.0, 3.0, 4.0]


def test_power_per_layer_as_function_and_wrong_length(test_config, dummy_backend, no_sleep, tmp_path):
    with make_experiment(tmp_path, dummy_backend, grid=(1, 2)) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        rectangle = Rectangle3D(Point3D(0, 0, -1), 10, 10, 3, hatch_size=2.0, slice_size=1.0, velocity=1000,
                                acceleration=500)
        experiment.add_structure(StructureType.NORMAL, "ramp", axes="XYZ", structure=rectangle,
                                 layer_power=lambda layer_id: 0.5 * (layer_id + 1))
        experiment.add_structure(StructureType.NORMAL, "short", axes="XYZ", structure=rectangle,
                                 layer_power=[1.0, 2.0])
        with pytest.raises(ValueError, match="layer"):
            experiment.build_programs()
    assert ExperimentStore.open(tmp_path).read().structure("ramp").layer_powers_mw == [0.5, 1.0, 1.5, 2.0]


RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]  # right, left, near, far


def test_experiment_center_is_checked_against_the_ellipse(test_config, dummy_backend, no_sleep, tmp_path):
    (tmp_path / "a").mkdir()
    with pytest.raises(ValueError, match="ellipse"):
        make_experiment(tmp_path / "a", dummy_backend, center=Point2D(5000, 18000), resin_edges=RESIN_EDGES)
    # Without the edge points only the bounding box is checked, as before
    (tmp_path / "b").mkdir()
    with make_experiment(tmp_path / "b", dummy_backend, center=Point2D(5000, 18000)):
        pass

    (tmp_path / "c").mkdir()
    with make_experiment(tmp_path / "c", dummy_backend, resin_edges=RESIN_EDGES) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
    # The edges are stored and come back on a restart
    parameters = Experiment.parameters_from_dictionary(tmp_path / "c")
    assert parameters["resin_edges"] == [tuple(map(float, e)) for e in RESIN_EDGES]


def test_expected_and_actual_printing_time(test_config, dummy_backend, no_sleep, tmp_path, caplog):
    import logging
    from nanofactorysystem.storage.summary import summary
    with caplog.at_level(logging.INFO):
        with make_experiment(tmp_path, dummy_backend, layer_overhead_s=2.0) as experiment:
            experiment.plane_fit(plane=dummy_backend.world.sample.plane())
            add_rectangle(experiment)
            experiment.build_programs()
            estimate = ExperimentStore.open(tmp_path).read().time_estimate
            experiment.print_experiment()

    # One value per layer: program time plus the overhead
    layers = estimate["structures"]["rect"]
    assert len(layers) == 4 and all(t > 2.0 for t in layers) and estimate["layer_overhead_s"] == 2.0
    assert estimate["total_s"] == pytest.approx(sum(layers))
    assert "Expected printing time" in caplog.text and "Printing took" in caplog.text
    record = ExperimentStore.open(tmp_path).read()
    data = summary(record)
    assert data["estimated_s"] == pytest.approx(sum(layers)) and data["duration_s"] is not None
    assert data["structures"][0]["estimated_s"] == pytest.approx(sum(layers))
    assert data["structures"][0]["duration_s"] is not None
    assert Experiment.parameters_from_dictionary(tmp_path)["layer_overhead_s"] == 2.0


def test_overview_before_and_after_printing(test_config, dummy_backend, no_sleep, tmp_path):
    with make_experiment(tmp_path, dummy_backend, overview_capture=True, overview_single_images=True) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.build_programs()
        experiment.print_experiment()
        lower, upper = experiment.overview_area()

    store = ExperimentStore.open(tmp_path)
    for phase in ("before", "after"):
        image, metadata = store.read_overview(phase)
        assert image.dtype == np.uint8 and image.ndim == 2 and (tmp_path / f"overview_{phase}.png").is_file()
        assert metadata["corners_included"] is False  # skip_corner: only the structure grid
        assert len(metadata["single_images"]) == len(metadata["positions_um"]) > 1
    # skip_corner: the area is the structure grid (one 500 um cell around the center)
    assert np.allclose(lower, [1310 - 250, 19500 - 250]) and np.allclose(upper, [1310 + 250, 19500 + 250])
    assert Experiment.parameters_from_dictionary(tmp_path)["overview_capture"] is True


def test_overview_area_includes_the_corner_markers(test_config, dummy_backend, no_sleep, tmp_path):
    from nanofactorysystem.experiment import OVERVIEW_BORDER_UM, QR_CODE_WIDTH_UM
    with make_experiment(tmp_path, dummy_backend, skip_corner=False) as experiment:
        lower, upper = experiment.overview_area()
        rectangle_low = np.minimum(experiment.rectangle_tl, experiment.rectangle_br)
    clearance = max(50, QR_CODE_WIDTH_UM) / 2 + OVERVIEW_BORDER_UM  # corner width 50 um in make_experiment
    assert np.allclose(lower, rectangle_low - clearance)
    assert not ExperimentStore.open(tmp_path).read_overview("before")  # overview_capture is off by default
