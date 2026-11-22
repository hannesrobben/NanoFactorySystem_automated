""" Split AeroBasic programs that are too long for ``PROGRAM LOAD`` on the A3200 (T125).

``PROGRAM <task> LOAD`` compiles the whole program file and keeps it on the
controller. The practical limit of this path is about 60 000 - 80 000 program
lines (Aerotech knowledge base "Introduction to Queue Mode and Command Queue in
A3200"). In the print of 2026-11-21 a layer with 81 751 lines loaded and every
layer with 96 737 lines or more failed with "out of memory" or ``!``. Until the
programs are run in queue mode (``PROGRAM BUFFEREDRUN``, follow-up todo), a
layer program with more than :data:`MAX_PROGRAM_LINES` lines is split into
parts that are loaded and run one after another.

A layer program is read as three blocks:

- body: the trailing run of motion lines (``RAPID``/``LINEAR``/``CW``/``CCW``)
  and of the lines that only gate the laser, set the power or set a feed rate,
  together with comments and blank lines;
- header: everything before the body (setup, IFOV configuration, positioning);
- footer: everything after the last motion line (``CRITICAL END``, ``IFOV OFF``,
  ``END PROGRAM``, ...).

Every part is ``header + replayed state + body slice + footer``. The body is
cut only in front of a ``RAPID``/``LINEAR`` line that is written with the laser
off (a ``RAPID``, or any move while ``GALVO LASEROVERRIDE`` is ``OFF``) and that
names every axis the body moves, so that the first move of a part goes to an
absolute position no matter where the previous part ended. The last power,
feed rate and axis feed rates set inside the body before the cut are written
again at the start of the part. Programs in incremental mode, programs whose
body cannot be cut like this, and programs whose header alone is too long are
refused with :class:`ProgramSplitError`.

Each part repeats the header, so it moves to the start position of the layer
and switches IFOV on again; the motion path is interrupted at every cut (the
laser is off there).
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

__all__ = ["MAX_PROGRAM_LINES", "ProgramSplitError", "SplitPlan", "count_lines", "existing_parts", "plan_split",
           "remove_parts", "split_lines", "split_program_file"]

#: Maximum number of lines of a program loaded with ``PROGRAM LOAD`` (maintainer decision 2026-11-22).
MAX_PROGRAM_LINES = 80_000

_MOTION = re.compile(r"^\s*(RAPID|LINEAR|G0|G1|CW|CCW)\b", re.IGNORECASE)
_CUTTABLE = re.compile(r"^\s*(RAPID|LINEAR|G0|G1)\b", re.IGNORECASE)
_RAPID = re.compile(r"^\s*(RAPID|G0)\b", re.IGNORECASE)
_LASER_GATE = re.compile(r"^\s*GALVO\s+LASEROVERRIDE\s+\w+\s+(ON|OFF|AUTO)\s*$", re.IGNORECASE)
_POWER = re.compile(r"^\s*\$AO\[[^\]]*\]\.\w+\s*=", re.IGNORECASE)
_FEED = re.compile(r"^\s*([A-Z]{0,2})F\s*(-?[\d.]+(?:E[-+]?\d+)?)\s*$", re.IGNORECASE)
_AXIS_WORD = re.compile(r"\b([A-EU-Z])\s*(-?[\d.]+(?:E[-+]?\d+)?)", re.IGNORECASE)
_FEED_WORD = re.compile(r"\bF\s*(-?[\d.]+(?:E[-+]?\d+)?)", re.IGNORECASE)
_INCREMENTAL = re.compile(r"^\s*(INCREMENTAL|G91)\b", re.IGNORECASE)


class ProgramSplitError(ValueError):
    """ A program cannot be split into loadable parts without changing what it prints. """


@dataclass
class SplitPlan:
    """ Where a program is cut into parts.

    Attributes
    ----------
    n_lines : int
        Number of lines of the program.
    max_lines : int
        Maximum number of lines per part.
    header_end : int
        Index of the first body line (the header is ``lines[:header_end]``).
    footer_start : int
        Index of the first footer line.
    cuts : list of int
        Line indices at which a new part starts (empty: no split needed).
    """

    n_lines: int
    max_lines: int
    header_end: int = 0
    footer_start: int = 0
    cuts: list[int] = field(default_factory=list)

    @property
    def n_parts(self) -> int:
        """ Number of programs the program is run as. """

        return len(self.cuts) + 1


def count_lines(path: Path | str) -> int:
    """ Return the number of text lines of a program file (fast, without decoding).

    Parameters
    ----------
    path : str or Path

    Returns
    -------
    int
    """

    data = Path(path).read_bytes()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def _is_comment(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("'") or stripped.startswith("//")


def _is_body_line(line: str) -> bool:
    return (_is_comment(line) or bool(_MOTION.match(line)) or bool(_LASER_GATE.match(line))
            or bool(_POWER.match(line)) or bool(_FEED.match(line)))


def _arguments(line: str) -> str:
    """ The words of a motion line after its keyword, without a trailing comment. """

    parts = line.split("'", 1)[0].split(None, 1)
    return parts[1] if len(parts) > 1 else ""


def _axes(line: str) -> set[str]:
    return {axis.upper() for axis, _ in _AXIS_WORD.findall(_arguments(line))}


def _laser_state(lines: list[str]) -> str:
    state = "OFF"
    for line in lines:
        match = _LASER_GATE.match(line)
        if match:
            state = match.group(1).upper()
    return state


def plan_split(lines: list[str], max_lines: int = MAX_PROGRAM_LINES) -> SplitPlan:
    """ Find where a program has to be cut so that no part is longer than ``max_lines`` lines.

    Parameters
    ----------
    lines : list of str
        Program lines without line endings.
    max_lines : int
        Maximum number of lines per part, including header, replayed state
        and footer.

    Returns
    -------
    SplitPlan
        Without cuts if the program is not longer than ``max_lines``.

    Raises
    ------
    ProgramSplitError
        If the program is longer than ``max_lines`` and cannot be split (see
        the module documentation).
    """

    n = len(lines)
    plan = SplitPlan(n_lines=n, max_lines=max_lines)
    if n <= max_lines:
        return plan

    footer_start = n
    while footer_start > 0 and not _MOTION.match(lines[footer_start - 1]):
        footer_start -= 1
    if footer_start == 0:
        raise ProgramSplitError(f"Program with {n} lines has no motion lines to split.")
    header_end = footer_start
    while header_end > 0 and _is_body_line(lines[header_end - 1]):
        header_end -= 1
    plan.header_end, plan.footer_start = header_end, footer_start

    if any(("INCREMENTAL" in line or "G91" in line) and _INCREMENTAL.match(line) for line in lines):
        raise ProgramSplitError("Programs in incremental mode (INCREMENTAL/G91) cannot be split.")

    header, footer = lines[:header_end], lines[footer_start:]
    replay_max = 8  # power + feed + up to six axis feed rates
    budget = max_lines - len(header) - len(footer) - 1 - replay_max
    if budget < 2:
        raise ProgramSplitError(f"Header ({len(header)} lines) and footer ({len(footer)} lines) leave no room for "
                                f"the body in parts of {max_lines} lines.")

    # A cut needs the laser off and an absolute position in every axis the body moves
    words = "\n".join(_arguments(line) for line in lines[header_end:footer_start] if _MOTION.match(line))
    body_axes = {axis.upper() for axis, _ in _AXIS_WORD.findall(words)}
    gates = [i for i in range(header_end, footer_start) if lines[i].lstrip()[:5].upper() == "GALVO"
             and _LASER_GATE.match(lines[i])]
    gate_states = [_LASER_GATE.match(lines[i]).group(1).upper() for i in gates]
    header_state = _laser_state(header)

    def can_cut(i: int) -> bool:
        line = lines[i]
        if not _CUTTABLE.match(line):
            return False
        k = bisect.bisect_left(gates, i) - 1
        state = gate_states[k] if k >= 0 else header_state
        laser_off = state == "OFF" or (state == "AUTO" and bool(_RAPID.match(line)))
        return laser_off and body_axes <= _axes(line)

    start = header_end
    while footer_start - start > budget:
        cut = next((i for i in range(start + budget, start, -1) if can_cut(i)), None)
        if cut is None:
            raise ProgramSplitError(f"No place to cut the program between lines {start + 2} and {start + budget + 1} "
                                    f"(laser off and an absolute position in the axes {''.join(sorted(body_axes))}).")
        start = cut
        plan.cuts.append(start)
    return plan


class _ReplayState:
    """ Power and feed rates set inside the body, written again at the start of the next part. """

    def __init__(self):
        self.power: Optional[str] = None
        self.feed: Optional[str] = None
        self.axis_feeds: dict[str, str] = {}

    def update(self, lines: list[str]) -> None:
        for line in lines:
            if line.lstrip().startswith("$"):
                if _POWER.match(line):
                    self.power = line.strip()
                continue
            if "F" not in line and "f" not in line:
                continue
            match = _FEED.match(line)
            if match:
                if match.group(1):
                    self.axis_feeds[match.group(1).upper()] = line.strip()
                else:
                    self.feed = match.group(2)
            elif _MOTION.match(line):
                words = _FEED_WORD.findall(_arguments(line))
                if words:
                    self.feed = words[-1]

    def lines(self) -> list[str]:
        replay = [self.power] if self.power else []
        replay += list(self.axis_feeds.values())
        if self.feed is not None:
            replay.append(f"F{self.feed}")
        return replay


def split_lines(lines: list[str], max_lines: int = MAX_PROGRAM_LINES, *, source: str = "") -> list[list[str]]:
    """ Split a program into parts of at most ``max_lines`` lines.

    Parameters
    ----------
    lines : list of str
        Program lines without line endings.
    max_lines : int
        Maximum number of lines per part.
    source : str
        Name of the original program, written into a comment of every part.

    Returns
    -------
    list of list of str
        One part (the program unchanged) if it is not longer than
        ``max_lines``.

    Raises
    ------
    ProgramSplitError
        If the program cannot be split.
    """

    plan = plan_split(lines, max_lines)
    if not plan.cuts:
        return [list(lines)]
    header, footer = lines[:plan.header_end], lines[plan.footer_start:]
    bounds = [plan.header_end, *plan.cuts, plan.footer_start]
    parts = []
    state = _ReplayState()
    for k in range(plan.n_parts):
        begin, end = bounds[k], bounds[k + 1]
        note = (f"' Part {k + 1} of {plan.n_parts} of {source or 'the program'} (lines {begin + 1}-{end}), "
                f"split because the program has more than {max_lines} lines (T125)")
        chunk = lines[begin:end]
        parts.append([note, *header, *(state.lines() if k else []), *chunk, *footer])
        state.update(chunk)
    return parts


def split_program_file(path: Path | str, max_lines: int = MAX_PROGRAM_LINES,
                       out_dir: Optional[Path | str] = None) -> list[Path]:
    """ Write the parts of a program file that is longer than ``max_lines`` lines.

    Parameters
    ----------
    path : str or Path
        Program file.
    max_lines : int
        Maximum number of lines per part.
    out_dir : str or Path, optional
        Folder of the parts; default: ``split/`` next to the program. Parts
        are named ``<stem>.part<k>of<n><suffix>``.

    Returns
    -------
    list of Path
        ``[path]`` if the program is short enough, else the part files in
        print order.

    Raises
    ------
    ProgramSplitError
        If the program cannot be split.
    """

    path = Path(path)
    if count_lines(path) <= max_lines:
        return [path]
    parts = split_lines(path.read_text().splitlines(), max_lines, source=path.name)
    out_dir = _parts_dir(path, out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    remove_parts(path, out_dir)
    width = len(str(len(parts)))
    files = []
    for k, part in enumerate(parts, start=1):
        file = out_dir / f"{path.stem}.part{k:0{width}d}of{len(parts)}{path.suffix}"
        file.write_text("\n".join(part) + "\n")
        files.append(file)
    return files


def _parts_dir(path: Path, out_dir: Optional[Path | str]) -> Path:
    return Path(out_dir) if out_dir is not None else path.parent / "split"


def _part_files(path: Path, out_dir: Optional[Path | str]) -> list[Path]:
    folder = _parts_dir(path, out_dir)
    if not folder.is_dir():
        return []
    pattern = re.compile(re.escape(path.stem) + r"\.part(\d+)of(\d+)" + re.escape(path.suffix) + "$")
    return [f for f in folder.iterdir() if pattern.match(f.name)]


def existing_parts(path: Path | str, max_lines: int = MAX_PROGRAM_LINES,
                   out_dir: Optional[Path | str] = None) -> Optional[list[Path]]:
    """ Return the parts written by :func:`split_program_file` if they are complete and still valid.

    Valid means: parts 1 to n of the same split all exist, none is older
    than the program and none is longer than ``max_lines`` lines.

    Parameters
    ----------
    path : str or Path
        Program file.
    max_lines : int
        Maximum number of lines per part.
    out_dir : str or Path, optional
        Folder of the parts (default: ``split/`` next to the program).

    Returns
    -------
    list of Path or None
        The parts in print order, or None.
    """

    path = Path(path)
    pattern = re.compile(re.escape(path.stem) + r"\.part(\d+)of(\d+)" + re.escape(path.suffix) + "$")
    found = {}
    for file in _part_files(path, out_dir):
        k, n = map(int, pattern.match(file.name).groups())
        found.setdefault(n, {})[k] = file
    if len(found) != 1:
        return None
    (n, files), = found.items()
    if sorted(files) != list(range(1, n + 1)):
        return None
    parts = [files[k] for k in range(1, n + 1)]
    mtime = path.stat().st_mtime
    if any(p.stat().st_mtime < mtime or count_lines(p) > max_lines for p in parts):
        return None
    return parts


def remove_parts(path: Path | str, out_dir: Optional[Path | str] = None) -> None:
    """ Delete the part files of a program (see :func:`split_program_file`). """

    for file in _part_files(Path(path), out_dir):
        file.unlink(missing_ok=True)
