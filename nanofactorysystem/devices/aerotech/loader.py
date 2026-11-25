"""Loading programs through the A3200 C library in worker processes, and running them on one task (T129, T132).

Work order: ``docs/design/PROGRAM_LOADING.md`` (requirements R1-R10, lab sessions in section 6, plan
after lab session 2 in section 7.2).

- :class:`LibraryLoader` compiles and adds every program in a short-lived worker process
  (``python -m nanofactorysystem.devices.aerotech.loader``, ``A3200ProgramAdd``, no task), so that the
  compile memory (19.6 kB per line) is returned to Windows when the worker disconnects; the added
  program stays on the controller. Associate, start, state, stop and removal go through one library
  connection of this process.
- :class:`MemoryBudget` keeps the whole PC below the budget of the maintainer (32 GB RAM, at most
  20-25 GB used, default 22 GB) and gives the largest part size that may be compiled.
- :class:`ProgramRunner` runs the parts of the layers on **one task** (task 1) with add-ahead: while
  one part runs, the next one is compiled without a task; when the current part has completed it is
  removed and the next one is associated with the task and started (T132, maintainer decision (b) of
  2026-11-25). Task 2 has untuned parameters on this controller (lookahead 100 instead of 10000 moves),
  so print parts never run there.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Hashable, Iterable, Optional, Protocol

from nanofactorysystem.aerobasic import TaskStatusDataItem
from nanofactorysystem.aerobasic.ascii import AerotechError, TaskFailedError
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.devices.aerotech import exec_program_name
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
    """ A compile (add) that runs in the background. """

    def result(self, timeout: Optional[float] = None) -> LoadResult: ...

    def cancel(self) -> None: ...


class ProgramLoader(Protocol):
    """ What :class:`ProgramRunner` needs from a loader (seam: :class:`LibraryLoader` or the dummy loader). """

    def add_async(self, path: Path) -> PendingLoad: ...

    def associate(self, task_id: int, name: str) -> None: ...

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
    """ Compiles and adds programs through the A3200 C library in worker processes (R1).

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

    def add_async(self, path: Path) -> PendingLoad:
        """ Compile and add a program without a task in a worker process (``A3200ProgramAdd``). """

        cmd = [self.python, "-m", "nanofactorysystem.devices.aerotech.loader", str(path), self.dll]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return _WorkerLoad(process, Path(path), count_lines(Path(path)))

    def associate(self, task_id: int, name: str) -> None:
        """ Bind an added program (by its file name) to a task.

        Raises
        ------
        TaskFailedError
            If ``A3200ProgramAssociate`` fails.
        """

        ok, error = self.lib.associate(task_id, name)
        if not ok:
            raise TaskFailedError(f"A3200ProgramAssociate({task_id}, {name}) failed: {error}")

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
    """ Worker process: compile and add one program without a task, report the result as JSON, disconnect.

    The added program stays on the controller after the worker has exited (lab session 1); the
    compile memory is returned to Windows at the disconnect.
    """

    from nanofactorysystem.devices.aerotech.library import peak_private_gb

    path, dll = Path(argv[0]), argv[1]
    start = time.time()
    try:
        with A3200Library(dll) as lib:
            ok, error = lib.add(path)
    except Exception as exc:  # report every failure to the parent
        ok, error = False, f"{type(exc).__name__}: {exc}"
    print(json.dumps({"ok": ok, "error": error, "load_s": round(time.time() - start, 2),
                      "peak_gb": peak_private_gb()}))


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
    """ Runs program parts on one task with add-ahead (R4-R8, T132).

    While a part runs, the next part is compiled and added without a task (``A3200ProgramAdd`` in a
    worker process). When the current part has completed, the task is stopped, the part is removed,
    and the next part is associated with the task (``A3200ProgramAssociate``) and started. At most two
    programs are added at a time: the running one and the next one.

    Parameters
    ----------
    loader : ProgramLoader
        Library loader (or the dummy loader).
    api : AerotechAsciiInterface
        For the program line number of a running task (stall and early-end detection).
    budget : MemoryBudget
    exec_dir : Path
        Folder for the execution copies (one unique ``.pgm`` name per part, see
        :func:`~nanofactorysystem.devices.aerotech.exec_program_name`; the compiled ``.OGM`` of the
        library lands next to it). Both are deleted after the part has run.
    task : int
        The task every part runs on (default 1, the task with the tuned parameters; decision (b) of
        T132: print parts never run on task 2).
    poll_s, stall_timeout_s : float
        Status polling interval, and the time without progress after which a running part fails.
    logger : logging.Logger, optional
    """

    loader: ProgramLoader
    api: object
    budget: MemoryBudget
    exec_dir: Path
    task: int = 1
    poll_s: float = 0.5
    stall_timeout_s: float = 600.0
    logger: Optional[logging.Logger] = None
    records: list[PartRecord] = field(default_factory=list)

    def __post_init__(self):
        self.exec_dir = Path(self.exec_dir)
        self.log = self.logger or logging.getLogger(__name__)
        self._session = uuid.uuid4().hex[:6]
        self._counter = 0

    def _exec_copy(self, part: Path) -> Path:
        """ Copy a part to a fresh ``.pgm`` name, unique across processes (the library compiles ``.pgm``). """

        self._counter += 1
        path = self.exec_dir / exec_program_name(self._session, self._counter, Path(part).stem)
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

    def run(self, items: Iterable[tuple[Hashable, list[Path]]],
            on_item_done: Optional[Callable[[Hashable], None]] = None) -> list[PartRecord]:
        """ Run the parts of every item (layer) in order; call ``on_item_done(key)`` after its last part.

        The next part is compiled while the current part runs, if the memory budget allows it;
        otherwise it is compiled after the current part has ended. ``on_item_done`` runs while the
        next part is compiling (captures between layers do not add to the printing time).

        Raises
        ------
        ProgramRunError
            On the first part that cannot be compiled, associated or started, ends in an error or
            before its last line, or stalls. The task is stopped and every added program removed
            first; ``key`` names the item.
        """

        queue = [(key, Path(part), k == len(parts) - 1) for key, parts in items for k, part in enumerate(parts)]
        if not queue:
            return self.records
        task_id = self.task
        added: dict[str, Path] = {}  # programs added on the controller and not removed yet
        pending: Optional[PendingLoad] = None
        upcoming: Optional[Path] = None
        last_end: Optional[float] = None

        def begin_add(index: int) -> None:
            nonlocal pending, upcoming
            upcoming = self._exec_copy(queue[index][1])
            added[upcoming.name] = upcoming
            pending = self.loader.add_async(upcoming)

        def release(name: str) -> bool:
            """ Remove one added program and its files; never raises. """

            removed = False
            try:
                removed = self.loader.remove(name)
            except Exception as error:  # cleanup must not hide the original failure
                self.log.error(f"Could not remove {name}: {error}")
            self._cleanup(added.pop(name))
            return removed

        def discard_all() -> None:
            """ Cancel the compile, stop the task and remove every added program; never raises. """

            if pending is not None:
                pending.cancel()
            try:
                self.loader.stop(task_id)
            except Exception as error:
                self.log.error(f"Could not stop task {task_id}: {error}")
            for name in list(added):
                release(name)

        def fail(message: str, key: Hashable) -> ProgramRunError:
            discard_all()
            self.log.error(message)
            return ProgramRunError(message, key)

        lines = count_lines(queue[0][1])
        if not self.budget.fits(lines):
            raise ProgramLoadError(f"{queue[0][1].name} ({lines} lines, about {self.budget.peak_gb(lines):.1f} GB to "
                                   f"compile) does not fit into the memory budget of {self.budget.budget_gb} GB")
        begin_add(0)
        for index, (key, part, item_done) in enumerate(queue):
            exec_path = upcoming
            record = PartRecord(key, part.name, task_id, count_lines(part))
            wait_start = time.time()
            result = pending.result(timeout=getattr(self.loader, "load_timeout_s", None))
            pending = None
            record.waited_for_load_s, record.load_s = round(time.time() - wait_start, 2), result.load_s
            if not result.ok:
                raise fail(f"Could not compile {part.name}: {result.error}", key)
            try:
                self.loader.associate(task_id, exec_path.name)
            except AerotechError as error:
                raise fail(f"Could not associate {part.name} with task {task_id}: {error}", key) from error
            if self.loader.state(task_id) != TaskState.program_ready:
                raise fail(f"{part.name} is not ready on task {task_id} ({self.loader.state(task_id).name})", key)
            try:
                self.loader.start(task_id)
            except AerotechError as error:
                raise fail(f"Could not start {part.name} on task {task_id}: {error}", key) from error
            started = time.time()
            record.gap_s = round(started - last_end, 2) if last_end is not None else None
            record.used_gb = used_memory_gb()

            # Add-ahead: compile the next part without a task while this one runs, if the budget allows
            prefetch_after = False
            if index + 1 < len(queue):
                next_lines = count_lines(queue[index + 1][1])
                if self.budget.fits(next_lines):
                    begin_add(index + 1)
                else:
                    prefetch_after = True
                    self.log.warning(f"Not enough memory to compile {queue[index + 1][1].name} while {part.name} "
                                     f"runs; it is compiled afterwards")

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
            if not release(exec_path.name):
                self.log.warning(f"Removing {exec_path.name} did not lower the added-program count")
            self.records.append(record)
            self.log.info(f"Part {part.name} on task {task_id}: {record.lines} lines, compile {record.load_s} s "
                          f"(waited {record.waited_for_load_s} s), run {record.run_s} s, gap {record.gap_s} s, "
                          f"PC memory {record.used_gb if record.used_gb is None else round(record.used_gb, 1)} GB")
            if prefetch_after:
                next_lines = count_lines(queue[index + 1][1])
                if not self.budget.fits(next_lines):
                    raise fail(f"{queue[index + 1][1].name} ({next_lines} lines) does not fit into the memory budget",
                               queue[index + 1][0])
                begin_add(index + 1)
            if item_done and on_item_done is not None:
                try:
                    on_item_done(key)
                except BaseException:
                    # Do not leave the next part added on the controller
                    discard_all()
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
