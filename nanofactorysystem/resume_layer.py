""" Continue a layer that stopped in the middle without exposing its printed part again (T170).

On 2026-11-28 layer 69 of ``surface_16bit`` stopped in part 6 of 11 after an axis fault.
``restart_experiment()`` prints a failed layer again from its start, which exposes every line
that was already written a second time. This module finds where the layer stopped and writes a
program that starts behind that point:

1. :func:`failure_point` reads the controller command log of the session (``/logs/a3200`` in
   ``experiment.h5``): the last program part loaded on task 1 and the program line numbers the
   task reported until it stopped (``~STATUS ... (1, ProgramLineNumber)``, every 0.5 s, and once
   more in the error state).
2. :func:`plan_resume` maps that part line to the line of the layer program and chooses the
   first ``RAPID`` behind it that names every moved axis (laser off, absolute position), at
   least ``margin_lines`` lines later. With ``next_column`` the rest of the hatch line in which
   the fault happened is skipped as well.
3. :func:`write_resume_program` writes ``header + replayed power/feed + rest of the body +
   footer`` and splits it into parts of at most ``max_lines`` lines like the build does.
4. :func:`mark_layer_printed` records the layer as printed in the experiment file (a new
   session), so that ``restart_experiment()`` continues with the next layer.

Why this never exposes a printed line twice: the controller cannot execute a move it has not
read yet, so the physical position is never ahead of the reported program line. Starting behind
the reported line can leave a gap (if the lookahead was ahead of the motion), never an overlap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nanofactorysystem.aerobasic.programs.split import (MAX_PROGRAM_LINES, _AXIS_WORD, _LASER_GATE, _MOTION, _RAPID,
                                                        _ReplayState, _arguments, _axes, _is_body_line, plan_split,
                                                        split_program_file)

__all__ = ["FailurePoint", "ResumePlan", "failure_point", "layer_program_for_part", "mark_layer_printed",
           "plan_resume", "write_resume_program"]

_LOAD = re.compile(r"'PROGRAM (\d+) LOAD \"[^\"]*?nfs_[0-9a-f]+_\d+_(?P<stem>[^\"\\/]+?)\.pgm\\?\"")
_TASK_POLL = re.compile(r"\[SUCCESS\] '~STATUS \((\d+), TaskMode\) \(\1, TaskState\).*\(\1, ProgramLineNumber\)"
                        r"\\n' -> '(?P<values>[-\d ]+)'")
_PART = re.compile(r"^(?P<layer>.+)\.part(?P<k>\d+)of(?P<n>\d+)$")
_ERROR_STATE = 8  # TaskState.error


@dataclass
class FailurePoint:
    """ Where a program part stopped, read from the controller command log.

    Attributes
    ----------
    stem : str
        Stem of the part file, e.g. ``program_surface_16bit.069.part06of11``.
    task_id : int
        Task the part ran on.
    last_line : int
        Highest program line number the task reported for this part.
    error_line : int or None
        Line number reported together with the error state (None if the log has no error state).
    """

    stem: str
    task_id: int
    last_line: int
    error_line: Optional[int]


@dataclass
class ResumePlan:
    """ Where a layer program is continued.

    Attributes
    ----------
    layer_lines : int
        Lines of the layer program.
    header_end, footer_start : int
        Body of the layer program is ``lines[header_end:footer_start]`` (0-based).
    stop_index : int
        0-based layer program line that corresponds to the reported part line (the line that
        was executing or the last one read; everything up to it counts as printed).
    resume_index : int
        0-based layer program line of the first move of the continued program (a ``RAPID``).
    """

    layer_lines: int
    header_end: int
    footer_start: int
    stop_index: int
    resume_index: int

    @property
    def printed_body_lines(self) -> int:
        """ Body lines up to the stop line (they are not written again). """

        return self.stop_index + 1 - self.header_end

    @property
    def skipped_lines(self) -> int:
        """ Body lines between the stop line and the resume line that are not written at all. """

        return self.resume_index - self.stop_index - 1

    @property
    def remaining_body_lines(self) -> int:
        """ Body lines the continued program writes. """

        return self.footer_start - self.resume_index


def _body_bounds(lines: list[str]) -> tuple[int, int]:
    """ First body line and first footer line, as :func:`~nanofactorysystem.aerobasic.programs.split.plan_split`
    reads them (also for programs short enough not to be split). """

    footer_start = len(lines)
    while footer_start > 0 and not _MOTION.match(lines[footer_start - 1]):
        footer_start -= 1
    if footer_start == 0:
        raise ValueError("The layer program has no motion lines")
    header_end = footer_start
    while header_end > 0 and _is_body_line(lines[header_end - 1]):
        header_end -= 1
    return header_end, footer_start


def failure_point(log_text: str, stem: Optional[str] = None) -> FailurePoint:
    """ Find the part that stopped and the last line it reported in a controller command log.

    Parameters
    ----------
    log_text : str
        Controller command log of one session (``/logs/a3200/<session>`` or ``A3200.log``).
    stem : str, optional
        Stem of the part to look for; default: the last part loaded in the log.

    Returns
    -------
    FailurePoint

    Raises
    ------
    ValueError
        If no matching ``PROGRAM LOAD`` or no line number poll after it is in the log.
    """

    lines = log_text.splitlines()
    loads = [(i, m) for i, line in enumerate(lines) if (m := _LOAD.search(line))
             and (stem is None or m.group("stem") == stem)]
    if not loads:
        raise ValueError(f"No PROGRAM LOAD {'of ' + stem if stem else ''} in the controller log")
    start, match = loads[-1]
    task_id, found_stem = int(match.group(1)), match.group("stem")
    last_line, error_line = None, None
    for line in lines[start + 1:]:
        if _LOAD.search(line):
            break
        poll = _TASK_POLL.search(line)
        if poll is None or int(poll.group(1)) != task_id:
            continue
        values = [int(v) for v in poll.group("values").split()]
        state, number = values[1], values[-1]
        last_line = number if last_line is None else max(last_line, number)
        if state == _ERROR_STATE and error_line is None:
            error_line = number
    if last_line is None:
        raise ValueError(f"No program line number of task {task_id} after the load of {found_stem} in the log")
    return FailurePoint(found_stem, task_id, last_line, error_line)


def layer_program_for_part(experiment: Path, stem: str) -> tuple[Path, int, int]:
    """ Layer program file, part number and part count of a part stem.

    Parameters
    ----------
    experiment : Path
        Experiment folder.
    stem : str
        Part stem, e.g. ``program_surface_16bit.069.part06of11``.

    Returns
    -------
    (Path, int, int)
        ``structures/<name>/programs/<layer stem>.txt``, k and n of ``part<k>of<n>``.
    """

    match = _PART.match(stem)
    if match is None:
        raise ValueError(f"{stem} is not the name of a program part (<layer>.part<k>of<n>)")
    layer_stem = match.group("layer")
    name = layer_stem.split(".")[0].removeprefix("program_")
    path = Path(experiment) / "structures" / name / "programs" / f"{layer_stem}.txt"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path, int(match.group("k")), int(match.group("n"))


def plan_resume(layer_lines: list[str], part: int, n_parts: int, part_line: int, *,
                max_lines: int = MAX_PROGRAM_LINES, margin_lines: int = 1, next_column: bool = False) -> ResumePlan:
    """ Map the reported line of a part to the layer program and choose where to continue.

    Parameters
    ----------
    layer_lines : list of str
        Lines of the whole layer program.
    part, n_parts : int
        Part that stopped (1-based) and number of parts, as in the part file name.
    part_line : int
        Program line number the task reported last (1-based line of the part file).
    max_lines : int
        Part size the layer was split with.
    margin_lines : int
        Lines behind the stop line that are skipped in any case (covers a 0-based line counter).
    next_column : bool
        Also skip the rest of the hatch line the stop line belongs to: continue at the first
        ``RAPID`` whose value in the hatch-step axis differs from the stop line.

    Returns
    -------
    ResumePlan

    Raises
    ------
    ValueError
        If the split does not give ``n_parts`` parts, the body gates the laser itself, or no
        place to continue is left.
    """

    plan = plan_split(layer_lines, max_lines)
    if plan.n_parts != n_parts:
        raise ValueError(f"The layer program splits into {plan.n_parts} parts, the log names {n_parts}: "
                         f"different program or part size")
    body_start, footer_start = _body_bounds(layer_lines)
    header = layer_lines[:body_start]
    if any(_LASER_GATE.match(line) for line in layer_lines[body_start:footer_start]):
        raise ValueError("The body switches the laser gate itself; continuing it is not supported")
    gate = [m.group(1).upper() for line in header if (m := _LASER_GATE.match(line))]
    if not gate or gate[-1] != "AUTO":
        raise ValueError("The laser gate is not AUTO in the header: a RAPID would not be written with the laser off")

    bounds = [body_start, *plan.cuts, footer_start]
    begin, end = bounds[part - 1], bounds[part]
    state = _ReplayState()
    state.update(layer_lines[body_start:begin])
    if plan.n_parts == 1:
        offset = body_start  # the layer program itself ran: its line numbers are the layer lines
    else:
        offset = 1 + len(header) + (len(state.lines()) if part > 1 else 0)  # note line + header + replay
    index_in_part = part_line - 1
    if index_in_part < offset:
        stop = begin - 1  # still in the header of the part: nothing of its body was written
    else:
        stop = min(begin + index_in_part - offset, end - 1)

    words = "\n".join(_arguments(line) for line in layer_lines[body_start:footer_start] if _MOTION.match(line))
    body_axes = {axis.upper() for axis, _ in _AXIS_WORD.findall(words)}

    def values(line: str) -> dict[str, float]:
        return {axis.upper(): float(value) for axis, value in _AXIS_WORD.findall(_arguments(line))}

    column_axis, column_value = None, None
    if next_column and stop >= body_start:
        rapid = next((i for i in range(stop, body_start - 1, -1) if _RAPID.match(layer_lines[i])), None)
        if rapid is not None and rapid + 1 < footer_start:
            here, there = values(layer_lines[rapid]), values(layer_lines[rapid + 1])
            constant = [a for a in sorted(body_axes) if a in here and a in there and here[a] == there[a]]
            if constant:
                column_axis, column_value = constant[0], here[constant[0]]
    for i in range(max(stop + 1 + margin_lines, body_start), footer_start):
        line = layer_lines[i]
        if not _RAPID.match(line) or not body_axes <= _axes(line):
            continue
        if column_axis is not None and values(line)[column_axis] == column_value:
            continue
        return ResumePlan(len(layer_lines), body_start, footer_start, stop, i)
    raise ValueError("No RAPID move is left behind the stop line: the layer is complete or nearly complete")


def write_resume_program(layer_lines: list[str], plan: ResumePlan, out_dir: Path, layer_name: str, *,
                         max_lines: int = MAX_PROGRAM_LINES) -> tuple[Path, list[Path]]:
    """ Write the continued layer program and its parts.

    Parameters
    ----------
    layer_lines : list of str
        Lines of the whole layer program.
    plan : ResumePlan
        From :func:`plan_resume`.
    out_dir : Path
        Output folder (created).
    layer_name : str
        File name of the layer program (for the file names and the comment).
    max_lines : int
        Maximum lines per part.

    Returns
    -------
    (Path, list of Path)
        The whole continued program and its parts in print order (``[program]`` if short enough).
    """

    header, footer = layer_lines[:plan.header_end], layer_lines[plan.footer_start:]
    state = _ReplayState()
    state.update(layer_lines[plan.header_end:plan.resume_index])
    note = (f"' Rest of {layer_name}: continues at layer line {plan.resume_index + 1} after a stop at line "
            f"{plan.stop_index + 1}; lines {plan.header_end + 1}-{plan.stop_index + 1} were printed, "
            f"{plan.skipped_lines} lines skipped (T170)")
    lines = [note, *header, *state.lines(), *layer_lines[plan.resume_index:plan.footer_start], *footer]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(layer_name).stem, Path(layer_name).suffix or ".txt"
    program = out_dir / f"{stem}.resume_from_{plan.resume_index + 1}{suffix}"
    program.write_text("\n".join(lines) + "\n")
    return program, split_program_file(program, max_lines, out_dir=out_dir / "split")


def mark_layer_printed(experiment: Path, structure: str, layer_id: int, note: str) -> str:
    """ Record a layer as printed in a new session of the experiment file.

    ``restart_experiment()`` then skips it and continues with the next layer in the print
    order.

    Parameters
    ----------
    experiment : Path
        Experiment folder.
    structure : str
        Structure name.
    layer_id : int
        Layer id.
    note : str
        What was printed; stored as the console log of the session.

    Returns
    -------
    str
        Session id.
    """

    from nanofactorysystem.storage import ExperimentStore
    from nanofactorysystem.storage.records import utc_timestamp

    store = ExperimentStore.open(Path(experiment))
    session = store.begin_session("restart")
    reason = "exception"
    try:
        store.update_progress(structure, layer_id, "ok", started=utc_timestamp())
        store.write_log("console", note)
        reason = "finished"
    finally:
        store.end_session(reason)
    return session
