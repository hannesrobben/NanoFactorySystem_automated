"""Unit tests for the HDF5 experiment store (nanofactorysystem/storage)."""
import os

import h5py
import numpy as np
import pytest

from nanofactorysystem.storage import (CaptureRecord, CornerRecord, ExperimentLock, ExperimentRecord,
                                       ExperimentStore, LayoutRecord, LockError, PlaneFitRecord, StructureRecord,
                                       z_function_from_json, z_function_to_json)
from nanofactorysystem.storage import schema
from nanofactorysystem.storage.locking import pid_alive


def record(uuid="0f0e0d0c-0000-4000-8000-000000000001"):
    return ExperimentRecord(
        uuid=uuid,
        parameters={"center_um": np.array([1310.0, 19500.0]), "grid": np.array([2, 3]), "setup": "IFOV_off",
                    "drop_direction": "UP", "skip_corner": False, "default_power_mw": 0.7},
        user={"key": "Test", "name": "Test User"},
        objective={"key": "Zeiss 20x", "magnification": 20.0},
        system={"sys_args": {"controller": {"zMax": 25000.0}}, "backend": "dummy"},
        software={"package_version": "0.7.0", "git_commit": "abc"},
    )


def structure(name="rect", index=0):
    return StructureRecord(
        index=index, name=name, type="NORMAL", grid_index=0, corner_position="", axes="XYZ", setup="IFOV_off",
        center_um=(1310.0, 19500.0, 20000.0), reference_um=(1310.0, 19500.0), power_mw=0.7,
        structure_class="nanofactorysystem.aerobasic.programs.drawings.lines.Rectangle3D",
        config={"__class__": "Rectangle3D", "__init__": {"width": 10}}, layer_files=["a.000.txt", "a.001.txt"],
        program_file="a.txt", layer_order=1, dhm_image_count=10)


def capture(kind="camera", layer_id=0):
    return CaptureRecord(kind=kind, structure="rect", phase="layer", layer_id=layer_id, image_index=0,
                         image_count=1 if kind == "camera" else 3, offset_um=(0.0, 0.0),
                         commanded_um=(1310.0, 19500.0, None),
                         actual_um={"X": 1310.0, "Y": 19500.0, "Z": 20001.0, "A": 0.0, "B": 0.0})


@pytest.fixture
def store(tmp_path):
    return ExperimentStore.create(tmp_path / "exp", record())


def test_create_writes_schema_and_metadata(store):
    with h5py.File(store.path, "r") as f:
        assert f.attrs["file_type"] == schema.FILE_TYPE
        assert f.attrs["schema_version"] == schema.SCHEMA_VERSION
        assert f.attrs["status"] == schema.STATUS_CREATED

    data = ExperimentStore.open(store.folder).read()
    assert data.uuid == record().uuid
    assert list(data.parameters["center_um"]) == [1310.0, 19500.0]
    assert data.parameters["skip_corner"] is False and data.parameters["drop_direction"] == "UP"
    assert data.system["sys_args"] == {"controller": {"zMax": 25000.0}}
    assert data.user["name"] == "Test User"


def test_create_refuses_existing_file(store):
    with pytest.raises(FileExistsError):
        ExperimentStore.create(store.folder, record())


def test_open_rejects_other_files_and_versions(tmp_path, store):
    with h5py.File(store.path, "a") as f:
        f.attrs["schema_version"] = "2.0"
    with pytest.raises(ValueError, match="schema version"):
        ExperimentStore.open(store.folder)

    other = tmp_path / "other"
    other.mkdir()
    with h5py.File(other / schema.FILE_NAME, "w") as f:
        f.attrs["file_type"] = "something else"
    with pytest.raises(ValueError, match="Not an experiment file"):
        ExperimentStore.open(other)


def test_no_file_handle_stays_open(store):
    store.add_structure(structure())
    # Exclusive access works between writes, so the store has closed the file
    with h5py.File(store.path, "r+"):
        pass


def test_structures_programs_and_progress_round_trip(store):
    store.add_structure(structure())
    store.write_layer_program("rect", 0, "LINEAR X1\n", "a.000.txt")
    store.write_structure_program("rect", "LINEAR X1\nLINEAR X2\n")
    store.update_progress("rect", 0, "ok", started="2026-09-30T08:00:00.000Z")
    store.update_progress("rect", 1, "failed", error="task error 42")
    store.set_structure_status("rect", "failed")

    data = store.read()
    stored = data.structure("rect")
    assert stored.ended.endswith("Z") and not stored.started  # "failed" records the end time
    assert stored == structure().__class__(**{**vars(structure()), "status": "failed", "ended": stored.ended})
    assert store.read_program("rect", 0) == "LINEAR X1\n"
    assert [(e["layer_id"], e["status"], e["error"]) for e in data.progress["rect"]] == [
        (0, "ok", ""), (1, "failed", "task error 42")]
    with h5py.File(store.path, "r") as f:
        assert f["progress"].attrs["printed_layers"] == 1


def test_structure_names_must_be_valid(store):
    with pytest.raises(ValueError):
        store.add_structure(structure(name="a/b"))


def test_captures_and_dhm_products(store):
    store.add_structure(structure())
    image = np.arange(12, dtype=np.uint8).reshape(3, 4)
    holograms = np.ones((3, 4, 4), dtype=np.uint8)
    camera_id = store.add_capture(capture("camera"), image, device={"ExposureTime": 20000.0})
    dhm_id = store.add_capture(capture("dhm"), holograms, device={"motor": 1000.0}, capture_times_s=[0.1, 0.1, 0.2])
    store.add_dhm_product(dhm_id, "phase", np.full((4, 4), 0.5), {"source": "dhm-pc", "unit": "rad"})

    assert (camera_id, dhm_id) == ("0000", "0001")
    rec, data, device = store.read_capture(camera_id)
    assert np.array_equal(data, image) and device == {"ExposureTime": 20000.0}
    assert rec.commanded_um == (1310.0, 19500.0, None) and rec.actual_um["Z"] == 20001.0
    _, data, _ = store.read_capture(dhm_id)
    assert data.shape == (3, 4, 4)
    product, meta = store.read_dhm_product(dhm_id, "phase")
    assert product.shape == (4, 4) and meta == {"source": "dhm-pc", "unit": "rad"}
    assert [c.capture_id for c in store.read().captures] == ["0000", "0001"]


def test_calibration_plane_fit_opl_and_layout(store, tmp_path):
    from nanofactorysystem.devices.coordinate_system import PlaneFit

    store.write_calibration(np.array([[0.0, 0.0], [1.0, 10.0]]), "quadratic", "cal.dat")
    points = np.array([[0.0, 0.0, 1.0], [100.0, 0.0, 2.0], [0.0, 100.0, 3.0]])
    plane = PlaneFit.from_points(points)
    name, parameters = z_function_to_json(plane)
    store.write_plane_fit(PlaneFitRecord(mode="1", source="measured", function=name, function_json=parameters,
                                         interface="high", sample_points_um=points[:, :2],
                                         interface_points_um=points), {"plane.zdc": b"PK\x03\x04zip"})
    store.write_opl_scan(812.5, "measured")
    corners = [CornerRecord("corner_tl", "TL", (0.0, 0.0), (45.0, 45.0), 0.0, True),
               CornerRecord("corner_tr", "TR", (100.0, 0.0), (55.0, 45.0), 90.0, False)]
    layout = LayoutRecord(rectangle_um=np.zeros((4, 2)), grid_positions_um=np.ones((6, 2)), corners=corners,
                          qrcode_um=(50.0, 0.0), qrcode_text="uuid")
    store.write_layout(layout, b"\x89PNG")
    store.write_layout(layout)  # keeps the plot

    data = store.read()
    assert data.calibration["fit_kind"] == "quadratic" and data.calibration["table"].shape == (2, 2)
    rebuilt = z_function_from_json(data.plane_fit.function, data.plane_fit.function_json)
    assert rebuilt(50.0, 50.0) == pytest.approx(plane(50.0, 50.0))
    assert store.plane_fit_container("plane.zdc") == b"PK\x03\x04zip"
    assert data.opl_scan["motor_pos_um"] == 812.5
    assert data.layout.double_corner.name == "corner_tl" and data.layout.qrcode_text == "uuid"
    with h5py.File(store.path, "r") as f:
        assert f["layout/plot"][()].tobytes() == b"\x89PNG"


def test_slicer_job_is_copied_into_the_structure(store):
    pytest.importorskip("shapely")
    from nanofactorysystem.aerobasic.slicer.pipeline import slice_geometry

    job = slice_geometry(np.full((8, 8), 2.0), pixel_size=1.0)
    store.add_structure(structure())
    store.write_slicer_job("rect", job)

    with h5py.File(store.path, "r") as f:
        slicer = f["structures/rect/slicer"]
        assert "metadata" in slicer and len(slicer["groups"]) == len(job.groups)


def test_sessions_and_lock(store):
    session = store.begin_session("new")
    assert (store.folder / schema.LOCK_NAME).exists()
    with pytest.raises(LockError):
        ExperimentStore.open(store.folder).begin_session("restart")
    store.end_session("finished")
    assert not (store.folder / schema.LOCK_NAME).exists()

    sessions = store.read().sessions
    assert session == "000" and sessions[0]["kind"] == "new" and sessions[0]["end_reason"] == "finished"


def test_stale_lock_is_replaced(tmp_path):
    lock_file = tmp_path / schema.LOCK_NAME
    import json
    import socket
    dead = max(os.getpid() + 1_000_000, 4_000_000)  # far above any running process id
    lock_file.write_text(json.dumps({"host": socket.gethostname(), "pid": dead, "started": "x"}))
    assert not pid_alive(dead)

    lock = ExperimentLock(lock_file)
    lock.acquire()
    assert json.loads(lock_file.read_text())["pid"] == os.getpid()
    lock.release()
    assert pid_alive(os.getpid())
