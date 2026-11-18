"""Material states, SZ2080 seed, JSON export and missing indices (T108, G7)."""
import json
import sqlite3
from pathlib import Path

import pytest

from nanofactorysystem.voxel import (PHYSICAL_STATES, REGISTRY_EXPORT_SCHEMA, SCHEMA_VERSION, MaterialProperty,
                                     MaterialRegistry, MaterialSnapshot, MissingPropertyError, VoxelDatabase,
                                     normalize_state)
from nanofactorysystem.voxel.migrations import migrate_0_to_1, migrate_1_to_2

SEED = Path(__file__).parents[2] / "config" / "material_seed.csv"
DHM_NM = 674.994


@pytest.fixture
def registry(tmp_path):
    with MaterialRegistry(tmp_path / "voxels.sqlite") as reg:
        yield reg


@pytest.fixture
def seeded(registry):
    registry.import_csv(SEED)
    return registry


def test_states_and_legacy_name():
    assert PHYSICAL_STATES == ("uncured", "cured_in_resin", "cured_developed")
    assert normalize_state("cured") == "cured_in_resin"
    assert normalize_state("cured_developed") == "cured_developed"
    with pytest.raises(ValueError, match="Unknown state"):
        normalize_state("liquid")


def test_version_2_database_with_cured_rows_is_migrated(tmp_path):
    path = tmp_path / "v2.sqlite"
    connection = sqlite3.connect(path, isolation_level=None)
    migrate_0_to_1(connection)
    migrate_1_to_2(connection)
    connection.execute("PRAGMA user_version = 2")
    connection.execute("INSERT INTO material (name, kind) VALUES ('ResinX', 'resin')")
    for state, n in (("uncured", 1.48), ("cured", 1.51), ("any", 1.50)):
        connection.execute("INSERT INTO material_property (material_id, key, value_real, unit, wavelength_nm, "
                           "state, date) VALUES (1, 'refractive_index', ?, '1', 633, ?, '2026-01-01')", (n, state))
    connection.close()

    with VoxelDatabase(path) as db:
        assert db.schema_version == SCHEMA_VERSION == 3
        material = MaterialRegistry(db).material("ResinX")
        states = sorted(p.state for p in material.properties)
        assert states == ["any", "cured_in_resin", "uncured"]
        assert material.refractive_index(633, "cured_in_resin") == 1.51
        assert material.refractive_index(633, "cured") == 1.51  # legacy query still works
        # The new CHECK constraint accepts the new states and rejects the old name.
        db.connection.execute("INSERT INTO material_property (material_id, key, value_real, unit, state, date) "
                              "VALUES (1, 'refractive_index', 1.52, '1', 'cured_developed', '2026-01-02')")
        with pytest.raises(sqlite3.IntegrityError):
            db.connection.execute("INSERT INTO material_property (material_id, key, value_real, unit, state, date)"
                                  " VALUES (1, 'refractive_index', 1.52, '1', 'cured', '2026-01-02')")


def test_old_csv_with_cured_still_loads(tmp_path, registry):
    path = tmp_path / "old.csv"
    path.write_text("material,kind,supplier,key,value,unit,wavelength_nm,state,temperature_c,uncertainty,source,"
                    "date,notes\nResinA,resin,,refractive_index,1.5,1,633,cured,,,,,\n", encoding="utf-8")
    assert registry.import_csv(path) == 1
    assert registry.material("ResinA").properties[0].state == "cured_in_resin"


def test_old_snapshot_dict_is_read_with_the_new_state():
    prop = MaterialProperty.from_dict({"key": "refractive_index", "value": 1.52, "unit": "1", "state": "cured"})
    assert prop.state == "cured_in_resin"


def test_sz2080_seed(seeded):
    sz = seeded.material("SZ2080")
    assert sz.refractive_index(DHM_NM, "uncured") == 1.508
    assert sz.refractive_index(DHM_NM, "cured_in_resin") == 1.52
    assert sz.refractive_index(DHM_NM, "cured_developed") == 1.52
    assert round(sz.refractive_index(DHM_NM, "cured_in_resin") - sz.refractive_index(DHM_NM, "uncured"), 6) == 0.012
    for prop in sz.properties:
        assert "maintainer's measurement" in prop.source and prop.date == "2026-11-18"


def test_missing_index_raises_with_the_source_named(seeded):
    sz = seeded.material("SZ2080")
    with pytest.raises(MissingPropertyError, match=r"SZ2080.*'uncured'.*633"):
        sz.require_refractive_index(633, "uncured")
    with pytest.raises(MissingPropertyError, match="maintainer's measurement"):
        sz.require_refractive_index(633, "uncured")  # the stored alternatives are listed
    assert sz.require_refractive_index(DHM_NM, "uncured").value == 1.508


def test_contract_snapshot(seeded):
    snapshot = seeded.material("SZ2080").contract_snapshot(DHM_NM, registry_version="3")
    assert snapshot["material_id"] == "sz2080" and snapshot["wavelength_nm"] == DHM_NM
    assert {k: v["n"] for k, v in snapshot["states"].items()} == {
        "uncured": 1.508, "cured_in_resin": 1.52, "cured_developed": 1.52}
    seeded.add_material("ResinY")
    seeded.add_property("ResinY", "refractive_index", 1.48, "1", wavelength_nm=DHM_NM, state="uncured")
    with pytest.raises(MissingPropertyError, match="cured_in_resin"):
        seeded.material("ResinY").contract_snapshot(DHM_NM)


def test_contract_snapshot_matches_the_dhmconnect_schema(seeded):
    schemas = pytest.importorskip("dhmconnect.schemas")
    capture = schemas.load_example("CaptureContext")
    capture["material"] = seeded.material("SZ2080").contract_snapshot(DHM_NM, "3")
    schemas.validate(capture, "CaptureContext")


def test_json_export(tmp_path, seeded):
    seeded.add_material("cover slip glass", kind="substrate")
    document = seeded.export_json(tmp_path / "materials.json")
    on_disk = json.loads((tmp_path / "materials.json").read_text(encoding="utf-8"))
    assert on_disk == document
    assert document["schema"] == REGISTRY_EXPORT_SCHEMA
    assert document["registry_schema_version"] == SCHEMA_VERSION
    assert "cured_developed" in document["states"]
    names = [m["name"] for m in document["materials"]]
    assert names == ["SZ2080", "cover slip glass"]
    # The export reads back into the same snapshot type the experiments store.
    sz = MaterialSnapshot.from_dict({"role": "resin", "name": "SZ2080", "known": True,
                                     "material": document["materials"][0]})
    assert sz.refractive_index(DHM_NM, "uncured") == 1.508
