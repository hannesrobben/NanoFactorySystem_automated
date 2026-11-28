"""Controller health check and recovery level R0 (T133, design ``docs/design/PROGRAM_LOADING.md`` section 8).

The health check has no side effects: it reads the ASCII interface, the task states of the
printing tasks, the axis faults and states, the memory of the PC and of the A3200 processes. R0
stops the printing tasks, removes the programs this package loads under fixed names and
acknowledges faults; it moves nothing. R1 restarts the ASCII interface (runs automatically after a
detected error, with a limit per structure), R2 resets the controller and R3 restarts the A3200
software; R2 and R3 run only after the operator agreed (maintainer decision 2026-11-26, T133).
"""
from __future__ import annotations

import csv
import io
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from nanofactorysystem.aerobasic import SingleAxis, TaskStatusDataItem
from nanofactorysystem.aerobasic.ascii import AerotechError
from nanofactorysystem.aerobasic.constants import AxisStatus, AxisStatusDataItem
from nanofactorysystem.aerobasic.constants.axes import AxisFault
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.devices.aerotech.library import used_memory_gb

AXES = (SingleAxis.X, SingleAxis.Y, SingleAxis.Z, SingleAxis.A, SingleAxis.B)
#: Programs this package loads under fixed names (run_program_as_task; the z-line program is kept on purpose)
EXEC_PROGRAM_NAMES = ("python_aerobasic_program.pgm",)
"""Fixed execution name used before T152; R0 still removes it (left over by an older version)."""
#: A 32-bit A3200 process above this working set is close to its 2 GB address space (lab 2026-11-24: 1.87 GB)
PROCESS_WARNING_GB = 1.5


def describe_axis_fault(fault: int) -> str:
    """ Names of the bits set in an ``AxisFault`` value, e.g. ``"PositionError|VelocityError"``.

    Parameters
    ----------
    fault : int
        Value of ``AXISSTATUS(<axis>, DATAITEM_AxisFault)``.

    Returns
    -------
    str
        The flag names joined by ``|``; bits without a name are given as hexadecimal rest.
    """

    names = [flag.name for flag in AxisFault if flag.value & fault]
    rest = fault & ~sum(flag.value for flag in AxisFault)
    if rest:
        names.append(f"0x{rest:08X}")
    return "|".join(names) if names else "none"


def axis_faults(api, axes=AXES) -> dict[str, int]:
    """ Read the fault value of every axis that has one (no side effects, nothing is acknowledged).

    Parameters
    ----------
    api : AerotechAsciiInterface
        Connected ASCII interface.
    axes : iterable of SingleAxis
        Axes to read.

    Returns
    -------
    dict of str to int
        Axis name to ``AxisFault`` value, only axes with a fault.

    Raises
    ------
    AerotechError, ValueError
        If the status cannot be read.
    """

    axes = tuple(axes)
    values = api.STATUS(*[(axis, AxisStatusDataItem.AxisFault) for axis in axes]).split()
    faults = {axis.name: int(float(v.replace(",", "."))) for axis, v in zip(axes, values)}
    return {name: fault for name, fault in faults.items() if fault}


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
                report.problems.append(f"axis {axis.name} has fault {fault} ({describe_axis_fault(fault)})")
            elif not report.axes[axis.name]["enabled"]:
                # Lab 2026-11-28 (T169): an axis fault during a print disables the axis; acknowledging the
                # fault (R0) does not enable it again, and every later move fails
                report.problems.append(f"axis {axis.name} is disabled")
            if not report.axes[axis.name]["homed"]:
                report.problems.append(f"axis {axis.name} is not homed")
    except (AerotechError, ValueError) as error:
        report.problems.append(f"axis states not readable: {error}")
    if check_processes:
        report.processes = a3200_processes()
        for process in report.processes:
            if process["working_set_gb"] > PROCESS_WARNING_GB:
                report.warnings.append(f"{process['name']} uses {process['working_set_gb']} GB (32-bit limit 2 GB); "
                                       f"restart the A3200 software before a long print")
    return report


def recover_r0(api, *, tasks: tuple[int, ...] = (1, 2), program_names: tuple[str, ...] = EXEC_PROGRAM_NAMES,
               on_removed: Optional[Callable[[str], None]] = None) -> list[str]:
    """ Recovery level R0: stop the printing tasks, remove the package's programs, acknowledge faults.

    Nothing moves. Every step is attempted even if an earlier one fails.

    Parameters
    ----------
    api : AerotechAsciiInterface
    tasks : tuple of int
        Tasks to stop.
    program_names : tuple of str
        Programs to remove. Since T152 every load has its own name: pass the
        names the controller object still lists (``A3200.exec_programs``)
        plus :data:`EXEC_PROGRAM_NAMES`. Names loaded by another process are
        not known here; they block nothing and disappear with a restart of
        the A3200 software.
    on_removed : callable, optional
        Called with every name whose ``REMOVEPROGRAM`` succeeded.

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
            if on_removed is not None:
                on_removed(name)
        except AerotechError as error:
            done.append(f"{name} not removed: {error}")
    try:
        api.ACKNOWLEDGEALL()
        done.append("faults acknowledged")
    except AerotechError as error:
        done.append(f"faults not acknowledged: {error}")
    return done


def terminate_ascii_interface() -> str:
    """ Terminate ``A3200AsciiInterface.exe`` (recovery level R1); the A3200 software starts it again.

    Lab session 2 (2026-11-25): respawned after 0.3 s, ASCII reachable after 1.0 s, LOAD works again; tasks,
    programs and axes are unchanged. It does not clear a program name blocked by a refused LOAD (session 3).

    Returns
    -------
    str
        Output of ``taskkill``.
    """

    result = subprocess.run(["taskkill", "/IM", "A3200AsciiInterface.exe", "/F"], capture_output=True, text=True,
                            timeout=30)
    return (result.stdout or result.stderr).strip()


def recover_r1(api, restart: Callable[[], str], *, wait_s: float = 30.0, interval_s: float = 0.5,
               sleep: Callable[[float], None] = time.sleep) -> list[str]:
    """ Recovery level R1: restart the ASCII interface and reconnect (T133).

    Nothing moves; tasks, programs and axes stay as they are. Used automatically by ``Experiment`` only after
    a detected error and only a limited number of times per structure.

    Parameters
    ----------
    api : AerotechAsciiInterface
        Interface to reconnect.
    restart : callable
        Terminates the interface process (:func:`terminate_ascii_interface`, or the backend's simulation).
    wait_s : float
        Longest wait until the interface answers again.
    interval_s : float
        Seconds between connection attempts.
    sleep : callable
        Sleep function (the dummy backend passes its virtual clock).

    Returns
    -------
    list of str
        What was done, for the log.

    Raises
    ------
    AerotechError
        If the interface does not answer within ``wait_s``.
    """

    done = [f"ASCII interface terminated: {restart() or 'ok'}"]
    api.close()
    waited = 0.0
    while True:
        try:
            api.connect()
            api.send("~VERSION")
            done.append(f"ASCII interface answers again after {waited:.1f} s")
            return done
        except (OSError, AerotechError) as error:
            api.close()
            if waited >= wait_s:
                raise AerotechError(f"R1: the ASCII interface did not answer within {wait_s:.0f} s ({error}).")
        sleep(interval_s)
        waited += interval_s


def reset_controller(api) -> list[str]:
    """ Recovery level R2: ``~RESETCONTROLLER`` (T133). Only between experiments and after the operator agreed.

    Lab session 2: 7.9 s; every axis is disabled and unhomed and every program removed. Afterwards the axes
    must be enabled and homed (Femtika software or Motion Composer) and the setup sent again.

    Returns
    -------
    list of str
        What was done, for the log.
    """

    reply = api.send("~RESETCONTROLLER")
    return [f"controller reset ({reply or 'ok'}); enable and home all axes before the next experiment"]


def restart_a3200_service() -> str:
    """ Recovery level R3: restart the service ``A3200CommService`` (administrator rights, lab session 3).

    Returns
    -------
    str
        Output of PowerShell ``Restart-Service``.
    """

    result = subprocess.run(["powershell", "-NoProfile", "-Command", "Restart-Service A3200CommService -Force"],
                            capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise AerotechError(f"R3 failed (administrator rights needed?): {(result.stderr or result.stdout).strip()}")
    return (result.stdout or "A3200CommService restarted").strip()
