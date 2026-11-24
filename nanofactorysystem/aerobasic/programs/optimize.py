"""Shorten generated AeroBasic programs without changing the exposed path beyond a chosen precision (T130).

The DOE layer programs have up to 2.2 M lines. Lab session 1 (2026-11-24) showed that the compile
memory grows with the text of a line (19.3 / 16.7 / 15.2 kB per line for 10 decimals / 5 decimals /
5 decimals without trailing zeros) and that the compile time grows only with the number of lines.
:func:`optimize_lines` therefore

- writes coordinates with at most ``decimals`` decimals in mm (default 5 = 10 nm) and without
  trailing zeros, feed rates without trailing zeros,
- omits a feed rate that equals the current (modal) one,
- omits axis words that do not change the commanded position (ABSOLUTE) or are zero (INCREMENTAL),
  and drops moves that move nothing,
- merges consecutive collinear ``LINEAR`` moves with the same feed rate (nothing between them, so
  the laser state is the same) into one move.

Lines it does not fully understand (variables, expressions, other commands) are kept unchanged, and
every command that may move an axis without telling the new position (``HOME``, ``MOVEABS``, IFOV
commands, ...) makes the commanded positions unknown, so nothing is omitted or merged across it.
It is not a build default: golden programs change only if the maintainer makes it one.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_MOTION = re.compile(r"^(RAPID|LINEAR|G0|G1)(\s+.*)?$", re.IGNORECASE)
_WORD = re.compile(r"([A-Z])\s*(-?(?:\d+\.?\d*|\.\d+))(?![\w.$\[])", re.IGNORECASE)
_FEED_LINE = re.compile(r"^F\s*(-?(?:\d+\.?\d*|\.\d+))$", re.IGNORECASE)
#: Commands that neither move an axis nor change the feed rate (positions stay known across them)
_NEUTRAL = ("'", "//", "ABSOLUTE", "INCREMENTAL", "GALVO LASEROVERRIDE", "$AO", "DWELL", "VELOCITY", "WAIT MODE",
            "LOOKAHEAD", "CRITICAL", "METRIC", "SECONDS", "MINUTES", "END PROGRAM", "DVAR", "PSOCONTROL",
            "PSOOUTPUT", "ENABLE")


@dataclass
class OptimizeStats:
    """ Lines and bytes before and after :func:`optimize_lines`. """

    lines_before: int = 0
    lines_after: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    merged_moves: int = 0
    dropped_moves: int = 0

    def text(self) -> str:
        return (f"{self.lines_before} -> {self.lines_after} lines "
                f"({100 * (1 - self.lines_after / max(self.lines_before, 1)):.1f} % fewer), "
                f"{self.bytes_before} -> {self.bytes_after} bytes "
                f"({100 * (1 - self.bytes_after / max(self.bytes_before, 1)):.1f} % fewer), "
                f"{self.merged_moves} moves merged, {self.dropped_moves} empty moves dropped")


def format_number(value: float, decimals: int) -> str:
    """ ``value`` with at most ``decimals`` decimals and without trailing zeros (``-0`` becomes ``0``). """

    text = f"{round(value, decimals):.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _parse_motion(rest: str) -> Optional[list[tuple[str, float]]]:
    """ Axis words of a motion line, or None if the line holds anything but plain numeric words. """

    rest = rest.strip()
    words = _WORD.findall(rest)
    if re.sub(r"\s+", "", rest) != "".join(f"{a}{v}" for a, v in words).replace(" ", ""):
        return None
    return [(axis.upper(), float(value)) for axis, value in words]


def optimize_lines(lines: list[str], *, decimals: int = 5, feed_decimals: int = 6,
                   merge: bool = True) -> tuple[list[str], OptimizeStats]:
    """ Optimise program lines (see the module documentation).

    Parameters
    ----------
    lines : list of str
        Program lines.
    decimals : int
        Decimals of coordinates in mm (5 = 10 nm).
    feed_decimals : int
        Decimals of feed rates.
    merge : bool
        Merge consecutive collinear LINEAR moves.

    Returns
    -------
    lines : list of str
    stats : OptimizeStats
    """

    stats = OptimizeStats(lines_before=len(lines), bytes_before=sum(len(line) + 1 for line in lines))
    tolerance = 0.5 * 10 ** -decimals
    out: list[str] = []
    absolute = True
    feed: Optional[float] = None
    position: dict[str, float] = {}  # commanded positions known exactly (rounded values that were sent)
    # The last emitted LINEAR move that a following collinear move may extend
    last: Optional[dict] = None

    def emit_move(kind: str, words: dict[str, float], new_feed: Optional[float]) -> str:
        parts = [kind] + [f"{axis}{format_number(value, decimals)}" for axis, value in words.items()]
        if new_feed is not None:
            parts.append(f"F{format_number(new_feed, feed_decimals)}")
        return " ".join(parts)

    for raw in lines:
        text = raw.strip()
        upper = text.upper()
        motion = _MOTION.match(text)
        if not motion:
            last = None
            feed_line = _FEED_LINE.match(text)
            if feed_line:
                value = round(float(feed_line.group(1)), feed_decimals)
                if feed is not None and value == feed:
                    continue  # the feed rate is already set
                feed = value
                out.append(f"F{format_number(value, feed_decimals)}")
                continue
            if upper == "ABSOLUTE":
                absolute = True
            elif upper == "INCREMENTAL":
                absolute = False
            elif not text or upper.startswith(_NEUTRAL):
                pass
            else:
                # Anything else may move an axis or change the feed: forget what is known
                position.clear()
                feed = None
            out.append(raw)
            continue

        kind = motion.group(1).upper()
        words = _parse_motion(motion.group(2) or "")
        if words is None:  # variables or expressions: keep the line; axes with a plain number stay known
            last = None
            for axis, value in re.findall(r"([A-Z])\s*([^\sA-Z]+)", (motion.group(2) or "").upper()):
                plain = re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", value)
                if axis == "F":
                    feed = round(float(value), feed_decimals) if plain and kind in ("LINEAR", "G1") else None
                elif plain and absolute:
                    position[axis] = round(float(value), decimals)
                else:
                    position.pop(axis, None)
            out.append(raw)
            continue

        line_feed = None
        targets: dict[str, float] = {}
        for axis, value in words:
            if axis == "F":
                line_feed = round(value, feed_decimals)
            else:
                targets[axis] = round(value, decimals)
        is_linear = kind in ("LINEAR", "G1")
        new_feed = None
        if line_feed is not None and (not is_linear or line_feed != feed):
            new_feed = line_feed
        if is_linear and line_feed is not None:
            feed = line_feed

        # Omit words that do not change the commanded position
        start = dict(position)
        if absolute:
            moving = {a: v for a, v in targets.items() if a not in position or abs(position[a] - v) > 1e-12}
        else:
            moving = {a: v for a, v in targets.items() if v != 0}
        if absolute:
            position.update(targets)
        else:
            for axis, value in targets.items():
                if axis in position:
                    position[axis] = round(position[axis] + value, decimals)
        if not moving and new_feed is None:
            stats.dropped_moves += 1
            continue
        if not moving and kind != "RAPID":
            last = None
            out.append(f"F{format_number(new_feed, feed_decimals)}")
            continue

        # Merge with the previous LINEAR move if both are absolute, have the same feed and are collinear
        if (merge and is_linear and absolute and new_feed is None and last is not None
                and _collinear(last["start"], last["end"], start, position, tolerance)):
            last["end"] = dict(position)
            last["words"].update(moving)
            out[last["index"]] = emit_move(last["kind"], last["words"], last["feed"])
            stats.merged_moves += 1
            continue

        out.append(emit_move(kind, moving, new_feed))
        if is_linear and absolute and all(a in start for a in targets):
            last = {"index": len(out) - 1, "kind": kind, "words": dict(moving), "feed": new_feed,
                    "start": start, "end": dict(position)}
        else:
            last = None

    stats.lines_after = len(out)
    stats.bytes_after = sum(len(line) + 1 for line in out)
    return out, stats


def _collinear(p0: dict, p1: dict, start: dict, p2: dict, tolerance: float) -> bool:
    """ True if the move p1 -> p2 continues p0 -> p1 in the same direction (all axes known). """

    if start != p1:
        return False
    axes = sorted(set(p0) | set(p1) | set(p2))
    if not all(a in p0 and a in p1 and a in p2 for a in axes):
        return False
    d1 = [p1[a] - p0[a] for a in axes]
    d2 = [p2[a] - p1[a] for a in axes]
    n1, n2 = math.hypot(*d1), math.hypot(*d2)
    if n1 == 0 or n2 == 0:
        return False
    if sum(x * y for x, y in zip(d1, d2)) <= 0:
        return False
    # Distance of p1 from the line p0 -> p2
    d = [p2[a] - p0[a] for a in axes]
    n = math.hypot(*d)
    along = sum((p1[a] - p0[a]) * c for a, c in zip(axes, d)) / n
    off = math.sqrt(max(sum((p1[a] - p0[a]) ** 2 for a in axes) - along ** 2, 0.0))
    return off <= tolerance


def optimize_file(path: str | Path, out: Optional[str | Path] = None, **options) -> OptimizeStats:
    """ Optimise a program file into ``out`` (default: ``<name>.opt<suffix>`` next to it). """

    path = Path(path)
    lines, stats = optimize_lines(path.read_text().splitlines(), **options)
    target = Path(out) if out is not None else path.with_name(f"{path.stem}.opt{path.suffix}")
    target.write_text("\n".join(lines) + "\n")
    return stats


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:]:
        print(f"{name}: {optimize_file(name).text()}")
