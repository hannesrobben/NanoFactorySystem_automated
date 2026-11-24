"""Simulated program loader of the dummy backend (T129, R10).

It loads and starts programs on the :class:`FakeA3200Transport` the ASCII interface talks to, so that
task states, program line numbers, injected task errors (``program_error_next``) and early ends
(``program_incomplete_next``) behave as with ``PROGRAM LOAD``. Load time and memory per line are
recorded in the call log, not slept.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.backends.dummy.a3200 import FakeA3200Transport
from nanofactorysystem.devices.aerotech.loader import LoadResult, count_lines


class _DoneLoad:
    def __init__(self, result: LoadResult):
        self._result = result

    def result(self, timeout: Optional[float] = None) -> LoadResult:
        return self._result

    def cancel(self) -> None:
        pass


class DummyLoader:
    """ Program loader on the simulated controller.

    Parameters
    ----------
    transport : FakeA3200Transport
        The simulated controller shared with the ASCII interface.
    seconds_per_line, kb_per_line : float
        Simulated compile time and memory per line (lab session 1: 96 µs, 19.6 kB), recorded in the call log.
    """

    load_timeout_s = None

    def __init__(self, transport: FakeA3200Transport, *, seconds_per_line: float = 96e-6, kb_per_line: float = 19.6):
        self.transport = transport
        self.world = transport.world
        self.seconds_per_line = seconds_per_line
        self.kb_per_line = kb_per_line
        self._load_failures: list[str] = []

    def fail_next_load(self, error: str = "Simulated compile error") -> None:
        """ Let the next load fail with ``error``. """

        self._load_failures.append(error)

    def load_async(self, path: Path, task_id: int) -> _DoneLoad:
        lines = count_lines(Path(path))
        load_s = round(lines * self.seconds_per_line, 3)
        if self._load_failures:
            error = self._load_failures.pop(0)
            self.world.calllog.record("loader", "load", (str(path), task_id), {"ok": False, "error": error},
                                      self.world.clock.now)
            return _DoneLoad(LoadResult(False, error, load_s, None, lines))
        self.transport._program_load(task_id, str(path), True)
        peak_gb = lines * self.kb_per_line / 1024 ** 2
        self.world.calllog.record("loader", "load", (str(path), task_id),
                                  {"ok": True, "lines": lines, "load_s": load_s, "peak_gb": peak_gb},
                                  self.world.clock.now)
        return _DoneLoad(LoadResult(True, "", load_s, peak_gb, lines))

    def start(self, task_id: int) -> None:
        self.transport._program_start(task_id)

    def state(self, task_id: int) -> TaskState:
        return TaskState(int(self.transport._task_item(task_id, "TaskState")))

    def stop(self, task_id: int) -> None:
        task = self.world.task(task_id)
        task.state = TaskState.idle.value
        task.running_polls = 0

    def remove(self, name: str) -> bool:
        removed = self.transport.loaded_programs.pop(Path(name).name.lower(), None) is not None
        if not removed:
            self.transport.unknown_removals.append(name)
        return removed

    def close(self) -> None:
        pass
