"""Lab tests for loading layer programs through the A3200 C library within a memory budget (T129).

Procedure and background: ``docs/guides/PROGRAM_LOADING_LAB_TESTS.md``; work order: ``docs/design/PROGRAM_LOADING.md``.

Known from ``library_load_check.py`` (2026-11-24): the ASCII interface (``A3200AsciiInterface.exe``, 32 bit)
cannot compile large programs; ``A3200ProgramLoad`` from 64-bit Python loads the full DOE layer 68
(1.25 M lines) in 129 s with a 19.3 GB peak in the loading process. The planned loader compiles in a
short-lived worker process, alternates tasks 1 and 2 (load the next part while the current one runs),
and keeps the PC below a memory budget (32 GB RAM, at most 20-25 GB used). These steps measure what
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
DEFAULT_KB_PER_LINE = 16.0  # 19.3 GB / 1.25 M lines measured on 2026-11-24, rounded up


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
    """ Matching processes with name, PID, parent, command line (PowerShell CIM query). """

    script = ("Get-CimInstance Win32_Process | Select-Object Name,ProcessId,ParentProcessId,CommandLine "
              "| ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    try:
        rows = json.loads(out.stdout.decode("utf-8", errors="replace") or "[]")
    except json.JSONDecodeError:
        return []
    rows = rows if isinstance(rows, list) else [rows]
    return [{"name": r["Name"], "pid": r["ProcessId"], "parent": r["ParentProcessId"],
             "command_line": r.get("CommandLine")} for r in rows if re.search(pattern, r.get("Name") or "")]


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
                      feed: float = 5.0, title: str = "synthetic") -> list[str]:
    """ Dry galvo program: laser gate forced off, axes A and B only, no stage axes, exactly ``n_lines`` lines.

    The galvo sweeps in ``segment_um`` steps between -0.05 and +0.05 mm and moves 1 µm in B per sweep.
    """

    header = [f"' {title}: dry galvo program (laser gate off, axes A/B only), program_loading_lab.py",
              "ABSOLUTE", "VELOCITY ON", "GALVO LASEROVERRIDE A OFF", f"F{feed:g}", "RAPID A0 B0"]
    footer = ["GALVO LASEROVERRIDE A OFF", "END PROGRAM"]
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
        }
        for name, argtypes in signatures.items():
            getattr(lib, name).argtypes = argtypes
            getattr(lib, name).restype = ctypes.c_int
        self.handle = ctypes.c_void_p()
        self._check(lib.A3200Connect(ctypes.byref(self.handle)), "A3200Connect")

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

    def __init__(self, timeout: float = 600.0):
        self.sock = socket.create_connection((ASCII_HOST, ASCII_PORT), timeout=10)
        self.sock.settimeout(timeout)

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


def try_ascii() -> Optional[Ascii]:
    try:
        return Ascii()
    except OSError:
        return None


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


def run_worker(path: Path, task_id: int, dll: str, keep: bool) -> subprocess.Popen:
    cmd = [sys.executable, __file__, "_worker", "--file", str(path), "--task", str(task_id), "--dll", dll]
    if keep:
        cmd.append("--keep")
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
    result = {"file": str(path), "task": task_id, "lines": count_lines(path),
              "mb": round(path.stat().st_size / 1e6, 1), "state_before": lib.state(task_id),
              "added_before": lib.added_programs(), "memory_before": process_memory()}
    start = time.time()
    ok, error = lib.load(task_id, path)
    result.update(ok=ok, error=error, load_s=round(time.time() - start, 1), memory_after_load=process_memory(),
                  state_after=lib.state(task_id), added_after=lib.added_programs())
    peak = result["memory_after_load"]["peak_private_gb"] - result["memory_before"]["private_gb"]
    result["kb_per_line"] = round(peak * GB / 1024 / max(result["lines"], 1), 2) if ok else None
    if not args.keep:
        result["stopped"] = lib.stop_and_wait(task_id)
        result["removed"], result["remove_error"] = lib.remove(path.name)
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
                    f"WS {mem.get('working_set_gb', '?')} GB  private {mem.get('private_gb', '?')} GB")
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
    session.log(f"Task states: {tasks}; programs added on the controller: {added}")
    ascii_client = try_ascii()
    ascii_state = "not reachable"
    if ascii_client:
        code, data, _ = ascii_client.send("~STATUS (1, TaskState)")
        ascii_state = f"reply {code}{data}"
        ascii_client.close()
    session.log(f"ASCII interface: {ascii_state}")
    session.record("system", {"memory": memory, "processes": rows, "services": svc, "tasks": tasks,
                              "added_programs": added, "ascii": ascii_state})


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
    ascii_client = try_ascii()
    if ascii_client is None:
        session.log("ASCII interface not reachable. Stopped.")
        sys.exit(1)
    task_id = args.task

    def attempt(label: str, path: Path) -> None:
        code, data, seconds = ascii_client.send(f'PROGRAM {task_id} LOAD "{path.resolve()}"')
        error = ascii_client.last_error() if code != "%" else ""
        ascii_client.send(f"PROGRAM {task_id} STOP")
        removed = ascii_client.send(f'REMOVEPROGRAM "{path.name}"')[0]
        session.record("sticky", {"attempt": label, "file": path.name, "reply": code + data,
                                  "seconds": round(seconds, 2), "error": error, "remove_reply": removed})
        session.log(f"{label:<45} reply '{code}{data}' after {seconds:.2f} s {error}")

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
         "cycle": step_cycle, "sticky": step_sticky, "watch": step_watch}


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=[*STEPS, "_worker"])
    parser.add_argument("--file", help="layer program (ladder), .ogm (ogm)")
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
    if args.step in ("ladder", "ogm") and (not args.file or not Path(args.file).is_file()):
        parser.error("--file must name an existing program file")
    session = Session(args.session or Path.cwd() / f"program_loading_lab_{datetime.date.today():%Y%m%d}")
    session.log(f"=== step {args.step} {' '.join(sys.argv[2:])}")
    STEPS[args.step](session, args)
    print(f"\nResults in {session.folder}")


if __name__ == "__main__":
    main()
