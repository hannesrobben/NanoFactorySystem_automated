"""Loading programs through the A3200 C library in worker processes, and running them on tasks 1 and 2 (T129).

Work order: ``docs/design/PROGRAM_LOADING.md`` (requirements R1-R10, lab session 1 in section 6).

- :class:`LibraryLoader` compiles and loads every program in a short-lived worker process
  (``python -m nanofactorysystem.devices.aerotech.loader``), so that the compile memory (19.6 kB per
  line) is returned to Windows when the worker disconnects; the loaded program stays on the
  controller. Start, state, stop and removal go through one library connection of this process.
- :class:`MemoryBudget` keeps the whole PC below the budget of the maintainer (32 GB RAM, at most
  20-25 GB used, default 22 GB) and gives the largest part size that may be compiled.
- :class:`ProgramRunner` runs the parts of the layers alternately on tasks 1 and 2: while one part
  runs, the next one is compiled and loaded on the other task (only one compile at a time, never on
  the running task). In lab session 1 the gap between two parts was 0.15 s.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Hashable, Iterable, Optional, Protocol

from nanofactorysystem.aerobasic import TaskStatusDataItem
from nanofactorysystem.aerobasic.ascii import AerotechError, TaskFailedError
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.devices.aerotech.library import DEFAULT_DLL, A3200Library, used_memory_gb

DEFAULT_KB_PER_LINE = 19.7  # lab session 1: 19.6 kB per line, linear from 50k to 400k lines


class ProgramLoadError(AerotechError):
    """A program could not be compiled or loaded through the library, or not within the memory budget."""


@dataclass
class LoadResult:
    """ Result of one compile and load. """

    ok: bool
    error: str = ""
    load_s: float = 0.0
    peak_gb: Optional[float] = None
    lines: int = 0


class PendingLoad(Protocol):
    """ A load that runs in the background. """

    def result(self, timeout: Optional[float] = None) -> LoadResult: ...

    def cancel(self) -> None: ...


class ProgramLoader(Protocol):
    """ What :class:`ProgramRunner` needs from a loader (seam: :class:`LibraryLoader` or the dummy loader). """

    def load_async(self, path: Path, task_id: int) -> PendingLoad: ...

    def start(self, task_id: int) -> None: ...

    def state(self, task_id: int) -> TaskState: ...

    def stop(self, task_id: int) -> None: ...

    def remove(self, name: str) -> bool: ...

    def close(self) -> None: ...


def count_lines(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 20), b""))


def last_statement_line(path: Path) -> int:
    """ Line number (1-based) of the last non-empty line; the controller reports at least this line at the end. """

    last = 0
    with open(path, "rb") as f:
        for i, line in enumerate(f, start=1):
            if line.strip():
                last = i
    return last


# ------------------------------------------------------------------------------------------- budget

@dataclass
class MemoryBudget:
    """ Memory budget of the whole PC for compiling programs (R2, R3).

    Parameters
    ----------
    budget_gb : float
        Memory all processes together may use (maintainer: 20-25 GB of 32 GB).
    reserve_gb : float
        Kept free for the growth of the experiment process (writing ``experiment.h5``, camera,
        monitoring) during a print.
    kb_per_line : float
        Peak compile memory per program line (lab session 1: 19.6 kB).
    safety : float
        Factor on the estimated peak.
    """

    budget_gb: float = 22.0
    reserve_gb: float = 3.0
    kb_per_line: float = DEFAULT_KB_PER_LINE
    safety: float = 1.2

    def peak_gb(self, n_lines: int) -> float:
        """ Estimated compile peak of a program with ``n_lines`` lines in GB (including the safety factor). """

        return n_lines * self.kb_per_line * self.safety / (1024 ** 2)

    def max_lines(self, used_gb: Optional[float] = None) -> int:
        """ Largest program (lines) that may be compiled while ``used_gb`` are in use (default: now).

        Raises
        ------
        ProgramLoadError
            If the budget leaves no room for a compile.
        """

        used = used_memory_gb() if used_gb is None else used_gb
        free = self.budget_gb - self.reserve_gb - (used or 0.0)
        lines = int(free * 1024 ** 2 / (self.kb_per_line * self.safety))
        if lines < 1000:
            raise ProgramLoadError(f"The memory budget leaves no room for a compile: {used:.1f} GB in use, budget "
                                   f"{self.budget_gb} GB, reserve {self.reserve_gb} GB")
        return lines

    def part_lines(self, used_gb: Optional[float] = None, *, step: int = 10_000) -> int:
        """ Part size for splitting layer programs: :meth:`max_lines` rounded down to ``step`` lines. """

        return max(step, (self.max_lines(used_gb) // step) * step)

    def fits(self, n_lines: int, used_gb: Optional[float] = None) -> bool:
        """ True if a program of ``n_lines`` lines may be compiled now (unknown memory use: True). """

        used = used_memory_gb() if used_gb is None else used_gb
        if used is None:
            return True
        return used + self.peak_gb(n_lines) <= self.budget_gb - self.reserve_gb


# ------------------------------------------------------------------------------------------- library loader

class _WorkerLoad:
    """ A load running in a worker process. """

    def __init__(self, process: subprocess.Popen, path: Path, lines: int):
        self.process, self.path, self.lines = process, path, lines
        self._result: Optional[LoadResult] = None

    def result(self, timeout: Optional[float] = None) -> LoadResult:
        if self._result is None:
            try:
                out, err = self.process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.cancel()
                return LoadResult(False, f"no result from the load worker within {timeout} s", lines=self.lines)
            rows = [line for line in out.splitlines() if line.startswith("{")]
            if not rows:
                self._result = LoadResult(False, f"load worker gave no result (exit {self.process.returncode}): "
                                                 f"{err.strip()[-500:]}", lines=self.lines)
            else:
                data = json.loads(rows[-1])
                self._result = LoadResult(bool(data["ok"]), data.get("error", ""), data.get("load_s", 0.0),
                                          data.get("peak_gb"), self.lines)
        return self._result

    def cancel(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()


class LibraryLoader:
    """ Loads programs through the A3200 C library in worker processes (R1).

    Parameters
    ----------
    dll : str or Path
        Path of ``A3200C64.dll``.
    python : str
        Python interpreter of the workers (default: this one, 64 bit).
    load_timeout_s : float
        Maximum time of one compile and load.

    Raises
    ------
    LibraryUnavailableError
        If the library cannot be used (not on the lab PC).
    """

    def __init__(self, dll: str | Path = DEFAULT_DLL, *, python: str = sys.executable, load_timeout_s: float = 1800.0):
        self.dll = str(dll)
        self.python = python
        self.load_timeout_s = load_timeout_s
        self.lib = A3200Library(self.dll)

    def load_async(self, path: Path, task_id: int) -> PendingLoad:
        cmd = [self.python, "-m", "nanofactorysystem.devices.aerotech.loader", str(path), str(task_id), self.dll]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return _WorkerLoad(process, Path(path), count_lines(Path(path)))

    def start(self, task_id: int) -> None:
        ok, error = self.lib.start(task_id)
        if not ok:
            raise TaskFailedError(f"A3200ProgramStart({task_id}) failed: {error}")

    def state(self, task_id: int) -> TaskState:
        return self.lib.state(task_id)

    def stop(self, task_id: int) -> None:
        self.lib.stop(task_id)

    def remove(self, name: str) -> bool:
        """ Remove a program; True only if the added-program count went down (R7). """

        before = self.lib.added_programs()
        ok, _ = self.lib.remove(name)
        after = self.lib.added_programs()
        return ok and before is not None and after is not None and after < before

    def close(self) -> None:
        self.lib.close()


def _worker(argv: list[str]) -> None:
    """ Worker process: load one program, report the result as JSON, disconnect (the program stays loaded). """

    from nanofactorysystem.devices.aerotech.library import peak_private_gb

    path, task_id, dll = Path(argv[0]), int(argv[1]), argv[2]
    start = time.time()
    try:
        with A3200Library(dll) as lib:
            ok, error = lib.load(task_id, path)
            state = lib.state(task_id).name if ok else ""
    except Exception as exc:  # report every failure to the parent
        ok, error, state = False, f"{type(exc).__name__}: {exc}", ""
    print(json.dumps({"ok": ok and state in ("program_ready", "program_complete"),
                      "error": error or ("" if state in ("program_ready", "program_complete") else f"task {state}"),
                      "load_s": round(time.time() - start, 2), "peak_gb": peak_private_gb()}))


# ------------------------------------------------------------------------------------------- runner

@dataclass
class PartRecord:
    """ Monitoring data of one part (R8). """

    key: Hashable
    part: str
    task: int
    lines: int
    load_s: float = 0.0
    waited_for_load_s: float = 0.0
    run_s: float = 0.0
    gap_s: Optional[float] = None
    last_line: Optional[int] = None
    used_gb: Optional[float] = None


class ProgramRunError(AerotechError):
    """A part failed in :class:`ProgramRunner`; ``key`` names the item (layer) it belongs to."""

    def __init__(self, message: str, key: Hashable = None):
        super().__init__(message)
        self.key = key


@dataclass
class ProgramRunner:
    """ Runs program parts alternately on tasks 1 and 2 with prefetch (R4-R8).

    Parameters
    ----------
    loader : ProgramLoader
        Library loader (or the dummy loader).
    api : AerotechAsciiInterface
        For the program line number of a running task (stall and early-end detection).
    budget : MemoryBudget
    exec_dir : Path
        Folder for the execution copies (one unique ``.pgm`` name per part; the compiled ``.OGM`` of the
        library lands next to it). Both are deleted after the part has run.
    tasks : tuple of int
        The two tasks that alternate.
    poll_s, stall_timeout_s : float
        Status polling interval, and the time without progress after which a running part fails.
    logger : logging.Logger, optional
    """

    loader: ProgramLoader
    api: object
    budget: MemoryBudget
    exec_dir: Path
    tasks: tuple[int, int] = (1, 2)
    poll_s: float = 0.5
    stall_timeout_s: float = 600.0
    logger: Optional[logging.Logger] = None
    records: list[PartRecord] = field(default_factory=list)

    def __post_init__(self):
        self.exec_dir = Path(self.exec_dir)
        self.log = self.logger or logging.getLogger(__name__)
        self._counter = 0

    def _exec_copy(self, part: Path, task_id: int) -> Path:
        """ Copy a part to a unique ``.pgm`` name (the library compiles ``.pgm``; two tasks never share a name). """

        self._counter += 1
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(part).stem)
        path = self.exec_dir / f"nfs_t{task_id}_{self._counter:05d}_{stem}.pgm"
        self.exec_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(part, path)
        return path

    def _cleanup(self, path: Path) -> None:
        for candidate in path.parent.glob(path.stem + ".*"):
            if candidate.suffix.lower() in (".pgm", ".ogm"):
                candidate.unlink(missing_ok=True)

    def _line(self, task_id: int) -> Optional[int]:
        try:
            return int(float(self.api.STATUS((task_id, TaskStatusDataItem.ProgramLineNumber))))
        except (AerotechError, ValueError):
            return None

    def _discard(self, task_id: int, exec_path: Optional[Path]) -> None:
        """ Stop a task and remove its program; never raises. """

        try:
            self.loader.stop(task_id)
        except Exception as error:  # cleanup after a failure must not hide the failure
            self.log.error(f"Could not stop task {task_id}: {error}")
        if exec_path is not None:
            try:
                self.loader.remove(exec_path.name)
            except Exception as error:
                self.log.error(f"Could not remove {exec_path.name}: {error}")
            self._cleanup(exec_path)

    def run(self, items: Iterable[tuple[Hashable, list[Path]]],
            on_item_done: Optional[Callable[[Hashable], None]] = None) -> list[PartRecord]:
        """ Run the parts of every item (layer) in order; call ``on_item_done(key)`` after its last part.

        The next part is loaded on the other task while the current part runs, if the memory budget
        allows it; otherwise it is loaded after the current part has ended. ``on_item_done`` runs while
        the next part is loading (captures between layers do not add to the printing time).

        Raises
        ------
        ProgramRunError
            On the first part that cannot be loaded, does not start, ends in an error or before its last
            line, or stalls. Both tasks are stopped and their programs removed first; ``key`` names the item.
        """

        queue = [(key, Path(part), k == len(parts) - 1) for key, parts in items for k, part in enumerate(parts)]
        if not queue:
            return self.records
        loaded: dict[int, Path] = {}
        pending, pending_index = None, None
        last_end: Optional[float] = None

        def begin_load(index: int) -> None:
            nonlocal pending, pending_index
            key, part, _ = queue[index]
            task_id = self.tasks[index % 2]
            exec_path = self._exec_copy(part, task_id)
            loaded[task_id] = exec_path
            pending, pending_index = self.loader.load_async(exec_path, task_id), index

        def fail(message: str, key: Hashable) -> ProgramRunError:
            if pending is not None:
                pending.cancel()
            for task_id, exec_path in list(loaded.items()):
                self._discard(task_id, exec_path)
            loaded.clear()
            self.log.error(message)
            return ProgramRunError(message, key)

        lines = count_lines(queue[0][1])
        if not self.budget.fits(lines):
            raise ProgramLoadError(f"{queue[0][1].name} ({lines} lines, about {self.budget.peak_gb(lines):.1f} GB to "
                                   f"compile) does not fit into the memory budget of {self.budget.budget_gb} GB")
        begin_load(0)
        for index, (key, part, item_done) in enumerate(queue):
            task_id = self.tasks[index % 2]
            exec_path = loaded[task_id]
            record = PartRecord(key, part.name, task_id, count_lines(part))
            wait_start = time.time()
            result = pending.result(timeout=getattr(self.loader, "load_timeout_s", None))
            pending = None
            record.waited_for_load_s, record.load_s = round(time.time() - wait_start, 2), result.load_s
            if not result.ok:
                raise fail(f"Could not load {part.name} on task {task_id}: {result.error}", key)
            if self.loader.state(task_id) != TaskState.program_ready:
                raise fail(f"{part.name} is not ready on task {task_id} ({self.loader.state(task_id).name})", key)
            try:
                self.loader.start(task_id)
            except AerotechError as error:
                raise fail(f"Could not start {part.name} on task {task_id}: {error}", key) from error
            started = time.time()
            record.gap_s = round(started - last_end, 2) if last_end is not None else None
            record.used_gb = used_memory_gb()

            # Prefetch: compile the next part on the other task while this one runs, if the budget allows
            prefetch_after = False
            if index + 1 < len(queue):
                next_lines = count_lines(queue[index + 1][1])
                if self.budget.fits(next_lines):
                    begin_load(index + 1)
                else:
                    prefetch_after = True
                    self.log.warning(f"Not enough memory to load {queue[index + 1][1].name} while {part.name} runs; "
                                     f"it is loaded afterwards")

            # Wait for the end; a part without progress for stall_timeout_s fails
            last_line, last_change = None, time.time()
            state = self.loader.state(task_id)
            while state in (TaskState.program_running, TaskState.program_ready):
                time.sleep(self.poll_s)
                state = self.loader.state(task_id)
                line = self._line(task_id)
                if line != last_line:
                    last_line, last_change = line, time.time()
                elif time.time() - last_change > self.stall_timeout_s:
                    raise fail(f"{part.name} made no progress on task {task_id} for {self.stall_timeout_s} s "
                               f"(line {line})", key)
            last_end = time.time()
            record.run_s = round(last_end - started, 2)
            record.last_line = self._line(task_id)
            expected = last_statement_line(part)
            if state != TaskState.program_complete:
                raise fail(f"{part.name} on task {task_id} ended in state {state.name} at line {record.last_line}", key)
            if record.last_line is not None and record.last_line < expected:
                raise fail(f"Program ended early: {part.name} on task {task_id} reported complete at line "
                           f"{record.last_line} of {expected}", key)
            self.loader.stop(task_id)
            if not self.loader.remove(exec_path.name):
                self.log.warning(f"Removing {exec_path.name} did not lower the added-program count")
            self._cleanup(exec_path)
            loaded.pop(task_id, None)
            self.records.append(record)
            self.log.info(f"Part {part.name} on task {task_id}: {record.lines} lines, load {record.load_s} s "
                          f"(waited {record.waited_for_load_s} s), run {record.run_s} s, gap {record.gap_s} s, "
                          f"PC memory {record.used_gb if record.used_gb is None else round(record.used_gb, 1)} GB")
            if prefetch_after:
                next_lines = count_lines(queue[index + 1][1])
                if not self.budget.fits(next_lines):
                    raise fail(f"{queue[index + 1][1].name} ({next_lines} lines) does not fit into the memory budget",
                               queue[index + 1][0])
                begin_load(index + 1)
            if item_done and on_item_done is not None:
                try:
                    on_item_done(key)
                except BaseException:
                    # Do not leave the prefetched part loaded on the other task
                    if pending is not None:
                        pending.cancel()
                    for other, other_path in list(loaded.items()):
                        self._discard(other, other_path)
                    raise
        return self.records


def max_part_lines(budget: MemoryBudget, used_gb: Optional[float] = None) -> int:
    """ Part size for the T125 split when loading through the library (R3); at least 10 000 lines. """

    try:
        return budget.part_lines(used_gb)
    except ProgramLoadError:
        return 10_000


if __name__ == "__main__":
    _worker(sys.argv[1:])
