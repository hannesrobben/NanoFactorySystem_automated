import abc
import logging
from pathlib import Path
from typing import Optional, Literal

from nanofactorysystem.aerobasic.constants import Axis, AxisStatusDataItem, TaskStatusDataItem, SingleAxis
from nanofactorysystem.aerobasic.constants.laser import GalvoLaserOverrideMode, IFOV_Mode
from nanofactorysystem.aerobasic.constants.motions import BezierMode
from nanofactorysystem.aerobasic.constants.system import SystemStatusDataItem, WaitMode
from nanofactorysystem.aerobasic.constants.tasks import VelocityMode


class AeroBasicAPI(abc.ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def __call__(self, program):
        """ Method to extend the current program """
        pass

    @abc.abstractmethod
    def send(self, command: str) -> str:
        pass

    @staticmethod
    def _assert_is_single_axis(axis: SingleAxis, *, name="Axis") -> None:
        if not axis.is_single_axis():
            raise ValueError(f"{name} has to be single axis (is {axis})")

    # =========================================================================================================
    # =============================================== Functions ===============================================
    # =========================================================================================================
    def ACKNOWLEDGEALL(self):
        # Acknowledge all errors and accept them
        return self.send("ACKNOWLEDGEALL")

    def ERROR_DECODE(self, error_code: int, error_location: int):
        # Acknowledge all errors and accept them
        return self.send(f"ERRORDECODE {error_code:d}, {error_location:d}")

    def ABSOLUTE(self):
        # Set programming mode to "ABSOLUTE"
        return self.send("ABSOLUTE")

    def INCREMENTAL(self):
        # Set programming mode to "Incremental"
        return self.send("INCREMENTAL")

    def ENABLE(self, axes: SingleAxis) -> str:
        # Enable an axis (can be multiple axes at once)
        return self.send(f"ENABLE {axes.parameter_name}")

    def DISABLE(self, axes: SingleAxis) -> str:
        # Disable an axis (can be multiple axes at once)
        return self.send(f"DISABLE {axes.parameter_name}")

    def ABORT(self, axes: SingleAxis) -> str:
        # Abort all movements on specified axes (can be multiple axes at once)
        return self.send(f"ABORT {axes.parameter_name}")

    def VELOCITY(self, mode: VelocityMode) -> str:
        # Change velocity mode
        return self.send(f"VELOCITY {mode.name}")

    def WAIT_MODE(self, mode: WaitMode) -> str:
        # Change wait mode
        # NOTE (HR) Program Setup command
        return self.send(f"WAIT MODE {mode.name}")

    def WAIT(self, mode: WaitMode, axis="X Y") -> str:
        # send wait command
        # NOTE auto wait is not possible
        if mode == WaitMode.AUTO:
            raise TypeError("WAIT MODE AUTO NOT POSSIBLE")
        return self.send(f"WAIT {mode.value} {axis}")

    def DWELL(self, duration: float):
        """
        :param duration: in seconds
        """
        # NOTE (HR) Program Flow Command
        assert 0 < duration < 4.29e6
        return self.send(f"DWELL {duration:.3f}")

    def HOME(self, axes: SingleAxis, *, conditional: bool = False) -> str:
        # Move axes to HOME position (can be multiple axes at once)
        cmd = f"HOME {axes.parameter_name}"
        if conditional:
            cmd += " CONDITIONAL"
        return self.send(cmd)

    def AXISSTATUS(self, axis: SingleAxis, axisstatus_dataitem: AxisStatusDataItem, *, additional_data=None) -> str:
        if not axis.is_single_axis():
            raise RuntimeError("Only single axis is allowed here")

        if additional_data is not None:
            additional_data = f", {additional_data}"
        else:
            additional_data = ""

        response = self.send(f"AXISSTATUS({axis.parameter_name}, {axisstatus_dataitem.as_dataitem}{additional_data})")
        return response

    def SYSTEMSTATUS(self, systemstatus_dataitem: SystemStatusDataItem, *, additional_data=None) -> str:
        if additional_data is not None:
            additional_data = f", {additional_data}"
        else:
            additional_data = ""

        response = self.send(f"SYSTEMSTATUS({systemstatus_dataitem.as_dataitem}{additional_data})")
        return response

    # Program loading
    def PROGRAM_LOAD(self, task_id: int, program_path: Path | str, *, absolute_path=True) -> str:
        if absolute_path:
            program_path = Path(program_path).absolute()

        return self.send(f"PROGRAM {task_id} LOAD \"{program_path}\"")

    def PROGRAM_ASSOCIATE(self, task_id: int, program_path: Path | str) -> str:
        program_name = Path(program_path).name
        return self.send(f"PROGRAM {task_id} ASSOCIATE \"{program_name}\"")

    def PROGRAM_START(self, task_id: int) -> str:
        return self.send(f"PROGRAM {task_id} START")

    def PROGRAM_STOP(self, task_id: Optional[int] = None) -> str:
        if task_id is None:
            return self.send(f"PROGRAM STOP")
        return self.send(f"PROGRAM {task_id} STOP")

    def PROGRAM_STATUS(
            self,
            task_id: Optional[int],
            taskstatus_dataitem: TaskStatusDataItem,
            *,
            additional_data=None
    ) -> str:
        if task_id is None:
            task_id = ""
        else:
            task_id = f"{task_id}, "
        if additional_data is not None:
            additional_data = f", {additional_data}"
        else:
            additional_data = ""

        response = self.send(f"TASKSTATUS({task_id}{taskstatus_dataitem.as_dataitem}{additional_data})")
        return response

    def REMOVE_PROGRAM(
            self,
            program_name: str | Path
    ):
        if isinstance(program_name, Path):
            program_name = program_name.name

        return self.send(f"REMOVEPROGRAM \"{program_name}\"")

    def APPLY_DEFAULTS_AXIS(self, axes: SingleAxis):
        return self.send(f"APPLYDEFAULTS AXIS {axes.parameter_name}")

    def APPLY_DEFAULTS_TASK(self, task_id: Optional[int] = None):
        if task_id is None:
            return self.send(f"APPLYDEFAULTS TASK")
        return self.send(f"APPLYDEFAULTS TASK {task_id}")

    # Synchronous Movements
    def LINEAR(
            self,
            X: Optional[float] = None,
            Y: Optional[float] = None,
            Z: Optional[float] = None,
            A: Optional[float] = None,
            B: Optional[float] = None,
            F: Optional[float] = None,
            E: Optional[float] = None
    ):
        if F is not None and E is not None:
            raise ValueError(f"Cannot specify dependent and independent velocity at same time ({E=}, {F=})")

        cmd = "LINEAR"
        # Axes
        if X is not None:
            cmd += f" X{X:.10f}"
        if Y is not None:
            cmd += f" Y{Y:.10f}"
        if Z is not None:
            cmd += f" Z{Z:.10f}"
        if A is not None:
            cmd += f" A{A:.10f}"
        if B is not None:
            cmd += f" B{B:.10f}"

        # Velocities
        if F is not None:
            cmd += f" F{F:f}"
        if E is not None:
            cmd += f" E{E:f}"

        return self.send(cmd)

    def RAPID(
            self,
            X: Optional[float] = None,
            Y: Optional[float] = None,
            Z: Optional[float] = None,
            A: Optional[float] = None,
            B: Optional[float] = None,
            F: Optional[float] = None,
            E: Optional[float] = None
    ):
        if F is not None and E is not None:
            raise ValueError(f"Cannot specify dependent and independent velocity at same time ({E=}, {F=})")

        cmd = "RAPID"
        # Axes
        if X is not None:
            cmd += f" X{X:.10f}"
        if Y is not None:
            cmd += f" Y{Y:.10f}"
        if Z is not None:
            cmd += f" Z{Z:.10f}"
        if A is not None:
            cmd += f" A{A:.10f}"
        if B is not None:
            cmd += f" B{B:.10f}"

        # Velocities
        if F is not None:
            cmd += f" F{F:f}"
        if E is not None:
            cmd += f" E{E:f}"

        return self.send(cmd)

    @staticmethod
    def _CW_CCW(
            axis1: SingleAxis,
            axis1_endpoint: float,
            axis2: SingleAxis,
            axis2_endpoint: float,
            radius: Optional[float] = None,
            axis1_center: Optional[float] = None,
            axis2_center: Optional[float] = None,
            velocity: float = None
    ) -> str:
        # Axes
        AeroBasicAPI._assert_is_single_axis(axis1, name="axis1")
        AeroBasicAPI._assert_is_single_axis(axis2, name="axis2")
        cmd = f"{axis1.parameter_name}{axis1_endpoint:.10f} {axis2.parameter_name}{axis2_endpoint:.10f}"

        # Need to have either radius OR (axis1_center and axis2_center)
        if (radius is None) == (axis1_center is None and axis2_center is None):
            raise ValueError(f"Invalid combination of arguments. Got {radius=}, {axis1_center=}, {axis2_center=}")

        if radius is not None:
            cmd += f" R{radius:.10f}"
        else:
            cmd += f" I{axis1_center:.10f} J{axis2_center:.10f}"

        # Velocity
        if velocity is not None:
            cmd += f" F{velocity}"

        return cmd

    def CW(
            self,
            axis1: SingleAxis,
            axis1_endpoint: float,
            axis2: SingleAxis,
            axis2_endpoint: float,
            radius: Optional[float] = None,
            axis1_center: Optional[float] = None,
            axis2_center: Optional[float] = None,
            velocity: float = None
    ):
        cmd_args = self._CW_CCW(
            axis1,
            axis1_endpoint,
            axis2,
            axis2_endpoint,
            radius,
            axis1_center,
            axis2_center,
            velocity
        )
        return self.send(f"CW {cmd_args}")

    def CCW(
            self,
            axis1: SingleAxis,
            axis1_endpoint: float,
            axis2: SingleAxis,
            axis2_endpoint: float,
            radius: Optional[float] = None,
            axis1_center: Optional[float] = None,
            axis2_center: Optional[float] = None,
            velocity: float = None
    ):
        cmd_args = self._CW_CCW(
            axis1,
            axis1_endpoint,
            axis2,
            axis2_endpoint,
            radius,
            axis1_center,
            axis2_center,
            velocity
        )
        return self.send(f"CCW {cmd_args}")

    def BEZIER(
            self,
            mode: BezierMode,
            ax_h: SingleAxis,
            ax_v: SingleAxis,
            p0_h: float,
            p1_h: float,
            p2_h: float,
            p3_h: Optional[float],
            p0_v: float,
            p1_v: float,
            p2_v: float,
            p3_v: Optional[float],
            tolerance: Optional[float]
    ):
        # Check parameters
        if not ax_h.is_single_axis():
            raise ValueError(f"ax_h has to be a single axis (is {ax_h})")
        if not ax_v.is_single_axis():
            raise ValueError(f"ax_v has to be a single axis (is {ax_v})")
        if (p3_h is None) != (p3_v is None):
            raise ValueError(f"Either set both p3_h and p3_v to None or != None. (Currently {p3_h=}, {p3_v=})")

        # Build command
        ax_h_string = f"{ax_h.parameter_name}, {p0_h}, {p1_h}, {p2_h}"
        ax_v_string = f"{ax_v.parameter_name}, {p0_v}, {p1_v}, {p2_v}"
        if p3_h:
            ax_h_string += f", {p3_h}"
            ax_v_string += f", {p3_v}"

        if tolerance:
            tolerance_string = f"TOLERANCE {tolerance}"
        else:
            tolerance_string = ""
        return self.send(f"BEZIER {mode.value} {ax_h_string}, {ax_v_string}{tolerance_string}")

    # Asynchronous Movements
    def FREERUN(self, axis: SingleAxis, velocity: float | bool | Literal["STOP"]):
        self._assert_is_single_axis(axis)

        if velocity is False:
            velocity = "STOP"

        if not isinstance(velocity, float) or velocity == "STOP":
            raise ValueError(f"Velocity cannot be {velocity}. Has to be either a float or False or 'STOP'")

        return self.send(f"FREERUN {axis.parameter_name} {velocity}")

    def MOVEABS(self, axis: SingleAxis, position: float, speed: float):
        self._assert_is_single_axis(axis)

        return self.send(f"MOVEABS {axis.parameter_name} {position} {speed}")

    def MOVEINC(self, axis: SingleAxis, distance: float, speed: float):
        self._assert_is_single_axis(axis)

        return self.send(f"MOVEINC {axis.parameter_name} {distance} {speed}")

    def MOVEDELAY(self, axis: SingleAxis, time_in_ms: float, ):
        # NOTE (HR) Motion command - waiting for a specific time
        self._assert_is_single_axis(axis)

        return self.send(f"MOVEDELAY {axis.parameter_name},  {time_in_ms}")

    def HOMEASYNC(self):
        pass

    def OSCILLATE(
            self,
            axis: SingleAxis,
            distance: float,
            frequency: float,
            cycles: int,
            num_iterations: int = 1
    ):
        # NOTE (HR) Program tuning command
        self._assert_is_single_axis(axis)
        return self.send(f"OSCILLATE {axis.parameter_name}, {distance}, {frequency}, {cycles}, {num_iterations}")

    # GALVO
    def GALVO_LASER_OVERRIDE(self, mode: GalvoLaserOverrideMode, *, axis=SingleAxis.A):
        if axis not in Axis.AB:
            raise ValueError(f"Axis needs to be AB (is {axis})")

        self.send(f"GALVO LASEROVERRIDE {axis.parameter_name} {mode.value}")

    def GALVO_ROTATION(self,
                       axis: SingleAxis,
                       compensation_angle: float):
        return self.send(f"GALVO ROTATION {axis.parameter_name} {compensation_angle:3f}")

    # IFOV
    def IFOV(self,
             mode: IFOV_Mode):
        return self.send(f"IFOV {mode.value}")

    def CONNECTED_SPEED(self,
                        speed_in_mm_per_sec: float = None,
                        axis=None):
        if speed_in_mm_per_sec is None:
            speed_in_mm_per_sec = 10  # max speed is ifov_size*100
        if axis is None:
            return self.send(f"F{speed_in_mm_per_sec}")
        elif axis.lower() == "a":
            return self.send(f"AF{speed_in_mm_per_sec}")
        elif axis.lower() == "b":
            return self.send(f"BF{speed_in_mm_per_sec}")
        elif axis.lower() == "z":
            return self.send(f"ZF{speed_in_mm_per_sec}")
        else:
            return


    def POWER(self,
              power: float):
        if power < 0:
            raise ValueError(f"Power needs to be >= 0")
        elif power > 10:
            raise ValueError(
                f"Power needs to be >= 10. Unit is NOT mW or µW. It has to interpolated from the calibration file and "
                f"therefore has a value between 0 and 10 to attenuate the attenuator!")
        return self.send(f"$AO[0].A={power}")

    def IFOV_TIME(self, search_time: int = 200):
        """
        Configures the maximum search time that the controller looks ahead in Infinite Field of View (IFOV).
        Use the IFOV TIME command to specify the maximum search time, in milliseconds, that the controller looks ahead
        into your AeroBasic program to generate servo motion in Infinite Field of View (IFOV).
            * The value that you use must be an integer that is divisible by 5 milliseconds.
            * The value that you use for <SearchTime> cannot exceed the value that you specify for the IFOVMaximumTime
              parameter.

        Aerotech recommends that you start with a value of 200 milliseconds for <SearchTime>.
        """
        if search_time % 5 != 0:
            raise ValueError(f"Search time is not divisible by 5ms ({search_time=})")
        # if search_time > IFOVMaximumTime:

        return self.send(f"IFOV TIME {search_time}")
