import abc
from typing import Optional, Any, Iterator, Literal

from nanofactorysystem.aerobasic import SingleAxis, BezierMode, Axis, GalvoLaserOverrideMode, IFOV_Mode, VelocityMode
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.setups import SetupIFOV
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D

class IFOV_AeroBasicProgram(AeroBasicProgram):
    IFOV_TIME = 200
    # IFOV Size should be half of Objective FOV BUT Femtika does full FOV
    IFOV_SIZE_20x = 0.50  # 0.500/2
    IFOV_SIZE_63x = 0.15  # 0.150/2

    # Writing speed is at maximum 100*ifov_size
    # Tracking speed should be a little higher than the actual writing speed (-> * 1.1 takes care of that)
    TRACKING_SPEED_63x = (IFOV_SIZE_63x*100)*1.1
    TRACKING_SPEED_20x = (IFOV_SIZE_20x*100)*1.1
    TRACKING_ACCELERATION = 600  # 1000 is possible - better results with 600
    VELOCITY_MODE = VelocityMode.ON

    RAMP_TYPE = ""

    ROTATION_A = -0.6  # experimental validated values for Zeiss 20x Objective
    ROTATION_B = -1.1  # experimental validated values for Zeiss 20x Objective

    def __init__(self, coordinate_system: CoordinateSystem):
        super().__init__()
        self.coordinate_system = coordinate_system

    def initialise_IFOV_configuration(self, objective="Zeiss 63x"):
        if objective == "Zeiss 20x":
            ifov_size = self.IFOV_SIZE_20x
        elif objective == "Zeiss 63x":
            ifov_size = self.IFOV_SIZE_63x
        else:
            raise NotImplementedError(f"Objective {objective} not implemented")

        self.comment("\nBasic configuration")
        self.send("LOOKAHEAD FAST")
        self.send("CRITICAL START")
        self.send("METRIC")
        self.send("SECONDS")
        self.send("ABSOLUTE")  # ABSOLUTE has to be set for IFOV
        self.VELOCITY(self.VELOCITY_MODE)
        self.send("WAIT MODE AUTO")
        self.END_IFOV()
        self.send("GALVO LASEROVERRIDE A AUTO")  # NOTE differs from Femtika original Setup

        # RAMP Rates
        self.comment("\nSetting Ramp rates and Type")
        self.send("RAMP MODE RATE")
        self.send("RAMP RATE 0")    # either 0 or high value between 40000 and 50000
        self.send("RAMP RATE A 0")
        self.send("RAMP RATE B 0")

        # Synchronize axes
        self.comment("\nSynchronize axes")
        self.send("IFOV AXISPAIR 0, A, X")
        self.send("IFOV AXISPAIR 1, B, Y")

        # ENCODING
        self.comment("\nEncoding Output")
        self.send("ENCODER OUT X ON 0,0")
        self.send("ENCODER OUT Y ON 0,0")

        # IFOV Settings
        self.comment("\nIFOV Settings")
        self.send(f"IFOV SYNCAXES Z")
        self.send(f"IFOV TIME {self.IFOV_TIME:f}")
        self.send(f"IFOV SIZE {ifov_size:f}")
        if objective == "Zeiss 63x":
            self.send(f"IFOV TRACKINGSPEED {self.TRACKING_SPEED_63x:f}")
        elif objective == "Zeiss 20x":
            self.send(f"IFOV TRACKINGSPEED {self.TRACKING_SPEED_20x:f}")
        self.send(f"IFOV TRACKINGACCEL {self.TRACKING_ACCELERATION:f}")
        # Compensation of tilted GALVO Axis
        # self.send(f"GALVO ROTATION A {self.ROTATION_A}")
        # self.send("GALVO ROTATION B {self.ROTATION_B}")

    def end_ifov_program(self):
        self.send("CRITICAL END")
        self.END_IFOV()
        self.send("ENCODER OUT X OFF")
        self.send("ENCODER OUT Y OFF")

    def start_buffered_run(self):
        self.send("WAIT (TASKSTATUS(1, DATAITEM_QueueLineCount) >=900 ) 1 1:")

    def _apply_ifov_conversion(self, coordinate: dict) -> dict:
        result = {}
        for k, v in coordinate.items():
            if k == "Z":
                # Z offset from the coordinate system (StaticOffset = PlaneFit-Z)
                result[k] = v + self.coordinate_system.z_function(0, 0)
            elif k == "X":
                result[k] = v + self.coordinate_system.offset_x
            elif k == "Y":
                result[k] = v + self.coordinate_system.offset_y
            else:
                result[k] = v
        # Unit scaling (µm → mm)
        return {k: v * self.coordinate_system.unit.value for k, v in result.items()}

    def LINEAR(self, X=None, Y=None, Z=None, A=None, B=None, E=None, F=None):
        coordinate = {"X": X, "Y": Y, "Z": Z, "A": A, "B": B}
        coordinate = {k: v for k, v in coordinate.items() if v is not None}
        converted = self._apply_ifov_conversion(coordinate)
        return super().LINEAR(**converted, F=None, E=None)

    def RAPID(self, X=None, Y=None, Z=None, A=None, B=None, E=None, F=None):
        coordinate = {"X": X, "Y": Y, "Z": Z, "A": A, "B": B}
        coordinate = {k: v for k, v in coordinate.items() if v is not None}
        converted = self._apply_ifov_conversion(coordinate)
        return super().RAPID(**converted, F=None, E=None)

    def RESET_GALVO(self):
        galvo_reset_coordinates = {"A": 0,
                                   "B": 0}
        return super().RAPID(**galvo_reset_coordinates, F=None, E=None)

    def COMPENSATE_GALVO_ROTATION(self,
                                  axis: SingleAxis):
        if axis == SingleAxis.A:
            rotation = self.ROTATION_A
        elif axis == SingleAxis.B:
            rotation = self.ROTATION_B
        else:
            raise SyntaxError(f"No compensation possible for {axis.name}")

        return super().GALVO_ROTATION(axis, rotation)

    def SET_SPEED(self,
                  F: float=None,
                  ax: Literal["A","B"]=None):
        """ default speed is 10 mm/s"""
        if F is not None and F >= 15:
            raise ValueError(f"Speed has to be in mm(!) per seconds. {F} mm/s is too high.")
        return super().CONNECTED_SPEED(speed_in_mm_per_sec=F, axis=ax)

    def SET_POWER(self,
                  power:float):
        """Power needs to be between 0 and 10.
        It is dependent on the calibration file."""
        return super().POWER(power)

    def START_IFOV(self):
        return super().IFOV(IFOV_Mode.ON)

    def END_IFOV(self):
        return super().IFOV(IFOV_Mode.OFF)

    # OLD
    '''
    def LINEAR(self,
               X: Optional[float] = None,
               Y: Optional[float] = None,
               Z: Optional[float] = None,
               A: Optional[float] = None,
               B: Optional[float] = None,
               E: Optional[float] = None,
               F: Optional[float] = None):
        coordinate = {
            "X": X,
            "Y": Y,
            "Z": Z,
            "A": A,
            "B": B,
        }
        coordinate = {k: v for k, v in coordinate.items() if v is not None}

        return super().LINEAR(**coordinate, F=None, E=None)

    def RAPID(self,
              X: Optional[float] = None,
              Y: Optional[float] = None,
              Z: Optional[float] = None,
              A: Optional[float] = None,
              B: Optional[float] = None,
              E: Optional[float] = None,
              F: Optional[float] = None):
        coordinate = {
            "X": X,
            "Y": Y,
            "Z": Z,
            "A": A,
            "B": B,
        }
        coordinate = {k: v for k, v in coordinate.items() if v is not None}

        return super().RAPID(**coordinate, F=None, E=None)
    '''


class DrawableAeroBasicProgram(AeroBasicProgram):
    def __init__(self, coordinate_system: CoordinateSystem):
        super().__init__()
        self.coordinate_system = coordinate_system

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
        coordinate = {
            "X": X,
            "Y": Y,
            "Z": Z,
            "A": A,
            "B": B,
        }
        coordinate = {k: v for k, v in coordinate.items() if v is not None}
        converted_coordinate = self.coordinate_system.convert(coordinate)

        if F is not None:
            F *= self.coordinate_system.unit.value
        if E is not None:
            E *= self.coordinate_system.unit.value
        return super().LINEAR(**converted_coordinate, F=F, E=E)

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
        return super().CW(
            **self._convert_CW_CCW_args(
                axis1=axis1,
                axis1_endpoint=axis1_endpoint,
                axis2=axis2,
                axis2_endpoint=axis2_endpoint,
                radius=radius,
                axis1_center=axis1_center,
                axis2_center=axis2_center,
                velocity=velocity
            )
        )

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
        return super().CCW(
            **self._convert_CW_CCW_args(
                axis1=axis1,
                axis1_endpoint=axis1_endpoint,
                axis2=axis2,
                axis2_endpoint=axis2_endpoint,
                radius=radius,
                axis1_center=axis1_center,
                axis2_center=axis2_center,
                velocity=velocity
            )
        )

    def _convert_CW_CCW_args(
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
        # Map axes
        axis1_mapped = self.coordinate_system.axis_mapping.get(axis1.parameter_name, axis1.parameter_name)
        axis2_mapped = self.coordinate_system.axis_mapping.get(axis2.parameter_name, axis2.parameter_name)

        # Convert endpoints
        axis1_endpoint = self.coordinate_system.convert({axis1.parameter_name: axis1_endpoint})[axis1_mapped]
        axis2_endpoint = self.coordinate_system.convert({axis2.parameter_name: axis2_endpoint})[axis2_mapped]

        # Convert radius
        if radius is not None:
            radius *= self.coordinate_system.unit.value

        # Convert axis center
        if axis1_center is not None:
            # axis1_center = self.coordinate_system.convert({axis1.parameter_name: axis1_center})[axis1_mapped]
            axis1_center = axis1_center * self.coordinate_system.unit.value
        if axis2_center is not None:
            # axis2_center = self.coordinate_system.convert({axis2.parameter_name: axis2_center})[axis2_mapped]
            axis2_center = axis2_center * self.coordinate_system.unit.value

        # Convert velocity
        if velocity is not None:
            velocity *= self.coordinate_system.unit.value

        return {
            'axis1': Axis(axis1_mapped),
            'axis1_endpoint': axis1_endpoint,
            'axis2': Axis(axis2_mapped),
            'axis2_endpoint': axis2_endpoint,
            'radius': radius,
            'axis1_center': axis1_center,
            'axis2_center': axis2_center,
            'velocity': velocity
        }

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
        raise NotImplemented("To be done")


class DrawableObject(abc.ABC):
    def __init__(self):
        pass

    def __repr__(self):
        return f"{self.__class__.__name__} at {self.center_point}"

    @property
    @abc.abstractmethod
    def center_point(self) -> Point2D:
        pass

    def draw_on(self, coordinate_system: CoordinateSystem, plot_name=None) -> DrawableAeroBasicProgram:
        program = DrawableAeroBasicProgram(coordinate_system)
        if plot_name is None:
            for layer in self.iterate_layers(coordinate_system):
                program.add_programm(layer)
            return program
        else:
            for layer in self.iterate_layers(coordinate_system, plot_name=plot_name):
                program.add_programm(layer)
            return program

    @abc.abstractmethod
    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        pass

    def _init_args(self) -> dict[str, Any]:
        # Try to import numpy safely
        try:
            import numpy as np
        except ImportError:
            np = None

        code = self.__init__.__code__

        # ÄNDERUNG 1: Verwende co_varnames statt co_names
        # co_varnames = lokale Variablen/Parameter im __init__
        # [1:] = skip 'self'
        param_names = code.co_varnames[1:]

        # ÄNDERUNG 2: Entferne die problematische Prüfung
        # (Die alte Zeile: if "__init__" not in code.co_names: return {})

        kwargs = {}
        for name in param_names:
            attr = getattr(self, name, "[NOT FOUND]")

            # Skip missing attributes
            if isinstance(attr, str) and attr == "[NOT FOUND]":
                continue

            # Skip special attributes
            if name in ("data", "height_profile"):
                continue

            # Properly handle serialization
            if hasattr(attr, "to_json"):
                attr = attr.to_json()
            elif np is not None and isinstance(attr, np.ndarray):
                attr = {
                    "type": "ndarray",
                    "shape": attr.shape,
                    "dtype": str(attr.dtype),
                    "values": attr.tolist()
                }
            elif isinstance(attr, (str, int, float, dict, list)) or attr is None:
                pass
            else:
                try:
                    attr = str(attr)
                except Exception:
                    attr = f"<unserializable object of type {type(attr).__name__}>"

            kwargs[name] = attr

        return kwargs

    def to_json(self):
        return {
            "__class__": self.__class__.__name__,
            "center_point": self.center_point.as_tuple(),
            "__init__": self._init_args()
        }

    # def _init_args(self) -> dict[str, Any]:
    #     code = self.__init__.__code__
    #     if "__init__" not in code.co_names:
    #         return {}
    #
    #     start_idx = code.co_names.index("__init__") + 1
    #     kwargs = {}
    #     # for name in code.co_names[start_idx:start_idx + code.co_argcount]: # here is a mistake - co_argcount is 5 but should be higher
    #     for name in code.co_names[start_idx:]:
    #         attr = getattr(self, name, "[NOT FOUND]")
    #         if name == "data" or name == "height_profile":
    #             continue
    #         if attr == "[NOT FOUND]":
    #             continue
    #         if hasattr(attr, "to_json"):
    #             attr = attr.to_json()
    #         elif not isinstance(attr, (str, int, float, dict, list)) or attr is not None:
    #             attr = str(attr)
    #
    #         kwargs[name] = attr
    #     return kwargs
    #
    # def _init_args(self) -> dict[str, Any]:
    #     # Try to import numpy safely
    #     try:
    #         import numpy as np
    #     except ImportError:
    #         np = None
    #
    #     code = self.__init__.__code__
    #     if "__init__" not in code.co_names:
    #         return {}
    #
    #     start_idx = code.co_names.index("__init__") + 1
    #     kwargs = {}
    #
    #     for name in code.co_names[start_idx:]:
    #         attr = getattr(self, name, "[NOT FOUND]")
    #
    #         # Skip missing attributes
    #         if isinstance(attr, str) and attr == "[NOT FOUND]":
    #             continue
    #
    #         # Skip special attributes
    #         if name in ("data", "height_profile"):
    #             continue
    #
    #             # Properly handle serialization
    #         if hasattr(attr, "to_json"):
    #             attr = attr.to_json()
    #         elif np is not None and isinstance(attr, np.ndarray):
    #             # Serialize numpy arrays safely
    #             attr = {
    #                 "type": "ndarray",
    #                 "shape": attr.shape,
    #                 "dtype": str(attr.dtype),
    #                 "values": attr.tolist()
    #             }
    #         elif isinstance(attr, (str, int, float, dict, list)) or attr is None:
    #             # Keep native types unchanged
    #             pass
    #         else:
    #             # Fallback for custom objects — avoid infinite loops
    #             try:
    #                 attr = str(attr)
    #             except Exception:
    #                 attr = f"<unserializable object of type {type(attr).__name__}>"
    #
    #         kwargs[name] = attr
    #
    #     return kwargs


class VoidStructure(DrawableObject):
    """ Structure that does nothing """

    @property
    def center_point(self) -> Point2D:
        return Point2D(0, 0)

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        yield DrawableAeroBasicProgram(coordinate_system)


class DrawablePoint(DrawableObject):
    def __init__(
            self,
            center: Point2D | Point3D,
            duration: float = 0.1
    ):
        """
        duration in seconds
        """
        super().__init__()
        self.center = center
        self.duration = duration

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        program.LINEAR(**self.center.as_dict())
        program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
        program.DWELL(self.duration)
        program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)
        yield program
