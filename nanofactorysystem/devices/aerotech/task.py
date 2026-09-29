import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from nanofactorysystem.aerobasic import TaskStatusDataItem, WaitMode
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, TaskFailedError
from nanofactorysystem.aerobasic.constants.tasks import TaskMode, TaskStatus0, TaskState, TaskStatus2, TaskStatus1

"""
Task -> Aerobasic task -> Im Prinzip nur ein Getter für Informationen
ExecutableProgram(ABC) -> Hat eine execute-Funktion und Callbacks für Vor- und Nach dem Task
-> SingleProgram(ExecutableProgram) -> Bekommt ein AeroBasic Programm
-> MultiStageProgram(ExecutableProgram) -> Bekommt eine LayerFactory und hat Callbacks für vor/nach jedem Layer

LayerFactory -> Iterator[AerobasicProgram]


"""


class Task:
    def __init__(self, api: AerotechAsciiInterface, task_id: int, *, file_path: Optional[Path | str] = None):
        self.api = api
        self.task_id = task_id

        self.file_path = Path(file_path) if file_path is not None else None

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

    def wait_to_finish(self, *, update_interval=0.5):
        current_lines = self.api.STATUS(
            (self.task_id, TaskStatusDataItem.ProgramLineNumber),
        )
        pbar = tqdm(
            desc=f"Task {self.task_id} running... (filepath={self.file_path})",
            total=self.total_lines,
            unit="lines"
        )
        pbar.update(int(current_lines))

        while self.task_state == TaskState.program_running:
            time.sleep(update_interval)
            self.update()
            pbar.n = self.current_line
            pbar.refresh()

        self.api.logger.info(f"Task {self.task_id} finished with task state {self.task_state}")

        if self.task_state != TaskState.program_complete:
            additional_info = ""
            if self.task_state == TaskState.error:
                error_code, error_location = self.api.STATUS(
                    (self.task_id, TaskStatusDataItem.TaskErrorCode),
                    (self.task_id, TaskStatusDataItem.TaskErrorLocation)
                ).split(" ")
                error_string = self.api.ERROR_DECODE(int(error_code), int(error_location))
                additional_info = f" {error_code}:{error_string}"
            pbar.close()
            raise TaskFailedError(
                f"Program not finished! {self.task_state}.{additional_info}"
            )

        if int(self.current_line) != self.total_lines:
            print(f"Task Mode: {self.task_mode}\nTask State: {self.task_state}\nTask Status 0: {self.task_status0}\nTask Status 1: {self.task_status1}\nTask Status 2: {self.task_status2}")

        pbar.close()

    def finish(self):
        self.api.PROGRAM_STOP(self.task_id)
        while self.task_state != TaskState.idle:
            time.sleep(0.1)
            self.update()
        if self.file_path is not None:
            self.api.REMOVE_PROGRAM(self.file_path)