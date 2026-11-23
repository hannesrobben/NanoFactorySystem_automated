"""Lab check: does loading a large layer program through the A3200 C library work where ``PROGRAM LOAD`` fails?

Background (DOE print, 2026-11-21/22): ``PROGRAM 1 LOAD "<file>"`` sent over the ASCII command interface
(TCP port 8000) failed with "An out of memory error occurred." for layer programs above about 80 000 lines.
After that first failure every further LOAD was refused within 0.4 s until the A3200 software was restarted.
On 2026-11-23 the maintainer loaded the full layer programs 69 and 68 (millions of lines) by hand in
Motion Composer 6.04.005 on tasks 1 and 2, without any problem. The task ran as "Program Running", not in queue mode.

Hypothesis: the ASCII command interface compiles the program inside the process that serves port 8000
(possibly a 32-bit process with 2-4 GB address space), whereas Motion Composer compiles through the A3200
library in its own process. If that holds, loading through the C library from Python (``A3200C64.dll``)
works like Motion Composer, and the program does not have to be split.

The script is standalone (standard library only), so it can be copied to the lab PC on its own.
Loading a program moves nothing and switches no laser; the script never starts a program.

Steps (run them in this order, each writes into the report folder):

1. ``python library_load_check.py inspect``
   Finds the A3200 libraries and headers, prints the prototypes of the program functions, and reports
   which process serves port 8000 (name, 32/64 bit, memory) plus every Aerotech-like process.
   Safe at any time, also while a program runs.
2. ``python library_load_check.py load --file <layer program> --task 3``
   Loads the file through the C library on an idle task (default 3, never a busy task), measures the
   time and the memory of this Python process and of the port-8000 process, reads the task state,
   then stops the task and removes the program again. Run it after the running layer has finished,
   or accept that the compiler shares the Windows cores with the running print.
3. Optional, last: ``python library_load_check.py ascii-load --file <same file> --task 3``
   The same file with ``PROGRAM <task> LOAD`` over the ASCII interface, with memory sampling.
   If this fails with "out of memory", the ASCII load path is likely broken until the A3200 software
   is restarted. Restart before printing again.

Send the report folder ``library_load_check_<timestamp>`` back.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

ASCII_HOST, ASCII_PORT = "127.0.0.1", 8000
SEARCH_ROOTS = [r"C:\Program Files (x86)\Aerotech", r"C:\Program Files\Aerotech"]
FUNCTIONS = ["A3200Connect", "A3200Disconnect", "A3200ProgramLoad", "A3200ProgramRun", "A3200ProgramStart",
             "A3200ProgramStop", "A3200ProgramBufferedRun", "A3200GetLastErrorString", "A3200GetLastError"]
# Prototypes the "load" step relies on; checked against the installed headers before any call
EXPECTED = {
    "A3200Connect": r"A3200Connect\s*\(\s*A3200Handle\s*\*\s*\w+\s*\)",
    "A3200ProgramLoad": r"A3200ProgramLoad\s*\(\s*A3200Handle\s+\w+\s*,\s*TASKID\s+\w+\s*,\s*LPCSTR\s+\w+\s*\)",
    "A3200Disconnect": r"A3200Disconnect\s*\(\s*A3200Handle\s+\w+\s*\)",
}
TASK_STATES = {0: "unavailable", 1: "inactive", 2: "idle", 3: "program_ready", 4: "program_running",
               5: "programfeed_held", 6: "program_paused", 7: "program_complete", 8: "error", 9: "queue"}
PROCESS_PATTERN = r"(?i)a3200|aerotech|composer|smc|intime|nanofactory"


# ----------------------------------------------------------------------------------------------- helpers

class Report:
    """ Collects results and writes them as JSON and text into the report folder. """

    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lines: list[str] = []
        self.data: dict = {}

    def say(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def save(self, step: str) -> None:
        (self.folder / f"{step}.txt").write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        (self.folder / f"{step}.json").write_text(json.dumps(self.data, indent=2, default=str), encoding="utf-8")
        print(f"\nReport written to {self.folder}")


def run(cmd: list[str]) -> str:
    """ Output of a console command (decoded leniently: German Windows uses cp850). """

    out = subprocess.run(cmd, capture_output=True)
    return out.stdout.decode("cp850", errors="replace")


def parse_listening_pid(netstat_output: str, port: int) -> Optional[int]:
    """ PID of the process listening on ``port`` in the output of ``netstat -ano -p TCP``. """

    for line in netstat_output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1].endswith(f":{port}") \
                and parts[2].endswith(":0"):
            return int(parts[-1])
    return None


def parse_tasklist(tasklist_csv: str) -> list[dict]:
    """ Rows of ``tasklist /fo csv /nh``: image name, PID and working set in kB. """

    rows = []
    for line in tasklist_csv.splitlines():
        fields = re.findall(r'"([^"]*)"', line)
        if len(fields) >= 5 and fields[1].isdigit():
            memory_kb = int(re.sub(r"\D", "", fields[4]) or 0)
            rows.append({"name": fields[0], "pid": int(fields[1]), "working_set_mb": round(memory_kb / 1024, 1)})
    return rows


def processes() -> list[dict]:
    return parse_tasklist(run(["tasklist", "/fo", "csv", "/nh"]))


def process_memory_mb(pid: int) -> Optional[float]:
    rows = parse_tasklist(run(["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"]))
    return rows[0]["working_set_mb"] if rows else None


def process_bitness(pid: int) -> str:
    """ "32 bit", "64 bit", or why it is unknown (IsWow64Process on 64-bit Windows). """

    if struct.calcsize("P") != 8 and not os.environ.get("PROCESSOR_ARCHITEW6432"):
        return "unknown (32-bit Windows?)"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return f"unknown (access denied, error {ctypes.get_last_error()}; run as administrator)"
    try:
        wow64 = ctypes.c_int(0)
        if not kernel32.IsWow64Process(ctypes.c_void_p(handle), ctypes.byref(wow64)):
            return "unknown (IsWow64Process failed)"
        return "32 bit" if wow64.value else "64 bit"
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def find_files(roots: list[str], patterns: list[str]) -> list[Path]:
    found = []
    for root in map(Path, roots):
        if root.is_dir():
            for pattern in patterns:
                found += root.rglob(pattern)
    return sorted(set(found))


def extract_prototypes(header_text: str, names: list[str]) -> dict[str, str]:
    """ One-line declarations of the given functions in a C header. """

    text = re.sub(r"/\*.*?\*/", " ", header_text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    prototypes = {}
    for name in names:
        match = re.search(rf"[\w\s\*]*\b{name}\s*\([^;{{]*\)\s*;", text)
        if match:
            prototypes[name] = " ".join(match.group(0).split())
    return prototypes


def check_signatures(prototypes: dict[str, str]) -> list[str]:
    """ Names of the functions whose prototype differs from what ``load`` assumes. """

    return [name for name, pattern in EXPECTED.items()
            if name not in prototypes or not re.search(pattern, prototypes[name])]


class Ascii:
    """ Minimal client of the ASCII command interface (reply: return character + data + newline). """

    def __init__(self, host: str = ASCII_HOST, port: int = ASCII_PORT, timeout: float = 600.0):
        self.sock = socket.create_connection((host, port), timeout=10)
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

    def task(self, task_id: int) -> tuple[str, int]:
        code, data, _ = self.send(f"~STATUS ({task_id}, TaskState) ({task_id}, ProgramLineNumber)")
        if code != "%":
            return f"query refused ({code}{data})", -1
        state, line = data.split()[:2]
        return TASK_STATES.get(int(float(state)), state), int(float(line))

    def close(self) -> None:
        self.sock.close()


class MemorySampler(threading.Thread):
    """ Peak working set of some processes while a load runs. """

    def __init__(self, pids: dict[str, int], interval: float = 0.5):
        super().__init__(daemon=True)
        self.pids, self.interval = pids, interval
        self.peak = {name: 0.0 for name in pids}
        self.first: dict[str, Optional[float]] = {name: process_memory_mb(pid) for name, pid in pids.items()}
        self._halt = threading.Event()

    def run(self) -> None:
        while not self._halt.is_set():
            for name, pid in self.pids.items():
                value = process_memory_mb(pid)
                if value is not None:
                    self.peak[name] = max(self.peak[name], value)
            self._halt.wait(self.interval)

    def stop(self) -> dict:
        self._halt.set()
        self.join()
        return {name: {"before_mb": self.first[name], "peak_mb": self.peak[name],
                       "after_mb": process_memory_mb(pid)} for name, pid in self.pids.items()}


def count_lines(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 20), b""))


def port_owner() -> Optional[int]:
    return parse_listening_pid(run(["netstat", "-ano", "-p", "TCP"]), ASCII_PORT)


def idle_task_or_exit(ascii_client: Ascii, task_id: int, report: Report) -> None:
    state, line = ascii_client.task(task_id)
    report.say(f"Task {task_id} before the load: {state} (line {line})")
    report.data["task_before"] = state
    if state != "idle":
        report.say(f"Task {task_id} is not idle. Choose another task (--task) or wait. Nothing was loaded.")
        report.save("refused")
        sys.exit(1)


def unload(ascii_client: Ascii, task_id: int, name: str, report: Report) -> None:
    """ Stop the task, wait for idle, remove the program (the name given to the load, without path). """

    ascii_client.send(f"PROGRAM {task_id} STOP")
    for _ in range(100):
        if ascii_client.task(task_id)[0] == "idle":
            break
        time.sleep(0.1)
    code, data, _ = ascii_client.send(f'REMOVEPROGRAM "{name}"')
    report.say(f'REMOVEPROGRAM "{name}": {code}{data}  -> task {task_id}: {ascii_client.task(task_id)[0]}')


# ----------------------------------------------------------------------------------------------- steps

def inspect(report: Report) -> None:
    report.say(f"Python {sys.version.split()[0]}, {struct.calcsize('P') * 8} bit, {sys.executable}")
    libraries = find_files(SEARCH_ROOTS, ["A3200C*.dll", "Aerotech.A3200*.dll"])
    headers = find_files(SEARCH_ROOTS, ["A3200*.h"])
    report.say("\nA3200 libraries:")
    for path in libraries:
        report.say(f"  {path}")
    report.say(f"\nA3200 headers: {len(headers)} found")
    prototypes: dict[str, str] = {}
    for path in headers:
        found = extract_prototypes(path.read_text(errors="replace"), FUNCTIONS)
        for name, text in found.items():
            prototypes.setdefault(name, f"{text}    [{path.name}]")
    report.say("\nPrototypes:")
    for name in FUNCTIONS:
        report.say(f"  {prototypes.get(name, name + ': not found')}")
    taskid = next((m.group(0) for p in headers
                   if (m := re.search(r"typedef\s+enum\s*\w*\s*\{[^}]*TASKID_01[^}]*\}\s*TASKID\s*;",
                                      p.read_text(errors="replace"), re.S))), None)
    report.say("\nTASKID enum: " + (" ".join(taskid.split())[:300] if taskid else "not found"))
    mismatch = check_signatures({k: v.split("    [")[0] for k, v in prototypes.items()})
    report.say("Signatures used by 'load': " + ("as expected" if not mismatch else f"DIFFERENT for {mismatch}"))

    pid = port_owner()
    report.say(f"\nProcess listening on port {ASCII_PORT}: " + ("none (A3200 software running?)" if pid is None else ""))
    all_processes = processes()
    if pid is not None:
        row = next((r for r in all_processes if r["pid"] == pid), {"name": "?", "working_set_mb": None})
        report.say(f"  {row['name']} (PID {pid}), {process_bitness(pid)}, working set {row['working_set_mb']} MB")
    report.say("\nAerotech-like processes:")
    matches = [r for r in all_processes if re.search(PROCESS_PATTERN, r["name"])]
    for r in matches:
        report.say(f"  {r['name']:<40} PID {r['pid']:>6}  {process_bitness(r['pid']):<10} {r['working_set_mb']:>9} MB")
    report.data.update(python=sys.version, libraries=list(map(str, libraries)), headers=list(map(str, headers)),
                       prototypes=prototypes, taskid_enum=taskid, signature_mismatch=mismatch,
                       port_owner_pid=pid,
                       processes=[dict(r, bitness=process_bitness(r["pid"])) for r in matches])
    report.save("inspect")


def load_with_library(report: Report, file: Path, task_id: int, dll: Optional[str], trust_signatures: bool) -> None:
    report.say(f"File: {file} ({count_lines(file)} lines, {file.stat().st_size / 1e6:.1f} MB)")
    bits = struct.calcsize("P") * 8
    candidates = [Path(dll)] if dll else find_files(SEARCH_ROOTS, ["A3200C64.dll" if bits == 64 else "A3200C.dll"])
    if not candidates:
        report.say(f"No {bits}-bit A3200 C library found under {SEARCH_ROOTS}; pass --dll.")
        report.save("load")
        sys.exit(1)
    dll_path = candidates[0]
    headers = find_files([str(dll_path.parents[1]), *SEARCH_ROOTS], ["A3200*.h"])
    prototypes = {}
    for path in headers:
        for name, text in extract_prototypes(path.read_text(errors="replace"), list(EXPECTED)).items():
            prototypes.setdefault(name, text)
    mismatch = check_signatures(prototypes)
    report.say(f"Library: {dll_path}\nHeader prototypes: {prototypes}")
    if mismatch and not trust_signatures:
        report.say(f"Prototypes of {mismatch} differ from the assumed ones or were not found. Nothing was called. "
                   f"Send the inspect report; --trust-signatures skips this check.")
        report.save("load")
        sys.exit(1)

    ascii_client = Ascii()
    idle_task_or_exit(ascii_client, task_id, report)
    os.add_dll_directory(str(dll_path.parent))
    lib = ctypes.WinDLL(str(dll_path))
    lib.A3200Connect.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.A3200ProgramLoad.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
    lib.A3200Disconnect.argtypes = [ctypes.c_void_p]
    for fn in (lib.A3200Connect, lib.A3200ProgramLoad, lib.A3200Disconnect):
        fn.restype = ctypes.c_int

    def last_error() -> str:
        try:
            buffer = ctypes.create_string_buffer(1024)
            lib.A3200GetLastErrorString.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
            lib.A3200GetLastErrorString(buffer, 1024)
            return buffer.value.decode(errors="replace")
        except AttributeError:
            return "(A3200GetLastErrorString not available)"

    handle = ctypes.c_void_p()
    if not lib.A3200Connect(ctypes.byref(handle)):
        report.say(f"A3200Connect failed: {last_error()}")
        report.save("load")
        sys.exit(1)
    pids = {"python (compiles here if the hypothesis holds)": os.getpid()}
    if (owner := port_owner()) is not None:
        pids[f"port {ASCII_PORT} owner"] = owner
    sampler = MemorySampler(pids)
    sampler.start()
    start = time.time()
    ok = lib.A3200ProgramLoad(handle, task_id, str(file.resolve()).encode("mbcs"))
    seconds = time.time() - start
    memory = sampler.stop()
    error = "" if ok else last_error()
    state, line = ascii_client.task(task_id)
    report.say(f"\nA3200ProgramLoad: {'OK' if ok else 'FAILED'} after {seconds:.1f} s {error}")
    report.say(f"Task {task_id} after the load: {state} (line {line})")
    for name, values in memory.items():
        report.say(f"Memory {name}: {values}")
    report.data.update(method="library", file=str(file), dll=str(dll_path), ok=bool(ok), seconds=seconds,
                       error=error, task_after=state, memory=memory)
    unload(ascii_client, task_id, file.name, report)
    lib.A3200Disconnect(handle)
    ascii_client.close()
    report.say("\nVerdict: " + ("the library loads what PROGRAM LOAD over ASCII could not -> loader via library"
                                if ok and state == "program_ready" else "the library load did not work, see above"))
    report.save("load")


def load_with_ascii(report: Report, file: Path, task_id: int) -> None:
    report.say(f"File: {file} ({count_lines(file)} lines, {file.stat().st_size / 1e6:.1f} MB)")
    ascii_client = Ascii()
    idle_task_or_exit(ascii_client, task_id, report)
    owner = port_owner()
    pids = {f"port {ASCII_PORT} owner": owner} if owner is not None else {}
    sampler = MemorySampler(pids)
    sampler.start()
    code, data, seconds = ascii_client.send(f'PROGRAM {task_id} LOAD "{file.resolve()}"')
    memory = sampler.stop()
    error = ascii_client.send("~LASTERROR")[1] if code != "%" else ""
    state, line = ascii_client.task(task_id)
    report.say(f"\nPROGRAM {task_id} LOAD: reply '{code}{data}' after {seconds:.1f} s {error}")
    report.say(f"Task {task_id} after the load: {state} (line {line})")
    for name, values in memory.items():
        report.say(f"Memory {name}: {values}")
    report.data.update(method="ascii", file=str(file), reply=code + data, seconds=seconds, error=error,
                       task_after=state, memory=memory)
    unload(ascii_client, task_id, file.name, report)
    ascii_client.close()
    if code != "%":
        report.say("\nThe ASCII load failed. Restart the A3200 software before printing over the ASCII interface.")
    report.save("ascii_load")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=["inspect", "load", "ascii-load"])
    parser.add_argument("--file", type=Path, help="layer program to load (load, ascii-load)")
    parser.add_argument("--task", type=int, default=3, help="idle task to load on (default 3)")
    parser.add_argument("--dll", help="path of A3200C64.dll if it is not found automatically")
    parser.add_argument("--trust-signatures", action="store_true",
                        help="call the library although the header prototypes could not be checked")
    parser.add_argument("--out", type=Path, default=None, help="report folder")
    args = parser.parse_args(argv)

    folder = args.out or Path.cwd() / f"library_load_check_{datetime.datetime.now():%Y%m%d-%H%M%S}"
    report = Report(folder)
    if args.step == "inspect":
        inspect(report)
        return
    if args.file is None or not args.file.is_file():
        parser.error("--file must name an existing layer program")
    if args.task == 0:
        parser.error("task 0 is the library task")
    if args.step == "load":
        load_with_library(report, args.file, args.task, args.dll, args.trust_signatures)
    else:
        load_with_ascii(report, args.file, args.task)


if __name__ == "__main__":
    main()
