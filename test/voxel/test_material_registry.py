"""Material registry in the voxel database (T75, docs/design/INFORMATION_MODEL.md §3.1, §8)."""
import sqlite3
from pathlib import Path

import pytest

from nanofactorysystem.voxel import (PROPERTY_CSV_COLUMNS, SCHEMA_VERSION, MaterialRegistry, MaterialSnapshot,
                                     UnitWarning, VoxelDatabase, as_material_dict, material_names,
                                     unregistered_snapshot)
from nanofactorysystem.voxel.migrations import migrate_0_to_1

SEED = Path(__file__).parents[2] / "config" / "material_seed.csv"


@pytest.fixture
def registry(tmp_path):
    with MaterialRegistry(tmp_path / "voxels.sqlite") as reg:
        yield reg


def test_version_1_database_is_migrated_and_keeps_its_data(tmp_path):
    path = tmp_path / "old.sqlite"
    connection = sqlite3.connect(path, isolation_level=None)
    migrate_0_to_1(connection)
    connection.execute("PRAGMA user_version = 1")
    connection.execute("INSERT INTO material (name, supplier) VALUES ('SZ2080', 'IESL-FORTH')")
    connection.execute("INSERT INTO voxel_measurement (material_id, objective, setup, power_mW, velocity_um_s, "
                       "width_um, method, date) VALUES (1, 'Zeiss 63x', 'IFOV_off', 1.0, 100.0, 0.5, 'SEM', "
                       "'2026-09-30')")
    connection.close()

    with VoxelDatabase(path) as db:
        assert db.schema_version == SCHEMA_VERSION == 3  # 3: material states of T108
        assert len(db.measurements("SZ2080")) == 1
        material = MaterialRegistry(db).material("SZ2080")
    assert (material.kind, material.supplier, material.properties) == ("resin", "IESL-FORTH", ())


def test_refractive_index_per_wavelength_and_state(registry):
    registry.add_material("ResinX", supplier="Lab")
    registry.add_property("ResinX", "refractive_index", 1.48, "1", wavelength_nm=633, state="uncured",
                          source="datasheet", date="2026-01-01")
    registry.add_property("ResinX", "refractive_index", 1.51, "1", wavelength_nm=633, state="cured",
                          source="datasheet", date="2026-01-01")
    registry.add_property("ResinX", "refractive_index", 1.52, "1", wavelength_nm=633, state="cured",
                          source="own measurement", date="2026-06-01")
    registry.add_property("ResinX", "refractive_index", 1.50, "1", wavelength_nm=532, state="any",
                          date="2026-01-01")
    material = registry.material("ResinX")

    assert material.refractive_index(633, "uncured") == 1.48
    assert material.refractive_index(633, "cured") == 1.52  # most recent date wins
    assert material.property("refractive_index", wavelength_nm=633, state="cured").source == "own measurement"
    assert material.refractive_index(532, "cured") == 1.50  # "any" matches every state
    assert material.refractive_index(780) is None  # no interpolation between wavelengths
    assert registry.get("unknown") is None


def test_exact_state_is_preferred_over_any(registry):
    registry.add_material("ResinY")
    registry.add_property("ResinY", "refractive_index", 1.40, "1", wavelength_nm=633, state="any", date="2026-09-01")
    registry.add_property("ResinY", "refractive_index", 1.45, "1", wavelength_nm=633, state="cured", date="2026-01-01")
    assert registry.material("ResinY").refractive_index(633, "cured") == 1.45


def test_new_keys_text_values_and_validation(registry):
    registry.add_material("ResinZ")
    registry.add_property("ResinZ", "photoinitiator", "Irgacure 369")  # text, new key, no unit needed
    registry.add_property("ResinZ", "post_bake_time", 10.0, "min", source="protocol")  # new numeric key
    material = registry.material("ResinZ")
    assert material.property("photoinitiator").value == "Irgacure 369"
    assert material.property("post_bake_time").unit == "min"

    with pytest.raises(ValueError, match="needs a unit"):
        registry.add_property("ResinZ", "density", 1.2)
    with pytest.raises(ValueError, match="Unknown state"):
        registry.add_property("ResinZ", "refractive_index", 1.5, "1", state="liquid")
    with pytest.raises(KeyError):
        registry.add_property("missing", "density", 1.2, "g/cm3")
    with pytest.warns(UnitWarning):
        registry.add_property("ResinZ", "density", 1200.0, "kg/m3")
    with pytest.raises(ValueError, match="exists as 'resin'"):
        registry.add_material("ResinZ", kind="substrate")
    with pytest.raises(ValueError, match="Unknown material kind"):
        registry.add_material("Glass", kind="glass")


def test_kinds_and_shared_material_table(registry):
    registry.add_material("boro-silicate glass", kind="substrate")
    registry.database.add_material("SZ2080")  # added through the voxel API: a resin
    assert registry.materials("substrate") == ["boro-silicate glass"]
    assert registry.materials("resin") == ["SZ2080"]
    assert registry.material("SZ2080").created == ""  # entries of the voxel API carry no creation time


def test_csv_round_trip_and_seed(tmp_path, registry):
    with MaterialRegistry(tmp_path / "seed.sqlite") as seeded:
        assert seeded.import_csv(SEED) == 3  # SZ2080 in three states (T108)
    registry.add_material("ResinX", supplier="Lab")
    registry.add_property("ResinX", "refractive_index", 1.48, "1", wavelength_nm=633, state="uncured",
                          uncertainty=0.002, source="datasheet", date="2026-01-01")
    registry.add_property("ResinX", "photoinitiator", "Irgacure 369", date="2026-01-02")
    registry.add_material("cover slip glass", kind="substrate")
    exported = tmp_path / "materials.csv"
    registry.export_csv(exported)

    with MaterialRegistry(tmp_path / "copy.sqlite") as copy:
        assert copy.import_csv(exported) == 2
        assert copy.materials() == ["ResinX", "cover slip glass"]
        assert copy.material("ResinX").properties == registry.material("ResinX").properties
        assert copy.material("cover slip glass").kind == "substrate"
    assert exported.read_text(encoding="utf-8").splitlines()[0] == ",".join(PROPERTY_CSV_COLUMNS)


def test_invalid_csv_row_imports_nothing(tmp_path, registry):
    path = tmp_path / "bad.csv"
    path.write_text(",".join(PROPERTY_CSV_COLUMNS) + "\n"
                    "ResinA,resin,,refractive_index,1.5,1,633,cured,,,,,\n"
                    "ResinB,resin,,density,1.2,,,,,,,,\n", encoding="utf-8")  # number without unit
    with pytest.raises(ValueError):
        registry.import_csv(path)
    assert registry.materials() == []


def test_snapshot_round_trip_and_unknown_names(registry):
    registry.add_material("ResinX")
    registry.add_property("ResinX", "refractive_index", 1.51, "1", wavelength_nm=633, state="cured")
    snapshot = registry.snapshot("ResinX", "resin", batch="L42", name_source="argument")
    assert snapshot.known and snapshot.registry_schema_version == 3 and snapshot.batch == "L42"
    assert snapshot.refractive_index(633, "cured") == 1.51
    assert MaterialSnapshot.from_dict(snapshot.to_dict()) == snapshot

    unknown = registry.snapshot("NotThere", "resin")
    assert not unknown.known and unknown.material is None and unknown.refractive_index() is None
    assert unregistered_snapshot("SZ2080", "resin").registry_file == ""
    with pytest.raises(ValueError, match="Unknown material role"):
        registry.snapshot("ResinX", "solvent")


def test_open_existing_never_creates_a_file(tmp_path):
    assert MaterialRegistry.open_existing(tmp_path / "none.sqlite") is None
    assert not (tmp_path / "none.sqlite").exists()


def test_material_names_precedence_and_substrate_material():
    names = material_names(materials={"medium": "immersion oil"},
                           substrate_material={"resin": "ResinX", "batch": "L42", "thickness_um": 75.0},
                           sample={"material": "SZ2080", "substrate": "boro-silicate glass"})
    assert names == {"resin": ("ResinX", "L42", "substrate"),
                     "substrate": ("boro-silicate glass", "", "sys_args"),
                     "medium": ("immersion oil", "", "argument")}
    assert material_names(materials={"resin": "IP-Dip"}, substrate_material={"resin": "ResinX", "batch": "L42"}) \
        == {"resin": ("IP-Dip", "L42", "argument")}
    with pytest.raises(ValueError):
        material_names(materials={"solvent": "PGMEA"})

    assert as_material_dict("SZ2080") == {"resin": "SZ2080"}
    assert as_material_dict({"substrate": "glass"}) == {"substrate": "glass"}
    assert as_material_dict(None) == {}
    with pytest.raises(TypeError):
        as_material_dict(42)
