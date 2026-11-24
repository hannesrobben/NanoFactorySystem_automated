"""Controller health check and recovery level R0 (T133, design ``docs/design/PROGRAM_LOADING.md`` section 8).

The health check has no side effects: it reads the ASCII interface, the task states of the
printing tasks, the axis faults and states, the memory of the PC and of the A3200 processes. R0
stops the printing tasks, removes the programs this package loads under fixed names and
acknowledges faults; it moves nothing. The levels R1-R3 (restart the ASCII interface, controller
reset, restart the A3200 software) follow after lab session 2 (T134).
"""
from __future__ import annotations

import csv
import io
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

from nanofactorysystem.aerobasic import SingleAxis, TaskStatusDataItem
from nanofactorysystem.aerobasic.ascii import AerotechError
from nanofactorysystem.aerobasic.constants import AxisStatus, AxisStatusDataItem
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.devices.aerotech.library import used_memory_gb

AXES = (SingleAxis.X, SingleAxis.Y, SingleAxis.Z, SingleAxis.A, SingleAxis.B)
#: Programs this package loads under fixed names (run_program_as_task; the z-line program is kept on purpose)
EXEC_PROGRAM_NAMES = ("python_aerobasic_program.pgm",)
#: A 32-bit A3200 process above this working set is close to its 2 GB address space (lab 2026-11-24: 1.87 GB)
PROCESS_WARNING_GB = 1.5


@dataclass
class HealthReport:
    """ Result of :func:`controller_health`; ``problems`` make it not ok, ``warnings`` do not. """

    ascii_ok: bool = False
    version: str = ""
    tasks: dict[int, str] = field(default_factory=dict)
    axes: dict[str, dict] = field(default_factory=dict)
    pc_used_gb: Optional[float] = None
    processes: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.ascii_ok and not self.problems

    def text(self) -> str:
        """ Readable summary for the log. """

        lines = [f"Controller health: {'ok' if self.ok else 'NOT OK'} (ASCII {'ok' if self.ascii_ok else 'down'}, "
                 f"version {self.version or '?'})",
                 f"  tasks: {self.tasks}",
                 "  axes: " + ", ".join(f"{name} {'en' if a.get('enabled') else 'dis'}abled"
                                        f"{', homed' if a.get('homed') else ''}"
                                        f"{', fault ' + str(a['fault']) if a.get('fault') else ''}"
                                        for name, a in self.axes.items()),
                 f"  PC memory in use: {self.pc_used_gb if self.pc_used_gb is None else round(self.pc_used_gb, 1)} GB",
                 "  A3200 processes: " + ", ".join(f"{p['name']} {p['working_set_gb']} GB" for p in self.processes)]
        lines += [f"  problem: {p}" for p in self.problems]
        lines += [f"  warning: {w}" for w in self.warnings]
        return "\n".join(lines)


def a3200_processes() -> list[dict]:
    """ A3200 processes with their working set in GB (``tasklist``; Windows only, else empty). """

    if sys.platform != "win32":
        return []
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh", "/fi", "imagename eq A3200*"], capture_output=True,
                             timeout=30).stdout.decode("mbcs", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_tasklist(out)


def parse_tasklist(text: str) -> list[dict]:
    """ Rows of ``tasklist /fo csv /nh``: name, PID and working set in GB ("1.234.567 K" in any locale). """

    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 5 or not row[1].strip().isdigit():
            continue
        kilobytes = int("".join(ch for ch in row[4] if ch.isdigit()) or 0)
        rows.append({"name": row[0], "pid": int(row[1]), "working_set_gb": round(kilobytes / 1024 ** 2, 3)})
    return rows


def controller_health(api, *, tasks: tuple[int, ...] = (1, 2), check_processes: bool = True) -> HealthReport:
    """ Check the controller without changing anything.

    Parameters
    ----------
    api : AerotechAsciiInterface
        Connected ASCII interface.
    tasks : tuple of int
        Tasks that print (they must be idle, ready or complete, not in error).
    check_processes : bool
        Also read the memory of the A3200 processes.

    Returns
    -------
    HealthReport
    """

    report = HealthReport(pc_used_gb=used_memory_gb())
    try:
        report.version = api.send("~VERSION")
        report.ascii_ok = True
    except (AerotechError, OSError, RuntimeError) as error:
        report.problems.append(f"ASCII interface not usable: {error}")
        return report
    try:
        states = api.STATUS(*[(t, TaskStatusDataItem.TaskState) for t in tasks]).split()
        report.tasks = {t: TaskState(int(s)).name for t, s in zip(tasks, states)}
        for t, state in report.tasks.items():
            if state == TaskState.error.name:
                report.problems.append(f"task {t} is in the error state")
            elif state == TaskState.program_running.name:
                report.warnings.append(f"task {t} is running a program")
            elif state in (TaskState.inactive.name, TaskState.unavailable.name):
                report.problems.append(f"task {t} is {state}")
    except (AerotechError, ValueError) as error:
        report.problems.append(f"task states not readable: {error}")
    try:
        query = [(axis, item) for axis in AXES for item in (AxisStatusDataItem.AxisFault,
                                                             AxisStatusDataItem.DriveStatus,
                                                             AxisStatusDataItem.AxisStatus)]
        values = [int(float(v.replace(",", "."))) for v in api.STATUS(*query).split()]
        for i, axis in enumerate(AXES):
            fault, drive, status = values[3 * i:3 * i + 3]
            report.axes[axis.name] = {"fault": fault, "enabled": bool(drive & 1),
                                      "homed": bool(status & AxisStatus.Homed.value)}
            if fault:
                report.problems.append(f"axis {axis.name} has fault {fault}")
    except (AerotechError, ValueError) as error:
        report.problems.append(f"axis states not readable: {error}")
    if check_processes:
        report.processes = a3200_processes()
        for process in report.processes:
            if process["working_set_gb"] > PROCESS_WARNING_GB:
                report.warnings.append(f"{process['name']} uses {process['working_set_gb']} GB (32-bit limit 2 GB); "
                                       f"restart the A3200 software before a long print")
    return report


def recover_r0(api, *, tasks: tuple[int, ...] = (1, 2), program_names: tuple[str, ...] = EXEC_PROGRAM_NAMES) -> list[str]:
    """ Recovery level R0: stop the printing tasks, remove the package's programs, acknowledge faults.

    Nothing moves. Every step is attempted even if an earlier one fails.

    Returns
    -------
    list of str
        What was done and what failed, for the log.
    """

    done = []
    for task_id in tasks:
        try:
            api.PROGRAM_STOP(task_id)
            done.append(f"task {task_id} stopped")
        except AerotechError as error:
            done.append(f"task {task_id} not stopped: {error}")
    for name in program_names:
        try:
            api.REMOVE_PROGRAM(name)
            done.append(f"{name} removed")
        except AerotechError as error:
            done.append(f"{name} not removed: {error}")
    try:
        api.ACKNOWLEDGEALL()
        done.append("faults acknowledged")
    except AerotechError as error:
        done.append(f"faults not acknowledged: {error}")
    return done
