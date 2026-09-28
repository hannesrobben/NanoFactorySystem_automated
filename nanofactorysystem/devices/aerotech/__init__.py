import datetime
import hashlib
import random
import time
import shutil
from functools import cached_property
from os import PathLike
from pathlib import Path
from typing import Optional

from nanofactorysystem.aerobasic import AxisStatusDataItem, SingleAxis, SystemStatusDataItem, WaitMode, Axis
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, DummyAsciiInterface
from nanofactorysystem.aerobasic.constants import AxisStatus
from nanofactorysystem.aerobasic.constants.tasks import ProgrammingMode, TaskState, VelocityMode
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.devices.aerotech.task import Task
from nanofactorysystem.devices.coordinate_system import Point3D


class Aerotech3200:
    MAX_NUMBER_OF_TASKS = 32

    def __init__(self, hostname: str = "127.0.0.1", port: int = 8000, *, dummy=False,
                 transport_factory=None, program_dir: Optional[PathLike | str] = None):
        """ Aerotech A3200 controller with program task handling.

        Parameters
        ----------
        hostname : str
            Host of the ASCII command interface.
        port : int
            TCP port of the ASCII command interface.
        dummy : bool
            Deprecated. Use the dummy backend (``System(..., backend="dummy")``
            or ``transport_factory``) instead.
        transport_factory : callable, optional
            Returns a socket-like object used instead of a new TCP socket,
            see :class:`AerotechAsciiInterface`.
        program_dir : str or Path, optional
            Directory for temporary program files and the uniform execution
            copy. Default: temporary programs in the current working
            directory and the execution copy in the home directory.
        """
        if dummy:
            self.api = DummyAsciiInterface()
        else:
            self.api = AerotechAsciiInterface(hostname=hostname, port=port, transport_factory=transport_factory)
        self.program_dir = Path(program_dir) if program_dir is not None else None

        # Own state
        self.programming_mode: Optional[ProgrammingMode] = None
        self.velocity_mode: Optional[VelocityMode] = None
        self.wait_mode: Optional[WaitMode] = None
        self.enabled_axes = SingleAxis._NO_AXIS
        self.tasks = tuple([Task(self.api, i) for i in range(Aerotech3200.MAX_NUMBER_OF_TASKS)])

        self.init_time = datetime.datetime.now()
        self.connect_time: Optional[datetime.datetime] = None
        self.close_time: Optional[datetime.datetime] = None

    def __del__(self):
        self.close()

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

    def save_log(self, folder: Path | str = ".") -> str:
        s = f"{self.__class__.__name__}:\nInitialized: {self.init_time}\nConnected: {self.connect_time}\nClosed: {self.close_time}\n\nCommands:\n"
        s += "\n".join(map(str, self.api.history))
        (Path(folder) / "A3200.log").write_text(s)
        return s

    def sync_internal_state(self):
        for task in self.tasks:
            task.update()

    @cached_property
    def version(self):
        return self.api.VERSION()

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
        # TODO(dwoiwode): Delete function
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

        # Copy program to uniform name for execution to avoid loading too many programs on controller.
        exec_dir = self.program_dir if self.program_dir is not None else Path.home()
        exec_path = exec_dir / "python_aerobasic_program.pgm"    # todo (hr 26.2.26 - Bugfixing) here maybe deletion of prior program?
        exec_path.write_bytes(path.read_bytes())

        # Load program
        if task_id is None:
            # TODO: Better algorithm to determine task_id
            task_id = 2
# here error occurs - HR - 20x objective - binary program loading
        self.api.PROGRAM_LOAD(task_id, exec_path)

        # Wait for program to be ready
        task = Task(self.api, task_id, file_path=path)
        query_delay = 0.1
        for i in range(int(program_ready_timeout / query_delay)):
            task.update()
            if task.task_state == TaskState.program_ready or task.task_state == TaskState.program_complete:
                break
            time.sleep(query_delay)
        else:
            # path is the individual filename of the layer. exec_path is the universal path which is loaded and printed
            raise RuntimeError(f"Could not load program {path} after {program_ready_timeout} seconds!")

        # Start program
        self.api.PROGRAM_START(task_id)

        # Wait for program to run
        for i in range(int(program_start_running_timeout / query_delay)):
            task.update()
            if task.task_state == TaskState.program_running or task.task_state == TaskState.program_complete:
                break
            time.sleep(query_delay)
        else:
            raise RuntimeError("Program did not start")

        return task

    def run_program_synchron(self, program: AeroBasicProgram):
        for line in program:
            self.api.send(line)

    def enable_axes(self, axes: SingleAxis):
        self.api.ENABLE(axes)
        self.enabled_axes |= axes

    def home(self):
        self.api.HOME(Axis.YZ | Axis.AB)
        self.api.LINEAR(Y=80)
        self.api.HOME(SingleAxis.X)
        self.api.LINEAR(Y=0)
