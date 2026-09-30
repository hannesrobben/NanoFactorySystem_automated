##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Human-readable JSON copies of the experiment file (design §7).

The copies are written from an :class:`ExperimentRecord`, i.e. from the data
read back from the experiment file, and keep the keys of the files written
before the store existed, so that older readers keep working.
"""
import json
import os
from pathlib import Path

import numpy as np

from . import schema
from .records import ExperimentRecord

DICTIONARY_NAME = "experiment_dictionary.json"
STRUCTURES_NAME = "structures.json"


def _plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def write_json(path: Path, data) -> None:
    """ Write JSON atomically (temporary file, then replace). """

    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(_plain(data), indent=4))
    os.replace(tmp, path)


def experiment_dictionary(record: ExperimentRecord, folder: Path) -> dict:
    """ Return the content of ``experiment_dictionary.json``.

    The keys of the dictionary written before the store are kept (with
    numbers instead of number strings); identification, software, plane fit,
    layout and calibration are added.

    Parameters
    ----------
    record : ExperimentRecord
    folder : Path
        Experiment folder. ``path`` is stored as ``"."``: all paths in the
        copies are relative to the experiment folder.

    Returns
    -------
    dict
    """

    from ..devices.coordinate_system import DropDirection

    parameters = record.parameters
    data = {
        "path": ".",
        "user": record.user.get("key", ""),
        "objective": record.objective.get("key", ""),
        "logger": parameters.get("log_file") or None,
        "sys_args": record.system.get("sys_args", {}),
    }
    for _, key, name, kind in schema.PARAMETERS:
        value = parameters.get(name)
        if kind == "enum" and name == "drop_direction":
            data[key] = DropDirection[value].value
            data["drop_direction_information"] = value
        else:
            data[key] = value
    data.update({
        "experiment_uuid": record.uuid,
        "experiment_label": record.label,
        "substrate_uuid": record.substrate_uuid,
        "substrate_label": record.substrate_label,
        "substrate": record.substrate,
        "schema_version": record.schema_version,
        "status": record.status,
        "created": record.created,
        "software": record.software,
    })
    if record.plane_fit is not None:
        plane = record.plane_fit
        data["plane_fit"] = {"mode": plane.mode, "source": plane.source, "function": plane.function,
                             "function_parameters": plane.function_json, "interface": plane.interface,
                             "sample_points_um": plane.sample_points_um}
    if record.layout is not None:
        layout = record.layout
        data["layout"] = {
            "experiment_rectangle_um": layout.rectangle_um,
            "corners": [vars(c) for c in layout.corners],
            "double_corner": vars(layout.double_corner) if layout.double_corner is not None else None,
            "qrcode_um": layout.qrcode_um,
        }
    if record.calibration is not None:
        data["calibration"] = {"fit_kind": record.calibration["fit_kind"],
                               "source_file": record.calibration["source_file"],
                               "table": record.calibration["table"]}
    return _plain(data)


def structures_list(record: ExperimentRecord) -> list[dict]:
    """ Return the content of ``structures.json``.

    One entry per structure with the keys of the file written before the
    store (``name``, ``axes``, ``power``, ``center_x/y/z``, ``structure``,
    ``program_file``, ``layer_files``, ``number of dhm images``) plus
    ``experiment_uuid``, ``type``, ``corner_position``, ``status`` and
    ``center_um``.

    Parameters
    ----------
    record : ExperimentRecord

    Returns
    -------
    list of dict
    """

    entries = []
    for s in record.structures:
        entries.append(_plain({
            "name": s.name,
            "axes": s.axes,
            "power": s.power_mw,
            "center_x": s.center_um[0],
            "center_y": s.center_um[1],
            "center_z": s.center_um[2],
            "structure": s.config,
            "program_file": s.program_file,
            "layer_files": s.layer_files,
            "number of dhm images": s.dhm_image_count,
            "experiment_uuid": record.uuid,
            "type": s.type,
            "corner_position": s.corner_position,
            "status": s.status,
            "center_um": s.center_um,
        }))
    return entries


def export_json(record: ExperimentRecord, folder: Path) -> None:
    """ Write ``experiment_dictionary.json`` and, if structures exist, ``structures.json``. """

    folder = Path(folder)
    write_json(folder / DICTIONARY_NAME, experiment_dictionary(record, folder))
    if record.structures:
        write_json(folder / STRUCTURES_NAME, structures_list(record))
