import math
from abc import ABC
from enum import Enum
from typing import Optional, Literal, Iterator, Tuple

import numpy as np

from nanofactorysystem.aerobasic import GalvoLaserOverrideMode, SingleAxis
from nanofactorysystem.aerobasic.programs.drawings import DrawableAeroBasicProgram, DrawableObject
from nanofactorysystem.aerobasic.programs.drawings.base import IFOV_AeroBasicProgram
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Coordinate, Point3D, Point2D
from nanofactorysystem.devices.power_calibration import PowerCalibration, resolve_power_calibration


class IFOV_Lines(DrawableObject):
    fitKind = "polynomial"  # "polynomial" and "spline" possible

    def __init__(
            self,
            reference_point: Point2D | Point3D,
            lines: list[list[Tuple[float, float]]],  # correct? - not sure for Typing
            *,
            velocity: float,
            power: float = None,
            calibration: Optional[PowerCalibration] = None
    ):
        """
        Reference point: Point2D or Point3D.
        lines: Has to be a list of tuples where each tuple is (start, end). Start and end point have to be of type
                Point2D or Point3D. If not then an error will occur.
        velocity: float in unit mm/s. If value is between 500 and 25000 it will be divided with 1000, because it will be
                assumed that a wrong unit of µm/s was being chosen.
        power: Possible to set the power at each line/ layer individually.
        calibration: Laser power calibration used to convert power (mW) into the attenuator value. Default: the
                calibration activated with power_calibration(...) (Experiment.build_programs() activates the one of
                the running system), otherwise attenuator.calibrationFile of the configuration.

        Note: Before each Line, the controller goes to the reference point.
        """
        super().__init__()
        self.reference_point = reference_point
        self.lines = lines
        # todo
        #   - velocity muss in mm/s sein
        #   - muss übergeben werden können!
        #   - kontrolle
        #   - maximum speed 100*ifov size - das dann als default
        #   - dynamic control of power - in the next class!
        if 500 <= velocity <= 25000:  # komplett überarbeiten!
            self.velocity = velocity / 1000
        elif 50 <= velocity < 500:
            self.velocity = 5
            raise Warning(f"Velocity v={velocity} is too high. Velocity was set to 5mm/s!")
        elif velocity>25000:
            raise ValueError(f"Velocity value {velocity} exceeds 25 mm/s.")
        else:
            self.velocity = velocity

        # todo change power to the corresponding value based on the calibration file - how to do it?
        self.power = power
        self.calibration = calibration

    @property
    def center_point(self) -> Point3D:
        return self.reference_point if isinstance(self.reference_point, Point3D) else Point3D(X=self.reference_point.X,
                                                                                              Y=self.reference_point.Y,
                                                                                              Z=0)

    def _get_power_val(self, power_mW):
        return resolve_power_calibration(self.calibration, self.fitKind).ptoa(power_mW)

    def iterate_layers(self, coordinate_system: CoordinateSystem,
                       objective="Zeiss 63x") -> Iterator[IFOV_AeroBasicProgram]:
        program = IFOV_AeroBasicProgram(coordinate_system)
        program.initialise_IFOV_configuration(objective=objective)
        # set power
        if self.power is not None:
            power_val = self._get_power_val(self.power)
            program.comment(f"Power set to {self.power} mW")
            program.SET_POWER(power=float(power_val))
        # set velocity - standard value ifov_size*100 -- has to be near maximum or low - bad results at middle values
        # if self.velocity is None: # dann die normalen sachen hier:
        #     pass
        if objective == "Zeiss 63x":
            program.SET_SPEED(F=5) # todo oben hier
            program.SET_SPEED(F=5, ax="A")
            program.SET_SPEED(F=5, ax="B")
            program.SET_SPEED(F=1, ax="Z")
        elif objective == "Zeiss 20x":
            program.SET_SPEED(F=10)
            program.SET_SPEED(F=10, ax="A")
            program.SET_SPEED(F=10, ax="B")
            program.SET_SPEED(F=1, ax="Z")
        else:
            raise ValueError(f"Objective {objective} is not supported.")

        # Initialize Galvo - not necessary needed?! Already in IFOV Setup done
        program.COMPENSATE_GALVO_ROTATION(axis=SingleAxis.A)
        # program.COMPENSATE_GALVO_ROTATION(axis=SingleAxis.B)  # only one Compensation axis should be addressed

        # IFOV only works with absolute system
        program.ABSOLUTE()

        # go to reference and reset
        if isinstance(self.reference_point, Point3D):
            program.RAPID(X=self.reference_point.X, Y=self.reference_point.Y, Z=self.reference_point.Z)
        elif isinstance(self.reference_point, Point2D):
            program.RAPID(X=self.reference_point.X, Y=self.reference_point.Y)
        else:
            raise ValueError("Reference Point is not a 2D or 3D Point.")

        program.RESET_GALVO()
        # start IFOV Program
        program.START_IFOV()

        for start, end in self.lines:
            assert isinstance(start, Point2D) or isinstance(start, Point3D), "Start Point is not a 2D/3D Point."
            assert isinstance(end, Point2D) or isinstance(end, Point3D), "End Point is not a 2D/3D Point."

            program.RAPID(A=start.X, B=start.Y)
            program.LINEAR(A=end.X, B=end.Y)

        program.end_ifov_program()

        yield program


class _Lines(DrawableObject, ABC):
    line_axis: SingleAxis

    def __init__(
            self,
            lines: list[tuple[float, float]],
            secondary_position: dict[str, float],
            *,
            velocity: float,
            acceleration: float,
            acceleration_distance_factor: float = 2
    ):
        super().__init__()
        self._validate_lines(lines)
        self.lines = lines
        self.secondary_position = secondary_position
        self.velocity = velocity
        self.acceleration = acceleration
        self.acceleration_distance_factor = acceleration_distance_factor

    @staticmethod
    def _direction(line_segment) -> Literal[1, -1]:
        return np.sign(line_segment[1] - line_segment[0])

    @staticmethod
    def _validate_lines(lines):
        """ Check whether lines are monoton ascending """
        direction = _Lines._direction(lines[0])
        for i, line in enumerate(lines[1:], start=1):
            if not _Lines._direction(line) == direction:
                raise ValueError(
                    f"Direction mismatch. "
                    f"Line {i} does not match with direction of line 0 ({lines[0]} vs {lines[i]}"
                )

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)

        # Go to start for acceleration
        acceleration_distance = self.acceleration_distance_factor * (self.velocity ** 2) / (2 * self.acceleration)
        start_value = self.lines[0][0] - self._direction(self.lines[0]) * acceleration_distance
        start_position = {self.line_axis.parameter_name: start_value, "F": self.velocity}
        start_position.update(self.secondary_position)
        program.LINEAR(**start_position)

        # Draw lines
        for line_start, line_end in self.lines:
            program.LINEAR(**{self.line_axis.parameter_name: line_start, "F": self.velocity})
            program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
            program.LINEAR(**{self.line_axis.parameter_name: line_end, "F": self.velocity})
            program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)

        # Go to end to decelerate
        end_value = self.lines[-1][1] + self._direction(self.lines[0]) * acceleration_distance
        end_position = {self.line_axis.parameter_name: end_value, "F": self.velocity}
        end_position.update(self.secondary_position)
        program.LINEAR(**end_position)

        yield program


class XLines(_Lines):
    """
    As an input only a list of Tuple(x_start, x_end) necessary!
    Y and Z values are extra Parameters to be given. They do not change, because it is a Line on one Plane.
    ToDo (HR): Create Functionalities for Vector printing.
    """
    line_axis = SingleAxis.X

    def __init__(
            self,
            y: float,
            z: float,
            lines: list[tuple[float, float]],
            *,
            velocity: float,
            acceleration: float
    ):
        super().__init__(lines, {"Y": y, "Z": z}, velocity=velocity, acceleration=acceleration)
        self.y = y
        self.z = z

    def center_point(self) -> Point3D:
        return Point3D((self.lines[0][0] + self.lines[-1][1]) / 2, self.y, self.z)


class YLines(_Lines):
    line_axis = SingleAxis.Y

    def __init__(
            self,
            x: float,
            z: float,
            lines: list[tuple[float, float]],
            *,
            velocity: float,
            acceleration: float
    ):
        super().__init__(lines, {"X": x, "Z": z}, velocity=velocity, acceleration=acceleration)
        self.x = x
        self.z = z

    def center_point(self) -> Point3D:
        return Point3D(self.x, (self.lines[0][0] + self.lines[-1][1]) / 2, self.z)


class ZLines(_Lines):
    line_axis = SingleAxis.Z

    def __init__(
            self,
            x: float,
            y: float,
            lines: list[tuple[float, float]],
            *,
            velocity: float,
            acceleration: float
    ):
        super().__init__(lines, {"X": x, "Y": y}, velocity=velocity, acceleration=acceleration)
        self.x = x
        self.y = y

    def center_point(self) -> Point3D:
        return Point3D(self.x, self.y, (self.lines[0][0] + self.lines[-1][1]) / 2)


class PolyLine(DrawableObject):
    """
    Function to Draw a shape with different Points in one Plane.
               x---------x
              /           \
             /             \
            /               \
           x                 x
            \               /
             \             /
              \           /
               x---------x

    X are Points and / \ - are the lines with LASER ON
    """

    def __init__(
            self,
            line: list[Coordinate],
            *,
            F: Optional[float] = None,
            E: Optional[float] = None,
    ):
        super().__init__()
        self.line = line
        self.F = F
        self.E = E

    @property
    def center_point(self) -> Point2D:
        values = {k: [] for k in self.line[0]}
        for coordinate in self.line:
            for k, v in coordinate.items():
                values[k].append(v)
        min_coord = {k: np.min(v) for k, v in values}
        max_coord = {k: np.max(v) for k, v in values}

        center = {k: (min_coord[k] + max_coord[k]) / 2 for k in min_coord}
        try:
            return Point3D(**center)
        except:
            return Point2D(**center)

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)

        program.LINEAR(**self.line[0], F=self.F, E=self.E)
        program.GALVO_LASER_OVERRIDE(mode=GalvoLaserOverrideMode.ON)
        for point in self.line[1:]:
            program.LINEAR(**point, F=self.F, E=self.E)
        program.GALVO_LASER_OVERRIDE(mode=GalvoLaserOverrideMode.OFF)
        yield program


class PolyLines(DrawableObject):

    def __init__(
            self,
            lines: list[list[Coordinate]],
            *,
            F: Optional[float] = None,
            E: Optional[float] = None,
    ):
        super().__init__()
        self.lines = lines
        self.F = F
        self.E = E

    @property
    def center_point(self) -> Point2D:
        values = {k: [] for k in self.lines[0][0]}
        for line in self.lines:
            for coordinate in line:
                for k, v in coordinate.items():
                    values[k].append(v)
        min_coord = {k: np.min(v) for k, v in values}
        max_coord = {k: np.max(v) for k, v in values}

        center = {k: (min_coord[k] + max_coord[k]) / 2 for k in min_coord}
        try:
            return Point3D(**center)
        except:
            return Point2D(**center)

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        for i, line in enumerate(self.lines):
            # Start
            program.comment(f"\n[Polyline] - Draw line {i}:")
            poly_line = PolyLine(line, F=self.F, E=self.E)
            program.add_programm(poly_line.draw_on(coordinate_system))

        yield program


class Corner(DrawableObject):
    def __init__(
            self,
            corner_center: Point2D | Point3D,
            length: float,
            width: float,
            height: float,
            hatch_size: float = 0.5,
            slice_size: float = 0.75,
            rotation_degree: float = 0,
            *,
            F: Optional[float] = None,
            E: Optional[float] = None,
            mark: bool = False
    ):
        """
                     Length
        \\-----------------   |
        |\\----------------   |
        ||X----------------  Width
        |||\\--------------   |
        ||||\\-------------   |
        |||||
        |||||
        |||||

        :param corner_center: Marked with X
        :param length: Length of corner
        :param width: Width of corner
        :param hatch_size: Distance between lines
        :param rotation_degree: Rotation of corner in degree
        :param F: Velocity used for Linear commands
        :param E: Velocity used for Linear commands
        """
        super().__init__()
        self.corner_center = corner_center
        self.width = width
        self.hatch_size = hatch_size
        self.length = length
        self.rotation_degree = rotation_degree
        self.rotation_rad = rotation_degree / 180 * math.pi
        self.height = height
        self.slice_size = slice_size
        self.F = F
        self.E = E
        self.mark = mark

    @property
    def center_point(self) -> Point2D:
        center_offset = (self.length - self.width) / 2
        return self.corner_center + Point2D(center_offset, center_offset).rotate2D(self.rotation_rad)

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        n_hatch = round(self.width / self.hatch_size) + 1
        hatch_size_corrected = self.width / (n_hatch - 1)

        for z in np.arange(0, self.height, self.slice_size):
            program = DrawableAeroBasicProgram(coordinate_system)
            program.LINEAR(Z=z + self.corner_center.Z)
            poly_lines = self.single_layer(
                self.corner_center + Point3D(0, 0, z),
                self.length,
                self.width,
                n_hatch,
                hatch_size_corrected,
                E=self.E,
                F=self.F,
                mark=self.mark,
                rotation_rad=self.rotation_rad
            )
            program.add_programm(poly_lines.draw_on(coordinate_system))
            yield program

    def single_layer(
            self,
            corner_center: Point2D | Point3D,
            length: float,
            width: float,
            n_hatch: int,
            hatch_size: float,
            *,
            E: Optional[float] = None,
            F: Optional[float] = None,
            rotation_rad: float = 0,
            mark: bool = False,
    ) -> PolyLines:
        lines = []
        lines_mark = []
        order = 1
        for i in range(n_hatch):
            center_diagonal = -(i - n_hatch / 2) * hatch_size
            offset = length - width / 2
            center_diagonal = Point2D(center_diagonal, center_diagonal)
            offset = Point2D(offset, offset)
            p1_raw = Point2D(X=offset.X, Y=center_diagonal.Y)
            p2_raw = Point2D(X=center_diagonal.X, Y=center_diagonal.Y)
            p3_raw = Point2D(X=center_diagonal.X, Y=offset.Y)
            p1 = corner_center + p1_raw.rotate2D(rotation_rad)
            p2 = corner_center + p2_raw.rotate2D(rotation_rad)
            p3 = corner_center + p3_raw.rotate2D(rotation_rad)
            p1, p2, p3 = [p1, p2, p3][::order]
            lines.append([p1.as_dict(), p2.as_dict(), p3.as_dict()])
            if mark:
                p1_mark = corner_center + (p1_raw - Point2D(0, 2 * width)).rotate2D(rotation_rad)
                p2a_mark = corner_center + (p2_raw - Point2D(0, 2 * width)).rotate2D(rotation_rad)
                p2b_mark = corner_center + (p2_raw - Point2D(2 * width, 0)).rotate2D(rotation_rad)
                p3_mark = corner_center + (p3_raw - Point2D(2 * width, 0)).rotate2D(rotation_rad)
                p1_mark, p2a_mark, p2b_mark, p3_mark = [p1_mark, p2a_mark, p2b_mark, p3_mark][::order]
                lines_mark.append([p1_mark.as_dict(), p2a_mark.as_dict()])
                lines_mark.append([p2b_mark.as_dict(), p3_mark.as_dict()])
            order *= -1
        lines += lines_mark
        return PolyLines(lines, F=F, E=E)


class VerticalLine(DrawableObject):
    def __init__(self, position: Point2D, z_min: float, z_max: float, *, F: Optional[float] = None):
        super().__init__()
        self.position = position
        self.z_min = z_min
        self.z_max = z_max
        self.F = F

    @property
    def center_point(self) -> Point2D:
        return self.position

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        point = self.position.as_dict()
        point["Z"] = self.z_min
        program.LINEAR(**point, F=self.F)
        program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
        point["Z"] = self.z_max
        program.LINEAR(**point, F=self.F)
        program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)
        yield program


class HatchingDirection(Enum):
    X = "X"
    Y = "Y"
    Z = "Z"

    def flip(self):
        if self == HatchingDirection.X:
            return HatchingDirection.Y
        return HatchingDirection.X


class Rectangle2D(DrawableObject):

    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            *,
            hatch_size: float,
            velocity: float,
            acceleration: float,
            hatching_direction: HatchingDirection
    ):
        super().__init__()
        self.center = center
        self.width = width
        self.length = length

        self.hatch_size = hatch_size
        self.velocity = velocity
        self.acceleration = acceleration
        self.hatching_direction = hatching_direction

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        bottom_left = self.center - Point2D(self.width / 2, self.length / 2)

        if self.hatching_direction == HatchingDirection.X:
            line_program = XLines
            hatching_start_position = bottom_left.X
            line_start = bottom_left.Y
            line_length = self.length
            hatching_length = self.width
        elif self.hatching_direction == HatchingDirection.Y:
            line_program = YLines
            hatching_start_position = bottom_left.Y
            line_start = bottom_left.X
            line_length = self.width
            hatching_length = self.length
        else:
            raise ValueError(f"HatchingDirection not found: {self.hatching_direction}")

        n_hatch = round(hatching_length / self.hatch_size) + 1
        hatch_size_opt = hatching_length / (n_hatch - 1)

        order = 1
        for i in range(n_hatch):
            line_position = hatching_start_position + i * hatch_size_opt
            lines = [
                [line_start, line_start + line_length][::order]
            ]
            line = line_program(
                line_position,
                z=self.center.Z,
                lines=lines,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            program.add_programm(line.draw_on(coordinate_system))
            order *= -1

        yield program


class Rectangle3D(DrawableObject):
    def __init__(
            self,
            center: Point2D | Point3D,
            width: float,
            length: float,
            height: float,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float,
    ):
        super().__init__()
        self.center = center
        self.width = width
        self.length = length
        self.height = height

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        # todo: i dont know exactly why i added Z==0 here. maybe rethink in future - 02.12 HOTFIX
        # if self.height == 0 and self.center.Z==0:
        if self.height == 0:
            yield program

        n_layer = abs(round(self.height / self.slice_size)) + 1
        slice_size_opt = self.height / (n_layer - 1)

        hatching_direction = HatchingDirection.X
        for i in range(n_layer):
            z_offset = i * slice_size_opt
            rectangle = Rectangle2D(
                center=self.center + Point3D(0, 0, z_offset),
                width=self.width,
                length=self.length,
                hatch_size=self.hatch_size,
                velocity=self.velocity,
                acceleration=self.acceleration,
                hatching_direction=hatching_direction
            )
            program = DrawableAeroBasicProgram(coordinate_system)
            program.LINEAR(Z=z_offset + self.center.Z)
            program.add_programm(rectangle.draw_on(coordinate_system))
            yield program
            hatching_direction = hatching_direction.flip()


class Stair(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            n_steps: int,
            step_height: float,
            step_length: float,
            step_width: float,  # same as structure max_width
            socket_height: float = 0.0,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float
    ):
        super().__init__()
        self.center = center
        self.n_steps = n_steps
        self.step_height = step_height
        self.step_length = step_length
        self.step_width = step_width
        self.socket_height = socket_height

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

    @property
    def structure_length(self) -> float:
        return self.n_steps * self.step_length

    @property
    def structure_width(self) -> float:
        return self.step_width

    @property
    def structure_height(self) -> float:
        return self.n_steps * self.step_height + self.socket_height

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        # Add socket
        if self.socket_height > 0:
            socket = Rectangle3D(
                center=self.center,
                width=self.structure_width,
                length=self.structure_length,
                height=self.socket_height,
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            yield from socket.iterate_layers(coordinate_system)

        # Add steps
        slice_size_opt = self.step_height / round(self.step_height / self.slice_size)
        for step in range(self.n_steps):
            z_step_offset = self.socket_height + step * self.step_height
            x_offset = (step / 2) * self.step_length

            step_rectangle = Rectangle3D(
                center=self.center + Point3D(0, -x_offset, z_step_offset),
                width=self.structure_width,
                length=self.structure_length - step * self.step_length,
                height=self.step_height,
                hatch_size=self.hatch_size,
                slice_size=slice_size_opt,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from step_rectangle.iterate_layers(coordinate_system)

        return program
