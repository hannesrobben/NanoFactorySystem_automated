import datetime
import hashlib
import random
import re
import time
import uuid
import shutil
from functools import cached_property
from os import PathLike
from pathlib import Path
from typing import Optional

from nanofactorysystem.aerobasic import AxisStatusDataItem, SingleAxis, SystemStatusDataItem, WaitMode, Axis
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError, TaskFailedError
from nanofactorysystem.aerobasic.constants import AxisStatus
from nanofactorysystem.aerobasic.constants.tasks import ProgrammingMode, TaskState, VelocityMode
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.devices.aerotech.task import Task
from nanofactorysystem.devices.coordinate_system import Point3D


EXEC_PROGRAM_PREFIX = "nfs_"
"""Prefix of the execution copies loaded by :meth:`AerotechController.run_program_as_task` (T152)."""


def exec_program_name(session: str, counter: int, stem: str) -> str:
    """ Name under which a program is loaded over ASCII: ``nfs_<session>_<counter>_<stem>.pgm`` (T152).

    A refused ``PROGRAM LOAD`` blocks its program name on the controller until
    the A3200 software is restarted, even for valid content (lab session 2,
    2026-11-25). A fresh name per load keeps one failure from blocking every
    later program.

    Parameters
    ----------
    session : str
        Token of the controller object, unique per process.
    counter : int
        Number of the load within the session.
    stem : str
        Stem of the program file; characters other than letters, digits,
        ``_``, ``-`` and ``.`` become ``_``, and it is cut to 60 characters.

    Returns
    -------
    str
        File name with the extension ``.pgm`` (at most 80 characters for a
        session token of 6 characters).
    """
    clean = re.sub(r"[^A-Za-z0-9_.-]", "_", stem)[:60]
    return f"{EXEC_PROGRAM_PREFIX}{session}_{counter:04d}_{clean}.pgm"


class AerotechController:
    """ Program tasks, status queries and command log of an Aerotech A3200 controller.

    Shared base class of :class:`Aerotech3200` and ``devices.A3200``. A
    subclass creates the :class:`AerotechAsciiInterface` and calls
    :meth:`_init_controller`.
    """

    MAX_NUMBER_OF_TASKS = 32

    def _init_controller(self, api: AerotechAsciiInterface, program_dir: Optional[PathLike | str] = None):
        """ Initialise the controller state.

        Parameters
        ----------
        api : AerotechAsciiInterface
            ASCII command interface (connected or not).
        program_dir : str or Path, optional
            Directory for temporary program files and the execution copies,
            see :meth:`run_program_as_task`.
        """
        self.api = api
        self.program_dir = Path(program_dir) if program_dir is not None else None

        # One fresh program name per ASCII load (T152); names loaded and not yet removed, with their copy
        self.exec_session = uuid.uuid4().hex[:6]
        self._exec_counter = 0
        self.exec_programs: dict[str, Path] = {}

        # Own state
        self.programming_mode: Optional[ProgrammingMode] = None
        self.velocity_mode: Optional[VelocityMode] = None
        self.wait_mode: Optional[WaitMode] = None
        self.enabled_axes = SingleAxis._NO_AXIS
        self.tasks = tuple([Task(self.api, i) for i in range(self.MAX_NUMBER_OF_TASKS)])

        self.init_time = datetime.datetime.now()
        self.connect_time: Optional[datetime.datetime] = None
        self.close_time: Optional[datetime.datetime] = None

    def __del__(self):
        try:
            self.close()
        except AttributeError:
            pass  # not completely initialised

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False  # Propagate exception to higher levels

    def connect(self):
        self.api.connect()
        self.connect_time = datetime.datetime.now()

    def close(self):
        self.api.close()
        self.close_time = datetime.datetime.now()

    def initialize(self):
        """
        1. Retrieve current configurations
            - Axis status (Enabled, disabled)
            - Axis position
            - Version
        2. Set standard parameter
            - SECONDS
            - PRIMARY
        :return:
        """
        self.set_programming_mode(ProgrammingMode.ABSOLUTE)
        self.set_velocity_mode(VelocityMode.ON)
        self.set_wait_mode(WaitMode.AUTO)

    def command_log(self) -> str:
        """ Return the controller log: init, connect and close times and every command sent.

        Returns
        -------
        str
            The text that :meth:`save_log` writes to ``A3200.log``.
        """

        s = f"{self.__class__.__name__}:\nInitialized: {self.init_time}\nConnected: {self.connect_time}\nClosed: {self.close_time}\n\nCommands:\n"
        s += "\n".join(map(str, self.api.history))
        return s

    def save_log(self, folder: Path | str = ".") -> str:
        """ Write :meth:`command_log` to ``<folder>/A3200.log`` and return it. """

        s = self.command_log()
        (Path(folder) / "A3200.log").write_text(s)
        return s

    def sync_internal_state(self):
        for task in self.tasks:
            task.update()

    @property
    def system_time(self) -> datetime.datetime:
        time_ms = float(self.api.SYSTEMSTATUS(SystemStatusDataItem.Timer))
        return datetime.datetime.fromtimestamp(time_ms / 1000)

    @property
    def xyz(self) -> Point3D:
        response = self.api.STATUS(
            (SingleAxis.X, AxisStatusDataItem.PositionFeedback),
            (SingleAxis.Y, AxisStatusDataItem.PositionFeedback),
            (SingleAxis.Z, AxisStatusDataItem.PositionFeedback)
        )
        return Point3D(*tuple(map(float, response.replace(",", ".").split(" "))))

    @property
    def axis_status(self) -> dict[SingleAxis, AxisStatus]:
        query_tuples = (
            (SingleAxis.X, AxisStatusDataItem.AxisStatus),
            (SingleAxis.Y, AxisStatusDataItem.AxisStatus),
            (SingleAxis.Z, AxisStatusDataItem.AxisStatus),
            (SingleAxis.A, AxisStatusDataItem.AxisStatus),
            (SingleAxis.B, AxisStatusDataItem.AxisStatus),
        )
        response = self.api.STATUS(*query_tuples)
        axis_status_tmp = map(lambda x: AxisStatus(int(x)), response.replace(",", ".").split(" "))
        axis_status = {axis: status for ((axis, dataitem), status) in zip(query_tuples, axis_status_tmp)}
        return axis_status

    def set_programming_mode(self, programming_mode: ProgrammingMode):
        # self.api.send(programming_mode.value)  # Quick, but dirty way

        programming_mode = ProgrammingMode(programming_mode)

        if programming_mode == ProgrammingMode.ABSOLUTE:
            self.api.ABSOLUTE()
        elif programming_mode == ProgrammingMode.INCREMENTAL:
            self.api.INCREMENTAL()
        else:
            raise NotImplementedError(f"Programming mode {programming_mode} not implemented yet.")
        self.programming_mode = programming_mode

    def set_velocity_mode(self, velocity_mode: VelocityMode):
        velocity_mode = VelocityMode(velocity_mode)

        self.api.VELOCITY(velocity_mode)
        self.velocity_mode = velocity_mode

    def set_wait_mode(self, wait_mode: WaitMode):
        wait_mode = WaitMode(wait_mode)

        self.api.WAIT_MODE(wait_mode)
        self.wait_mode = wait_mode

    def run_program_as_task(
            self,
            program: PathLike | AeroBasicProgram,
            *,
            task_id: Optional[int] = None,
            program_ready_timeout=10,  # Seconds
            program_start_running_timeout=10,  # Seconds
    ) -> Task:
        """ Load a program on a task over ASCII, start it and return the running task.

        The program is copied to a fresh name
        (:func:`exec_program_name`, T152) and loaded under that name, so that
        a refused load does not block the next program. The returned
        :class:`Task` removes it under that name (T127); after a removal the
        copy is deleted. Names not removed yet are listed in
        :attr:`exec_programs` (for recovery level R0).

        Parameters
        ----------
        program : path or AeroBasicProgram
            Program file, or a program that is written to a temporary file.
        task_id : int, optional
            Controller task (default 2).
        program_ready_timeout : float
            Seconds after the LOAD reply until the task must be ready. The
            compile itself happens before the reply (limited by the
            interface's ``load_timeout``).
        program_start_running_timeout : float
            Seconds after START until the task must be running or complete.

        Returns
        -------
        Task
            The started task.

        Raises
        ------
        AerotechError
            If the controller refuses the LOAD or does not reply in time
            (message with the controller's reason).
        TaskFailedError
            If the task goes into the error state (message with the decoded
            error code) or is not ready/running in time. The task is stopped
            and the program removed before the error is raised.
        """
        # Either use path as program or convert AeroBasicProgram to temporary file
        if isinstance(program, AeroBasicProgram):
            now = datetime.datetime.now()
            hash_str = hashlib.sha256(str(random.random()).encode()).hexdigest()
            path = Path(f"{now :%Y%m%d_%H%M%S}_automatic_program_{hash_str[:5]}.pgm")
            if self.program_dir is not None:
                path = self.program_dir / path
            path.parent.mkdir(exist_ok=True, parents=True)
            program.write(path)
        else:
            path = Path(program)

        # Copy the program to a fresh name: a refused load blocks only that name (T152)
        exec_path = self._exec_copy(path)

        # Load program; the program is removed under the name it was loaded with (T127)
        if task_id is None:
            task_id = 2
        self.note_task_load(task_id)
        task = Task(self.api, task_id, file_path=path, program_name=exec_path.name,
                    on_removed=self.program_removed)
        load_start = time.time()
        try:
            self.api.PROGRAM_LOAD(task_id, exec_path)
        except AerotechError as error:
            task.abort()
            raise type(error)(f"Could not load program {path} on task {task_id}: {error}") from error
        self.api.logger.info(f"Loaded {path.name} on task {task_id} in {time.time() - load_start:.1f} s")

        # Wait for program to be ready
        query_delay = 0.1
        for i in range(int(program_ready_timeout / query_delay)):
            task.update()
            if task.task_state == TaskState.program_ready or task.task_state == TaskState.program_complete:
                break
            if task.task_state == TaskState.error:
                info = task.error_info()
                task.abort()
                raise TaskFailedError(f"Could not load program {path} (task state error): {info}")
            time.sleep(query_delay)
        else:
            # path is the individual filename of the layer. exec_path is the universal path which is loaded and printed
            state = task.task_state.name
            task.abort()
            raise TaskFailedError(f"Could not load program {path} after {program_ready_timeout} seconds "
                                  f"(task state {state})!")

        # Start program
        try:
            self.api.PROGRAM_START(task_id)
        except AerotechError as error:
            task.abort()
            raise type(error)(f"Could not start program {path} on task {task_id}: {error}") from error

        # Wait for program to run
        for i in range(int(program_start_running_timeout / query_delay)):
            task.update()
            if task.task_state == TaskState.program_running or task.task_state == TaskState.program_complete:
                break
            if task.task_state == TaskState.error:
                info = task.error_info()
                task.abort()
                raise TaskFailedError(f"Program {path} did not start (task state error): {info}")
            time.sleep(query_delay)
        else:
            state = task.task_state.name
            task.abort()
            raise TaskFailedError(f"Program {path} did not start within {program_start_running_timeout} seconds "
                                  f"(task state {state})")

        return task

    def note_task_load(self, task_id: int) -> None:
        """ Count a program loaded or associated on ``task_id`` (T135).

        A program kept on a task (the z-line program) checks this count before
        it starts again: another program on its task replaced it. Loaders that
        bypass :meth:`run_program_as_task` (the library loader) call it too.

        Parameters
        ----------
        task_id : int
            Controller task.
        """

        loads = self.__dict__.setdefault("_task_loads", {})
        loads[int(task_id)] = loads.get(int(task_id), 0) + 1

    def task_load_count(self, task_id: int) -> int:
        """ Number of programs loaded on ``task_id`` through :meth:`note_task_load` (T135). """

        return self.__dict__.get("_task_loads", {}).get(int(task_id), 0)

    def _exec_copy(self, path: Path) -> Path:
        """ Copy a program file to the next fresh execution name and register it (T152). """

        exec_dir = self.program_dir if self.program_dir is not None else Path.home()
        exec_dir.mkdir(parents=True, exist_ok=True)
        self._exec_counter += 1
        exec_path = exec_dir / exec_program_name(self.exec_session, self._exec_counter, path.stem)
        exec_path.write_bytes(path.read_bytes())
        self.exec_programs[exec_path.name] = exec_path
        return exec_path

    def program_removed(self, name: str) -> None:
        """ Forget a removed execution copy and delete its file; unknown names are ignored.

        Parameters
        ----------
        name : str
            Program name passed to ``REMOVEPROGRAM``.
        """
        exec_path = self.exec_programs.pop(name, None)
        if exec_path is None:
            return
        try:
            exec_path.unlink(missing_ok=True)
        except OSError as error:
            self.api.logger.warning(f"Could not delete the execution copy {exec_path}: {error}")

    def run_program_synchron(self, program: AeroBasicProgram):
        for line in program:
            self.api.send(line)

    def enable_axes(self, axes: SingleAxis):
        self.api.ENABLE(axes)
        self.enabled_axes |= axes


class Aerotech3200(AerotechController):
    """ Aerotech A3200 controller with program task handling, without configuration.

    Can be used on its own; ``System`` uses ``devices.A3200``, which offers
    the same task handling plus the µm-based helpers.
    """

    def __init__(self, hostname: str = "127.0.0.1", port: int = 8000, *, dummy=False,
                 transport_factory=None, program_dir: Optional[PathLike | str] = None,
                 z_max: Optional[float] = None):
        """ Aerotech A3200 controller with program task handling.

        Parameters
        ----------
        hostname : str
            Host of the ASCII command interface.
        port : int
            TCP port of the ASCII command interface.
        dummy : bool
            Deprecated. Connects to a new simulated controller
            (``FakeA3200Transport``) instead of the hardware. Prefer the
            dummy backend (``System(..., backend="dummy")``) or
            ``transport_factory``.
        transport_factory : callable, optional
            Returns a socket-like object used instead of a new TCP socket,
            see :class:`AerotechAsciiInterface`.
        program_dir : str or Path, optional
            Directory for temporary program files and the uniform execution
            copy. Default: temporary programs in the current working
            directory and the execution copy in the home directory.
        z_max : float, optional
            Maximum z position in µm. Immediate absolute z moves beyond it are
            refused (see :attr:`AerotechAsciiInterface.z_limit`).
        """
        if dummy:
            from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
            transport = FakeA3200Transport(SimulatedWorld())
            self.api = AerotechAsciiInterface(hostname=hostname, port=port, transport_factory=lambda: transport)
        else:
            self.api = AerotechAsciiInterface(hostname=hostname, port=port, transport_factory=transport_factory)
        if z_max is not None:
            self.api.z_limit = z_max / 1000
        self._init_controller(self.api, program_dir)

        if dummy:
            self.connect()

    @cached_property
    def version(self):
        return self.api.VERSION()

    def home(self):
        self.api.HOME(Axis.YZ | Axis.AB)
        self.api.LINEAR(Y=80)
        self.api.HOME(SingleAxis.X)
        self.api.LINEAR(Y=0)
