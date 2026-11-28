import time
from pathlib import Path
from typing import Callable, Optional

from tqdm import tqdm

from nanofactorysystem.aerobasic import TaskStatusDataItem, WaitMode
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError, TaskFailedError
from nanofactorysystem.aerobasic.constants.tasks import TaskMode, TaskStatus0, TaskState, TaskStatus2, TaskStatus1

"""
Task -> Aerobasic task -> basically only a getter for information
ExecutableProgram(ABC) -> has an execute function and callbacks before and after the task
-> SingleProgram(ExecutableProgram) -> gets an AeroBasic program
-> MultiStageProgram(ExecutableProgram) -> gets a LayerFactory and has callbacks before/after each layer

LayerFactory -> Iterator[AerobasicProgram]


"""


class Task:
    def __init__(self, api: AerotechAsciiInterface, task_id: int, *, file_path: Optional[Path | str] = None,
                 program_name: Optional[str] = None, on_removed: Optional[Callable[[str], None]] = None):
        """ Handle of a controller task running a program.

        Parameters
        ----------
        api : AerotechAsciiInterface
        task_id : int
        file_path : str or Path, optional
            Program file (its line count is the expected last line).
        program_name : str, optional
            Name under which the program was loaded on the controller (the
            file name given to ``PROGRAM LOAD``, without path).
            :meth:`finish` and :meth:`abort` remove the program under this
            name (T127); without it, the name of ``file_path`` is used.
        on_removed : callable, optional
            Called with the program name after a successful ``REMOVEPROGRAM``
            (the controller deletes its execution copy, T152).
        """
        self.api = api
        self.task_id = task_id

        self.file_path = Path(file_path) if file_path is not None else None
        self.program_name = program_name
        self.on_removed = on_removed

        self._task_status0 = None
        self._task_status1 = None
        self._task_status2 = None
        self._task_mode = None
        self._task_state = None
        self._current_line = None

    def __repr__(self):
        return f"Task(task_id={self.task_id}, file_path={self.file_path})"

    def update(self):
        mode, state, status_0, status_1, status_2, current_line = self.api.STATUS(
            (self.task_id, TaskStatusDataItem.TaskMode),
            (self.task_id, TaskStatusDataItem.TaskState),
            (self.task_id, TaskStatusDataItem.TaskStatus0),
            (self.task_id, TaskStatusDataItem.TaskStatus1),
            (self.task_id, TaskStatusDataItem.TaskStatus2),
            (self.task_id, TaskStatusDataItem.ProgramLineNumber),
        ).split(" ")

        self._task_mode = TaskMode(int(mode))
        self._task_state = TaskState(int(state))
        self._task_status0 = TaskStatus0(int(status_0))
        self._task_status1 = TaskStatus1(int(status_1))
        self._task_status2 = TaskStatus2(int(status_2))
        self._current_line = int(current_line)

    def reset(self):
        self._task_mode = None
        self._task_state = None
        self._task_status0 = None
        self._task_status1 = None
        self._task_status2 = None
        self._current_line = None

    @property
    def total_lines(self) -> Optional[int]:
        if self.file_path is None:
            return None
        return len(self.file_path.read_text().splitlines())

    @property
    def last_statement_line(self) -> Optional[int]:
        """ Line number (1-based) of the last non-empty line of the program file; None without a file. """

        if self.file_path is None:
            return None
        lines = self.file_path.read_text().splitlines()
        return max((i for i, line in enumerate(lines, start=1) if line.strip()), default=0)

    @property
    def removal_name(self) -> Optional[str]:
        """ Name passed to ``REMOVEPROGRAM``: the loaded name, else the name of the program file. """

        if self.program_name:
            return self.program_name
        return self.file_path.name if self.file_path is not None else None

    def error_info(self) -> str:
        """ Task error and axis faults at the moment of the failure, for the error message.

        With ``ERRORDECODE``: ``"<code>: <text>"`` from ``TaskErrorCode`` and
        ``TaskErrorLocation``. The ASCII interface of the lab controller refuses
        ``ERRORDECODE`` (lab 2026-11-28, T169); the code and location are then
        reported undecoded. The fault of every axis that has one is appended
        (``axis faults: X PositionError``), read before any recovery
        acknowledges it. Never raises: what cannot be read is noted instead.
        """

        try:
            error_code, error_location = (int(float(v)) for v in self.api.STATUS(
                (self.task_id, TaskStatusDataItem.TaskErrorCode),
                (self.task_id, TaskStatusDataItem.TaskErrorLocation)
            ).split(" "))
        except (AerotechError, ValueError) as error:
            info = f"(task error code not readable: {error})"
        else:
            try:
                info = f"{error_code}: {self.api.ERROR_DECODE(error_code, error_location)}"
            except AerotechError as error:
                info = (f"task error {error_code} at location {error_location} "
                        f"(ERRORDECODE not available: {error})")
        from nanofactorysystem.devices.aerotech.health import axis_faults, describe_axis_fault
        try:
            faults = axis_faults(self.api)
        except (AerotechError, ValueError) as error:
            return f"{info}; axis faults not readable: {error}"
        if faults:
            info += "; axis faults: " + ", ".join(f"{axis} {describe_axis_fault(fault)} ({fault})"
                                                  for axis, fault in faults.items())
        return info

    @property
    def task_mode(self) -> TaskMode:
        if self._task_mode is None:
            self.update()
        return self._task_mode

    @property
    def current_line(self) -> int:
        if self._current_line is None:
            self.update()
        return self._current_line

    @property
    def task_state(self) -> TaskState:
        if self._task_state is None:
            self.update()
        return self._task_state

    @property
    def task_status0(self) -> TaskStatus0:
        if self._task_status0 is None:
            self.update()
        return self._task_status0

    @property
    def task_status1(self) -> TaskStatus1:
        if self._task_status1 is None:
            self.update()
        return self._task_status1

    @property
    def task_status2(self) -> TaskStatus2:
        if self._task_status2 is None:
            self.update()
        return self._task_status2

    @property
    def wait_mode(self) -> WaitMode:
        return WaitMode.from_task_mode(self.task_mode)

    def wait_to_finish(self, *, update_interval=0.5, stall_timeout: float = 600.0):
        """ Wait until the task is no longer running.

        Parameters
        ----------
        update_interval : float
            Seconds between status queries.
        stall_timeout : float
            Raise :class:`TaskFailedError` if the program line number does
            not change for this many seconds while the task is running.
            Long programs are fine as long as they progress.

        Raises
        ------
        TaskFailedError
            If the task does not end in ``program_complete`` or stalls.
        """
        current_lines = self.api.STATUS(
            (self.task_id, TaskStatusDataItem.ProgramLineNumber),
        )
        pbar = tqdm(
            desc=f"Task {self.task_id} running... (filepath={self.file_path})",
            total=self.total_lines,
            unit="lines"
        )
        pbar.update(int(current_lines))

        last_line = None
        stalled = 0.0
        while self.task_state == TaskState.program_running:
            time.sleep(update_interval)
            self.update()
            pbar.n = self.current_line
            pbar.refresh()
            # Detect a stalled program; count the waiting time via the sleep intervals
            if self.current_line == last_line:
                stalled += update_interval
                if stalled >= stall_timeout:
                    pbar.close()
                    raise TaskFailedError(f"Task {self.task_id} made no progress for {stall_timeout} s "
                                          f"(line {self.current_line})")
            else:
                last_line = self.current_line
                stalled = 0.0

        self.api.logger.info(f"Task {self.task_id} finished with task state {self.task_state}")

        if self.task_state != TaskState.program_complete:
            additional_info = f" {self.error_info()}" if self.task_state == TaskState.error else ""
            pbar.close()
            raise TaskFailedError(
                f"Program not finished! {self.task_state}.{additional_info}"
            )

        # A program that reports "complete" before its last line did not print everything (2026-11-22:
        # parts of 79 992 lines complete at line 8357 and 4198). Every normal end so far was at the last line.
        last_line = self.last_statement_line
        if last_line is not None and int(self.current_line) < last_line:
            pbar.close()
            raise TaskFailedError(
                f"Program ended early: task {self.task_id} reported complete at line {self.current_line} of "
                f"{last_line} (mode {self.task_mode}, status0 {self.task_status0}, status1 {self.task_status1}, "
                f"status2 {self.task_status2})")

        pbar.close()

    def finish(self, *, timeout: float = 30.0, update_interval: float = 0.1):
        """ Stop the task, wait until it is idle and remove the program under its loaded name (T127).

        A failed removal is logged and does not raise: the program has run.

        Raises
        ------
        TaskFailedError
            If the task is not idle after ``timeout`` seconds.
        """
        self.api.PROGRAM_STOP(self.task_id)
        waited = 0.0
        while self.task_state != TaskState.idle:
            if waited >= timeout:
                raise TaskFailedError(f"Task {self.task_id} not idle {timeout} s after PROGRAM STOP "
                                      f"({self.task_state})")
            time.sleep(update_interval)
            waited += update_interval
            self.update()
        self.remove_program()

    def remove_program(self) -> bool:
        """ Send ``REMOVEPROGRAM`` with :attr:`removal_name`; log a failure instead of raising.

        Returns
        -------
        bool
            False if the controller refused the removal or there is no name.
        """

        name = self.removal_name
        if name is None:
            return False
        try:
            self.api.REMOVE_PROGRAM(name)
        except AerotechError as error:
            self.api.logger.warning(f"Could not remove program '{name}' after task {self.task_id}: {error}")
            return False
        if self.on_removed is not None:
            self.on_removed(name)
        return True

    def abort(self, *, timeout: float = 10.0, update_interval: float = 0.1) -> None:
        """ Clean up after a failed program: stop the task, wait for idle, remove the program.

        Never raises; every problem is logged, so that the original error
        stays the one reported.
        """

        try:
            self.api.PROGRAM_STOP(self.task_id)
            self.reset()
            waited = 0.0
            while self.task_state != TaskState.idle and waited < timeout:
                time.sleep(update_interval)
                waited += update_interval
                self.update()
        except AerotechError as error:
            self.api.logger.error(f"Could not stop task {self.task_id}: {error}")
        self.remove_program()