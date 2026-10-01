##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Experiment summary: what was printed with which parameters (design §10, T49)."""
from typing import Any, Optional

from .records import ExperimentRecord, StructureRecord

SUMMARY_NAME = "experiment_summary.json"

# Structure types that are markers of the experiment, not user structures
MARKER_TYPES = ("CORNER", "QRCODE")

# Constructor arguments of the drawing classes that hold slice, hatch, velocity and power
SLICE_KEYS = ("slice_size", "slice_size_opt", "layer_height")
HATCH_KEYS = ("hatch_size", "hatch_distance", "hatch_dist", "hatch_size_opt")
VELOCITY_KEYS = ("velocity", "scan_speed_um_s", "horizontal_velocity", "F")
POWER_KEYS = ("power", "power_val")

COLUMNS = ("name", "type", "x_um", "y_um", "slice_um", "hatch_um", "power_mw", "layer_power_mw", "velocity",
           "velocity_unit",
           "voxel_width_um", "voxel_height_um", "ifov", "dhm", "camera", "n_layers", "printed_layers", "status")


def _first_number(arguments: dict, keys) -> Optional[float]:
    for key in keys:
        value = arguments.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _power_range(powers: list[float]) -> Optional[str]:
    """ ``"<min>-<max>"`` of the layer powers (or the single value), None without power per layer. """

    if not powers:
        return None
    low, high = min(powers), max(powers)
    return f"{low:g}" if low == high else f"{low:g}-{high:g}"


def print_parameters(structure: StructureRecord) -> dict[str, Any]:
    """ Return slice, hatch, velocity and power of a structure from its constructor arguments.

    The drawing classes name these parameters differently (``slice_size``,
    ``hatch_size``/``hatch_distance``, ``velocity``/``F``/``scan_speed_um_s``,
    …); the first known name wins, missing values are None.

    Parameters
    ----------
    structure : StructureRecord

    Returns
    -------
    dict
        ``slice_um``, ``hatch_um``, ``velocity``, ``velocity_unit``,
        ``power_mw``, ``voxel_width_um`` and ``voxel_height_um``. Slicer
        structures (``Model3D_Slicer``) report the slice and hatch size they
        were sliced with (after voxel compensation, T54) and the voxel size
        used (None without voxel data). The velocity is given as passed to
        the structure; ``velocity_unit`` is ``"mm/s"`` for IFOV structures
        (``IFOV_Lines`` and the structures built on it) and ``"um/s"``
        otherwise; for ``Model3D_Slicer`` values below 500 are mm/s (its IFOV
        convention). The power
        is the power the structure itself sets (IFOV structures), else the
        power set for the structure before printing (design decision D5).
    """

    config = structure.config if isinstance(structure.config, dict) else {}
    arguments = config.get("__init__", {})
    slicing = (config.get("params") or {}).get("slicing") or {}
    voxel = config.get("voxel") or {}
    if slicing:  # Model3D_Slicer: own JSON format with the job parameters
        arguments = {"slice_size": slicing.get("layer_height_um"), "hatch_size": slicing.get("hatch_spacing_um"),
                     "velocity": config.get("velocity"), "power": config.get("power")}
    own_power = _first_number(arguments, POWER_KEYS)
    velocity = _first_number(arguments, VELOCITY_KEYS)
    ifov_class = "IFOV" in structure.structure_class.rsplit(".", 1)[-1].upper()
    if slicing:  # IFOV convention of Model3D_Slicer: 500–25000 in um/s, smaller values in mm/s
        ifov_class = velocity is not None and velocity < 500
    return {
        "voxel_width_um": _first_number(voxel, ("width_um",)),
        "voxel_height_um": _first_number(voxel, ("height_um",)),
        "slice_um": _first_number(arguments, SLICE_KEYS),
        "hatch_um": _first_number(arguments, HATCH_KEYS),
        "velocity": velocity,
        "velocity_unit": "mm/s" if ifov_class else "um/s",
        "power_mw": own_power if own_power is not None else structure.power_mw,
    }


def summary(record: ExperimentRecord) -> dict[str, Any]:
    """ Return the summary of an experiment.

    Parameters
    ----------
    record : ExperimentRecord

    Returns
    -------
    dict
        Experiment fields (``experiment_uuid``, ``experiment_label``,
        ``substrate_label``, ``objective``, ``setup``, ``drop_direction``,
        ``plane_fit_mode``, ``program_source``, ``dhm_usage``, ``camera_capture``, ``started``,
        ``status``) and ``structures``, one row per user structure (corners
        and QR code excluded) with the keys in :data:`COLUMNS`.
    """

    parameters = record.parameters
    dhm = bool(parameters.get("dhm_usage", False))
    camera = bool(parameters.get("camera_capture", True))  # files before T45 always took camera images
    rows = []
    for structure in record.structures:
        if structure.type in MARKER_TYPES:
            continue
        printed = sum(1 for event in record.progress.get(structure.name, []) if event.get("status") == "ok")
        rows.append({
            "name": structure.name,
            "type": structure.type,
            "x_um": structure.center_um[0],
            "y_um": structure.center_um[1],
            **print_parameters(structure),
            "layer_power_mw": _power_range(structure.layer_powers_mw),
            "ifov": structure.setup == "IFOV_on",
            "dhm": dhm,
            "camera": camera,
            "n_layers": structure.n_layers,
            "printed_layers": printed,
            "status": structure.status,
        })
    return {
        "experiment_uuid": record.uuid,
        "experiment_label": record.label,
        "substrate_label": record.substrate_label,
        "objective": record.objective.get("key", ""),
        "setup": parameters.get("setup", ""),
        "drop_direction": parameters.get("drop_direction", ""),
        "plane_fit_mode": parameters.get("plane_fit_mode"),
        "program_source": parameters.get("program_source", "DRAWING"),
        "dhm_usage": dhm,
        "camera_capture": camera,
        "started": record.created,
        "status": record.status,
        "structures": [{column: row[column] for column in COLUMNS} for row in rows],
    }


def format_table(data: dict[str, Any]) -> str:
    """ Format a summary as fixed-width text table for the log.

    Parameters
    ----------
    data : dict
        Result of :func:`summary`.

    Returns
    -------
    str
        A header line with the experiment and one line per structure.
    """

    def text(value) -> str:
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, float):
            return f"{value:g}"
        return str(value)

    header = (f"Experiment {data['experiment_uuid']} {data['experiment_label']} ({data['objective']}, "
              f"{data['setup']}, drop {data['drop_direction']}, status {data['status']})")
    rows = [[text(row[column]) for column in COLUMNS] for row in data["structures"]]
    widths = [max([len(column)] + [len(row[i]) for row in rows]) for i, column in enumerate(COLUMNS)]
    lines = [header, "  ".join(column.ljust(w) for column, w in zip(COLUMNS, widths))]
    lines += ["  ".join(value.ljust(w) for value, w in zip(row, widths)) for row in rows]
    if not rows:
        lines.append("(no user structures)")
    return "\n".join(lines)
