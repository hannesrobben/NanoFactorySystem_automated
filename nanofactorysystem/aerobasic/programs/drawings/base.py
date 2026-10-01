import abc
import enum
import importlib
import inspect
import warnings
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

    # Constructor parameters that are stored under another attribute name (parameter -> attribute)
    _json_attributes: dict[str, str] = {}

    # Constructor parameters that are not serialised; arrays such as height profiles are stored (N046)
    _json_skip: tuple[str, ...] = ()

    def _init_args(self) -> dict[str, Any]:
        """ Return the constructor arguments of this structure in JSON form.

        Only the parameters of ``__init__`` are considered. Each is read from
        the attribute of the same name (or the one named in
        ``_json_attributes``) and encoded with :func:`encode_json_value`, so
        that :func:`structure_from_json` can rebuild the structure. A
        parameter without such an attribute cannot be recovered; a warning
        names it, and :meth:`to_json` lists it under ``"__missing__"``.

        Returns
        -------
        dict
            Parameter name → encoded value.
        """

        arguments, _ = self._collect_init_args()
        return arguments

    def _collect_init_args(self) -> tuple[dict[str, Any], list[str]]:
        arguments, missing = {}, []
        for name in _init_parameters(type(self)):
            if name in self._json_skip:
                missing.append(name)
                continue
            attribute = self._json_attributes.get(name, name)
            if not hasattr(self, attribute):
                missing.append(name)
                continue
            try:
                arguments[name] = encode_json_value(getattr(self, attribute))
            except TypeError:
                missing.append(name)
        if missing:
            warnings.warn(f"{type(self).__name__}: the constructor arguments {missing} cannot be stored; "
                          f"the structure cannot be rebuilt from its JSON form without them.", stacklevel=3)
        return arguments, missing

    def to_json(self) -> dict[str, Any]:
        """ Return a JSON-compatible description of this structure.

        Returns
        -------
        dict
            ``__class__`` (class name), ``__module__``, ``center_point``,
            ``__init__`` (encoded constructor arguments) and, if some
            arguments could not be stored, ``__missing__``.
        """

        arguments, missing = self._collect_init_args()
        data = {
            "__class__": self.__class__.__name__,
            "__module__": self.__class__.__module__,
            "center_point": self.center_point.as_tuple(),
            "__init__": arguments,
        }
        if missing:
            data["__missing__"] = missing
        return data


def _init_parameters(cls) -> list[str]:
    """ Names of the named parameters of ``cls.__init__`` (without ``self``, ``*args``, ``**kwargs``). """

    parameters = inspect.signature(cls.__init__).parameters.values()
    return [p.name for p in parameters
            if p.name != "self" and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]


def encode_json_value(value) -> Any:
    """ Encode a constructor argument so that :func:`decode_json_value` can restore it.

    Enums become ``{"__enum__": "<module>.<class>", "name": ...}``, objects
    with a ``to_json`` method ``{"__object__": "<module>.<class>", "value": ...}``
    (restored with ``from_json`` or the class called with the value as
    keyword arguments), NumPy arrays ``{"type": "ndarray", ...}`` as before.

    Raises
    ------
    TypeError
        If the value cannot be encoded.
    """

    import numpy as np

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, enum.Enum):
        return {"__enum__": f"{type(value).__module__}.{type(value).__qualname__}", "name": value.name}
    if isinstance(value, np.ndarray):
        return {"type": "ndarray", "shape": list(value.shape), "dtype": str(value.dtype), "values": value.tolist()}
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "to_json"):
        return {"__object__": f"{type(value).__module__}.{type(value).__qualname__}", "value": value.to_json()}
    if isinstance(value, (list, tuple)):
        return [encode_json_value(v) for v in value]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return {k: encode_json_value(v) for k, v in value.items()}
    raise TypeError(f"Cannot encode {type(value).__name__} for JSON")


def _import(qualified_name: str):
    module_name, _, name = qualified_name.rpartition(".")
    obj = importlib.import_module(module_name)
    return getattr(obj, name)


def decode_json_value(value) -> Any:
    """ Restore a value written by :func:`encode_json_value`. """

    import numpy as np

    if isinstance(value, list):
        return [decode_json_value(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "__enum__" in value:
        return _import(value["__enum__"])[value["name"]]
    if "__object__" in value:
        cls = _import(value["__object__"])
        if hasattr(cls, "from_json"):
            return cls.from_json(value["value"])
        return cls(**value["value"])
    if value.get("type") == "ndarray":
        return np.asarray(value["values"], dtype=value["dtype"]).reshape(value["shape"])
    return {k: decode_json_value(v) for k, v in value.items()}


def structure_from_json(data: dict[str, Any]) -> "DrawableObject":
    """ Rebuild a structure from :meth:`DrawableObject.to_json`.

    Parameters
    ----------
    data : dict
        JSON form of the structure (with ``__module__``, written since T56).

    Returns
    -------
    DrawableObject

    Raises
    ------
    ValueError
        If the module is not stored, or a required constructor argument is
        missing.
    """

    if "__module__" not in data:
        raise ValueError(f"Cannot rebuild {data.get('__class__')}: the JSON form has no __module__ (written "
                         f"before T56).")
    cls = _import(f"{data['__module__']}.{data['__class__']}")
    arguments = {name: decode_json_value(value) for name, value in data["__init__"].items()}
    required = [p.name for p in inspect.signature(cls.__init__).parameters.values()
                if p.name != "self" and p.default is p.empty and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
    lacking = [name for name in required if name not in arguments]
    if lacking:
        raise ValueError(f"Cannot rebuild {cls.__name__}: the arguments {lacking} were not stored.")
    return cls(**arguments)


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
