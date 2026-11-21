"""substrate_layout.json / .png next to substrate.json, rewritten on every index change (T118)."""
import json
import logging

import pytest

from nanofactorysystem.storage import substrate_layout
from nanofactorysystem.storage.substrate_layout import LAYOUT_JSON, LAYOUT_PNG, LAYOUT_SCHEMA
from nanofactorysystem.storage.substrate_store import SubstrateStore

EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


@pytest.fixture
def store(tmp_path):
    store = SubstrateStore(tmp_path / "root")
    store.create("Test", "TU", label="TU-26-001", substrate_type="cover_slip")
    store.add_resin_drop("TU-26-001", EDGES, material="SZ2080")
    return store


def read_layout(store):
    return json.loads((store.folder("TU-26-001") / LAYOUT_JSON).read_text())


def test_created_substrate_has_both_files(store):
    folder = store.folder("TU-26-001")
    assert (folder / LAYOUT_PNG).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    layout = read_layout(store)
    assert layout["schema"] == LAYOUT_SCHEMA and layout["image"] == LAYOUT_PNG
    assert layout["substrate"]["label"] == "TU-26-001"
    assert layout["substrate"]["substrate_type"] == "cover_slip"
    [drop] = layout["resin_drops"]
    assert drop["edges_um"] == EDGES and drop["material"] == "SZ2080"
    assert drop["ellipse"]["cx_um"] == pytest.approx(1200, abs=600)
    assert layout["experiments"] == []


def test_planned_then_registered_experiment(store):
    plan_id = store.plan_experiment("TU-26-001", "rect", objective="Zeiss 63x",
                                    area_um=[[0, 20000], [300, 20300]], resin_drop=0, center_um=[150, 20150])
    [planned] = read_layout(store)["experiments"]
    assert (planned["name"], planned["status"], planned["state"]) == ("rect", "planned", "planned")
    assert planned["area_um"] == [[0.0, 20000.0], [300.0, 20300.0]]
    assert planned["center_um"] == [150.0, 20150.0]

    store.register_experiment("TU-26-001", {
        "uuid": "u1", "label": "TU-26-001-A", "path": "TU-26-001-A_20261121-1000", "started": "now",
        "objective": "Zeiss 63x", "status": "created", "center_um": [150.0, 20150.0],
        "area_um": [[0.0, 20000.0], [300.0, 20300.0]], "resin_drop": 0}, replaces=plan_id)
    store.update_experiment("TU-26-001", "u1", status="finished")
    [done] = read_layout(store)["experiments"]
    assert (done["label"], done["status"], done["state"]) == ("TU-26-001-A", "finished", "done")
    assert done["path"] == "TU-26-001-A_20261121-1000"
    assert read_layout(store)["bounds_um"][0][0] == pytest.approx(-3333)


def test_write_layout_on_request(store):
    folder = store.folder("TU-26-001")
    (folder / LAYOUT_JSON).unlink()
    (folder / LAYOUT_PNG).unlink()
    assert store.write_layout("TU-26-001") == (folder / LAYOUT_JSON, folder / LAYOUT_PNG)
    assert (folder / LAYOUT_JSON).is_file() and (folder / LAYOUT_PNG).is_file()


def test_failed_layout_never_breaks_the_index(store, monkeypatch, caplog):
    def broken(*_args, **_kwargs):
        raise RuntimeError("no plot")
    monkeypatch.setattr(substrate_layout, "write_substrate_layout", broken)
    with caplog.at_level(logging.WARNING):
        store.update_substrate("TU-26-001", notes="still written")
    assert store.get("TU-26-001").notes == "still written"
    assert "not written" in caplog.text


def test_plot_without_anything(tmp_path):
    store = SubstrateStore(tmp_path)
    store.create("Test", "TU", label="TU-26-002")
    assert json.loads((store.folder("TU-26-002") / LAYOUT_JSON).read_text())["bounds_um"] is None
    assert (store.folder("TU-26-002") / LAYOUT_PNG).is_file()
