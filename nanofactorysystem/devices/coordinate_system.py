import abc
import dataclasses
import math
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from typing import TypedDict, Callable, Iterable

import numpy as np

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface


class Coordinate(TypedDict, total=False):
    X: float
    Y: float
    Z: float
    A: float
    B: float


@dataclass
class Point2D:
    X: float
    Y: float

    def __add__(self, other):
        if isinstance(other, Point2D):
            return Point2D(X=self.X + other.X, Y=self.Y + other.Y)
        return Point2D(X=self.X + other, Y=self.Y + other)

    def __sub__(self, other):
        return self.__add__(-other)

    def __neg__(self):
        return self.__class__(**{k: -v for k, v in self.as_dict().items()})

    def __mul__(self, other) -> "Point2D":
        return self.__class__(**{k: v * other for k, v in self.as_dict().items()})

    def to_2d(self) -> "Point2D":
        return Point2D(X=self.X, Y=self.Y)

    def to_json(self) -> dict[str, float]:
        return self.as_dict()

    def as_dict(self) -> Coordinate:
        return dataclasses.asdict(self)  # dataclasses have been imported as dataclass --> mistake??

    def as_tuple(self):
        return dataclasses.astuple(self)

    def rotate2D(self, rotation_rad: float) -> "Point2D":
        x_new = self.X * math.cos(rotation_rad) - self.Y * math.sin(rotation_rad)
        y_new = self.X * math.sin(rotation_rad) + self.Y * math.cos(rotation_rad)
        return Point2D(x_new, y_new)


@dataclass
class Point3D(Point2D):
    Z: float

    def __add__(self, other):
        if isinstance(other, Point3D):
            return Point3D(X=self.X + other.X, Y=self.Y + other.Y, Z=self.Z + other.Z)
        if isinstance(other, Point2D):
            return Point3D(X=self.X + other.X, Y=self.Y + other.Y, Z=self.Z)
        return Point3D(X=self.X + other, Y=self.Y + other, Z=self.Z + other)


    def rotate2D(self, rotation_rad: float) -> "Point3D":
        return Point3D(0, 0, self.Z) + super().rotate2D(rotation_rad)  # Small hack to only implement once


class DropDirection(Enum):
    """ Orientation of the resin drop on the substrate.

    The drop direction never changes the z coordinates of a structure: a
    structure point at local height z is written at ``plane(x, y) + z`` for
    both directions (``CoordinateSystem.convert``). It changes the order of
    printing and which interface is the substrate surface. Places that depend
    on it:

    - ``Experiment.print_structure`` (and restart): layers are printed in
      ascending layer order for UP and in descending order for DOWN.
    - ``Experiment.plane_fit``: the plane is fitted through the "high"
      interface points for UP and through the "low" ones for DOWN.
    - ``tools.detector.Scanner`` / ``tools.layer.Layer``: if two focus ranges
      are found, DOWN keeps the lowest one (a range above is e.g. the
      substrate/immersion-oil interface), UP keeps the highest one; the drop
      direction reaches the tools as ``sys_args["layer"]["dropDirection"]``.
    - ``QRCode.pixel_program``: the vertical pixel lines are drawn in negative
      z direction for UP and in positive z direction for DOWN.
    - ``storage.legacy.read_legacy``: the layer order of old progress files.

    Dip-in lithography (objective immersed in the resin) behaves like UP
    without an upper end of the resin; it needs a different computation and
    is planned (future_todo.md F8). There is no ``DIP_IN`` member yet.
    """

    UP = -1
    DOWN = 1

    def to_text(self):
        return f"Droplet is facing down" if self.name == "DOWN" else "Droplet is facing up"

class ZFunction(abc.ABC):
    @abc.abstractmethod
    def __call__(self, x: float, y: float) -> float:
        pass


class StaticOffset(ZFunction):
    def __init__(self, value: float):
        self.value = value

    def __call__(self, x: float, y: float) -> float:
        return self.value

    def __repr__(self) -> str:
        return f"StaticOffset(value={self.value})"


class Plane(ZFunction):
    def __init__(self, parameters: np.ndarray):
        self.parameters = parameters

    def __call__(self, x: float, y: float) -> float:
        return np.dot(self.parameters, [x, y, 1])


class PlaneFit(Plane):
    def __init__(self, parameters: np.ndarray, *, points: np.ndarray):
        super().__init__(parameters)
        self.points = np.asarray(points)

    def __str__(self) -> str:
        s = [
            f"polar angle:    {self.theta_degree:.1f}° ({100 * self.slope:.2f}%)",
            f"azimuth angle:  {self.phi_degree:.1f}°",
            f"mean deviation: {self.average:.3f} µm (max. {self.max_dev:.3f} µm)"
        ]
        return "\n".join(s)

    @property
    def A(self) -> np.ndarray:
        A = np.array(self.points)
        A[:, -1] = 0
        return A

    @property
    def b(self) -> np.ndarray:
        return self.points[:, -1]

    @cached_property
    def dev(self) -> np.ndarray:
        return np.dot(self.A, self.parameters) - self.b

    @cached_property
    def max_dev(self) -> float:
        return np.max(np.abs(self.dev))

    @cached_property
    def average(self) -> float:
        return np.sqrt(np.sum(np.square(self.dev))) / len(self.dev)

    @cached_property
    def p0(self) -> np.ndarray:
        return np.asarray([0, 0, self(0, 0)])

    @cached_property
    def p1(self) -> np.ndarray:
        return np.asarray([1, 0, self(1, 0)]) - self.p0

    @cached_property
    def p2(self) -> np.ndarray:
        return np.asarray([0, 1, self(0, 1)]) - self.p0

    @cached_property
    def slope(self) -> float:
        x, y, z = np.cross(self.p1, self.p2)

        # Length of y projection and length of vector
        rxy = np.hypot(x, y)
        return rxy / z

    @cached_property
    def theta_degree(self) -> float:
        x, y, z = np.cross(self.p1, self.p2)

        # Length of y projection and length of vector
        rxy = np.hypot(x, y)
        return np.arctan2(rxy, z) * 180.0 / np.pi

    @cached_property
    def phi_degree(self) -> float:
        x, y, z = np.cross(self.p1, self.p2)
        phi = math.atan2(y, x) * 180 / np.pi
        return (phi % 360) - 180

    @classmethod
    def from_points(cls, points: np.ndarray | Iterable[Iterable[float]]):
        # Copy A and b, so that we can change them without affecting 'points'
        A = np.array(points, dtype=float)  # constructing an array
        b = np.array(A[:, -1])  # separating z coordinates
        A[:, -1] = 1.0  # set z to 1
        parameters, _, _, _ = np.linalg.lstsq(A, b, rcond=None)  # return x_slope, y_slope and z0
        return PlaneFit(parameters, points=points)

    @classmethod
    def measure(cls, api: AerotechAsciiInterface):
        pass


class Unit(Enum):
    cm = 10
    mm = 1
    um = 1e-3
    nm = 1e-6


class CoordinateSystem:
    def __init__(
            self,
            offset_x=0,
            offset_y=0,
            z_function: Callable[[float, float], float] | float = 0,
            drop_direction: DropDirection = DropDirection.DOWN,
            unit: Unit = Unit.mm
    ):
        self.offset_x = offset_x
        self.offset_y = offset_y
        if isinstance(z_function, (float, int)):
            z_function = StaticOffset(z_function)
        self.z_function = z_function
        self.drop_direction = drop_direction
        self.unit = unit

        self.axis_mapping = {}

    def __str__(self):
        return f"CoordinateSystem(offset_x={self.offset_x}, offset_y={self.offset_y}, z_function={self.z_function})"

    def convert(self, coordinate: Coordinate) -> Coordinate:
        new_coordinate = {}
        # NOTE Potential bug discovered (HR - 10.03.26 - fixed
        # x = self.offset_x  #old
        # y = self.offset_y
        x = coordinate.get("X", 0) + self.offset_x
        y = coordinate.get("Y", 0) + self.offset_y
        if "X" in coordinate:
            new_coordinate[self.axis_mapping.get("X", "X")] = coordinate["X"] + self.offset_x
        if "Y" in coordinate:
            new_coordinate[self.axis_mapping.get("Y", "Y")] = coordinate["Y"] + self.offset_y
        if "Z" in coordinate:
            new_coordinate[self.axis_mapping.get("Z", "Z")] = coordinate["Z"] + self.z_function(x, y)

        # Unit conversion
        new_coordinate = {k: v * self.unit.value for k, v in new_coordinate.items()}

        return new_coordinate

    def to_unit(self, unit: Unit) -> "CoordinateSystem":
        coordinate_system = CoordinateSystem(
            offset_x=self.offset_x,
            offset_y=self.offset_y,
            z_function=self.z_function,
            drop_direction=self.drop_direction,
            unit=unit
        )
        coordinate_system.axis_mapping = self.axis_mapping.copy()
        return coordinate_system

