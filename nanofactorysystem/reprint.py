""" Print missing layers of a stored structure again (interim solution of T125).

In the DOE print of 2026-11-21 the controller refused to load 57 of 73 layer
programs (more than about 80 000 lines, see ``aerobasic.programs.split``), and
the experiment went on with the next layer. :meth:`Experiment.reprint_layers`
prints such layers afterwards from the layer programs stored in the
experiment file, splitting too long programs into parts. This module selects
the layers and shows the plan without hardware (``mains/reprint_layers.py``).

The stored layer programs hold absolute stage coordinates (the plane fit of
the original session). Reprinting them is only meaningful while the sample is
still mounted as it was.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from nanofactorysystem.aerobasic.programs.split import MAX_PROGRAM_LINES, count_lines
from nanofactorysystem.storage import ExperimentRecord, ExperimentStore, StructureRecord

__all__ = ["ReprintLayer", "format_plan", "layer_id_of", "missing_layers", "reprint_plan", "select_layers"]


def layer_id_of(file) -> int:
    """ Layer id from a layer program file name ``program_<name>.<iii>.txt``. """

    return int(str(file).split(".")[-2])


def _structure(record: ExperimentRecord, name: str) -> StructureRecord:
    structure = next((s for s in record.structures if s.name == name), None)
    if structure is None:
        names = ", ".join(s.name for s in record.structures)
        raise ValueError(f"No structure '{name}' in the experiment (structures: {names}).")
    return structure


def _printed(record: ExperimentRecord, name: str) -> set[int]:
    return {int(e["layer_id"]) for e in record.progress.get(name, []) if e.get("status") == "ok"}


def missing_layers(record: ExperimentRecord, name: str) -> list[int]:
    """ Layer ids of a structure that were never printed successfully, ascending.

    Parameters
    ----------
    record : ExperimentRecord
    name : str
        Structure name.

    Returns
    -------
    list of int

    Raises
    ------
    ValueError
        If the experiment has no structure ``name``.
    """

    printed = _printed(record, name)
    return sorted(i for i in map(layer_id_of, _structure(record, name).layer_files) if i not in printed)


def select_layers(record: ExperimentRecord, name: str, layer_ids: Optional[Iterable[int]] = None) -> list[int]:
    """ Check and return the layers to reprint, ascending.

    Parameters
    ----------
    record : ExperimentRecord
    name : str
        Structure name.
    layer_ids : iterable of int, optional
        Layers to print; default: every layer without a successful print
        (:func:`missing_layers`).

    Returns
    -------
    list of int

    Raises
    ------
    ValueError
        If the structure is unknown, a layer does not exist, or a layer was
        already printed (it would be exposed twice).
    """

    if layer_ids is None:
        return missing_layers(record, name)
    existing = set(map(layer_id_of, _structure(record, name).layer_files))
    ids = sorted({int(i) for i in layer_ids})
    unknown = [i for i in ids if i not in existing]
    if unknown:
        raise ValueError(f"Structure '{name}' has no layers {unknown} (layers {min(existing)}-{max(existing)}).")
    again = sorted(set(ids) & _printed(record, name))
    if again:
        raise ValueError(f"Layers {again} of '{name}' were already printed and would be exposed twice.")
    return ids


@dataclass
class ReprintLayer:
    """ One layer of a reprint plan.

    Attributes
    ----------
    layer_id : int
    file : Path
        Layer program.
    n_lines : int
        Number of program lines.
    n_parts : int
        Approximate number of parts the layer is printed in.
    last_status : str
        Last recorded status of the layer ("failed", or "" if never attempted).
    error : str
        Last recorded error.
    """

    layer_id: int
    file: Path
    n_lines: int
    n_parts: int
    last_status: str
    error: str


def reprint_plan(path: Path | str, name: str, layer_ids: Optional[Iterable[int]] = None,
                 max_lines: Optional[int] = MAX_PROGRAM_LINES) -> list[ReprintLayer]:
    """ The layers a reprint would print, in print order, read from the experiment file only.

    Parameters
    ----------
    path : str or Path
        Experiment folder.
    name : str
        Structure name.
    layer_ids : iterable of int, optional
        See :func:`select_layers`.
    max_lines : int or None
        Maximum number of lines per program (None: never split).

    Returns
    -------
    list of ReprintLayer
    """

    path = Path(path)
    record = ExperimentStore.open(path).read(include_captures=False)
    structure = _structure(record, name)
    files = {layer_id_of(f): path / f for f in structure.layer_files}
    last = {}
    for event in record.progress.get(name, []):
        last[int(event["layer_id"])] = event
    rows = []
    ids = select_layers(record, name, layer_ids)
    for layer_id in (ids if structure.layer_order >= 0 else ids[::-1]):
        n_lines = count_lines(files[layer_id])
        # Each part repeats the header (about 50 lines for IFOV layers)
        n_parts = 1 if max_lines is None or n_lines <= max_lines else math.ceil(n_lines / (max_lines - 60))
        event = last.get(layer_id, {})
        rows.append(ReprintLayer(layer_id, files[layer_id], n_lines, n_parts, event.get("status", ""),
                                 event.get("error", "")))
    return rows


def format_plan(rows: list[ReprintLayer], name: str) -> str:
    """ The reprint plan as text table.

    Parameters
    ----------
    rows : list of ReprintLayer
    name : str
        Structure name.

    Returns
    -------
    str
    """

    if not rows:
        return f"Structure '{name}': no layers to print."
    lines = [f"Structure '{name}': {len(rows)} layers to print in this order "
             f"({sum(r.n_parts for r in rows)} programs in total, about):",
             f"{'layer':>5}  {'lines':>9}  {'parts':>5}  last status / error"]
    for r in rows:
        error = r.error.replace("\n", " ")
        lines.append(f"{r.layer_id:>5}  {r.n_lines:>9}  {r.n_parts:>5}  {r.last_status or 'not attempted'}"
                     f"{' / ' + error[:80] if error else ''}")
    return "\n".join(lines)
