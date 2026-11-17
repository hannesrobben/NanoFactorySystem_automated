"""Unit tests for substrates, the default data location and the experiment index (storage/substrate_store.py)."""
import json
from pathlib import Path

import pytest

from nanofactorysystem.config import use_config, DEFAULT_CONFIG
from nanofactorysystem.storage.substrate_store import (SubstrateStore, SyncedFolderError, check_not_synced,
                                                       default_root, experiment_letters, find_experiments,
                                                       initials, substrate_overview)


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
    # record version 2 since T76 (was "1.0")
    assert data["schema_version"] == "2.0" and data["notes"] == "first drop in the center"
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


V1_RECORD = {
    "schema_version": "1.0", "label": "HR-26-003", "uuid": "0f0e0d0c-0000-4000-8000-000000000003",
    "created": "2026-10-01T08:00:00.000Z", "user": "Hannes",
    "material": {"substrate": "boro-silicate glass", "thickness_um": 700.0, "resin": "SZ2080",
                 "resin_thickness_um": 75.0, "batch": "L42"},
    "resin_drops": [{"edges_um": [[0.0, 0.0], [1.0, 1.0]], "added": "2026-10-01T08:00:00.000Z"}],
    "notes": "", "experiments": [], "extra": {}}


def test_version_1_record_is_read_as_version_2(tmp_path):
    folder = tmp_path / "HR-26-003"
    folder.mkdir()
    (folder / "substrate.json").write_text(json.dumps(V1_RECORD))
    store = SubstrateStore(tmp_path)

    record = store.get("HR-26-003")

    assert record.material == V1_RECORD["material"]  # the free dict is kept
    assert (record.substrate_material, record.dimensions) == ("boro-silicate glass", {"thickness_um": 700.0})
    drop = record.resin_drops[0]
    assert (drop["material"], drop["batch"], drop["thickness_um"], drop["application"]) == \
           ("SZ2080", "L42", 75.0, "drop")
    assert record.material_names(0)["resin"] == "SZ2080"
    # Reading does not rewrite the file; the next change writes version 2
    assert json.loads((folder / "substrate.json").read_text())["schema_version"] == "1.0"
    store.update_substrate("HR-26-003", substrate_type="cover_slip")
    data = json.loads((folder / "substrate.json").read_text())
    assert data["schema_version"] == "2.0" and data["substrate_type"] == "cover_slip"
    assert data["resin_drops"][0]["material"] == "SZ2080" and data["material"] == V1_RECORD["material"]


def test_version_2_fields_and_material_per_drop(tmp_path):
    store = SubstrateStore(tmp_path)
    label = store.create("Hannes", "HR", substrate_material="cover slip glass", substrate_type="cover_slip",
                         dimensions={"shape": "round", "diameter_mm": 30.0, "thickness_um": 170.0}).label
    store.add_resin_drop(label, [[0, 0], [1, 1]], material="SZ2080", batch="L1", thickness_um=50.0)
    store.add_resin_drop(label, [[5, 5], [6, 6]], material="IP-Dip", application="dip_in")
    record = store.get(label)

    assert record.drop_index([[5, 5], [6, 6]]) == 1 and record.drop_index([[9, 9]]) is None
    assert record.material_names(0) == {"substrate": "cover slip glass", "resin": "SZ2080", "batch": "L1"}
    assert record.material_names(1)["resin"] == "IP-Dip" and record.material_names()["resin"] == "IP-Dip"

    with pytest.raises(ValueError, match="substrate type"):
        store.create("Hannes", "HR", substrate_type="glass plate")
    with pytest.raises(ValueError, match="do not belong"):
        store.create("Hannes", "HR", dimensions={"shape": "round", "width_mm": 20.0})
    with pytest.raises(ValueError, match="application"):
        store.add_resin_drop(label, [[0, 0]], application="spin")
    with pytest.raises(ValueError, match="cannot be changed"):
        store.update_substrate(label, uuid="x")


def test_planned_entries_are_replaced_by_the_experiment(tmp_path):
    store = SubstrateStore(tmp_path)
    label = store.create("Hannes", "HR").label
    plan_a = store.plan_experiment(label, "left", objective="Zeiss 20x", area_um=((0, 0), (10, 10)), resin_drop=0)
    store.plan_experiment(label, "right", objective="Zeiss 20x", area_um=((20, 0), (30, 10)))
    # Planning again (a substrate main started twice) replaces the entry instead of adding one
    assert store.plan_experiment(label, "left", objective="Zeiss 20x", area_um=((0, 0), (12, 12))) == plan_a
    assert [e["name"] for e in store.get(label).experiments] == ["left", "right"]
    assert store.next_experiment_label(label) == f"{label}-A"
    assert find_experiments(tmp_path, substrate=label) == []  # planned entries only on request
    assert [e["name"] for e in find_experiments(tmp_path, status="planned")] == ["left", "right"]

    store.register_experiment(label, entry(f"{label}-A", "u1", "2026-11-17T08:00:00.000Z", status="created")
                              | {"area_um": [[0, 0], [12, 12]], "resin_drop": 0}, replaces=plan_a)

    overview = substrate_overview(tmp_path, label, refresh=False, qr_clearance_um=70.0)
    assert [(o.name, o.status, o.state, o.area_um) for o in overview] == [
        (f"{label}-A", "created", "running", [[0, 0], [12, 12]]),
        ("right", "planned", "planned", [[20.0, 0.0], [30.0, 10.0]])]
    assert overview[0].folder == tmp_path / label / f"{label}-A_20260930-0800" and overview[1].folder is None
    # With refresh the experiment file is the truth; a missing file is reported, the index values stay
    refreshed = substrate_overview(tmp_path, label, qr_clearance_um=70.0)
    assert refreshed[0].status == "created" and refreshed[0].error
