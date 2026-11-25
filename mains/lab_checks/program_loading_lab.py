"""Lab tests for loading layer programs through the A3200 C library within a memory budget (T129).

Procedure and background: ``docs/guides/PROGRAM_LOADING_LAB_TESTS.md``; work order: ``docs/design/PROGRAM_LOADING.md``.

Known from ``library_load_check.py`` (2026-11-24): the ASCII interface (``A3200AsciiInterface.exe``, 32 bit)
cannot compile large programs; ``A3200ProgramLoad`` from 64-bit Python loads the full DOE layer 68
(1.25 M lines) in 129 s with a 19.3 GB peak in the loading process. The planned loader compiles in a
short-lived worker process, runs every part on task 1 and compiles the next part without a task while
the current one runs (add-ahead, T132; lab sessions 1 and 2 alternated tasks 1 and 2), and keeps the PC below a memory budget (32 GB RAM, at most 20-25 GB used). These steps measure what
that design needs:

``system``     RAM, A3200 processes (bitness, memory, command line, parent), services, task states, added programs.
``ladder``     load-only: the first N lines of a real layer program for several N, each in a fresh worker
               process: load time, peak memory per line, memory after disconnect, whether the program stays
               loaded after the worker exits, whether removing it works.
``precision``  load-only: the same synthetic program with 10 decimals, 5 decimals and trimmed numbers.
``ogm``        load-only: Motion Composer's compiled ``.ogm`` through the library (precompiling possible?).
``cycle``      dry run (laser gate forced off, galvo axes A/B only, no stage axes): synthetic parts printed
               alternately on tasks 1 and 2, the next part loaded while the current one runs; gaps between
               parts, last line of every part, memory timeline.
``sticky``     ASCII only, run LAST: after one refused LOAD, is only that program name blocked or every load?
               Restart the A3200 software afterwards.
``watch``      memory log (system and A3200/python processes) every few seconds until Ctrl+C.

Added for lab session 2 (T134, ``docs/guides/PROGRAM_LOADING_LAB_TESTS.md`` section "Session 2"):

``api``             copies the A3200 headers, lists reset/added-program/associate/compiler functions, the
                    ``A3200AddedProgram`` struct, the public .NET API of ``A3200\\DotNet`` and the controller
                    configuration files (parameter files, ``AerParam.pgm``) into ``<session>/api``.
``ogm-clean``       compile a part through the library (writes the ``.OGM``), remove it, load the ``.OGM`` of a
                    never-loaded name, and a renamed copy; which name removes each program.
``add-associate``   ``A3200ProgramAdd`` (compile without a task) and ``A3200ProgramAssociate`` (bind to a task).
``hold``            two programs (e.g. two full-layer ``.ogm``) loaded on tasks 1 and 2 at the same time; the
                    operator notes the INtime memory before, during and after.
``taskspeed``       dry run: the same synthetic program on task 1 and task 2, with the bare header and with the
                    header of a real layer (T132).
``runner``          dry run of the package's library loader (T129: ``LibraryLoader`` + ``ProgramRunner``) with
                    synthetic galvo parts; since T132 on task 1 with add-ahead (lab session 2 ran it alternating).
``recover-ascii``   recovery level R1: terminate ``A3200AsciiInterface.exe``; is it started again, and does LOAD
                    over ASCII work afterwards?
``reset``           recovery level R2: ``~RESETCONTROLLER`` over ASCII (or ``A3200Reset``; confirmation); which states
                    survive (axis enable, home, position, task states, added programs)?
``restart-service`` recovery level R3: ``Restart-Service A3200CommService`` (administrator); time until the
                    ASCII interface and the library are usable again, states before/after.

Every step writes into one session folder (``--session``, default ``program_loading_lab_<date>`` in the
current directory); send that folder back. Standard library only; the script never switches the laser on.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Optional

ASCII_HOST, ASCII_PORT = "127.0.0.1", 8000
DLL_DEFAULT = r"C:\Program Files (x86)\Aerotech\A3200\CLibrary\Bin64\A3200C64.dll"
TASK_STATES = {0: "unavailable", 1: "inactive", 2: "idle", 3: "program_ready", 4: "program_running",
               5: "programfeed_held", 6: "program_paused", 7: "program_complete", 8: "error", 9: "queue"}
PROCESS_PATTERN = r"(?i)a3200|aerotech|composer|intime|python"
GB = 1024 ** 3
DEFAULT_KB_PER_LINE = 19.7  # lab session 1 (2026-11-24): 19.6 kB per line, linear from 50k to 400k lines
SEARCH_ROOTS = [r"C:\Program Files (x86)\Aerotech", r"C:\Program Files\Aerotech"]
CONFIG_ROOTS = [r"C:\ProgramData\Aerotech", r"C:\Users\Public\Documents\Aerotech",
                str(Path.home() / "Documents" / "Aerotech"), str(Path.home() / "Documents" / "A3200")]
ASCII_REPLY_TIMEOUT = 60.0  # an ASCII LOAD got no reply within 600 s in lab session 1
STALE_MINUTES = 60  # A3200 processes older than this were not restarted for the session
AXES = ("X", "Y", "Z", "A", "B")
TINY_PROGRAM = ["' tiny valid program, program_loading_lab.py", "DWELL 0.01", "END PROGRAM"]
# Mode lines of a generated layer program (test/golden/binary_grating_ifov_63x.txt, "Basic configuration")
REAL_HEADER = ["LOOKAHEAD FAST", "CRITICAL START", "METRIC", "SECONDS", "ABSOLUTE", "VELOCITY ON", "WAIT MODE AUTO"]
RESET_SIGNATURE = r"\bA3200Reset\s*\(\s*A3200Handle\s+\w+\s*\)"


# ============================================================================================ memory

class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def system_memory() -> dict:
    """ Physical memory of the PC in GB (total, available, used) and the commit limit (RAM + page file). """

    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    total, available = status.ullTotalPhys / GB, status.ullAvailPhys / GB
    return {"total_gb": round(total, 2), "available_gb": round(available, 2), "used_gb": round(total - available, 2),
            "commit_limit_gb": round(status.ullTotalPageFile / GB, 2),
            "commit_available_gb": round(status.ullAvailPageFile / GB, 2)}


def process_memory(pid: Optional[int] = None) -> Optional[dict]:
    """ Working set and private bytes (current and peak) of a process in GB; None if not accessible. """

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    if pid is None or pid == os.getpid():
        handle, close = ctypes.c_void_p(-1), False  # pseudo handle of the current process
    else:
        raw = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY_LIMITED_INFORMATION | VM_READ
        if not raw:
            return None
        handle, close = ctypes.c_void_p(raw), True
    try:
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return {"working_set_gb": round(counters.WorkingSetSize / GB, 3),
                "peak_working_set_gb": round(counters.PeakWorkingSetSize / GB, 3),
                "private_gb": round(counters.PrivateUsage / GB, 3),
                "peak_private_gb": round(counters.PeakPagefileUsage / GB, 3)}
    finally:
        if close:
            kernel32.CloseHandle(handle)


def process_bitness(pid: int) -> str:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    raw = kernel32.OpenProcess(0x1000, False, pid)
    if not raw:
        return "unknown (access denied)"
    try:
        wow64 = ctypes.c_int(0)
        kernel32.IsWow64Process(ctypes.c_void_p(raw), ctypes.byref(wow64))
        return "32 bit" if wow64.value else "64 bit"
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(raw))


def processes(pattern: str = PROCESS_PATTERN) -> list[dict]:
    """ Matching processes with name, PID, parent, command line and start time (PowerShell CIM query). """

    script = ("Get-CimInstance Win32_Process | Select-Object Name,ProcessId,ParentProcessId,CommandLine,"
              "@{n='Created';e={if ($_.CreationDate) { $_.CreationDate.ToString('s') } else { $null }}} "
              "| ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    try:
        rows = json.loads(out.stdout.decode("utf-8", errors="replace") or "[]")
    except json.JSONDecodeError:
        return []
    rows = rows if isinstance(rows, list) else [rows]
    return [{"name": r["Name"], "pid": r["ProcessId"], "parent": r["ParentProcessId"],
             "command_line": r.get("CommandLine"), "created": r.get("Created"),
             "age_min": process_age_minutes(r.get("Created"))}
            for r in rows if re.search(pattern, r.get("Name") or "")]


def process_age_minutes(created: Optional[str], now: Optional[datetime.datetime] = None) -> Optional[float]:
    """ Minutes since a process start time in ISO format (``None`` if unknown). """

    if not created:
        return None
    try:
        start = datetime.datetime.fromisoformat(created)
    except ValueError:
        return None
    return round(((now or datetime.datetime.now()) - start).total_seconds() / 60, 1)


def stale_a3200_processes(rows: list[dict], limit_minutes: float = STALE_MINUTES) -> list[str]:
    """ A3200 processes started more than ``limit_minutes`` ago: the software was not restarted for the session. """

    return [f"{r['name']} (PID {r['pid']}, started {r['created']})" for r in rows
            if (r.get("name") or "").lower().startswith("a3200") and (r.get("age_min") or 0) > limit_minutes]


def pid_of(name: str) -> Optional[int]:
    return next((r["pid"] for r in processes() if r["name"].lower() == name.lower()), None)


def services() -> list[dict]:
    script = ("Get-CimInstance Win32_Service | Where-Object { $_.PathName -match 'Aerotech|A3200|INtime' } "
              "| Select-Object Name,DisplayName,State,StartMode,PathName | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    try:
        rows = json.loads(out.stdout.decode("utf-8", errors="replace") or "[]")
    except json.JSONDecodeError:
        return []
    return rows if isinstance(rows, list) else [rows]


# ============================================================================================ programs

def count_lines(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 20), b""))


def read_lines(path: Path) -> list[str]:
    return path.read_text(errors="replace").splitlines()


_MOTION = re.compile(r"^\s*(RAPID|LINEAR|G0|G1)\b", re.IGNORECASE)


def truncated_program(lines: list[str], n_lines: int) -> list[str]:
    """ The first lines of a program plus its footer (the lines after its last move), ``n_lines`` in total.

    For load (compile) tests only: the program is a valid AeroBasic program of the requested length, but
    it does not print the layer.
    """

    last_move = max(i for i, line in enumerate(lines) if _MOTION.match(line))
    footer = lines[last_move + 1:]
    if n_lines >= len(lines):
        return list(lines)
    return lines[:max(n_lines - len(footer), 1)] + footer


def synthetic_program(n_lines: int, *, decimals: int = 10, trim: bool = False, segment_um: float = 2.0,
                      feed: float = 5.0, title: str = "synthetic", header_style: str = "bare") -> list[str]:
    """ Dry galvo program: laser gate forced off, axes A and B only, no stage axes, exactly ``n_lines`` lines.

    The galvo sweeps in ``segment_um`` steps between -0.05 and +0.05 mm and moves 1 µm in B per sweep.
    ``header_style="real"`` adds the mode lines of a generated layer program (``REAL_HEADER``: lookahead,
    critical section, metric, seconds, ...) and closes the critical section in the footer.
    """

    first = f"' {title}: dry galvo program (laser gate off, axes A/B only), program_loading_lab.py"
    if header_style == "bare":
        header = [first, "ABSOLUTE", "VELOCITY ON", "GALVO LASEROVERRIDE A OFF", f"F{feed:g}", "RAPID A0 B0"]
        footer = ["GALVO LASEROVERRIDE A OFF", "END PROGRAM"]
    elif header_style == "real":
        header = [first, *REAL_HEADER, "GALVO LASEROVERRIDE A OFF", f"F{feed:g}", "RAPID A0 B0"]
        footer = ["CRITICAL END", "GALVO LASEROVERRIDE A OFF", "END PROGRAM"]
    else:
        raise ValueError(f"Unknown header style {header_style!r}")
    n_body = n_lines - len(header) - len(footer)
    if n_body < 1:
        raise ValueError(f"A synthetic program needs at least {len(header) + len(footer) + 1} lines")
    step, steps = segment_um / 1000, int(round(0.1 / (segment_um / 1000)))

    def number(value: float) -> str:
        text = f"{value:.{decimals}f}"
        return (text.rstrip("0").rstrip(".") or "0") if trim else text

    body = []
    for i in range(n_body):
        sweep, k = divmod(i, steps)
        a = -0.05 + (k if sweep % 2 == 0 else steps - k) * step
        b = -0.05 + (sweep % 100) * 0.001
        body.append(f"{'RAPID' if i % 2 == 0 else 'LINEAR'} A{number(a)} B{number(b)}")
    return header + body + footer


def write_program(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def source_line_count(path: Path) -> Optional[int]:
    """ Lines of the AeroBasic source: the file itself, or for a compiled ``.ogm`` the ``.pgm`` next to it.

    Lab session 1 counted line breaks in the binary ``.ogm`` and reported a wrong memory per line.
    """

    if path.suffix.lower() == ".ogm":
        source = path.with_suffix(".pgm")
        return count_lines(source) if source.is_file() else None
    return count_lines(path)


def compiled_file(source: Path) -> Optional[Path]:
    """ The ``.ogm`` that a library load wrote next to ``source`` (any case of the name), if present. """

    stem = source.stem.lower()
    return next((p for p in source.parent.iterdir() if p.stem.lower() == stem and p.suffix.lower() == ".ogm"), None)


def program_name_candidates(path: Path) -> list[str]:
    """ Names under which the controller may list a loaded program, most likely first. """

    names = [path.name, path.stem + ".pgm", path.stem + ".ogm", path.stem]
    names += [name.upper() for name in names]
    return list(dict.fromkeys(names))


def parse_axis_states(data: str, axes: tuple[str, ...] = AXES) -> dict:
    """ Reply of ``~STATUS (<axis>, DriveStatus) (<axis>, AxisStatus) (<axis>, PositionFeedback) ...``.

    Bit 0 of DriveStatus is "enabled", bit 0 of AxisStatus is "homed"
    (``nanofactorysystem.aerobasic.constants.axes``).
    """

    values = data.replace(",", ".").split()
    states = {}
    for i, axis in enumerate(axes):
        drive, status, position = values[3 * i:3 * i + 3]
        states[axis] = {"enabled": bool(int(float(drive)) & 1), "homed": bool(int(float(status)) & 1),
                        "position": float(position)}
    return states


def prototype(header_text: str, name: str) -> Optional[str]:
    """ The declaration of function ``name`` in C header text, whitespace normalised. """

    match = re.search(rf"[\w\s\*]*\b{name}\s*\([^;{{}}]*\)\s*;", header_text)
    return " ".join(match.group(0).split()) if match else None


# ============================================================================================ controller

class Library:
    """ The A3200 C library functions used here (prototypes checked by ``library_load_check.py inspect``). """

    def __init__(self, dll: str = DLL_DEFAULT):
        self._dll_directory = os.add_dll_directory(str(Path(dll).parent))
        self.lib = lib = ctypes.WinDLL(dll)
        handle, task, text, dword = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, wintypes.DWORD
        signatures = {
            "A3200Connect": [ctypes.POINTER(ctypes.c_void_p)], "A3200Disconnect": [handle],
            "A3200ProgramLoad": [handle, task, text], "A3200ProgramStart": [handle, task],
            "A3200ProgramStop": [handle, task], "A3200ProgramStopAndWait": [handle, task, dword],
            "A3200ProgramRemove": [handle, text], "A3200ProgramGetTaskState": [handle, task, ctypes.POINTER(ctypes.c_int)],
            "A3200ProgramGetAddedProgramCount": [handle, ctypes.POINTER(dword)],
            "A3200GetLastErrorString": [ctypes.c_char_p, dword],
            "A3200ProgramAdd": [handle, text], "A3200ProgramAssociate": [handle, task, text],
        }
        for name, argtypes in signatures.items():
            getattr(lib, name).argtypes = argtypes
            getattr(lib, name).restype = ctypes.c_int
        self.handle = ctypes.c_void_p()
        self._check(lib.A3200Connect(ctypes.byref(self.handle)), "A3200Connect")

    def exported(self, name: str) -> bool:
        try:
            getattr(self.lib, name)
            return True
        except AttributeError:
            return False

    def add(self, path: Path) -> tuple[bool, str]:
        """ ``A3200ProgramAdd``: compile and add a program without associating it with a task. """

        ok = self.lib.A3200ProgramAdd(self.handle, str(path.resolve()).encode("mbcs"))
        return bool(ok), "" if ok else self.error()

    def associate(self, task_id: int, name: str) -> tuple[bool, str]:
        ok = self.lib.A3200ProgramAssociate(self.handle, task_id, name.encode("mbcs"))
        return bool(ok), "" if ok else self.error()

    def reset(self) -> tuple[bool, str]:
        """ ``A3200Reset(handle)``; the caller has checked the prototype in the installed headers. """

        function = self.lib.A3200Reset
        function.argtypes, function.restype = [ctypes.c_void_p], ctypes.c_int
        ok = function(self.handle)
        return bool(ok), "" if ok else self.error()

    def remove_verified(self, path: Path) -> tuple[Optional[str], list[dict]]:
        """ Remove a program by trying the candidate names until the added-program count drops.

        Returns the name that removed it (``None`` if none did) and every attempt with its result.
        """

        attempts, before = [], self.added_programs()
        for name in program_name_candidates(path):
            ok, error = self.remove(name)
            after = self.added_programs()
            attempts.append({"name": name, "ok": ok, "error": error, "count": after})
            if before is not None and after is not None and after < before:
                return name, attempts
        return None, attempts

    def error(self) -> str:
        buffer = ctypes.create_string_buffer(2048)
        self.lib.A3200GetLastErrorString(buffer, 2048)
        return buffer.value.decode(errors="replace")

    def _check(self, ok: int, what: str) -> None:
        if not ok:
            raise RuntimeError(f"{what} failed: {self.error()}")

    def load(self, task_id: int, path: Path) -> tuple[bool, str]:
        ok = self.lib.A3200ProgramLoad(self.handle, task_id, str(path.resolve()).encode("mbcs"))
        return bool(ok), "" if ok else self.error()

    def start(self, task_id: int) -> None:
        self._check(self.lib.A3200ProgramStart(self.handle, task_id), f"A3200ProgramStart({task_id})")

    def stop_and_wait(self, task_id: int, timeout_ms: int = 10000) -> bool:
        return bool(self.lib.A3200ProgramStopAndWait(self.handle, task_id, timeout_ms))

    def remove(self, name: str) -> tuple[bool, str]:
        ok = self.lib.A3200ProgramRemove(self.handle, name.encode("mbcs"))
        return bool(ok), "" if ok else self.error()

    def state(self, task_id: int) -> str:
        value = ctypes.c_int(-1)
        if not self.lib.A3200ProgramGetTaskState(self.handle, task_id, ctypes.byref(value)):
            return f"query failed: {self.error()}"
        return TASK_STATES.get(value.value, str(value.value))

    def added_programs(self) -> Optional[int]:
        count = wintypes.DWORD(0)
        return count.value if self.lib.A3200ProgramGetAddedProgramCount(self.handle, ctypes.byref(count)) else None

    def close(self) -> None:
        if self.handle:
            self.lib.A3200Disconnect(self.handle)
            self.handle = ctypes.c_void_p()


class Ascii:
    """ Minimal ASCII command interface client (reply: return character + data + newline). """

    def __init__(self, timeout: float = ASCII_REPLY_TIMEOUT):
        self.sock = socket.create_connection((ASCII_HOST, ASCII_PORT), timeout=10)
        self.sock.settimeout(timeout)
        self.timeout = timeout

    def send(self, command: str) -> tuple[str, str, float]:
        start = time.time()
        self.sock.sendall((command + "\n").encode("ascii"))
        reply = b""
        while not reply.endswith(b"\n"):
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("ASCII interface closed the connection")
            reply += chunk
        text = reply.decode("ascii", errors="replace").strip()
        return text[:1], text[1:], time.time() - start

    def line(self, task_id: int) -> Optional[int]:
        code, data, _ = self.send(f"~STATUS ({task_id}, ProgramLineNumber)")
        return int(float(data.split()[0])) if code == "%" and data else None

    def last_error(self) -> str:
        return self.send("~LASTERROR")[1]

    def close(self) -> None:
        self.sock.close()


def try_ascii(timeout: float = ASCII_REPLY_TIMEOUT) -> Optional[Ascii]:
    try:
        return Ascii(timeout)
    except OSError:
        return None


def ascii_task_state(client: Ascii, task_id: int) -> str:
    code, data, _ = client.send(f"~STATUS ({task_id}, TaskState)")
    return TASK_STATES.get(int(float(data)), data) if code == "%" and data else f"{code}{data}"


def ascii_load_probe(folder: Path, task_id: int, timeout: float = ASCII_REPLY_TIMEOUT) -> dict:
    """ Load, stop and remove a tiny valid program over ASCII: does LOAD over the ASCII interface work?

    Runs only on an idle task. A refusal or a missing reply means the interface is in the blocked state
    of 2026-11-21/24 (restart needed).
    """

    path = write_program(folder / "probe_tiny.pgm", TINY_PROGRAM)
    client = try_ascii(timeout)
    if client is None:
        return {"reachable": False, "ok": False, "error": "ASCII interface not reachable"}
    try:
        state = ascii_task_state(client, task_id)
        if state != "idle":
            return {"reachable": True, "ok": None, "error": f"task {task_id} is {state}, probe skipped"}
        code, data, seconds = client.send(f'PROGRAM {task_id} LOAD "{path.resolve()}"')
        error = client.last_error() if code != "%" else ""
        client.send(f"PROGRAM {task_id} STOP")
        client.send(f'REMOVEPROGRAM "{path.name}"')
        return {"reachable": True, "ok": code == "%", "reply": code + data, "seconds": round(seconds, 2),
                "error": error}
    except (TimeoutError, OSError) as error:
        return {"reachable": True, "ok": False, "error": f"no reply within {timeout} s ({error})"}
    finally:
        client.close()


def axis_states(client: Ascii) -> dict:
    query = " ".join(f"({a}, DriveStatus) ({a}, AxisStatus) ({a}, PositionFeedback)" for a in AXES)
    code, data, _ = client.send(f"~STATUS {query}")
    if code != "%":
        return {"error": f"{code}{data}"}
    try:
        return parse_axis_states(data)
    except (ValueError, IndexError):
        return {"error": f"unexpected reply {data!r}"}


def controller_snapshot(dll: str, timeout: float = ASCII_REPLY_TIMEOUT) -> dict:
    """ Task states and added programs (library), axis states (ASCII) and the A3200 processes. """

    snapshot: dict = {"time": datetime.datetime.now().isoformat(timespec="seconds")}
    try:
        lib = Library(dll)
        snapshot["tasks"] = {t: lib.state(t) for t in (1, 2)}
        snapshot["added_programs"] = lib.added_programs()
        lib.close()
    except (OSError, RuntimeError) as error:
        snapshot["library"] = f"not usable: {error}"
    client = try_ascii(timeout)
    if client:
        try:
            snapshot["axes"] = axis_states(client)
        except (TimeoutError, OSError) as error:
            snapshot["axes"] = {"error": str(error)}
        client.close()
    else:
        snapshot["axes"] = {"error": "ASCII interface not reachable"}
    snapshot["processes"] = [{k: r[k] for k in ("name", "pid", "created")} for r in processes()
                             if r["name"].lower().startswith("a3200")]
    return snapshot


# ============================================================================================ session

class Session:
    """ One folder for all steps of a lab session; every step appends to ``results.jsonl`` and ``log.txt``. """

    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.programs = folder / "programs"

    def log(self, text: str = "") -> None:
        print(text)
        with open(self.folder / "log.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%H:%M:%S}  {text}\n")

    def record(self, step: str, data: dict) -> None:
        entry = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "step": step, **data}
        with open(self.folder / "results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")


def kb_per_line_estimate(session: Session) -> float:
    """ Largest peak memory per line measured so far in this session (default 16 kB). """

    values = [DEFAULT_KB_PER_LINE]
    path = session.folder / "results.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("ok") and entry.get("kb_per_line"):
                values.append(entry["kb_per_line"])
    return max(values[1:] or values)


def fits_budget(session: Session, n_lines: int, budget_gb: float) -> tuple[bool, str]:
    need = n_lines * kb_per_line_estimate(session) * 1024 / GB * 1.2
    memory = system_memory()
    text = (f"estimated peak {need:.1f} GB, PC uses {memory['used_gb']:.1f} of {memory['total_gb']:.1f} GB, "
            f"budget {budget_gb:.0f} GB")
    return memory["used_gb"] + need <= budget_gb, text


def run_worker(path: Path, task_id: int, dll: str, keep: bool, *, source_lines: Optional[int] = None,
               mode: str = "load") -> subprocess.Popen:
    cmd = [sys.executable, __file__, "_worker", "--file", str(path), "--task", str(task_id), "--dll", dll,
           "--mode", mode]
    if keep:
        cmd.append("--keep")
    if source_lines is not None:
        cmd += ["--source-lines", str(source_lines)]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def worker_result(proc: subprocess.Popen, timeout: float = 1800) -> dict:
    out, err = proc.communicate(timeout=timeout)
    lines = [line for line in out.splitlines() if line.startswith("{")]
    if not lines:
        return {"ok": False, "error": f"worker gave no result (exit {proc.returncode}): {err.strip()[-500:]}"}
    return json.loads(lines[-1])


def worker(args) -> None:
    """ Hidden step: load one program in this process, report memory, optionally remove it again. """

    path, task_id = Path(args.file), args.task
    lib = Library(args.dll)
    lines = args.source_lines if args.source_lines is not None else source_line_count(path)
    result = {"file": str(path), "task": task_id, "mode": args.mode, "lines": lines,
              "mb": round(path.stat().st_size / 1e6, 1), "state_before": lib.state(task_id),
              "added_before": lib.added_programs(), "memory_before": process_memory()}
    start = time.time()
    if args.mode == "add":
        # Compile and add without a task, then bind the added program to the task by name
        ok, error = lib.add(path)
        result.update(add_s=round(time.time() - start, 1), added_after_add=lib.added_programs(),
                      state_after_add=lib.state(task_id), associations=[])
        if ok:
            associate_start = time.time()
            for name in program_name_candidates(path):
                done, why = lib.associate(task_id, name)
                result["associations"].append({"name": name, "ok": done, "error": why,
                                               "state": lib.state(task_id)})
                if done:
                    break
            result["associate_s"] = round(time.time() - associate_start, 2)
            ok = lib.state(task_id) == "program_ready"
            error = "" if ok else "no candidate name made the task program_ready"
    else:
        ok, error = lib.load(task_id, path)
    result.update(ok=ok, error=error, load_s=round(time.time() - start, 1), memory_after_load=process_memory(),
                  state_after=lib.state(task_id), added_after=lib.added_programs())
    peak = result["memory_after_load"]["peak_private_gb"] - result["memory_before"]["private_gb"]
    result["kb_per_line"] = round(peak * GB / 1024 / lines, 2) if ok and lines else None
    if not args.keep:
        result["stopped"] = lib.stop_and_wait(task_id)
        name, attempts = lib.remove_verified(path)
        result["removed"], result["removed_as"], result["remove_attempts"] = name is not None, name, attempts
        result["remove_error"] = "" if name else "no candidate name lowered the added-program count"
        result["added_after_remove"] = lib.added_programs()
        result["state_after_remove"] = lib.state(task_id)
    lib.close()
    result["memory_after_disconnect"] = process_memory()
    print(json.dumps(result))


def require_idle(lib: Library, task_id: int, session: Session) -> None:
    state = lib.state(task_id)
    if state != "idle":
        session.log(f"Task {task_id} is {state}, not idle (tasks 1 and 2 are usable, 3 is inactive). Stopped.")
        sys.exit(1)


# ============================================================================================ steps

def step_system(session: Session, args) -> None:
    memory = system_memory()
    session.log(f"RAM: {memory}")
    rows = []
    for proc in processes():
        mem = process_memory(proc["pid"]) or {}
        rows.append({**proc, "bitness": process_bitness(proc["pid"]), **mem})
        session.log(f"  {proc['name']:<32} PID {proc['pid']:>6} parent {proc['parent']:>6} {rows[-1]['bitness']:<22} "
                    f"WS {mem.get('working_set_gb', '?')} GB  private {mem.get('private_gb', '?')} GB  "
                    f"started {proc.get('created')}")
    stale = stale_a3200_processes(rows)
    if stale:
        session.log(f"WARNING: A3200 processes older than {STALE_MINUTES} min: {', '.join(stale)}. If you restarted "
                    f"the A3200 software for this session, it did not take effect. Restart it and repeat 'system'.")
    svc = services()
    session.log("Services: " + "; ".join(f"{s.get('Name')} ({s.get('State')}, {s.get('StartMode')})" for s in svc))
    tasks, added = {}, None
    try:
        lib = Library(args.dll)
        tasks = {t: lib.state(t) for t in range(1, 5)}
        added = lib.added_programs()
        lib.close()
    except (OSError, RuntimeError) as error:
        session.log(f"Library not usable: {error}")
    session.log(f"Task states: {tasks}; programs added on the controller: {added}"
                + ("  (expected 0 after a restart)" if added else ""))
    ascii_client = try_ascii(args.reply_timeout)
    ascii_state, axes = "not reachable", {}
    if ascii_client:
        code, data, _ = ascii_client.send("~STATUS (1, TaskState)")
        ascii_state = f"reply {code}{data}"
        axes = axis_states(ascii_client)
        ascii_client.close()
    session.log(f"ASCII interface: {ascii_state}; axes: {axes}")
    probe = ascii_load_probe(session.programs, args.task, args.reply_timeout) if not args.no_probe else None
    if probe is not None:
        session.log(f"ASCII LOAD probe (tiny program on task {args.task}): {probe}")
        if probe.get("reachable") and probe.get("ok") is False:
            session.log("The ASCII interface refuses LOAD: restart the A3200 software before the other steps.")
    session.record("system", {"memory": memory, "processes": rows, "services": svc, "tasks": tasks,
                              "added_programs": added, "ascii": ascii_state, "axes": axes, "ascii_load_probe": probe,
                              "stale_a3200_processes": stale})


def step_ladder(session: Session, args) -> None:
    source = Path(args.file)
    lines = read_lines(source)
    session.log(f"Ladder from {source.name} ({len(lines)} lines), sizes {args.sizes}, task {args.task}")
    lib = Library(args.dll)
    require_idle(lib, args.task, session)
    lib.close()
    for n in args.sizes:
        ok, text = fits_budget(session, n, args.budget_gb)
        if not ok:
            session.log(f"{n:>9} lines: skipped, {text}")
            session.record("ladder", {"lines": n, "skipped": text})
            continue
        path = write_program(session.programs / f"ladder_{n}.pgm", truncated_program(lines, n))
        session.log(f"{n:>9} lines: loading in a worker ({text}) ...")
        result = worker_result(run_worker(path, args.task, args.dll, keep=True))
        # After the worker has exited: is the program still loaded? Then remove it from here.
        lib = Library(args.dll)
        result["state_after_worker_exit"] = lib.state(args.task)
        result["stopped"] = lib.stop_and_wait(args.task)
        result["removed"], result["remove_error"] = lib.remove(path.name)
        result["added_after_remove"] = lib.added_programs()
        result["state_after_remove"] = lib.state(args.task)
        lib.close()
        session.record("ladder", result)
        session.log(f"           ok={result.get('ok')} {result.get('load_s')} s, "
                    f"peak {result.get('memory_after_load', {}).get('peak_private_gb')} GB "
                    f"({result.get('kb_per_line')} kB/line), after disconnect "
                    f"{result.get('memory_after_disconnect', {}).get('private_gb')} GB, after worker exit: "
                    f"{result['state_after_worker_exit']}, removed={result['removed']}, added programs "
                    f"{result.get('added_before')} -> {result.get('added_after')} -> {result['added_after_remove']} "
                    f"{result.get('error', '')}")
        path.unlink(missing_ok=True)


def step_precision(session: Session, args) -> None:
    variants = {"10_decimals": dict(decimals=10), "5_decimals": dict(decimals=5),
                "5_decimals_trimmed": dict(decimals=5, trim=True)}
    lib = Library(args.dll)
    require_idle(lib, args.task, session)
    lib.close()
    for name, options in variants.items():
        ok, text = fits_budget(session, args.lines, args.budget_gb)
        if not ok:
            session.log(f"{name}: skipped, {text}")
            continue
        path = write_program(session.programs / f"precision_{name}.pgm",
                             synthetic_program(args.lines, title=name, **options))
        result = worker_result(run_worker(path, args.task, args.dll, keep=False))
        result["variant"] = name
        session.record("precision", result)
        session.log(f"{name:<20} {result.get('mb')} MB: ok={result.get('ok')} {result.get('load_s')} s, "
                    f"{result.get('kb_per_line')} kB/line, removed={result.get('removed')} {result.get('error', '')}")
        path.unlink(missing_ok=True)


def step_ogm(session: Session, args) -> None:
    path = Path(args.file)
    lib = Library(args.dll)
    require_idle(lib, args.task, session)
    lib.close()
    before = {p: p.stat().st_mtime for p in path.parent.glob("*.ogm")}
    result = worker_result(run_worker(path, args.task, args.dll, keep=False))
    result["new_ogm_files"] = [str(p) for p in path.parent.glob("*.ogm") if before.get(p) != p.stat().st_mtime]
    session.record("ogm", result)
    session.log(f"Library load of {path.name}: ok={result.get('ok')} {result.get('load_s')} s, "
                f"{result.get('kb_per_line')} kB/line, state {result.get('state_after')}, "
                f"removed={result.get('removed')} {result.get('error', '')}")


def step_cycle(session: Session, args) -> None:
    if not args.axes_safe:
        session.log("The cycle moves the galvo axes A/B (laser gate forced off). Close the shutter, make sure "
                    "the galvo may move, then repeat with --axes-safe.")
        sys.exit(1)
    ok, text = fits_budget(session, 2 * args.lines, args.budget_gb)  # two parts are loaded at the same time
    session.log(f"Cycle: {args.parts} parts of {args.lines} lines, tasks 1/2 alternating; {text}")
    if not ok:
        session.log("Over budget; choose fewer --lines. Stopped.")
        sys.exit(1)
    parts = [write_program(session.programs / f"cycle_part{k + 1}of{args.parts}.pgm",
                           synthetic_program(args.lines, segment_um=args.segment_um, title=f"part {k + 1}"))
             for k in range(args.parts)]
    lib = Library(args.dll)
    for task_id in (1, 2):
        require_idle(lib, task_id, session)
    ascii_client = try_ascii()
    timeline = open(session.folder / "cycle_memory.csv", "w", newline="")
    writer = csv.writer(timeline)
    writer.writerow(["t_s", "pc_used_gb", "pc_available_gb", "event"])
    t0 = time.time()

    def sample(event: str = "") -> None:
        memory = system_memory()
        writer.writerow([round(time.time() - t0, 1), memory["used_gb"], memory["available_gb"], event])

    task_of = lambda k: 1 if k % 2 == 0 else 2  # noqa: E731
    sample("load part 1")
    first = worker_result(run_worker(parts[0], task_of(0), args.dll, keep=True))
    session.record("cycle_load", first)
    if not first.get("ok"):
        session.log(f"Part 1 could not be loaded: {first.get('error')}")
        sys.exit(1)
    rows, prefetch = [], None
    for k, part in enumerate(parts):
        task_id = task_of(k)
        if k > 0:
            wait_start = time.time()
            result = worker_result(prefetch)
            session.record("cycle_load", result)
            rows[-1]["waited_for_load_s"] = round(time.time() - wait_start, 1)
            if not result.get("ok"):
                session.log(f"Part {k + 1} could not be loaded: {result.get('error')}")
                break
        ready = lib.state(task_id)
        if ready != "program_ready":
            session.log(f"Part {k + 1} is not ready on task {task_id} ({ready}); a program loaded by a worker "
                        f"may not survive the end of the worker. The cycle stops.")
            break
        lib.start(task_id)
        started = time.time()
        if k > 0:
            rows[-1]["gap_to_next_start_s"] = round(started - rows[-1]["end_t"], 2)
        sample(f"start part {k + 1} on task {task_id}")
        if k + 1 < len(parts):
            prefetch = run_worker(parts[k + 1], task_of(k + 1), args.dll, keep=True)
            sample(f"prefetch part {k + 2} on task {task_of(k + 1)}")
        last_line, state = None, lib.state(task_id)
        while state in ("program_running", "program_ready"):
            if state == "program_ready" and time.time() - started > 30:
                break  # START had no effect
            time.sleep(0.5)
            state = lib.state(task_id)
            if ascii_client:
                last_line = ascii_client.line(task_id) or last_line
            sample()
        end = time.time()
        if ascii_client:
            last_line = ascii_client.line(task_id)
        expected = count_lines(part)
        row = {"part": k + 1, "task": task_id, "state": state, "last_line": last_line, "file_lines": expected,
               "ended_at_last_line": last_line == expected if last_line is not None else None,
               "run_s": round(end - started, 1), "end_t": end}
        rows.append(row)
        sample(f"end part {k + 1}: {state} line {last_line}")
        session.log(f"Part {k + 1} on task {task_id}: {state}, line {last_line} of {expected}, {row['run_s']} s")
        lib.stop_and_wait(task_id)
        removed, error = lib.remove(part.name)
        row["removed"], row["added_programs"] = removed, lib.added_programs()
        if state != "program_complete":
            session.log("A part did not complete; the cycle stops.")
            break
    if prefetch and prefetch.poll() is None:
        prefetch.kill()
    lib.close()
    timeline.close()
    if ascii_client:
        ascii_client.close()
    for row in rows:
        session.record("cycle_part", row)
    gaps = [r.get("gap_to_next_start_s") for r in rows if r.get("gap_to_next_start_s") is not None]
    session.log(f"Gaps between parts (s): {gaps}; every part at its last line: "
                f"{all(r['ended_at_last_line'] for r in rows if r['ended_at_last_line'] is not None)}")
    for part in parts:
        part.unlink(missing_ok=True)


def step_sticky(session: Session, args) -> None:
    folder = session.programs
    ok_a = write_program(folder / "sticky_ok_a.pgm", ["' small valid program A", "DWELL 0.01", "END PROGRAM"])
    ok_b = write_program(folder / "sticky_ok_b.pgm", ["' small valid program B", "DWELL 0.01", "END PROGRAM"])
    bad = write_program(folder / "sticky_bad.pgm", ["' deliberately invalid", "THIS IS NOT AEROBASIC 123",
                                                     "END PROGRAM"])
    ascii_client = try_ascii(args.reply_timeout)
    if ascii_client is None:
        session.log("ASCII interface not reachable. Stopped.")
        sys.exit(1)
    task_id = args.task

    def attempt(label: str, path: Path) -> None:
        nonlocal ascii_client
        start = time.time()
        try:
            code, data, seconds = ascii_client.send(f'PROGRAM {task_id} LOAD "{path.resolve()}"')
            error = ascii_client.last_error() if code != "%" else ""
            ascii_client.send(f"PROGRAM {task_id} STOP")
            removed = ascii_client.send(f'REMOVEPROGRAM "{path.name}"')[0]
        except (TimeoutError, OSError) as exc:
            # No reply: the connection is out of step, open a new one for the next attempt
            code, data, seconds = "-", "", time.time() - start
            error, removed = f"no reply within {args.reply_timeout} s ({exc})", ""
            ascii_client.close()
            ascii_client = try_ascii(args.reply_timeout)
            if ascii_client is None:
                session.log("ASCII interface no longer reachable. Stopped.")
                sys.exit(1)
        session.record("sticky", {"attempt": label, "file": path.name, "reply": code + data,
                                  "seconds": round(seconds, 2), "error": error, "remove_reply": removed})
        session.log(f"{label:<45} reply '{code}{data}' after {seconds:.2f} s {error}")

    probe = ascii_load_probe(session.programs, task_id, args.reply_timeout)
    session.record("sticky", {"attempt": "0 probe before the test", **probe})
    if not probe.get("ok"):
        session.log(f"The ASCII interface already refuses LOAD before the test ({probe}). Restart the A3200 "
                    f"software, then run 'sticky' again. Stopped.")
        sys.exit(1)

    attempt("1 valid program A (baseline)", ok_a)
    attempt("2 invalid program (provokes the refusal)", bad)
    attempt("3 valid program B (other name)", ok_b)
    write_program(bad, ["' now valid under the name of the failed program", "DWELL 0.01", "END PROGRAM"])
    attempt("4 valid content under the failed name", bad)
    attempt("5 valid program A again", ok_a)
    ascii_client.close()
    try:
        lib = Library(args.dll)
        ok, error = lib.load(task_id, ok_b)
        lib.stop_and_wait(task_id)
        lib.remove(ok_b.name)
        lib.close()
        session.record("sticky", {"attempt": "6 library load while ASCII refuses", "ok": ok, "error": error})
        session.log(f"{'6 library load of program B':<45} ok={ok} {error}")
    except (OSError, RuntimeError) as error:
        session.log(f"6 library not usable: {error}")
    session.log("Restart the A3200 software before printing over the ASCII interface again.")


# ------------------------------------------------------------------------------------- lab session 2 (T134)

def find_files(roots: list[str], patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for root in map(Path, roots):
        if root.is_dir():
            for pattern in patterns:
                found += root.rglob(pattern)
    return sorted(set(found))


DOTNET_SCRIPT = r"""
$ErrorActionPreference = 'Continue'
foreach ($p in Get-ChildItem -Path '{folder}' -Filter 'Aerotech*.dll') {{
  try {{ $a = [Reflection.Assembly]::LoadFrom($p.FullName) }} catch {{ "LOADFAIL $($p.Name): $($_.Exception.Message)"; continue }}
  try {{ $types = $a.GetTypes() }} catch [Reflection.ReflectionTypeLoadException] {{ $types = $_.Exception.Types | Where-Object {{ $_ }} }}
  "ASSEMBLY $($p.Name) $($a.GetName().Version)"
  foreach ($t in $types) {{
    if (-not $t.IsPublic) {{ continue }}
    "TYPE $($t.FullName)"
    foreach ($m in $t.GetMethods([Reflection.BindingFlags]'Public,Instance,Static,DeclaredOnly')) {{
      if ($m.Name -match 'Compil|Load|Program|Reset|Associate|Remove|Add|Run|Build') {{
        "  $($m.ReturnType.Name) $($m.Name)(" + (($m.GetParameters() | ForEach-Object {{ "$($_.ParameterType.Name) $($_.Name)" }}) -join ', ') + ")"
      }}
    }}
  }}
}}
"""


def step_api(session: Session, args) -> None:
    """ Copy headers, list the functions T129/T131/T133 need, dump the .NET API and the configuration files. """

    target = session.folder / "api"
    (target / "include").mkdir(parents=True, exist_ok=True)
    headers = find_files(SEARCH_ROOTS, ["A3200*.h"])
    for header in headers:
        shutil.copy2(header, target / "include" / header.name)
    text = "\n".join(h.read_text(errors="replace") for h in headers)
    names = sorted(set(re.findall(
        r"\b(A3200\w*(?:Reset|Added|Associate|Compil|Acknowledge|Fault|ParameterGet|ParameterSet|Initialize)\w*)\s*\(",
        text)))
    session.log(f"{len(headers)} headers copied to {target / 'include'}; functions of interest:")
    found = {}
    for name in names:
        found[name] = prototype(text, name)
        session.log(f"  {found[name] or name + ': prototype not parsed'}")
    struct = re.search(r"typedef\s+struct\s*\w*\s*\{[^}]*\}\s*A3200AddedProgram\s*;", text, re.S)
    session.log("A3200AddedProgram: " + (" ".join(struct.group(0).split()) if struct else "not found"))
    reset_ok = bool(re.search(RESET_SIGNATURE, text))
    exported = None
    try:
        lib = Library(args.dll)
        exported = lib.exported("A3200Reset")
        lib.close()
    except (OSError, RuntimeError) as error:
        session.log(f"Library not usable: {error}")
    session.log(f"A3200Reset: prototype as expected = {reset_ok}, exported by the DLL = {exported}")

    # Controller configuration and compiler files (parameter files, AerParam.pgm of the compiler error)
    config_files = find_files(SEARCH_ROOTS + CONFIG_ROOTS, ["AerParam*", "*.prm*"])
    (target / "config").mkdir(exist_ok=True)
    copied = []
    for i, path in enumerate(config_files):
        if path.is_file() and path.stat().st_size < 20e6:
            destination = target / "config" / f"{i:03d}_{path.name}"
            shutil.copy2(path, destination)
            copied.append({"source": str(path), "copy": destination.name, "bytes": path.stat().st_size})
    listing = [f"{p.stat().st_size:>12}  {p}" for root in CONFIG_ROOTS if Path(root).is_dir()
               for p in list(Path(root).rglob("*"))[:3000] if p.is_file()]
    (target / "config_files.txt").write_text("\n".join(listing), encoding="utf-8")
    session.log(f"{len(copied)} configuration files copied, {len(listing)} files listed in config_files.txt")

    # .NET API (Motion Composer is a .NET program; its compile path needs a third of the C library's memory)
    assemblies = [p for p in find_files(SEARCH_ROOTS, ["Aerotech.A3200.dll"])]
    dotnet = {}
    if assemblies:
        script = DOTNET_SCRIPT.format(folder=str(assemblies[0].parent))
        shells = {"64": "powershell",
                  "32": str(Path(os.environ.get("WINDIR", r"C:\Windows")) /
                            r"SysWOW64\WindowsPowerShell\v1.0\powershell.exe")}
        for bits, shell in shells.items():
            out = subprocess.run([shell, "-NoProfile", "-Command", script], capture_output=True)
            dump = out.stdout.decode("utf-8", errors="replace")
            (target / f"dotnet_{bits}bit.txt").write_text(dump + out.stderr.decode("utf-8", errors="replace"),
                                                         encoding="utf-8")
            dotnet[bits] = {"lines": len(dump.splitlines()), "compile_methods": [
                line.strip() for line in dump.splitlines() if re.search(r"(?i)compil", line)][:50]}
            session.log(f".NET dump ({bits} bit): {dotnet[bits]['lines']} lines; compile methods: "
                        f"{dotnet[bits]['compile_methods'][:10]}")
    else:
        session.log("Aerotech.A3200.dll not found")
    session.record("api", {"headers": [str(h) for h in headers], "functions": found,
                           "added_program_struct": struct.group(0) if struct else None,
                           "reset_prototype_ok": reset_ok, "reset_exported": exported,
                           "config_files": copied, "dotnet": dotnet})


def load_part(session: Session, args, path: Path, task_id: int, *, source_lines: Optional[int] = None,
              mode: str = "load") -> dict:
    result = worker_result(run_worker(path, task_id, args.dll, keep=True, source_lines=source_lines, mode=mode))
    session.log(f"  {mode} {path.name} on task {task_id}: ok={result.get('ok')} {result.get('load_s')} s, "
                f"peak {result.get('memory_after_load', {}).get('peak_private_gb')} GB, {result.get('kb_per_line')} "
                f"kB/line, added {result.get('added_before')} -> {result.get('added_after')} {result.get('error', '')}")
    return result


def unload_part(session: Session, lib: Library, path: Path, task_id: int) -> dict:
    stopped = lib.stop_and_wait(task_id)
    name, attempts = lib.remove_verified(path)
    session.log(f"  removed {path.name}: as {name!r} (attempts {[a['name'] for a in attempts]}), "
                f"added programs now {lib.added_programs()}")
    return {"stopped": stopped, "removed_as": name, "remove_attempts": attempts, "state": lib.state(task_id)}


def step_ogm_clean(session: Session, args) -> None:
    """ Compile a part through the library, then load its ``.OGM`` and a renamed copy under never-used names. """

    stamp = datetime.datetime.now().strftime("%H%M%S")
    folder = session.programs / f"ogm_clean_{stamp}"
    lines = (truncated_program(read_lines(Path(args.file)), args.lines) if args.file
             else synthetic_program(args.lines, title="ogm clean"))
    pgm = write_program(folder / f"ogmclean_{stamp}.pgm", lines)
    lib = Library(args.dll)
    require_idle(lib, args.task, session)
    ok, text = fits_budget(session, len(lines), args.budget_gb)
    if not ok:
        session.log(f"Over budget ({text}); choose fewer --lines. Stopped.")
        sys.exit(1)
    session.log(f"ogm-clean with {pgm.name} ({len(lines)} lines) on task {args.task}")
    record: dict = {"source": str(pgm), "lines": len(lines), "added_at_start": lib.added_programs()}
    record["compile"] = load_part(session, args, pgm, args.task)
    record["compile"].update(unload_part(session, lib, pgm, args.task))
    ogm = compiled_file(pgm)
    record["ogm"] = str(ogm) if ogm else None
    if ogm is None:
        session.log(f"No .OGM next to {pgm.name}; files: {[p.name for p in folder.iterdir()]}. Stopped.")
        session.record("ogm_clean", record)
        return
    record["ogm_mb"] = round(ogm.stat().st_size / 1e6, 1)
    record["load_ogm"] = load_part(session, args, ogm, args.task, source_lines=len(lines))
    record["load_ogm"].update(unload_part(session, lib, ogm, args.task))
    copy = folder / f"ogmcopy_{stamp}.ogm"
    shutil.copy2(ogm, copy)
    record["load_copy"] = load_part(session, args, copy, args.task, source_lines=len(lines))
    record["load_copy"].update(unload_part(session, lib, copy, args.task))
    record["added_at_end"] = lib.added_programs()
    lib.close()
    session.record("ogm_clean", record)
    session.log(f"Compile {record['compile'].get('load_s')} s vs. .ogm {record['load_ogm'].get('load_s')} s; "
                f"names that removed them: {record['compile']['removed_as']!r}, {record['load_ogm']['removed_as']!r}, "
                f"{record['load_copy']['removed_as']!r}")
    for path in folder.iterdir():
        path.unlink(missing_ok=True)


def step_add_associate(session: Session, args) -> None:
    """ ``A3200ProgramAdd`` without a task, then ``A3200ProgramAssociate`` to the task (prefetch without a free task). """

    stamp = datetime.datetime.now().strftime("%H%M%S")
    pgm = write_program(session.programs / f"addassoc_{stamp}.pgm", synthetic_program(args.lines, title="add"))
    lib = Library(args.dll)
    require_idle(lib, args.task, session)
    ok, text = fits_budget(session, args.lines, args.budget_gb)
    if not ok:
        session.log(f"Over budget ({text}); choose fewer --lines. Stopped.")
        sys.exit(1)
    session.log(f"add-associate with {pgm.name} ({args.lines} lines) on task {args.task}")
    result = load_part(session, args, pgm, args.task, mode="add")
    session.log(f"  add {result.get('add_s')} s (added {result.get('added_before')} -> "
                f"{result.get('added_after_add')}, task {result.get('state_after_add')}), associate "
                f"{result.get('associate_s')} s: {result.get('associations')}")
    result.update(unload_part(session, lib, pgm, args.task))
    lib.close()
    session.record("add_associate", result)
    for path in session.programs.glob(f"addassoc_{stamp}.*"):
        path.unlink(missing_ok=True)


def step_hold(session: Session, args) -> None:
    """ Two programs loaded on tasks 1 and 2 at once; the operator reads the INtime memory. """

    files = [Path(args.file), Path(args.file2)]
    lib = Library(args.dll)
    for task_id in (1, 2):
        require_idle(lib, task_id, session)
    notes = {"before": input("INtime memory before loading (as shown by the INtime tool, free/used): ")}
    results = []
    for task_id, path in zip((1, 2), files):
        lines = source_line_count(path)
        if path.suffix.lower() != ".ogm":
            ok, text = fits_budget(session, lines or 0, args.budget_gb)
            if not ok:
                session.log(f"{path.name} over budget ({text}). Stopped.")
                break
        results.append(load_part(session, args, path, task_id, source_lines=lines))
    notes["loaded"] = input("INtime memory with both programs loaded: ")
    for task_id, path in zip((1, 2), files[:len(results)]):
        results[task_id - 1].update(unload_part(session, lib, path, task_id))
    notes["after"] = input("INtime memory after removing both: ")
    lib.close()
    session.record("hold", {"files": [str(f) for f in files], "results": results, "intime_memory": notes})


def run_and_wait(lib: Library, ascii_client: Optional[Ascii], task_id: int) -> tuple[str, Optional[int], float]:
    lib.start(task_id)
    started = time.time()
    state, last_line = lib.state(task_id), None
    while state in ("program_running", "program_ready"):
        if state == "program_ready" and time.time() - started > 30:
            break  # START had no effect
        time.sleep(0.5)
        state = lib.state(task_id)
    if ascii_client:
        last_line = ascii_client.line(task_id)
    return state, last_line, round(time.time() - started, 1)


def step_taskspeed(session: Session, args) -> None:
    """ Dry: the same synthetic program on task 1 and task 2, bare header and real layer header (T132). """

    if not args.axes_safe:
        session.log("taskspeed moves the galvo axes A/B (laser gate forced off). Close the shutter, make sure the "
                    "galvo may move, then repeat with --axes-safe.")
        sys.exit(1)
    lib = Library(args.dll)
    for task_id in (1, 2):
        require_idle(lib, task_id, session)
    ascii_client = try_ascii(args.reply_timeout)
    rows = []
    for style in ("bare", "real"):
        path = write_program(session.programs / f"taskspeed_{style}.pgm",
                             synthetic_program(args.speed_lines, header_style=style, title=f"taskspeed {style}"))
        expected = count_lines(path)
        for task_id in (1, 2):
            loaded = load_part(session, args, path, task_id)
            if not loaded.get("ok"):
                session.log("Load failed; the step stops.")
                break
            state, last_line, run_s = run_and_wait(lib, ascii_client, task_id)
            row = {"header": style, "task": task_id, "state": state, "last_line": last_line, "file_lines": expected,
                   "run_s": run_s, "ms_per_line": round(1000 * run_s / expected, 3)}
            row.update(unload_part(session, lib, path, task_id))
            rows.append(row)
            session.record("taskspeed", row)
            session.log(f"{style:<5} header, task {task_id}: {state}, line {last_line} of {expected}, {run_s} s "
                        f"({row['ms_per_line']} ms per line)")
        path.unlink(missing_ok=True)
    if ascii_client:
        ascii_client.close()
    lib.close()
    for style in ("bare", "real"):
        times = {r["task"]: r["run_s"] for r in rows if r["header"] == style}
        if 1 in times and 2 in times:
            session.log(f"{style} header: task 2 / task 1 = {times[2] / times[1]:.2f}")


def step_runner(session: Session, args) -> None:
    """ Dry: the package's LibraryLoader + ProgramRunner (T129) with synthetic galvo parts on task 1 (add-ahead, T132). """

    if not args.axes_safe:
        session.log("runner moves the galvo axes A/B (laser gate forced off). Close the shutter, make sure the galvo "
                    "may move, then repeat with --axes-safe.")
        sys.exit(1)
    import logging
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface
    from nanofactorysystem.devices.aerotech.loader import LibraryLoader, MemoryBudget, ProgramRunner

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    folder = session.programs / "runner"
    parts = [write_program(folder / f"runner_part{k + 1}of{args.parts}.pgm",
                           synthetic_program(args.lines, segment_um=args.segment_um, title=f"runner part {k + 1}"))
             for k in range(args.parts)]
    api = AerotechAsciiInterface(load_timeout=args.reply_timeout)
    try:
        api.connect()
        loader = LibraryLoader(args.dll)
    except (OSError, RuntimeError) as exc:
        session.log(f"Controller not usable ({type(exc).__name__}: {exc}). Stopped.")
        sys.exit(1)
    runner = ProgramRunner(loader, api, MemoryBudget(budget_gb=args.budget_gb), exec_dir=folder / "exec",
                           logger=logging.getLogger("runner"))
    session.log(f"runner: {args.parts} parts of {args.lines} lines through the package loader")
    error = ""
    try:
        runner.run([(k, [part]) for k, part in enumerate(parts)])
    except Exception as exc:  # record every failure of the integrated path
        error = f"{type(exc).__name__}: {exc}"
        session.log(f"runner failed: {error}")
    finally:
        loader.close()
        api.close()
    for record in runner.records:
        session.record("runner_part", {k: v for k, v in vars(record).items()})
        session.log(f"  part {record.part} task {record.task}: load {record.load_s} s, waited "
                    f"{record.waited_for_load_s} s, run {record.run_s} s, gap {record.gap_s} s, last line "
                    f"{record.last_line}, PC {record.used_gb} GB")
    session.record("runner", {"parts": args.parts, "lines": args.lines, "completed": len(runner.records),
                              "error": error})
    for part in parts:
        part.unlink(missing_ok=True)


def confirmed(phrase: str, text: str) -> bool:
    print(text)
    return input(f"Type {phrase} to continue: ").strip() == phrase


def wait_until(check, timeout_s: float, interval_s: float = 2.0) -> Optional[float]:
    """ Seconds until ``check()`` is true, ``None`` after ``timeout_s``. """

    start = time.time()
    while time.time() - start < timeout_s:
        if check():
            return round(time.time() - start, 1)
        time.sleep(interval_s)
    return None


def ascii_reachable() -> bool:
    client = try_ascii(5)
    if client is None:
        return False
    client.close()
    return True


def library_usable(dll: str) -> bool:
    try:
        Library(dll).close()
        return True
    except (OSError, RuntimeError):
        return False


def step_recover_ascii(session: Session, args) -> None:
    """ Recovery level R1: terminate the ASCII interface process; is it started again and does LOAD work? """

    if not args.confirm or not confirmed("R1", "R1 terminates A3200AsciiInterface.exe (no motion; every "
                                                      "ASCII client loses its connection)."):
        session.log("R1 needs --confirm and the typed confirmation. Stopped.")
        sys.exit(1)
    record = {"before": controller_snapshot(args.dll, args.reply_timeout),
              "probe_before": ascii_load_probe(session.programs, args.task, args.reply_timeout)}
    old = pid_of("A3200AsciiInterface.exe")
    out = subprocess.run(["taskkill", "/PID", str(old), "/F"], capture_output=True) if old else None
    record["taskkill"] = out.stdout.decode(errors="replace") + out.stderr.decode(errors="replace") if out else "no PID"
    session.log(f"R1: terminated PID {old}: {record['taskkill'].strip()}")
    record["respawn_s"] = wait_until(lambda: (pid_of("A3200AsciiInterface.exe") or old) != old, args.wait_s)
    record["ascii_reachable_s"] = wait_until(lambda: ascii_reachable(), 60) \
        if record["respawn_s"] is not None else None
    record["probe_after"] = ascii_load_probe(session.programs, args.task, args.reply_timeout)
    record["after"] = controller_snapshot(args.dll, args.reply_timeout)
    session.record("recover_ascii", record)
    session.log(f"R1: started again after {record['respawn_s']} s, ASCII reachable after "
                f"{record['ascii_reachable_s']} s, LOAD probe before {record['probe_before'].get('ok')} after "
                f"{record['probe_after'].get('ok')}")
    if record["respawn_s"] is None:
        session.log("The ASCII interface was not started again: run 'restart-service --confirm' as administrator "
                    "or restart the A3200 software.")


def step_reset(session: Session, args) -> None:
    """ Recovery level R2: controller reset (``~RESETCONTROLLER`` over ASCII or ``A3200Reset``), states before/after.

    ``~RESETCONTROLLER`` is the documented ASCII command with the function of "Reset Controller" in Motion
    Composer; the interface answers when the reset is complete. The library path is used only if the
    installed headers declare ``A3200Reset(A3200Handle)``.
    """

    if args.reset_via == "library":
        headers = "\n".join(h.read_text(errors="replace") for h in find_files(SEARCH_ROOTS, ["A3200*.h"]))
        if not re.search(RESET_SIGNATURE, headers):
            session.log(f"A3200Reset(A3200Handle) not found in the installed headers "
                        f"({prototype(headers, 'A3200Reset')}). Not called; use --reset-via ascii.")
            sys.exit(1)
    warning = ("R2 resets the controller like 'Reset Controller' in Motion Composer. Axes may be disabled and lose "
               "their home; a Z axis without brake may move when disabled. Move the objective to a safe Z first, "
               "close the shutter.")
    if not args.confirm or not confirmed("RESET", warning):
        session.log("R2 needs --confirm and the typed confirmation. Stopped.")
        sys.exit(1)
    lib = Library(args.dll)
    for task_id in (1, 2):
        if lib.state(task_id) == "program_running":
            session.log(f"Task {task_id} is running. Stopped.")
            sys.exit(1)
    lib.close()
    record = {"before": controller_snapshot(args.dll, args.reply_timeout), "via": args.reset_via}
    start = time.time()
    if args.reset_via == "library":
        lib = Library(args.dll)
        ok, error = lib.reset()
        lib.close()
    else:
        client = try_ascii(args.wait_s)
        if client is None:
            session.log("ASCII interface not reachable; use --reset-via library. Stopped.")
            sys.exit(1)
        try:
            code, data, _ = client.send("~RESETCONTROLLER")
            ok = code == "%"
            error = "" if ok else f"{code}{data} {client.last_error()}"
        except (TimeoutError, OSError) as exc:
            ok, error = False, f"no reply within {args.wait_s} s ({exc})"
        client.close()
    record.update(reset_ok=ok, reset_error=error, reset_call_s=round(time.time() - start, 1))
    record["library_usable_s"] = wait_until(lambda: library_usable(args.dll), args.wait_s)
    record["ascii_reachable_s"] = wait_until(lambda: ascii_reachable(), args.wait_s)
    record["after"] = controller_snapshot(args.dll, args.reply_timeout)
    record["probe_after"] = ascii_load_probe(session.programs, args.task, args.reply_timeout)
    session.record("reset", record)
    session.log(f"R2: ok={ok} {error} in {record['reset_call_s']} s; library after {record['library_usable_s']} s, "
                f"ASCII after {record['ascii_reachable_s']} s")
    session.log(f"  axes before {record['before'].get('axes')}")
    session.log(f"  axes after  {record['after'].get('axes')}")
    session.log(f"  added programs {record['before'].get('added_programs')} -> {record['after'].get('added_programs')}"
                f", LOAD probe after: {record['probe_after'].get('ok')}")


def step_restart_service(session: Session, args) -> None:
    """ Recovery level R3: restart the A3200 service (administrator), states before and after. """

    warning = ("R3 restarts the Windows service A3200CommService (needs an administrator PowerShell). All A3200 "
               "connections are lost; Motion Composer must be closed. Axes may be disabled afterwards.")
    if not args.confirm or not confirmed("RESTART", warning):
        session.log("R3 needs --confirm and the typed confirmation. Stopped.")
        sys.exit(1)
    record = {"before": controller_snapshot(args.dll, args.reply_timeout)}
    start = time.time()
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "Restart-Service -Name A3200CommService -Force"],
                         capture_output=True)
    record.update(restart_s=round(time.time() - start, 1), returncode=out.returncode,
                  output=(out.stdout + out.stderr).decode(errors="replace").strip())
    session.log(f"R3: Restart-Service returned {out.returncode} after {record['restart_s']} s {record['output']}")
    record["ascii_reachable_s"] = wait_until(lambda: ascii_reachable(), args.wait_s)
    record["library_usable_s"] = wait_until(lambda: library_usable(args.dll), args.wait_s)
    record["after"] = controller_snapshot(args.dll, args.reply_timeout)
    record["probe_after"] = ascii_load_probe(session.programs, args.task, args.reply_timeout)
    session.record("restart_service", record)
    session.log(f"R3: ASCII after {record['ascii_reachable_s']} s, library after {record['library_usable_s']} s, "
                f"LOAD probe after: {record['probe_after'].get('ok')}")
    session.log(f"  axes before {record['before'].get('axes')}")
    session.log(f"  axes after  {record['after'].get('axes')}")


def step_watch(session: Session, args) -> None:
    path = session.folder / f"watch_{datetime.datetime.now():%H%M%S}.csv"
    session.log(f"Memory log every {args.interval} s into {path.name}; stop with Ctrl+C")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "pc_used_gb", "pc_available_gb", "process", "pid", "working_set_gb", "private_gb"])
        try:
            while True:
                now = datetime.datetime.now().isoformat(timespec="seconds")
                memory = system_memory()
                writer.writerow([now, memory["used_gb"], memory["available_gb"], "PC", "", "", ""])
                for proc in processes():
                    mem = process_memory(proc["pid"]) or {}
                    writer.writerow([now, "", "", proc["name"], proc["pid"], mem.get("working_set_gb"),
                                     mem.get("private_gb")])
                f.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            session.log("Memory log stopped.")


STEPS = {"system": step_system, "ladder": step_ladder, "precision": step_precision, "ogm": step_ogm,
         "cycle": step_cycle, "sticky": step_sticky, "watch": step_watch,
         "api": step_api, "ogm-clean": step_ogm_clean, "add-associate": step_add_associate, "hold": step_hold,
         "taskspeed": step_taskspeed, "runner": step_runner, "recover-ascii": step_recover_ascii, "reset": step_reset,
         "restart-service": step_restart_service}


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=[*STEPS, "_worker"])
    parser.add_argument("--file", help="layer program (ladder, ogm-clean), .ogm (ogm), first program (hold)")
    parser.add_argument("--file2", help="second program (hold)")
    parser.add_argument("--speed-lines", type=int, default=100_000, help="lines per program (taskspeed)")
    parser.add_argument("--reply-timeout", type=float, default=ASCII_REPLY_TIMEOUT,
                        help="seconds to wait for an ASCII reply (default 60)")
    parser.add_argument("--no-probe", action="store_true", help="system: skip the ASCII LOAD probe")
    parser.add_argument("--confirm", action="store_true", help="recover-ascii, reset, restart-service")
    parser.add_argument("--wait-s", type=float, default=180.0, help="seconds to wait for a recovery (default 180)")
    parser.add_argument("--reset-via", choices=["ascii", "library"], default="ascii",
                        help="reset: ~RESETCONTROLLER over ASCII (default) or A3200Reset through the library")
    parser.add_argument("--mode", choices=["load", "add"], default="load", help=argparse.SUPPRESS)
    parser.add_argument("--source-lines", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--task", type=int, default=2, help="task for load-only steps (default 2)")
    parser.add_argument("--sizes", type=lambda s: [int(x) for x in s.split(",")],
                        default=[50_000, 100_000, 200_000, 400_000, 800_000], help="ladder sizes in lines")
    parser.add_argument("--lines", type=int, default=200_000, help="lines per synthetic program (precision, cycle)")
    parser.add_argument("--parts", type=int, default=4, help="parts in the cycle")
    parser.add_argument("--segment-um", type=float, default=2.0, help="galvo step of the synthetic programs")
    parser.add_argument("--budget-gb", type=float, default=22.0, help="memory budget of the whole PC")
    parser.add_argument("--axes-safe", action="store_true", help="confirm that the galvo may move (cycle)")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between samples (watch)")
    parser.add_argument("--dll", default=DLL_DEFAULT)
    parser.add_argument("--keep", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--session", type=Path, default=None, help="session folder (default: one per day)")
    args = parser.parse_args(argv)

    if args.step == "_worker":
        worker(args)
        return
    if args.step in ("ladder", "ogm", "hold") and (not args.file or not Path(args.file).is_file()):
        parser.error("--file must name an existing program file")
    if args.step == "hold" and (not args.file2 or not Path(args.file2).is_file()):
        parser.error("--file2 must name an existing program file")
    if args.step == "ogm-clean" and args.file and not Path(args.file).is_file():
        parser.error("--file must name an existing program file")
    session = Session(args.session or Path.cwd() / f"program_loading_lab_{datetime.date.today():%Y%m%d}")
    session.log(f"=== step {args.step} {' '.join(sys.argv[2:])}")
    STEPS[args.step](session, args)
    print(f"\nResults in {session.folder}")


if __name__ == "__main__":
    main()
