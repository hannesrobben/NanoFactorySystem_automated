##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Plain data records of an experiment (see docs/design/EXPERIMENT_STORAGE.md).

The records hold data only; they know nothing about HDF5 or JSON files.
Positions are absolute stage coordinates in µm unless a name says otherwise.
"""
import datetime
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np


def utc_timestamp() -> str:
    """ Return the current time as ISO 8601 string in UTC with milliseconds.

    Returns
    -------
    str
        E.g. ``"2026-09-29T18:18:49.123Z"``.
    """

    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class CaptureRecord:
    """ Metadata of one camera or DHM capture at one position.

    Parameters
    ----------
    kind : {"camera", "dhm"}
        Device that took the capture.
    structure : str
        Name of the structure the capture belongs to.
    phase : {"before", "layer", "after"}
        Before the structure, after a layer, or after the structure.
    layer_id : int
        Layer after which the capture was taken; -1 for before/after.
    image_index : int
        Index of the capture position within a series of positions.
    image_count : int
        Number of images in the capture (DHM: holograms of a series).
    offset_um : tuple of float
        (x, y) offset of the capture position from the structure center.
    commanded_um : tuple
        (X, Y, Z, A, B) target of the moves before the capture; an axis that
        was not commanded is None (Z is not moved before a capture, the galvo
        axes are set to 0). Records written before T58 have (X, Y, Z) only.
    actual_um : dict
        Positions of the axes X, Y, Z, A, B read from the controller after
        the move.
    time : str
        Start of the capture (ISO 8601, UTC).
    file : str, optional
        File the capture was written to, relative to the experiment folder
        (only for captures stored outside the experiment file).
    capture_id : str, optional
        Id of the capture in the experiment file (``"0000"``, ``"0001"``, …).
    """

    kind: str
    structure: str
    phase: str
    layer_id: int
    image_index: int
    image_count: int
    offset_um: tuple[float, float]
    commanded_um: tuple[Optional[float], ...]
    actual_um: dict[str, float] = field(default_factory=dict)
    time: str = field(default_factory=utc_timestamp)
    file: Optional[str] = None
    capture_id: Optional[str] = None

    def to_dict(self) -> dict:
        """ Return the record as JSON-compatible dictionary. """

        data = asdict(self)
        data["offset_um"] = list(self.offset_um)
        data["commanded_um"] = list(self.commanded_um)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CaptureRecord":
        """ Build a record from the dictionary written by :meth:`to_dict`. """

        data = dict(data)
        data["offset_um"] = tuple(data["offset_um"])
        data["commanded_um"] = tuple(data["commanded_um"])
        return cls(**data)


@dataclass
class StructureRecord:
    """ One structure of an experiment as built and printed.

    Parameters
    ----------
    index : int
        Print order.
    name : str
        Unique structure name.
    type : str
        ``StructureType`` name (``"NORMAL"``, ``"CORNER"``, ``"QRCODE"``, …).
    grid_index : int
        Grid cell of the structure, -1 for corners and the QR code.
    corner_position : str
        ``"TL"``, ``"TR"``, ``"BR"``, ``"BL"`` for corners, else ``""``.
    axes : str
        Printing axes (``"ABZ"`` or ``"XYZ"``).
    setup : str
        IFOV setup of the experiment (``"IFOV_off"`` or ``"IFOV_on"``).
    center_um : tuple of float
        Absolute (X, Y, Z) of the structure center.
    reference_um : tuple of float
        (X, Y) grid point before the structure's own center offset.
    power_mw : float
        Laser power set for the structure.
    structure_class : str
        Module-qualified class name of the ``DrawableObject``.
    config : dict
        ``DrawableObject.to_json()``.
    layer_files : list of str
        Layer program files, relative to the experiment folder if inside it.
    program_file : str
        Whole-structure program file.
    layer_order : int
        +1 (ascending layer ids) or -1 (descending), from the drop direction.
    dhm_image_count : int
        Holograms per DHM capture.
    status : str
        ``"pending"``, ``"printing"``, ``"printed"`` or ``"failed"``.
    repeat_of : str
        Name of the repeated structure for ``REPEAT`` structures, else ``""``.
    started, ended : str
        When printing of the structure started and ended (ISO 8601, UTC), or ``""``.
    layer_powers_mw : list of float
        Laser power of each layer if the structure sets it per layer (T31),
        else empty.
    """

    index: int
    name: str
    type: str
    grid_index: int
    corner_position: str
    axes: str
    setup: str
    center_um: tuple[float, float, float]
    reference_um: tuple[float, float]
    power_mw: float
    structure_class: str
    config: dict
    layer_files: list[str]
    program_file: str
    layer_order: int
    dhm_image_count: int
    status: str = "pending"
    repeat_of: str = ""
    started: str = ""
    ended: str = ""
    layer_powers_mw: list[float] = field(default_factory=list)

    @property
    def n_layers(self) -> int:
        """ Number of layers. """

        return len(self.layer_files)


@dataclass
class PlaneFitRecord:
    """ Substrate surface used for an experiment.

    Parameters
    ----------
    mode : str
        Plane-fit mode (the integer mode as string until T44 names them).
    source : {"measured", "loaded", "given"}
        Measured now, loaded from an earlier measurement, or passed in.
    function : str
        Class name of the z function (``"PlaneFit"``, ``"Plane"``, …).
    function_json : dict
        Parameters of the z function (see :func:`z_function_to_json`).
    interface : str
        Interface used for the drop direction (``"low"``/``"high"``), or ``""``.
    sample_points_um : ndarray
        N×2 points planned for the measurement.
    interface_points_um : ndarray
        M×3 points the fit used (empty if the plane was given).
    time : str
        When the plane was determined or passed in.
    """

    mode: str
    source: str
    function: str
    function_json: dict
    interface: str
    sample_points_um: np.ndarray
    interface_points_um: np.ndarray
    time: str = field(default_factory=utc_timestamp)


@dataclass
class CornerRecord:
    """ One corner marker of the experiment rectangle.

    Parameters
    ----------
    name, position : str
        Structure name and ``"TL"``/``"TR"``/``"BR"``/``"BL"``.
    reference_um : tuple of float
        Grid corner (X, Y) the corner structure is placed at.
    center_um : tuple of float
        (X, Y) of the corner geometry (reference plus the structure's center offset).
    rotation_deg : float
        Rotation of the corner structure.
    double : bool
        True for the marked (double) corner that shows the orientation.
    """

    name: str
    position: str
    reference_um: tuple[float, float]
    center_um: tuple[float, float]
    rotation_deg: float
    double: bool


@dataclass
class LayoutRecord:
    """ Geometry of the experiment as printed.

    Parameters
    ----------
    rectangle_um : ndarray
        4×2 corners TL, TR, BR, BL of the experiment rectangle.
    grid_positions_um : ndarray
        (rows·cols)×2 grid cell centers in print order.
    corners : list of CornerRecord
        Corner markers (empty with ``skip_corner``).
    qrcode_um : tuple of float, optional
        (X, Y) of the QR code, None without QR code.
    qrcode_text : str
        Text of the QR code (the experiment UUID).
    """

    rectangle_um: np.ndarray
    grid_positions_um: np.ndarray
    corners: list[CornerRecord] = field(default_factory=list)
    qrcode_um: Optional[tuple[float, float]] = None
    qrcode_text: str = ""

    @property
    def double_corner(self) -> Optional[CornerRecord]:
        """ The marked corner, or None. """

        return next((c for c in self.corners if c.double), None)


@dataclass
class ExperimentRecord:
    """ Everything stored about an experiment except bulk image data.

    Parameters
    ----------
    uuid : str
        Experiment UUID (= QR-code text).
    parameters : dict
        ``Experiment`` constructor parameters in the file's typed form
        (see ``schema.PARAMETERS``).
    user, objective, system, software, substrate : dict
        Contents of the corresponding ``/metadata`` groups (``substrate``:
        copy of the substrate record at the start, and ``information``, the
        free substrate information of older scripts).
    label, substrate_uuid, substrate_label : str
        Identification (empty until substrates are used, T48).
    created, updated, status, schema_version : str
        File attributes.
    sessions : list of dict
        One entry per process that wrote the file.
    calibration : dict, optional
        ``{"table": N×2 array, "fit_kind": str, "source_file": str}``.
    plane_fit : PlaneFitRecord, optional
    opl_scan : dict, optional
        ``{"motor_pos_um": float, "source": str, "time": str}``.
    layout : LayoutRecord, optional
    structures : list of StructureRecord
    progress : dict
        Layer events per structure name (list of dicts).
    captures : list of CaptureRecord
    time_estimate : dict, optional
        Expected printing time (``time_estimate.TimeEstimate.to_dict()``).
    """

    uuid: str
    parameters: dict[str, Any]
    user: dict = field(default_factory=dict)
    objective: dict = field(default_factory=dict)
    system: dict = field(default_factory=dict)
    software: dict = field(default_factory=dict)
    substrate: dict = field(default_factory=dict)
    label: str = ""
    substrate_uuid: str = ""
    substrate_label: str = ""
    created: str = ""
    updated: str = ""
    status: str = ""
    schema_version: str = ""
    sessions: list[dict] = field(default_factory=list)
    calibration: Optional[dict] = None
    plane_fit: Optional[PlaneFitRecord] = None
    opl_scan: Optional[dict] = None
    layout: Optional[LayoutRecord] = None
    structures: list[StructureRecord] = field(default_factory=list)
    progress: dict[str, list[dict]] = field(default_factory=dict)
    captures: list[CaptureRecord] = field(default_factory=list)
    time_estimate: Optional[dict] = None

    def structure(self, name: str) -> StructureRecord:
        """ Return the structure with the given name. """

        for structure in self.structures:
            if structure.name == name:
                return structure
        raise KeyError(f"No structure {name!r} in experiment {self.uuid}")


def z_function_to_json(z_function) -> tuple[str, dict]:
    """ Describe a z function (substrate surface) as class name and parameters.

    Parameters
    ----------
    z_function : ZFunction
        ``StaticOffset``, ``Plane``, ``PlaneFit`` or another z function.

    Returns
    -------
    tuple of (str, dict)
        Class name and JSON-compatible parameters. Unknown classes are
        described by their ``repr`` only.
    """

    name = type(z_function).__name__
    if hasattr(z_function, "points"):
        return name, {"parameters": np.asarray(z_function.parameters, dtype=float).tolist(),
                      "points": np.asarray(z_function.points, dtype=float).tolist()}
    if hasattr(z_function, "parameters"):
        return name, {"parameters": np.asarray(z_function.parameters, dtype=float).tolist()}
    if hasattr(z_function, "value"):
        return name, {"value": float(z_function.value)}
    return name, {"repr": repr(z_function)}


def z_function_from_json(name: str, data: dict):
    """ Rebuild a z function written by :func:`z_function_to_json`.

    Parameters
    ----------
    name : str
        Class name.
    data : dict
        Parameters.

    Returns
    -------
    ZFunction
        ``PlaneFit``, ``Plane`` or ``StaticOffset``; other classes are
        rebuilt as ``Plane`` if they had plane parameters.

    Raises
    ------
    ValueError
        If the function cannot be rebuilt (only a ``repr`` was stored).
    """

    from ..devices.coordinate_system import Plane, PlaneFit, StaticOffset

    if "points" in data and name == "PlaneFit":
        return PlaneFit(np.asarray(data["parameters"]), points=np.asarray(data["points"]))
    if "parameters" in data:
        return Plane(np.asarray(data["parameters"]))
    if "value" in data:
        return StaticOffset(data["value"])
    raise ValueError(f"Cannot rebuild z function {name}: {data}")
