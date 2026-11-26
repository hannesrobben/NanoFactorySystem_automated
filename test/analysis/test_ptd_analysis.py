"""Cell tables of test fields from the experiment file and import of measured voxel sizes (T147, T164)."""
import csv
import importlib
import json
from pathlib import Path

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from experiment_analysis import ExperimentFile  # noqa: E402
from experiment_analysis.ptd import (MEASUREMENT_COLUMNS, cell_table, export_cell_table,  # noqa: E402
                                     import_voxel_measurements, save_cell_table)
from nanofactorysystem.testprint import ParameterTestInputs  # noqa: E402
from nanofactorysystem.testprint import parameter_tests  # noqa: E402
from nanofactorysystem.testprint.field import write_rows  # noqa: E402
from nanofactorysystem.voxel.database import VoxelDatabase  # noqa: E402

MAINS = Path(__file__).parents[2] / "mains"
INPUTS = ParameterTestInputs("SZ2080", source="tests").to_json()


def filled_rows():
    field = parameter_tests.full_f1(inputs=INPUTS, half="a")
    rows = []
    for row in field.cell_table()[:3]:
        rows.append({"experiment_uuid": "uuid-1", "material": "SZ2080", "objective": "Zeiss 63x",
                     "setup": "IFOV_on", "velocity_um_s": 5000.0, **row})
    rows[0].update(width_um=0.31, width_std_um=0.02, n_lines=4, method="SEM")
    rows[1].update(height_um=0.9, method="DHM", notes="edge")
    return rows                                                       # rows[2] stays empty


def test_import_voxel_measurements(tmp_path):
    rows = filled_rows()
    path = write_rows(tmp_path / "f1.csv", rows, MEASUREMENT_COLUMNS)
    database = VoxelDatabase(tmp_path / "voxels.sqlite")
    assert import_voxel_measurements(path, database) == 2
    stored = database.measurements(material="SZ2080")
    assert len(stored) == 2
    first = next(m for m in stored if m["method"] == "SEM")
    assert first["width_um"] == 0.31 and first["n_lines"] == 4 and first["experiment_uuid"] == "uuid-1"
    assert first["power_mW"] == pytest.approx(rows[0]["power_mw"])
    assert first["setup"] == "IFOV_on" and first["velocity_um_s"] == 5000.0
    assert rows[1]["cell_id"] in next(m for m in stored if m["method"] == "DHM")["notes"]


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
    common = importlib.import_module("parametertest.common")
    monkeypatch.setattr(common, "USER", "Test")
    [folder] = common.run(["full"], only=["F1"], backend=dummy_backend, plane=dummy_backend.world.sample.plane(),
                          data_root=tmp_path / "data")

    rows = cell_table(folder)
    inputs = common.load_inputs().to_json()
    expected = {half: parameter_tests.full_f1(inputs=inputs, half=half).cell_table() for half in "ab"}
    assert len(rows) == sum(len(table) for table in expected.values())
    record = ExperimentFile(folder).record(include_captures=False)
    centers = {s.name: s.center_um for s in record.structures}
    for row in rows:
        reference = next(c for c in expected[row["half"]] if c["cell_id"] == row["cell_id"])
        for key, value in reference.items():
            assert row[key] == value, key
        assert row["experiment_uuid"] == record.uuid and row["material"] == common.RESIN
        assert row["setup"] == "IFOV_on" and row["velocity_um_s"] > 0
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
