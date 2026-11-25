"""Cell tables of PTD fields from the experiment file and import of measured voxel sizes (T147)."""
import csv
import importlib
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from experiment_analysis import ExperimentFile  # noqa: E402
from experiment_analysis.ptd import (MEASUREMENT_COLUMNS, cell_table, export_cell_table,  # noqa: E402
                                     import_voxel_measurements, save_cell_table)
from nanofactorysystem.testprint import ptd01  # noqa: E402
from nanofactorysystem.testprint.field import write_rows  # noqa: E402
from nanofactorysystem.voxel.database import VoxelDatabase  # noqa: E402

MAINS = Path(__file__).parents[2] / "mains"
sys.path.insert(0, str(Path(__file__).parents[1] / "testprint"))
from ptd_examples import EXAMPLE_CALIBRATION  # noqa: E402


def filled_rows():
    field = ptd01.field_f1(calibration=EXAMPLE_CALIBRATION.to_json(), label_power_mw=0.7)
    rows = []
    for row in field.cell_table()[:3]:
        rows.append({"experiment_uuid": "uuid-1", "material": "SZ2080", "objective": "Zeiss 63x",
                     "setup": "IFOV_on", "velocity_um_s": 5000.0, **row})
    rows[0].update(width_um=0.31, width_std_um=0.02, n_lines=4, method="SEM")
    rows[1].update(height_um=0.9, method="DHM", notes="edge")
    return rows                                                       # rows[2] stays empty


def test_import_voxel_measurements(tmp_path):
    path = write_rows(tmp_path / "f1.csv", filled_rows(), MEASUREMENT_COLUMNS)
    database = VoxelDatabase(tmp_path / "voxels.sqlite")
    assert import_voxel_measurements(path, database) == 2
    stored = database.measurements(material="SZ2080")
    assert len(stored) == 2
    first = next(m for m in stored if m["method"] == "SEM")
    assert first["width_um"] == 0.31 and first["n_lines"] == 4 and first["experiment_uuid"] == "uuid-1"
    assert first["power_mW"] == pytest.approx(EXAMPLE_CALIBRATION.power_mw(ptd01.F1_P_REL[0]))
    assert first["setup"] == "IFOV_on" and first["velocity_um_s"] == 5000.0
    assert "F1-r0c1" in next(m for m in stored if m["method"] == "DHM")["notes"]


def test_import_refuses_a_row_without_method(tmp_path):
    rows = filled_rows()
    rows[0]["method"] = ""
    path = write_rows(tmp_path / "f1.csv", rows, MEASUREMENT_COLUMNS)
    with pytest.raises(ValueError, match="method"):
        import_voxel_measurements(path, VoxelDatabase(tmp_path / "voxels.sqlite"))


def test_other_fields_are_not_imported(tmp_path):
    rows = filled_rows()
    for row in rows:
        row["field_id"] = 3
    path = write_rows(tmp_path / "f3.csv", rows, MEASUREMENT_COLUMNS)
    assert import_voxel_measurements(path, VoxelDatabase(tmp_path / "voxels.sqlite")) == 0


@pytest.mark.slow
def test_cell_table_from_the_dry_run_experiment(monkeypatch, test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    monkeypatch.syspath_prepend(str(MAINS))
    common = importlib.import_module("Experiments.ptd01.common")
    monkeypatch.setattr(common, "USER", "Test")
    [folder] = common.run_fields([3], calibration_path=common.EXAMPLE_CALIBRATION_FILE, replicates=2,
                                 backend=dummy_backend, plane=dummy_backend.world.sample.plane(),
                                 data_root=tmp_path / "data", allow_example=True)

    rows = cell_table(folder)
    expected = ptd01.field_f3(calibration=EXAMPLE_CALIBRATION.to_json(), label_power_mw=common.LABEL_POWER_MW)
    table = expected.cell_table()
    assert len(rows) == 2 * len(table)                               # the field and its REPEAT copy
    structures = sorted({r["structure"] for r in rows})
    assert len(structures) == 2 and "F3_line_pairs" in structures
    record = ExperimentFile(folder).record(include_captures=False)
    centers = {s.name: s.center_um for s in record.structures}
    for row in rows:
        reference = next(c for c in table if c["cell_id"] == row["cell_id"])
        for key, value in reference.items():
            assert row[key] == value, key
        assert row["experiment_uuid"] == record.uuid and row["material"] == "SZ2080"
        assert row["velocity_um_s"] == 5000.0 and row["setup"] == "IFOV_on"
        assert row["stage_x_um"] == pytest.approx(centers[row["structure"]][0] + row["x_um"], abs=1e-3)
        assert row["stage_y_um"] == pytest.approx(centers[row["structure"]][1] + row["y_um"], abs=1e-3)

    path = export_cell_table(folder, tmp_path / "cells.csv")
    with path.open(encoding="utf-8") as handle:
        exported = list(csv.DictReader(handle))
    assert len(exported) == len(rows) and set(MEASUREMENT_COLUMNS) <= set(exported[0])
    assert exported[0]["width_um"] == ""

    location = save_cell_table(folder)
    assert location.endswith("ptd01_cell_table")
    stored = ExperimentFile(folder).load_result("ptd01_cell_table")
    data = stored[0] if isinstance(stored, tuple) else stored
    if isinstance(data, dict):
        data = data.get("data", data)
    text = data.decode() if isinstance(data, bytes) else str(data)
    assert len(json.loads(text)) == len(rows)
