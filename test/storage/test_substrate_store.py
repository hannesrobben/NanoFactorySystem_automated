"""Unit tests for substrates, the default data location and the experiment index (storage/substrate_store.py)."""
import json
from pathlib import Path

import pytest

from nanofactorysystem.config import use_config, DEFAULT_CONFIG
from nanofactorysystem.storage.substrate_store import (SubstrateStore, SyncedFolderError, check_not_synced,
                                                       default_root, experiment_letters, find_experiments,
                                                       initials)


def entry(label, uuid, started, objective="Zeiss 20x", status="finished"):
    return {"uuid": uuid, "label": label, "path": f"{label}_20260930-0800", "started": started,
            "objective": objective, "status": status, "center_um": [0.0, 0.0],
            "double_corner_um": [1.0, 2.0], "double_corner_rotation_deg": 0.0}


def test_initials():
    assert initials({"initials": "hr", "name": "Hannes Robben"}) == "HR"
    assert initials({"name": "Hannes Robben"}) == "HR"
    assert initials({"name": "Anna-Lena Maier"}) == "ALM"
    assert initials({"key": "test"}) == "TE"


def test_experiment_letters():
    assert [experiment_letters(i) for i in (0, 1, 25, 26, 27, 51, 52)] == ["A", "B", "Z", "AA", "AB", "AZ", "BA"]


def test_labels_count_per_year(tmp_path):
    store = SubstrateStore(tmp_path)
    assert store.next_label("HR", 2026) == "HR-26-001"
    store.create("Hannes", "HR", label="HR-26-001")
    store.create("Hannes", "HR", label="HR-26-007")
    store.create("Hannes", "HR", label="HR-25-012")
    assert store.next_label("HR", 2026) == "HR-26-008"
    assert store.next_label("HR", 2027) == "HR-27-001"
    assert store.next_label("KM", 2026) == "KM-26-001"
    with pytest.raises(FileExistsError):
        store.create("Hannes", "HR", label="HR-26-001")


def test_substrate_record_round_trip(tmp_path):
    store = SubstrateStore(tmp_path)
    created = store.create("Hannes", "HR", material={"substrate": "boro-silicate glass", "thickness_um": 700.0},
                           notes="first drop in the center")
    store.add_resin_drop(created.label, [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]])

    for key in (created.label, created.uuid):
        loaded = store.get(key)
        assert loaded.uuid == created.uuid and loaded.material["thickness_um"] == 700.0
        assert loaded.resin_drops[0]["edges_um"][1] == [-3333.0, 22420.0]
    data = json.loads((tmp_path / created.label / "substrate.json").read_text())
    assert data["schema_version"] == "1.0" and data["notes"] == "first drop in the center"
    with pytest.raises(KeyError):
        store.get("HR-99-999")


def test_register_and_update_experiments(tmp_path):
    store = SubstrateStore(tmp_path)
    label = store.create("Hannes", "HR").label
    assert store.next_experiment_label(label) == f"{label}-A"
    store.register_experiment(label, entry(f"{label}-A", "u1", "2026-09-30T08:00:00.000Z", status="created"))
    assert store.next_experiment_label(label) == f"{label}-B"
    with pytest.raises(ValueError):
        store.register_experiment(label, entry(f"{label}-A", "u2", "2026-09-30T09:00:00.000Z"))

    store.update_experiment(label, "u1", status="finished")
    assert store.get(label).experiments[0]["status"] == "finished"
    assert not (tmp_path / label / "substrate.lock").exists()
    with pytest.raises(KeyError):
        store.update_experiment(label, "unknown", status="finished")


def test_find_experiments(tmp_path):
    store = SubstrateStore(tmp_path)
    a = store.create("Hannes", "HR").label
    b = store.create("Hannes", "HR").label
    store.register_experiment(a, entry(f"{a}-A", "u1", "2026-09-28T08:00:00.000Z", "Zeiss 20x"))
    store.register_experiment(a, entry(f"{a}-B", "u2", "2026-09-30T08:00:00.000Z", "Zeiss 63x", "aborted"))
    store.register_experiment(b, entry(f"{b}-A", "u3", "2026-09-29T08:00:00.000Z", "Zeiss 63x"))

    assert [e["uuid"] for e in find_experiments(tmp_path)] == ["u1", "u3", "u2"]
    assert [e["uuid"] for e in find_experiments(tmp_path, substrate=a)] == ["u1", "u2"]
    assert [e["uuid"] for e in find_experiments(tmp_path, objective="Zeiss 63x")] == ["u3", "u2"]
    assert [e["uuid"] for e in find_experiments(tmp_path, since="2026-09-29", until="2026-09-29")] == ["u3"]
    assert [e["uuid"] for e in find_experiments(tmp_path, status="aborted")] == ["u2"]
    found = find_experiments(tmp_path, substrate=store.get(b).uuid)[0]
    assert found["substrate_label"] == b and Path(found["folder"]) == tmp_path / b / f"{b}-A_20260930-0800"


def test_synced_folder_is_refused(tmp_path):
    with pytest.raises(SyncedFolderError):
        check_not_synced(tmp_path / "Seafile" / "data")
    with pytest.raises(SyncedFolderError):
        check_not_synced(tmp_path / "onedrive" / "data")
    check_not_synced(tmp_path / "Femtika_Experiment")
    check_not_synced(tmp_path / "Mirror", names=["Mirror2"])


def test_default_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    config = DEFAULT_CONFIG | {"user:Test": {"name": "Test User"},
                               "user:Other": {"name": "Other", "dataRoot": str(tmp_path / "Seafile" / "x")}}
    with use_config(config):
        assert default_root("Test") == tmp_path / "Documents" / "Femtika_Experiment" / "Test"
        with pytest.raises(SyncedFolderError):
            default_root("Other")
        assert default_root("Other", allow_synced_root=True) == tmp_path / "Seafile" / "x"


def test_import_legacy_substrate_information(tmp_path):
    legacy = tmp_path / "substrate_information.json"
    legacy.write_text(json.dumps({"Name": "old substrate", "Number of drops": 2}))

    record = SubstrateStore(tmp_path / "root").import_legacy(legacy, "Hannes", "HR")

    assert record.notes == "old substrate" and record.extra["Number of drops"] == 2
