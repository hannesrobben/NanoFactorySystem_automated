##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Unpack an experiment file into a folder of common file formats.

The folder mirrors the HDF5 tree (one folder per group, see
:mod:`experiment_analysis.convert` for the file formats) and adds overview
files at the top::

    <target>/
      README.txt                  what is where, source file, time of unpacking
      experiment_info.json        identification, status, counts
      summary.txt                 summary table as in the console log
      experiment_dictionary.json  the JSON copies of the experiment folder
      structures.json
      print_progress.json
      experiment_summary.json
      tables/                     CSV tables: summary, structures, captures, progress, sessions
      metadata/ calibration/ plane_fit/ layout/ structures/ logs/ overview/ analysis/ …
                                  the mirrored HDF5 groups

Captures are in ``structures/<name>/captures/<id>/`` (``image.png`` or
``holograms/``); ``tables/captures.csv`` lists them with structure, phase,
layer and stage position.
"""
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Union

import h5py
import numpy as np

from .access import ExperimentFile, PathLike, lock_holder, resolve_file
from .convert import ConvertOptions, plain, write_json, write_records_csv, write_tree

log = logging.getLogger(__name__)

README = """\
Unpacked experiment
===================

Source file : {source}
Unpacked    : {time} (UTC)
Experiment  : {label}  (UUID {uuid})
Substrate   : {substrate}
Status      : {status}
Snapshot    : {snapshot}

Top level
---------
summary.txt                  summary of all user structures (text table)
experiment_info.json         identification, status and counts
experiment_dictionary.json   experiment parameters, plane fit, layout, calibration
structures.json              all structures with their configuration
print_progress.json          print progress per structure and layer
experiment_summary.json      summary (same content as summary.txt)
tables/*.csv                 tables for Excel ({csv})

Mirrored file content (one folder per HDF5 group)
-------------------------------------------------
attributes.json              attributes of the group
<name>.attributes.json       attributes of a dataset
*.txt                        texts (layer programs, logs) and single numbers
*.csv                        number arrays and tables ({csv})
*.png                        images (8 or 16 bit, lossless); *_preview.png: scaled preview of a number array
<name>/<name>_000.png        image stacks (e.g. DHM holograms), one file per image
*.zdc                        SciDataContainer files (plane fit; captures with zdc=True), open with 7-Zip
                             or rename to .zip
*.npy                        arrays without a better format (NumPy)

Important folders
-----------------
metadata/                    experiment parameters, user, objective, system, software, sessions
plane_fit/                   plane function, sample and interface points, container files
layout/plot.png              plot of the experiment layout
structures/<name>/programs/  AeroBasic layer programs (layer_000.txt, …)
structures/<name>/progress/  one folder per printed layer (status, times)
structures/<name>/captures/  camera images (image.png) and DHM holograms (holograms/), per capture id
overview/<phase>/image.png   stitched camera overview before/after printing
logs/console, logs/a3200     console log and controller command log per session
analysis/                    results stored by analysis scripts
"""


def _captures_table(record) -> list[dict]:
    rows = []
    for c in record.captures:
        actual = {f"actual_{axis.lower()}_um": c.actual_um.get(axis) for axis in "XYZAB"}
        commanded = dict(zip(("commanded_x_um", "commanded_y_um", "commanded_z_um"), c.commanded_um))
        rows.append({"capture_id": c.capture_id, "structure": c.structure, "kind": c.kind, "phase": c.phase,
                     "layer_id": c.layer_id, "image_index": c.image_index, "image_count": c.image_count,
                     "offset_x_um": c.offset_um[0], "offset_y_um": c.offset_um[1], **commanded, **actual,
                     "time": c.time,
                     "folder": f"structures/{c.structure}/captures/{c.capture_id}"})
    return rows


def _structures_table(record) -> list[dict]:
    rows = []
    for s in record.structures:
        rows.append({"index": s.index, "name": s.name, "type": s.type, "status": s.status,
                     "grid_index": s.grid_index, "corner_position": s.corner_position, "axes": s.axes,
                     "setup": s.setup, "x_um": s.center_um[0], "y_um": s.center_um[1], "z_um": s.center_um[2],
                     "power_mw": s.power_mw, "n_layers": s.n_layers, "layer_order": s.layer_order,
                     "dhm_image_count": s.dhm_image_count, "repeat_of": s.repeat_of, "started": s.started,
                     "ended": s.ended, "class": s.structure_class})
    return rows


def _progress_table(record) -> list[dict]:
    return [{"structure": name, **event} for name, events in record.progress.items() for event in events]


def _write_overview_files(file: ExperimentFile, target: Path, options: ConvertOptions, zdc: bool) -> dict:
    """ Write the summary, the JSON copies and the tables; returns counts for ``experiment_info.json``. """

    from nanofactorysystem.storage.json_copies import experiment_dictionary, print_progress, structures_list
    from nanofactorysystem.storage.summary import format_table, summary

    record = file.record()
    data = summary(record)
    (target / "summary.txt").write_text(format_table(data) + "\n", encoding="utf-8")
    write_json(target / "experiment_summary.json", data)
    write_json(target / "experiment_dictionary.json", experiment_dictionary(record, file.folder))
    write_json(target / "structures.json", structures_list(record))
    write_json(target / "print_progress.json", print_progress(record))
    tables = target / "tables"
    tables.mkdir(exist_ok=True)
    for name, rows in (("summary", data["structures"]), ("structures", _structures_table(record)),
                       ("captures", _captures_table(record)), ("progress", _progress_table(record)),
                       ("sessions", record.sessions)):
        if rows:
            write_records_csv(tables / f"{name}.csv", rows, options)
    if zdc:
        for capture in record.captures:
            folder = target / "structures" / capture.structure / "captures" / capture.capture_id
            folder.mkdir(parents=True, exist_ok=True)
            try:
                file.store.export_capture(capture.capture_id, folder / "capture.zdc")
            except Exception as error:  # keep unpacking; the PNG files are written anyway
                log.warning(f"Capture {capture.capture_id} not exported as .zdc: {error}")
    return {"structures": len(record.structures), "captures": len(record.captures),
            "camera_captures": sum(c.kind == "camera" for c in record.captures),
            "dhm_captures": sum(c.kind == "dhm" for c in record.captures),
            "printed_layers": sum(e.get("status") == "ok" for events in record.progress.values() for e in events),
            "sessions": len(record.sessions)}


def _snapshot(source: Path, folder: Path, attempts: int = 10) -> Path:
    """ Copy the file of a running experiment and check that the copy can be opened. """

    import time
    copy = folder / source.name
    for attempt in range(attempts):
        shutil.copy2(source, copy)
        try:
            with h5py.File(copy, "r", locking=False) as f:
                f.visit(lambda name: None)
            return copy
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5)
    return copy


def unpack_experiment(source: PathLike, target: PathLike, *, overwrite: bool = False, archive: bool = False,
                      zdc: bool = False, csv_style: str = "de", previews: bool = True,
                      snapshot: Optional[bool] = None) -> Path:
    """ Unpack an experiment file into common file formats.

    Parameters
    ----------
    source : str or Path
        ``experiment.h5`` or the experiment folder.
    target : str or Path
        Output folder. It is created; an existing non-empty folder is refused
        unless ``overwrite`` is True.
    overwrite : bool
        Delete the content of an existing output folder first.
    archive : bool
        Also write ``<target>.zip`` of the output folder.
    zdc : bool
        Also export every capture as SciDataContainer file ``capture.zdc``
        (as written before the experiment file existed; slower).
    csv_style : {"de", "en"}
        ``"de"``: ``;`` and decimal comma (German Excel), ``"en"``: ``,`` and
        decimal point.
    previews : bool
        Write scaled ``_preview.png`` images of large number arrays.
    snapshot : bool, optional
        Unpack a copy of the file instead of the file itself. None (default):
        only while an experiment process holds the file, so that the output
        is consistent and the printing process is never disturbed.

    Returns
    -------
    Path
        The output folder, or the ``.zip`` file with ``archive=True``.

    Raises
    ------
    FileExistsError
        If the output folder is not empty and ``overwrite`` is False.
    """

    from nanofactorysystem.storage import utc_timestamp

    source = resolve_file(source)
    target = Path(target)
    if target.resolve() in source.resolve().parents:
        # overwrite would delete the experiment itself
        raise ValueError(f"The output folder must not contain the experiment file: {target}")
    if target.exists() and any(target.iterdir()):
        if not overwrite:
            raise FileExistsError(f"Output folder is not empty: {target} (pass overwrite=True)")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    options = ConvertOptions(csv_style=csv_style, previews=previews)
    busy = lock_holder(source)
    use_snapshot = busy is not None if snapshot is None else snapshot

    with tempfile.TemporaryDirectory(prefix="nanofactory_unpack_") as tmp:
        if use_snapshot:
            log.info(f"Unpacking a snapshot of {source}" + (" (experiment is running)" if busy else ""))
            file = ExperimentFile(_snapshot(source, Path(tmp)))
        else:
            file = ExperimentFile(source)
        info = file.info()
        files = file._retry(lambda f: write_tree(f, target, options))
        counts = _write_overview_files(file, target, options, zdc)

    info.update(path=str(source), busy=busy is not None, snapshot=use_snapshot, unpacked=utc_timestamp(),
                csv_style=csv_style, counts=counts, files=len(files))
    write_json(target / "experiment_info.json", info)
    (target / "README.txt").write_text(README.format(
        source=source, time=info["unpacked"], label=info.get("experiment_label") or "-",
        uuid=info.get("experiment_uuid") or "-", substrate=info.get("substrate_label") or "-",
        status=info.get("status") or "-",
        snapshot="yes, copy of a running experiment" if busy else ("yes" if use_snapshot else "no"),
        csv="separator ';', decimal comma" if csv_style == "de" else "separator ',', decimal point"),
        encoding="utf-8")
    npy = [p for p in files if p.suffix == ".npy"]
    if npy:
        log.warning(f"{len(npy)} arrays written as .npy (no common format), e.g. {npy[0]}")
    if archive:
        return Path(shutil.make_archive(str(target), "zip", root_dir=target))
    return target
