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

__all__ = ["MEASUREMENT_COLUMNS", "VOXEL_FIELDS", "PREFIXES", "ptd_structures", "cell_table", "export_cell_table",
           "import_voxel_measurements", "save_cell_table", "add_relative_columns", "voxel_lengths_from_gaps"]

PathLike = Union[str, Path]

# Columns filled during the evaluation (empty in the exported template)
MEASUREMENT_COLUMNS = ("width_um", "height_um", "width_std_um", "height_std_um", "n_lines", "present", "merged",
                       "collapsed", "method", "notes")
# Fields whose measured widths / heights are voxel sizes (design §7)
VOXEL_FIELDS = (0, 1, 2)
# Factory name prefixes of the test prints: PTD-01 version 1 and the parameter tests of version 2
PREFIXES = ("ptd01.", "quick_pt.", "full_pt01.", "voxel_pt01.")
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


def ptd_structures(experiment: Union[PathLike, ExperimentFile], prefix=PREFIXES) -> list[dict[str, Any]]:
    """ The PTD fields of an experiment: factory name, builder arguments and every printed copy.

    Parameters
    ----------
    experiment : path or ExperimentFile
        ``experiment.h5`` or its folder.
    prefix : str or tuple of str
        Factory name prefix(es) of the test prints (default: PTD-01 and the parameter tests).

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
        prefixes = (prefix,) if isinstance(prefix, str) else tuple(prefix)
        if geometry.get("kind") != "factory" or not str(geometry.get("name", "")).startswith(prefixes):
            continue
        arguments = {k: decode_json_value(v) for k, v in geometry.get("arguments", {}).items()
                     if k not in _STRUCTURE_ONLY}
        copies = [(s.name, tuple(float(v) for v in s.center_um[:2])) for s in record.structures
                  if s.name == entry["name"] or s.repeat_of == entry["name"]]
        found.append({"name": entry["name"], "factory": geometry["name"], "arguments": arguments, "copies": copies})
    return found


def cell_table(experiment: Union[PathLike, ExperimentFile], prefix=PREFIXES) -> list[dict[str, Any]]:
    """ The cell table of every PTD field of an experiment, regenerated from ``/spec``.

    Parameters
    ----------
    experiment : path or ExperimentFile
    prefix : str or tuple of str
        Factory name prefix(es) (default :data:`PREFIXES`).

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
        source = (item["arguments"].get("inputs") or item["arguments"].get("calibration")
                  or item["arguments"].get("stage_a") or {})
        material = source.get("material", "")
        for structure, (x0, y0) in item["copies"]:
            for cell in field.cell_table():
                rows.append({"experiment_uuid": record.uuid, "experiment_label": record.label,
                             "structure": structure, "material": material, "objective": objective, "setup": setup,
                             "velocity_um_s": velocity, "stage_x_um": round(x0 + cell["x_um"], 3),
                             "stage_y_um": round(y0 + cell["y_um"], 3), **cell})
    return rows


def export_cell_table(experiment: Union[PathLike, ExperimentFile], path: PathLike,
                      prefix=PREFIXES) -> Path:
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


def save_cell_table(experiment: Union[PathLike, ExperimentFile], prefix=PREFIXES, *,
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
    return exp.save_result("ptd01_cell_table", json.dumps(rows), attrs={"n_cells": len(rows), "prefix": json.dumps(prefix)},
                           wait_s=wait_s)


# ----------------------------------------------------------------------------------------------
# Parameter tests version 2: relative columns and voxel length from the gap test (T163)
# ----------------------------------------------------------------------------------------------
def add_relative_columns(rows: list[dict[str, Any]], *, p_th_mw: float, voxel_model=None) -> list[dict[str, Any]]:
    """ Copies of the cell-table rows with the relative columns of the evaluation.

    The parameter tests print on absolute axes; once the threshold and the voxel size are measured (Quick PT,
    Voxel PT-01, fit), this adds ``p_rel = power / P_th`` and, with a voxel model whose validity range holds the
    cell power, ``h_rel = hatch / w(P)``, ``s_rel = spacing / w(P)`` and ``dz_rel = slice / l(P)``.

    Parameters
    ----------
    rows : list of dict
        Cell-table rows (:func:`cell_table` or a filled CSV read as dicts).
    p_th_mw : float
        Measured polymerisation threshold.
    voxel_model : VoxelFitModel, optional
        Fitted model w(P), l(P); outside its range the columns stay empty (no extrapolation).

    Returns
    -------
    list of dict

    Raises
    ------
    ValueError
        For a non-positive threshold.
    """

    if p_th_mw is None or float(p_th_mw) <= 0:
        raise ValueError(f"p_th_mw must be > 0, got {p_th_mw}")
    result = []
    for row in rows:
        new = dict(row)
        power = _number(row.get("power_mw"))
        if power is not None:
            new["p_rel"] = round(power / float(p_th_mw), 6)
            if voxel_model is not None and voxel_model.contains(power):
                width, length = voxel_model.width_um(power), voxel_model.length_um(power)
                for column, relative, size in (("hatch_um", "h_rel", width), ("spacing_um", "s_rel", width),
                                               ("slice_um", "dz_rel", length)):
                    value = _number(row.get(column))
                    if value is not None and size > 0:
                        new[relative] = round(value / size, 6)
        result.append(new)
    return result


def _present(value) -> Optional[bool]:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip().lower() in ("1", "true", "yes", "y", "x")


def voxel_lengths_from_gaps(rows: list[dict[str, Any]], *, base_power_mw: Optional[float] = None) -> list[dict]:
    """ Voxel length l(P) from the filled Voxel PT-01 rows (gap test).

    Per lid power the largest gap with the lid still present and the smallest larger gap without lid bracket
    the bridgeable gap ``g_max`` (midpoint, uncertainty half the step). The lid attaches while lid voxel and base
    top overlap, ``g_max ≈ (l(P) + l_base) / 2``; the experiment whose lid power equals the base power gives
    ``l_base = g_max``, every other power ``l(P) = 2 · g_max - l_base``.

    Parameters
    ----------
    rows : list of dict
        Rows with ``power_mw``, ``gap_um``, ``present`` (1/0, true/false) and ``base_power_mw``; rows without a
        ``present`` value are ignored.
    base_power_mw : float, optional
        Power of the bases (default: the ``base_power_mw`` column).

    Returns
    -------
    list of dict
        Per power: ``power_mw``, ``g_attached_um``, ``g_missing_um``, ``g_max_um``, ``length_um``,
        ``length_unc_um`` (None where the bracket is open).

    Raises
    ------
    ValueError
        Without rows with a ``present`` value, or without the experiment at the base power.
    """

    by_power: dict[float, list[tuple[float, bool]]] = {}
    bases = set()
    for row in rows:
        present = _present(row.get("present"))
        if present is None or row.get("gap_um") in (None, ""):
            continue
        by_power.setdefault(round(float(row["power_mw"]), 6), []).append((float(row["gap_um"]), present))
        if row.get("base_power_mw") not in (None, ""):
            bases.add(round(float(row["base_power_mw"]), 6))
    if not by_power:
        raise ValueError("No gap-test rows with a 'present' value.")
    if base_power_mw is not None:
        base = round(float(base_power_mw), 6)
    else:
        base = bases.pop() if len(bases) == 1 else None
    brackets = {}
    for power, cells in sorted(by_power.items()):
        cells.sort()
        attached = [g for g, present in cells if present]
        g_attached = max(attached) if attached else None
        missing = [g for g, present in cells if not present and (g_attached is None or g > g_attached)]
        g_missing = min(missing) if missing else None
        if g_attached is not None and g_missing is not None:
            g_max, unc = (g_attached + g_missing) / 2, (g_missing - g_attached) / 2
        else:
            g_max, unc = None, None
        brackets[power] = (g_attached, g_missing, g_max, unc)
    if base is None or base not in brackets or brackets[base][2] is None:
        raise ValueError(f"The experiment at the base power ({base} mW) with a closed bracket is needed for l_base.")
    l_base, l_base_unc = brackets[base][2], brackets[base][3]
    result = []
    for power, (g_attached, g_missing, g_max, unc) in brackets.items():
        if g_max is None:
            length = length_unc = None
        elif power == base:
            length, length_unc = l_base, l_base_unc
        else:
            length, length_unc = 2 * g_max - l_base, 2 * unc + l_base_unc
        result.append({"power_mw": power, "g_attached_um": g_attached, "g_missing_um": g_missing, "g_max_um": g_max,
                       "length_um": None if length is None else round(length, 6),
                       "length_unc_um": None if length_unc is None else round(length_unc, 6)})
    return result
