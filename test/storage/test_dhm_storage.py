"""DHM service results in the experiment file (T83, docs/design/EXPERIMENT_STORAGE.md §15)."""
import json

import h5py
import numpy as np
import pytest

from dhm_example import CONFIG_HASH, layer_product_header, product_set_header, write_dhm_example
from nanofactorysystem.storage import CaptureRecord, ExperimentStore
from nanofactorysystem.storage import schema


@pytest.fixture
def example(tmp_path):
    path = write_dhm_example(tmp_path / "exp")
    return ExperimentStore.open(path.parent, read_locking=False)


def test_schema_version_is_1_3(example):
    with h5py.File(example.path, "r") as f:
        assert f.attrs["schema_version"] == "1.3" == schema.SCHEMA_VERSION


def test_product_set_round_trip(example):
    job = example.read_capture_job("0000")
    assert job["adapter"] == "service" and job["job_state"] == "acknowledged" and job["job_id"] == "job-100"
    assert job["config_hash"] == CONFIG_HASH and job["group_id"] == "grp-0001"
    assert job["raw_ref"]["n_frames"] == 2 and job["raw_ref"]["path"].endswith("0000_job-100.h5")
    header, buffers = example.read_dhm_result("0000")
    assert header["message_type"] == "ProductSet" and header["job_id"] == "job-100"
    assert set(buffers) == {"phase_rad", "intensity_rel", "valid"}
    assert buffers["phase_rad"].dtype == np.float32 and buffers["valid"].dtype == np.uint8


def test_frame_records_round_trip(example):
    frames = example.read_capture_job("0000")["frames"]
    original = product_set_header("0000", "job-100", [])["reconstruction"]["frames"]
    assert len(frames) == 2
    for read, written in zip(frames, original):
        assert read["index"] == written["index"] and read["used"] == written["used"]
        assert read["reject_reason"] == written["reject_reason"]
        assert read["acquisition"] == written["acquisition"]
        for key, value in written["metrics"].items():
            assert read["metrics"][key] == pytest.approx(value) if value is not None else read["metrics"][key] is None


def test_flat_traceability_attributes(example):
    with h5py.File(example.path, "r", locking=False) as f:
        dataset = f["structures/pillar_03/captures/0000/products/phase_rad"]
        assert dataset.attrs["config_hash"] == CONFIG_HASH
        assert dataset.attrs["z_um"] == pytest.approx(-2.4)
        assert dataset.attrs["propagation_index"] == pytest.approx(1.508)
        assert list(dataset.attrs["pixel_um"]) == pytest.approx([0.1738, 0.1738])
        assert dataset.attrs["background_id"] == "bg-0001"
        assert json.loads(dataset.attrs["quality_json"])["reference_source"] == "mask_a_priori"


def test_layer_product_uses_the_mira_layout(example):
    assert example.dhm_groups() == ["grp-0001"]
    header, buffers, info = example.read_layer_product("grp-0001")
    assert info["kind"] == "layer" and info["layer_id"] == 4 and info["members"] == ["0000", "0001"]
    assert info["group_spec"]["seed"] == 7 and info["recovered"] is False
    assert header["message_type"] == "LayerProduct" and len(header["tiles"]) == 2
    assert buffers["field"].dtype == np.complex64
    # Plain h5py reader: header_json + one dataset per buffer descriptor (MIRA LayerProduct.from_h5)
    with h5py.File(example.path, "r", locking=False) as f:
        group = f["dhm_groups/grp-0001/product"]
        descriptors = json.loads(group.attrs["header_json"])["buffers"]
        assert [d["name"] for d in descriptors] == ["phase_rad", "intensity_rel", "valid", "field"]
        assert all(list(group[d["name"]].shape) == d["shape"] for d in descriptors)


def test_open_captures_and_failed_job(example):
    open_ = example.open_captures()
    assert [c["capture_id"] for c in open_] == ["0002"] and open_[0]["job_state"] == "reserved"
    failed = example.read_capture_job("0003")
    assert failed["job_state"] == "failed" and failed["error"] == "busy"
    with pytest.raises(KeyError):
        example.read_dhm_result("0002")


def test_legacy_capture_is_unchanged_and_reads_with_defaults(example):
    with h5py.File(example.path, "r", locking=False) as f:
        group = f["structures/pillar_03/captures/0004"]
        assert "job_state" not in group.attrs and "holograms" in group
    job = example.read_capture_job("0004")
    assert job["adapter"] == "legacy" and job["job_state"] == "stored" and job["raw_ref"] == {}
    assert example.open_captures() == example.open_captures(("reserved", "sent", "acquired"))


def test_orphans_and_calibration(example):
    orphans = example.read_dhm_orphans()
    assert list(orphans) == ["job-099"] and orphans["job-099"]["size_bytes"] == 4096
    assert "data" not in orphans["job-099"]
    backgrounds = example.read_dhm_calibrations("background")
    assert backgrounds["bg-0001"]["result"]["n_frames"] == 10


def test_second_delivery_of_a_job_is_dropped(tmp_path):
    path = write_dhm_example(tmp_path / "exp")
    store = ExperimentStore.open(path.parent)
    buffers = [("phase_rad", np.full((16, 16), 9.0, np.float32))]
    assert store.add_dhm_result("0000", product_set_header("0000", "job-100", buffers), buffers) is False
    _, stored = store.read_dhm_result("0000")
    assert not np.any(stored["phase_rad"] == 9.0)


def test_recovered_result_is_marked(tmp_path):
    path = write_dhm_example(tmp_path / "exp")
    store = ExperimentStore.open(path.parent)
    buffers = [("phase_rad", np.zeros((16, 16), np.float32))]
    store.update_capture_job("0002", job_state="sent", job_id="job-120")
    assert store.add_dhm_result("0002", product_set_header("0002", "job-120", buffers), buffers,
                                recovered={"reason": "sync after restart", "original_session": "000"})
    job = store.read_capture_job("0002")
    assert job["recovered"] is True and job["job_state"] == "stored"
    header, _, _ = store.read_layer_product("grp-0001")
    assert header["group_id"] == "grp-0001"


def test_validation_of_states_kinds_and_adapters(tmp_path):
    path = write_dhm_example(tmp_path / "exp")
    store = ExperimentStore.open(path.parent)
    camera = CaptureRecord(kind="camera", structure="pillar_03", phase="before", layer_id=-1, image_index=0,
                           image_count=1, offset_um=(0.0, 0.0), commanded_um=(None, None, None))
    with pytest.raises(ValueError, match="DHM captures"):
        store.reserve_capture(camera, recipe={}, context={})
    with pytest.raises(ValueError, match="job state"):
        store.update_capture_job("0002", job_state="done")
    with pytest.raises(ValueError, match="group kind"):
        store.add_layer_product("g", layer_product_header("g", "j", [], []), [], kind="mosaic", structure="s",
                                phase="layer", layer_id=0, members=[])
    with pytest.raises(ValueError, match="calibration kind"):
        store.write_dhm_calibration("focus", "x", parameters={}, result={})


def test_read_of_the_whole_record_still_works(example):
    record = example.read()
    assert [c.capture_id for c in record.captures] == ["0000", "0001", "0002", "0003", "0004"]


def test_unpack_lists_jobs_and_products(tmp_path):
    import csv

    from experiment_analysis import unpack_experiment

    path = write_dhm_example(tmp_path / "exp")
    target = unpack_experiment(path.parent, tmp_path / "out", csv_style="en", previews=False)
    with (target / "tables" / "captures.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = {row["capture_id"]: row for row in csv.DictReader(handle)}
    assert rows["0000"]["job_id"] == "job-100" and rows["0000"]["job_state"] == "acknowledged"
    assert rows["0000"]["products"] == "intensity_rel phase_rad valid"
    assert rows["0002"]["job_state"] == "reserved" and rows["0004"]["job_state"] == "stored"


def _tree(path):
    names = []
    with h5py.File(path, "r", locking=False) as f:
        f.visititems(lambda name, obj: names.append((name, sorted(obj.attrs))))
    return names


def test_vendored_example_matches_the_generator(tmp_path):
    """ test/storage/data/dhm_example/experiment.h5 is the file the other repositories vendor (§15). """

    from pathlib import Path

    committed = Path(__file__).parent / "data" / "dhm_example" / "experiment.h5"
    generated = write_dhm_example(tmp_path / "exp")
    assert _tree(committed) == _tree(generated), "regenerate: python test/storage/dhm_example.py <folder>"
