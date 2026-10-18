"""Tests for the analysis tools in analysis/experiment_analysis (unpacking and live access)."""
import json
import os
import socket
import zipfile

import numpy as np
import pytest
from PIL import Image

from experiment_analysis import ExperimentBusyError, ExperimentFile, lock_holder, unpack_experiment
from experiment_analysis.__main__ import main as cli
from experiment_analysis.convert import ConvertOptions, safe_name, write_csv
from nanofactorysystem.storage import ExperimentStore
from test_experiment import add_rectangle, make_experiment


@pytest.fixture
def printed(test_config, dummy_backend, no_sleep, tmp_path):
    """ Folder of a printed dummy experiment with camera and DHM captures, overview images and a DHM product. """

    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, dhm_usage=True, overview_capture=True,
                         overview_single_images=True) as experiment:
        experiment.plot_experiment()
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.build_programs()
        experiment.print_experiment()
    store = ExperimentStore.open(path)
    dhm = next(c for c in store.read().captures if c.kind == "dhm")
    store.add_dhm_product(dhm.capture_id, "phase", np.linspace(0, 1, 64 * 64).reshape(64, 64),
                          {"source": "offline", "unit": "rad"})
    return path


def foreign_lock(folder):
    """ Lock file of another running process on this computer (the parent process). """

    (folder / "experiment.lock").write_text(json.dumps({"host": socket.gethostname(), "pid": os.getppid(),
                                                        "started": "2026-10-18T10:00:00.000Z"}))


# --------------------------------------------------------------------------- unpacking

@pytest.mark.slow
def test_unpack_writes_common_formats(printed, tmp_path):
    out = unpack_experiment(printed / "experiment.h5", tmp_path / "out")
    store = ExperimentStore.open(printed)
    record = store.read()

    assert out == tmp_path / "out"
    for name in ("README.txt", "summary.txt", "experiment_info.json", "experiment_dictionary.json",
                 "structures.json", "print_progress.json", "experiment_summary.json", "tables/summary.csv",
                 "tables/structures.csv", "tables/captures.csv", "tables/progress.csv", "tables/sessions.csv",
                 "attributes.json", "layout/plot.png", "metadata/experiment/attributes.json",
                 "calibration/attenuator.csv", "overview/before/image.png", "overview/after/image.png"):
        assert (out / name).is_file(), name
    info = json.loads((out / "experiment_info.json").read_text(encoding="utf-8"))
    assert info["experiment_uuid"] == record.uuid and info["snapshot"] is False
    assert info["counts"]["captures"] == len(record.captures) > 0
    assert not list(out.rglob("*.npy"))  # every dataset has a common format

    # Layer programs as text, identical to the stored ones
    rect = out / "structures" / "rect"
    assert (rect / "programs" / "layer_000.txt").read_text(encoding="utf-8") == store.read_program("rect", 0)
    assert json.loads((rect / "attributes.json").read_text(encoding="utf-8"))["config"]["__class__"]
    # Camera images and holograms are lossless PNGs
    camera = next(c for c in record.captures if c.kind == "camera")
    _, image, _ = store.read_capture(camera.capture_id)
    assert np.array_equal(np.asarray(Image.open(rect / "captures" / camera.capture_id / "image.png")), image)
    dhm = next(c for c in record.captures if c.kind == "dhm")
    _, holograms, _ = store.read_capture(dhm.capture_id)
    stack = sorted((rect / "captures" / dhm.capture_id / "holograms").glob("*.png"))
    assert len(stack) == len(holograms)
    assert np.array_equal(np.asarray(Image.open(stack[-1])), holograms[-1])
    # DHM product: full values as CSV, scaled preview as PNG
    products = rect / "captures" / dhm.capture_id / "products"
    assert (products / "phase_preview.png").is_file()
    assert json.loads((products / "phase.attributes.json").read_text(encoding="utf-8"))["metadata"]["unit"] == "rad"
    # Logs per session as text
    assert list((out / "logs" / "console").glob("*.txt")) and list((out / "logs" / "a3200").glob("*.txt"))
    # Capture table: one row per capture with its folder
    lines = (out / "tables" / "captures.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == len(record.captures) + 1 and lines[0].split(";")[0] == "capture_id"


@pytest.mark.slow
def test_unpack_refuses_existing_output_and_the_experiment_folder(printed, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "old.txt").write_text("x")
    with pytest.raises(FileExistsError):
        unpack_experiment(printed, out)
    unpack_experiment(printed, out, overwrite=True)
    assert not (out / "old.txt").exists() and (out / "summary.txt").is_file()

    with pytest.raises(ValueError, match="must not contain"):
        unpack_experiment(printed, printed, overwrite=True)
    with pytest.raises(ValueError, match="must not contain"):
        unpack_experiment(printed, printed.parent, overwrite=True)
    assert (printed / "experiment.h5").is_file()


@pytest.mark.slow
def test_unpack_archive_and_zdc(printed, tmp_path):
    result = unpack_experiment(printed, tmp_path / "out", archive=True, zdc=True, csv_style="en")

    assert result == tmp_path / "out.zip" and zipfile.is_zipfile(result)
    names = zipfile.ZipFile(result).namelist()
    assert "summary.txt" in names and any(n.endswith("capture.zdc") for n in names)
    assert any(n.endswith("plane.zdc") or n.startswith("plane_fit/") for n in names)
    header = (tmp_path / "out" / "tables" / "captures.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert header.startswith("capture_id,structure,")


@pytest.mark.slow
def test_unpack_while_printing_uses_a_snapshot(printed, tmp_path):
    foreign_lock(printed)

    unpack_experiment(printed, tmp_path / "out")

    info = json.loads((tmp_path / "out" / "experiment_info.json").read_text(encoding="utf-8"))
    assert info["busy"] is True and info["snapshot"] is True
    assert (tmp_path / "out" / "summary.txt").is_file()
    assert (printed / "experiment.lock").is_file()  # the lock of the other process stays


def test_csv_styles_and_file_names(tmp_path):
    write_csv(tmp_path / "de.csv", [[1.5, "a;b", np.nan]], ["x", "y", "z"], ConvertOptions("de"))
    write_csv(tmp_path / "en.csv", [[1.5, "a;b", np.nan]], ["x", "y", "z"], ConvertOptions("en"))

    assert (tmp_path / "de.csv").read_text(encoding="utf-8-sig") == 'x;y;z\n1,5;"a;b";\n'
    assert (tmp_path / "en.csv").read_text(encoding="utf-8-sig") == "x,y,z\n1.5,a;b,\n"
    assert safe_name('rect:1/"a"?') == "rect_1__a__"
    with pytest.raises(ValueError):
        ConvertOptions("fr")


# ------------------------------------------------------------------------- live access

@pytest.mark.slow
def test_experiment_file_reads_everything(printed):
    exp = ExperimentFile(printed / "experiment.h5")
    record = ExperimentStore.open(printed).read()

    assert exp.info()["experiment_uuid"] == record.uuid and exp.is_busy is False
    assert [s.name for s in exp.structures()] == [s.name for s in record.structures]
    cameras = exp.captures(structure="rect", kind="camera")
    assert cameras and all(c.kind == "camera" and c.structure == "rect" for c in cameras)
    assert exp.image(cameras[0].capture_id).ndim == 2
    assert exp.program("rect", 0) == ExperimentStore.open(printed).read_program("rect", 0)
    assert exp.plane() is not None and np.isfinite(exp.plane()(1310.0, 19500.0))
    assert exp.overview("after")[0].ndim == 2
    assert "rect" in exp.summary_table() and exp.summary()["structures"][0]["name"] == "rect"
    assert exp.logs("console") and exp.logs("a3200")
    assert exp.read("/structures/rect/programs/layer_000").startswith(exp.program("rect", 0)[:10])
    assert exp.read("/structures/rect")["name"] == "rect"
    assert "structures/" in exp.tree(max_depth=1) and "rect" in exp.keys("/structures")
    dhm = exp.captures(kind="dhm")[0]
    data, metadata = exp.product(dhm.capture_id, "phase")
    assert data.shape == (64, 64) and metadata["unit"] == "rad"


@pytest.mark.slow
def test_save_load_and_delete_results(printed, tmp_path):
    exp = ExperimentFile(printed)
    capture = exp.captures(kind="camera")[0].capture_id
    before = exp.updated

    path = exp.save_result("roughness", {"profile_nm": np.arange(100.0), "x_um": np.arange(100.0) * 0.1},
                           structure="rect", attrs={"rms_nm": 3.2, "method": "line fit", "window": {"a": 1}})
    exp.save_result("mean_grey", 12.5, capture=capture)
    exp.save_result("note", "looks fine")

    assert path == "/analysis/structures/rect/roughness"
    data, attrs = exp.load_result("roughness", structure="rect")
    assert np.array_equal(data["profile_nm"], np.arange(100.0)) and attrs["rms_nm"] == 3.2
    assert attrs["window"] == {"a": 1} and attrs["created"] and attrs["source"]
    assert exp.load_result("mean_grey", capture=capture)[0] == 12.5
    assert exp.load_result("note")[0] == "looks fine"
    assert exp.results() == ["/analysis/captures/" + capture + "/mean_grey", "/analysis/experiment/note",
                             "/analysis/structures/rect/roughness"]
    assert exp.updated >= before and exp.has_changed()
    assert not exp.has_changed()

    created = attrs["created"]
    exp.save_result("roughness", np.zeros(3), structure="rect")
    assert exp.load_result("roughness", structure="rect")[1]["created"] == created  # kept on replace
    with pytest.raises(FileExistsError):
        exp.save_result("roughness", 1.0, structure="rect", overwrite=False)
    with pytest.raises(KeyError):
        exp.save_result("x", 1.0, structure="missing")
    with pytest.raises(KeyError):
        exp.save_result("x", 1.0, capture="9999")
    with pytest.raises(ValueError):
        exp.save_result("a/b", 1.0)
    exp.delete_result("note")
    assert "/analysis/experiment/note" not in exp.results()
    assert not (printed / "experiment.lock").exists()

    # The printing side still reads the file, and the results are part of an unpacked folder
    assert ExperimentStore.open(printed).read().structure("rect").status == "printed"
    out = unpack_experiment(printed, tmp_path / "out")
    assert (out / "analysis" / "structures" / "rect" / "roughness" / "data.csv").is_file()


@pytest.mark.slow
def test_writes_are_refused_while_an_experiment_process_holds_the_file(printed):
    exp = ExperimentFile(printed)
    foreign_lock(printed)

    assert exp.is_busy and lock_holder(printed / "experiment.h5")["pid"] == os.getppid()
    assert exp.info()["busy"] is True and exp.structures()  # reading works
    with pytest.raises(ExperimentBusyError):
        exp.save_result("x", 1.0)
    with pytest.raises(ExperimentBusyError):
        exp.add_dhm_product(exp.captures(kind="dhm")[0].capture_id, "amplitude", np.ones((4, 4)), {}, wait_s=0.1)

    (printed / "experiment.lock").write_text(json.dumps({"host": socket.gethostname(), "pid": 2 ** 30}))
    assert not exp.is_busy  # stale lock of a finished process
    exp.add_dhm_product(exp.captures(kind="dhm")[0].capture_id, "amplitude", np.ones((4, 4)), {"unit": "a.u."})
    assert exp.product(exp.captures(kind="dhm")[0].capture_id, "amplitude")[1]["unit"] == "a.u."


@pytest.mark.slow
def test_reading_during_an_experiment_session(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.build_programs()
        exp = ExperimentFile(path)
        assert exp.info()["status"] == "built" and [s.name for s in exp.structures()] == ["rect"]
        exp.has_changed()
        experiment.print_experiment()  # the experiment writes while the reader exists
        assert exp.has_changed() and exp.structure("rect").status == "printed"
        with pytest.raises(ExperimentBusyError):
            exp.save_result("x", 1.0)
    exp.save_result("x", 1.0)


@pytest.mark.slow
def test_wait_for_change_times_out(printed):
    exp = ExperimentFile(printed)
    assert exp.wait_for_change(timeout_s=0.0, poll_s=0.0) is False


def test_rejects_other_files(tmp_path):
    import h5py
    with pytest.raises(FileNotFoundError):
        ExperimentFile(tmp_path)
    with h5py.File(tmp_path / "experiment.h5", "w") as f:
        f.attrs["file_type"] = "something else"
    with pytest.raises(ValueError, match="Not an experiment file"):
        ExperimentFile(tmp_path)


@pytest.mark.slow
def test_command_line(printed, tmp_path, capsys):
    assert cli(["unpack", str(printed), str(tmp_path / "out"), "--csv", "en"]) == 0
    assert (tmp_path / "out" / "summary.txt").is_file()
    assert cli(["info", str(printed / "experiment.h5")]) == 0
    assert "experiment_uuid" in capsys.readouterr().out
    assert cli(["tree", str(printed), "--depth", "1"]) == 0
    assert "structures/" in capsys.readouterr().out
