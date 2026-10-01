"""Voxel database with synthetic data (T53, docs/design/VOXEL_DATABASE.md §7)."""
import csv
import math
import sqlite3
from pathlib import Path

import pytest

from nanofactorysystem.voxel import CSV_COLUMNS, SCHEMA_VERSION, VoxelDatabase

SEED = Path(__file__).parents[2] / "config" / "voxel_seed.csv"
MATERIAL, OBJECTIVE, SETUP = "SZ2080", "Zeiss 63x", "IFOV_off"


def linear_width(power, velocity):
    """ Synthetic width, linear in (ln P, ln v), so that linear interpolation reproduces it exactly. """

    return 2.0 + 0.3 * math.log(power) - 0.1 * math.log(velocity)


@pytest.fixture
def db(tmp_path):
    with VoxelDatabase.create(tmp_path / "voxels.sqlite") as database:
        yield database


def add(db, power, velocity, *, width=None, height=None, n_lines=1, material=MATERIAL, setup=SETUP):
    return db.add_measurement(material, OBJECTIVE, setup, power, velocity, width_um=width, height_um=height,
                              n_lines=n_lines, method="SEM", date="2026-09-30")


def test_schema_version_and_migration(tmp_path):
    with VoxelDatabase(tmp_path / "new.sqlite") as db:
        assert db.schema_version == SCHEMA_VERSION == 1
        assert {"material", "voxel_measurement"} <= {r[0] for r in db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}

    # A newer database is refused
    connection = sqlite3.connect(tmp_path / "future.sqlite")
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(RuntimeError, match="schema version 99"):
        VoxelDatabase(tmp_path / "future.sqlite")
    with pytest.raises(FileExistsError):
        VoxelDatabase.create(tmp_path / "new.sqlite")


def test_constraints(db):
    with pytest.raises(ValueError):
        add(db, 1.0, 1000.0)  # neither width nor height
    with pytest.raises(ValueError):
        db.add_measurement(MATERIAL, OBJECTIVE, "IFOV_maybe", 1.0, 1000.0, width_um=0.5, method="SEM")
    with pytest.raises(ValueError):
        db.add_measurement(MATERIAL, OBJECTIVE, SETUP, 1.0, 1000.0, width_um=0.5, method="guess")
    with pytest.raises(sqlite3.IntegrityError):
        add(db, -1.0, 1000.0, width=0.5)
    with pytest.raises(sqlite3.IntegrityError):
        add(db, 1.0, 1000.0, width=0.0)


def test_exact_hit_averages_duplicates_weighted_by_lines(db):
    add(db, 2.0, 1000.0, width=0.40, n_lines=1)
    add(db, 2.0, 1000.0, width=0.50, n_lines=3)

    size = db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 2.0, 1000.0)

    assert size.width_um == pytest.approx((0.40 + 3 * 0.50) / 4) and size.width_method == "exact"
    assert size.height_um is None and size.height_method == ""


def test_2d_interpolation_inside_the_hull(db):
    for power in (1.0, 2.0, 4.0):
        for velocity in (500.0, 2000.0, 8000.0):
            add(db, power, velocity, width=linear_width(power, velocity))

    size = db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 1.5, 1000.0)

    assert size.width_um == pytest.approx(linear_width(1.5, 1000.0))
    assert size.width_method == "interpolated-2d" and size.n_points == 9


def test_outside_the_hull_unknown_material_and_too_few_points(db):
    for power, velocity in ((1.0, 500.0), (4.0, 500.0), (1.0, 8000.0), (4.0, 8000.0)):
        add(db, power, velocity, width=linear_width(power, velocity))

    assert db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 8.0, 1000.0) is None  # no extrapolation
    assert db.voxel_size("OrmoComp", OBJECTIVE, SETUP, 2.0, 1000.0) is None
    assert db.voxel_size(MATERIAL, "Zeiss 20x", SETUP, 2.0, 1000.0) is None
    with VoxelDatabase(db.path, min_points=5) as strict:
        assert strict.voxel_size(MATERIAL, OBJECTIVE, SETUP, 2.0, 1000.0) is None


def test_dose_fallback_for_a_power_series(db):
    for power in (1.0, 2.0, 4.0):  # one velocity only: collinear in (ln P, ln v)
        add(db, power, 1000.0, height=power)

    size = db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 3.0, 1000.0)
    assert size.height_method == "interpolated-dose" and size.n_points == 3
    # Linear in ln(P^2/v) between the neighbours 2 mW and 4 mW
    t = (math.log(9.0) - math.log(4.0)) / (math.log(16.0) - math.log(4.0))
    assert size.height_um == pytest.approx(2.0 + t * 2.0)
    # Off the measured line or outside the dose range: no value
    assert db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 3.0, 2000.0) is None
    assert db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 5.0, 1000.0) is None


def test_width_and_height_with_different_points(db):
    for power, velocity in ((1.0, 500.0), (4.0, 500.0), (1.0, 8000.0), (4.0, 8000.0)):
        add(db, power, velocity, width=linear_width(power, velocity))
    add(db, 2.0, 1000.0, height=1.2)  # a single height measurement

    inside = db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 2.0, 2000.0)
    assert inside.width_method == "interpolated-2d" and inside.height_um is None
    at_height = db.voxel_size(MATERIAL, OBJECTIVE, SETUP, 2.0, 1000.0)
    assert at_height.height_um == 1.2 and at_height.height_method == "exact"


def test_csv_round_trip_and_seed(tmp_path, db):
    add(db, 2.0, 1000.0, width=0.5, height=1.1)
    add(db, 3.0, 1000.0, width=0.6, material="OrmoComp", setup="IFOV_on")
    exported = tmp_path / "export.csv"

    db.export_csv(exported)

    with open(exported, newline="", encoding="utf-8") as fp:
        assert tuple(csv.DictReader(fp).fieldnames) == CSV_COLUMNS
    with VoxelDatabase.create(tmp_path / "copy.sqlite", seed=exported) as copy:
        assert copy.materials() == ["OrmoComp", "SZ2080"]  # unknown materials are created
        rows = copy.measurements()
        assert [(r["material"], r["setup"], r["width_um"], r["height_um"]) for r in rows] == [
            ("SZ2080", SETUP, 0.5, 1.1), ("OrmoComp", "IFOV_on", 0.6, None)]
        assert rows[0]["source"] == "export.csv"
    # The versioned seed file has the import format and builds an (empty) database
    with VoxelDatabase.create(tmp_path / "seeded.sqlite", seed=SEED) as seeded:
        assert seeded.measurements() == []


def test_invalid_csv_row_imports_nothing(tmp_path, db):
    bad = tmp_path / "bad.csv"
    bad.write_text(",".join(CSV_COLUMNS) + "\n"
                   "SZ2080,Zeiss 63x,IFOV_off,1.0,1000,0.5,,,,1,SEM,,2026-09-30,\n"
                   "SZ2080,Zeiss 63x,IFOV_off,2.0,1000,,,,,1,SEM,,2026-09-30,\n", encoding="utf-8")

    with pytest.raises(ValueError):
        db.import_csv(bad)
    assert db.measurements() == []


def test_default_path_from_the_configuration(tmp_path):
    from nanofactorysystem.config import DEFAULT_CONFIG, use_config
    from nanofactorysystem.storage.substrate_store import SyncedFolderError
    from nanofactorysystem.voxel import default_path

    with use_config(DEFAULT_CONFIG | {"system": {"voxelDatabase": str(tmp_path / "lab" / "voxels.sqlite")}}):
        assert default_path() == tmp_path / "lab" / "voxels.sqlite"
    with use_config(DEFAULT_CONFIG | {"system": {"voxelDatabase": str(tmp_path / "Seafile" / "v.sqlite")}}):
        with pytest.raises(SyncedFolderError):
            default_path()
