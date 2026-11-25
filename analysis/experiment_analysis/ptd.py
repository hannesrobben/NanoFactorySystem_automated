##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Cell tables of PTD test fields and import of measured voxel sizes (T147, design §8).

The cell table of a field is regenerated from the experiment file alone: ``/spec`` holds the factory
call of every field (name ``ptd01.f<n>`` and its JSON arguments), and the pure field builder of
``nanofactorysystem.testprint.ptd01`` rebuilds the field from them (no ``BuildContext`` needed). The
stage position of every cell is the stage centre of the structure (structure records, also for REPEAT
copies) plus the cell centre in field coordinates.

- :func:`cell_table` returns one row (dict) per cell and structure; pandas is not required
  (``pandas.DataFrame(rows)`` if wanted).
- :func:`export_cell_table` writes it as CSV with empty columns for the measured values that are filled
  in during the SEM / DHM evaluation.
- :func:`import_voxel_measurements` writes filled rows of F0, F1 and F2 into the voxel database.
- :func:`save_cell_table` stores the table in the experiment file through ``ExperimentFile`` (result
  ``/analysis/experiment/ptd01_cell_table``, design §5.9 of EXPERIMENT_STORAGE.md).

Example::

    from experiment_analysis.ptd import export_cell_table
    export_cell_table(r"D:/.../HR-26-003-B_20261201-1015", "F3_cells.csv")
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional, Union

from nanofactorysystem.aerobasic.programs.drawings.base import decode_json_value
from nanofactorysystem.aerobasic.programs.drawings.lines import ifov_writing_speed_mm_s

from .access import ExperimentFile

__all__ = ["MEASUREMENT_COLUMNS", "VOXEL_FIELDS", "ptd_structures", "cell_table", "export_cell_table",
           "import_voxel_measurements", "save_cell_table"]

PathLike = Union[str, Path]

# Columns filled during the evaluation (empty in the exported template)
MEASUREMENT_COLUMNS = ("width_um", "height_um", "width_std_um", "height_std_um", "n_lines", "present", "merged",
                       "collapsed", "method", "notes")
# Fields whose measured widths / heights are voxel sizes (design §7)
VOXEL_FIELDS = (0, 1, 2)
# Factory arguments that are not field arguments
_STRUCTURE_ONLY = ("dwell_after_power_s",)


def _find(data, key: str):
    """ The first value of ``key`` in a nested spec dict (the spec groups its settings in sections). """

    if isinstance(data, dict):
        if key in data and not isinstance(data[key], dict):
            return data[key]
        for value in data.values():
            found = _find(value, key)
            if found is not None:
                return found
    return None


def _experiment(experiment: Union[PathLike, ExperimentFile]) -> ExperimentFile:
    return experiment if isinstance(experiment, ExperimentFile) else ExperimentFile(experiment)


def ptd_structures(experiment: Union[PathLike, ExperimentFile], prefix: str = "ptd01.") -> list[dict[str, Any]]:
    """ The PTD fields of an experiment: factory name, builder arguments and every printed copy.

    Parameters
    ----------
    experiment : path or ExperimentFile
        ``experiment.h5`` or its folder.
    prefix : str
        Factory name prefix of the test print.

    Returns
    -------
    list of dict
        ``{"name", "factory", "arguments", "copies": [(structure name, (x, y) stage µm), ...]}``.

    Raises
    ------
    ValueError
        If the experiment file holds no spec.
    """

    exp = _experiment(experiment)
    record = exp.record(include_captures=False)
    if not record.spec:
        raise ValueError(f"{exp.path} holds no experiment spec (/spec); the cell table cannot be rebuilt.")
    found = []
    for entry in record.spec.get("structures", []):
        geometry = entry.get("geometry", {})
        if geometry.get("kind") != "factory" or not str(geometry.get("name", "")).startswith(prefix):
            continue
        arguments = {k: decode_json_value(v) for k, v in geometry.get("arguments", {}).items()
                     if k not in _STRUCTURE_ONLY}
        copies = [(s.name, tuple(float(v) for v in s.center_um[:2])) for s in record.structures
                  if s.name == entry["name"] or s.repeat_of == entry["name"]]
        found.append({"name": entry["name"], "factory": geometry["name"], "arguments": arguments, "copies": copies})
    return found


def cell_table(experiment: Union[PathLike, ExperimentFile], prefix: str = "ptd01.") -> list[dict[str, Any]]:
    """ The cell table of every PTD field of an experiment, regenerated from ``/spec``.

    Parameters
    ----------
    experiment : path or ExperimentFile
    prefix : str
        Factory name prefix (``"ptd01."``).

    Returns
    -------
    list of dict
        One row per cell and printed copy: experiment UUID and label, structure, material, objective,
        setup, velocity, stage position of the cell, then the columns of ``ParameterField.cell_table()``.
    """

    from nanofactorysystem.testprint import field_builder

    exp = _experiment(experiment)
    record = exp.record(include_captures=False)
    spec = record.spec or {}
    objective = _find(spec, "objective") or record.objective.get("name", "")
    setup = _find(spec, "setup") or ""
    velocity = float(ifov_writing_speed_mm_s(objective)) * 1000.0 if objective else None
    rows = []
    for item in ptd_structures(exp, prefix):
        field = field_builder(item["factory"], "nanofactorysystem.testprint")(**item["arguments"])
        material = item["arguments"].get("calibration", item["arguments"].get("stage_a", {})).get("material", "")
        for structure, (x0, y0) in item["copies"]:
            for cell in field.cell_table():
                rows.append({"experiment_uuid": record.uuid, "experiment_label": record.label,
                             "structure": structure, "material": material, "objective": objective, "setup": setup,
                             "velocity_um_s": velocity, "stage_x_um": round(x0 + cell["x_um"], 3),
                             "stage_y_um": round(y0 + cell["y_um"], 3), **cell})
    return rows


def export_cell_table(experiment: Union[PathLike, ExperimentFile], path: PathLike,
                      prefix: str = "ptd01.") -> Path:
    """ Write the cell table as CSV with empty measurement columns (the template for the evaluation).

    Returns
    -------
    Path

    Raises
    ------
    ValueError
        If a cell parameter uses the name of a measurement column (it would pre-fill the template).
    """

    from nanofactorysystem.testprint.field import write_rows

    rows = cell_table(experiment, prefix)
    clashes = sorted({key for row in rows for key in MEASUREMENT_COLUMNS if key in row})
    if clashes:
        raise ValueError(f"Cell parameters {clashes} use the names of measurement columns; rename them in the "
                         f"field builder.")
    return write_rows(path, rows, MEASUREMENT_COLUMNS)


def _number(value) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def import_voxel_measurements(path: PathLike, database, *, fields=VOXEL_FIELDS, source: str = "") -> int:
    """ Write the filled rows of F0, F1 and F2 of a cell-table CSV into the voxel database.

    A row is imported if it belongs to ``fields`` and has a width or a height. ``method`` (e.g.
    ``"SEM"``, ``"DHM"``) is required in every imported row.

    Parameters
    ----------
    path : path-like
        Filled CSV written by :func:`export_cell_table`.
    database : VoxelDatabase
        Target database.
    fields : sequence of int
        Field ids whose sizes are voxel sizes (default F0, F1, F2).
    source : str
        Origin stored with every measurement (default: the CSV file name).

    Returns
    -------
    int
        Number of imported measurements.

    Raises
    ------
    ValueError
        For a filled row without ``method`` or without power.
    """

    imported = 0
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):
            if int(row.get("field_id") or -1) not in fields:
                continue
            width, height = _number(row.get("width_um")), _number(row.get("height_um"))
            if width is None and height is None:
                continue
            method = (row.get("method") or "").strip()
            power = _number(row.get("power_mw"))
            if not method or power is None:
                raise ValueError(f"{path}, line {number}: a measured row needs 'method' and 'power_mw'.")
            n_lines = int(float(row["n_lines"])) if (row.get("n_lines") or "").strip() else 1
            database.add_measurement(row["material"], row["objective"], row["setup"], power,
                                     float(row["velocity_um_s"]), width_um=width, height_um=height,
                                     width_std_um=_number(row.get("width_std_um")),
                                     height_std_um=_number(row.get("height_std_um")), n_lines=n_lines,
                                     method=method, experiment_uuid=row.get("experiment_uuid", ""),
                                     notes=f"{row.get('cell_id', '')} {row.get('notes', '')}".strip(),
                                     source=source or Path(path).name)
            imported += 1
    return imported


def save_cell_table(experiment: Union[PathLike, ExperimentFile], prefix: str = "ptd01.", *,
                    wait_s: float = 0.0) -> str:
    """ Store the cell table in the experiment file (``/analysis/experiment/ptd01_cell_table``).

    Returns
    -------
    str
        HDF5 path of the result.

    Raises
    ------
    ExperimentBusyError
        While an experiment process holds the file (after ``wait_s``).
    """

    exp = _experiment(experiment)
    rows = cell_table(exp, prefix)
    return exp.save_result("ptd01_cell_table", json.dumps(rows), attrs={"n_cells": len(rows), "prefix": prefix},
                           wait_s=wait_s)
