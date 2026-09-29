##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Plain data records of an experiment (see docs/design/EXPERIMENT_STORAGE.md).

The records hold data only; they know nothing about HDF5 or JSON files.
"""
import datetime
from dataclasses import asdict, dataclass, field
from typing import Optional


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

    Positions are absolute stage coordinates in µm.

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
        (X, Y, Z) target of the move before the capture; an axis that was
        not commanded is None.
    actual_um : dict
        Positions of the axes X, Y, Z, A, B read from the controller after
        the move.
    time : str
        Start of the capture (ISO 8601, UTC).
    file : str, optional
        File the capture was written to, relative to the experiment folder.
    """

    kind: str
    structure: str
    phase: str
    layer_id: int
    image_index: int
    image_count: int
    offset_um: tuple[float, float]
    commanded_um: tuple[Optional[float], Optional[float], Optional[float]]
    actual_um: dict[str, float] = field(default_factory=dict)
    time: str = field(default_factory=utc_timestamp)
    file: Optional[str] = None

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
