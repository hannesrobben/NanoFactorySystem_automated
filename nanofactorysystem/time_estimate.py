##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Expected printing time of AeroBasic layer programs (T28).

Every move takes its path length divided by its speed; a fixed overhead per
layer (default 5 s, maintainer decision 2026-10-01) covers loading the task,
captures and, in future, the reconstruction. The estimate ignores
acceleration, so short moves are estimated too fast; compare it with the
stored start and end times of the printed structures.

Programs are in mm and mm/s (``METRIC``, ``SECONDS``). Recognised statements:
``LINEAR``/``RAPID`` (axes X, Y, Z, A, B and a modal ``F``), ``F <speed>``
(default speed; ``RAPID`` moves use it, else ``rapid_speed_mm_s``), ``ABSOLUTE``/``INCREMENTAL`` and
``DWELL <s>``; everything else takes no time.
"""
import math
import re
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_LAYER_OVERHEAD_S = 5.0
DEFAULT_RAPID_SPEED_MM_S = 10.0

_MOVE = re.compile(r"^(LINEAR|RAPID)\b(.*)$")
_ARGUMENT = re.compile(r"([XYZABEF])\s*(-?[0-9.]+(?:[eE][-+]?[0-9]+)?)")
_SPEED = re.compile(r"^F\s+(-?[0-9.]+)$")
_DWELL = re.compile(r"^DWELL\s+([0-9.]+)")


def estimate_program_s(text: str, *, rapid_speed_mm_s: float = DEFAULT_RAPID_SPEED_MM_S) -> float:
    """ Expected run time of one AeroBasic program in seconds, without overhead.

    Parameters
    ----------
    text : str
        Program text.
    rapid_speed_mm_s : float
        Speed of ``RAPID`` moves and of moves before any speed is set.

    Returns
    -------
    float
    """

    position: dict[str, Optional[float]] = {axis: None for axis in "XYZAB"}
    absolute = True
    feed: Optional[float] = None  # modal speed of LINEAR moves
    default: Optional[float] = None  # default speed (F statement), also for RAPID moves
    total = 0.0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("'"):
            continue
        upper = line.upper()
        if upper.startswith("ABSOLUTE"):
            absolute = True
            continue
        if upper.startswith("INCREMENTAL"):
            absolute = False
            continue
        if match := _SPEED.match(upper):
            feed = default = float(match.group(1))
            continue
        if match := _DWELL.match(upper):
            total += float(match.group(1))
            continue
        match = _MOVE.match(upper)
        if not match:
            continue
        kind, arguments = match.groups()
        delta = {}
        for axis, value in _ARGUMENT.findall(arguments):
            value = float(value)
            if axis == "F":
                if kind == "LINEAR":
                    feed = value
            elif axis == "E":
                continue
            elif absolute:
                if position[axis] is not None:  # the start of an axis that was never set is unknown
                    delta[axis] = value - position[axis]
                position[axis] = value
            else:
                delta[axis] = value
                position[axis] = (position[axis] or 0.0) + value
        # Stage (X, Y) and galvo (A, B) offsets add up at the sample
        dx = delta.get("X", 0.0) + delta.get("A", 0.0)
        dy = delta.get("Y", 0.0) + delta.get("B", 0.0)
        distance = math.sqrt(dx ** 2 + dy ** 2 + delta.get("Z", 0.0) ** 2)
        speed = (feed if kind == "LINEAR" else default) or rapid_speed_mm_s
        if distance > 0 and speed > 0:
            total += distance / speed
    return total


@dataclass
class TimeEstimate:
    """ Expected printing time of an experiment.

    Parameters
    ----------
    layer_overhead_s : float
        Overhead added per layer.
    structures : dict
        Per structure name the expected seconds of every layer (program time
        plus overhead).
    """

    layer_overhead_s: float = DEFAULT_LAYER_OVERHEAD_S
    structures: dict[str, list[float]] = field(default_factory=dict)

    def structure_s(self, name: str) -> float:
        """ Expected seconds of one structure. """

        return float(sum(self.structures.get(name, [])))

    @property
    def total_s(self) -> float:
        """ Expected seconds of all structures. """

        return float(sum(sum(layers) for layers in self.structures.values()))

    def to_dict(self) -> dict:
        """ JSON-compatible form (stored in the experiment file). """

        return {"layer_overhead_s": self.layer_overhead_s, "total_s": self.total_s,
                "structures": {name: list(map(float, layers)) for name, layers in self.structures.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "TimeEstimate":
        """ Inverse of :meth:`to_dict`. """

        return cls(float(data.get("layer_overhead_s", DEFAULT_LAYER_OVERHEAD_S)),
                   {name: list(map(float, layers)) for name, layers in data.get("structures", {}).items()})


def format_duration(seconds: Optional[float]) -> str:
    """ ``"1 h 02 min"``, ``"3 min 05 s"`` or ``"12 s"``; ``"-"`` for None. """

    if seconds is None:
        return "-"
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"
