import numpy as np
from typing import Iterator

from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection, Rectangle3D
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D, CoordinateSystem


class DOEstep(DrawableObject):
    """ Step DOE consisting of rectangle with dimensions of 'feature size'. """

    def __init__(
            self,
            center: Point3D,
            feature_size: float | list[float],
            height_profile: np.array,
            socket_height: float = 0.0,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float
    ):
        super().__init__()
        self.center = center
        self.feature_size = feature_size  # kept as given, so that to_json() can store it
        if isinstance(feature_size, float):
            self.feature_width = feature_size
            self.feature_length = feature_size
        elif isinstance(feature_size, list) and len(feature_size) == 2:
            self.feature_width, self.feature_length = feature_size
        else:
            raise ValueError("Feature size has to be a float number or a list of float numbers with the length of 2!")
        self.y_steps, self.x_steps = height_profile.shape
        self.socket_height = socket_height
        self.height_profile = height_profile

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

    @property
    def structure_length(self) -> float:
        return self.feature_length * self.y_steps

    @property
    def structure_width(self) -> float:
        return self.feature_width * self.x_steps

    @property
    def structure_height(self) -> np.array:
        return self.height_profile + self.socket_height

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
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
        z_step_offset = self.socket_height
        for step_x in range(self.x_steps):
            for step_y in range(self.y_steps):
                x_offset = -self.x_steps / 2 * self.feature_width + step_x * self.feature_width + self.feature_width / 2
                y_offset = -self.y_steps / 2 * self.feature_length + step_y * self.feature_length + self.feature_length / 2
                slice_size_opt = self.height_profile[step_y][step_x] / round(
                    self.height_profile[step_y][step_x] / self.slice_size)

                step_rectangle = Rectangle3D(
                    center=self.center + Point3D(x_offset, y_offset, z_step_offset),
                    width=self.feature_width,
                    length=self.feature_length,
                    height=self.height_profile[step_y][step_x],
                    hatch_size=self.hatch_size,
                    slice_size=slice_size_opt,
                    velocity=self.velocity,
                    acceleration=self.acceleration
                )

                yield from step_rectangle.iterate_layers(coordinate_system)

        return program


class Simple_DOE(DrawableObject):
    def __init__(self,
                 center: Point2D | Point3D,
                 rows: int,
                 columns: int,
                 z_profile,
                 pixel_size,
                 *,
                 hatch_size: float,
                 slice_size: float,
                 velocity: float,
                 acceleration: float
                 ):
        super().__init__()
        self.center = center
        self.z_profile = np.asarray(z_profile)
        self.rows = int(rows)
        self.columns = int(columns)
        try:
            (self.rows, self.columns) == self.z_profile.shape
        except Exception as e:
            print(f"Error {e} while comparing shape of height profile {self.z_profile.shape} and specified rows"
                  f"and columns ({rows, columns})")

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

        self.feature_size = pixel_size

    @property
    def center_point(self) -> Point2D:
        return self.center

    @property
    def structure_length(self) -> float:
        # length = x-direction
        return self.feature_size * self.z_profile.shape[0]

    @property
    def structure_width(self) -> float:
        # width = y-direction
        return self.feature_size * self.z_profile.shape[1]

    @property
    def max_structure_height(self) -> float:
        return np.max(self.z_profile)

    @property
    def min_structure_height(self) -> float:
        return np.min(self.z_profile)

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        """
        Very basic implementation of a DOE structure printed with Rectangles one by one.
        Future version should deliver layer by layer across all pixels.
        """
        program = DrawableAeroBasicProgram(coordinate_system)
        for i in range(self.rows):
            # iterating over rows
            x_offset = self.feature_size * (i - np.ceil(self.rows / 2))

            for j in range(self.columns):
                height = self.z_profile[i][j]
                y_offset = self.feature_size * (j - np.ceil(self.columns / 2))
                slice_size_opt = height / round(height / self.slice_size)

                DOE_pixel = Rectangle3D(
                    center=self.center + Point3D(X=x_offset, Y=y_offset, Z=0),
                    width=self.feature_size,
                    length=self.feature_size,
                    height=height,
                    hatch_size=self.hatch_size,
                    slice_size=slice_size_opt,
                    velocity=self.velocity,
                    acceleration=self.acceleration
                )
                yield from DOE_pixel.iterate_layers(coordinate_system)
        return program


class Binary_grating(DrawableObject):
    def __init__(self,
                 center: Point2D | Point3D,
                 max_width: float,
                 max_length: float,
                 width_phase: float,
                 period: float,
                 height: float,
                 base_height: float = 0,
                 rotation_angle: float = 0.0,
                 *,
                 hatch_size: float,
                 slice_size: float,
                 velocity: float,
                 acceleration: float
                 ):
        super().__init__()
        self.center = center
        self.center = center
        self.full_width_grating = max_width
        self.length_grating = max_length  # max_length of grating - no
        self.width_phase = width_phase
        self.period_width = period  # period_width along max_width of grating
        self.height = height  # height of grating
        self.base_height = base_height  # height of base-rectangle

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

    @property
    def center_point(self) -> Point2D:
        return self.center

    @property
    def structure_length(self) -> float:
        return self.length_grating

    @property
    def structure_width(self) -> float:
        # max_width = y-direction
        return self.full_width_grating

    @property
    def max_structure_height(self) -> float:
        return self.height + self.base_height

    @property
    def min_structure_height(self) -> float:
        return self.base_height

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        """
        """
        program = DrawableAeroBasicProgram(coordinate_system)
        # Add socket
        if self.base_height > 0:
            slice_size_opt = self.base_height / round(self.base_height / self.slice_size)
            socket = Rectangle3D(
                center=self.center,
                width=self.structure_width,
                length=self.structure_length,
                height=self.base_height,
                hatch_size=self.hatch_size,
                slice_size=slice_size_opt,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            yield from socket.iterate_layers(coordinate_system)

        # Add grating
        slice_size_opt = self.height / round(self.height / self.slice_size)
        n_grating = self.full_width_grating/ self.period_width
        number_of_periods = int(np.floor(n_grating))
        for step in range(number_of_periods):
            # check for max_width difference
            assert self.width_phase<self.period_width, "max_width of period has to be bigger than the max_width of grating"

            x_offset = -self.full_width_grating/2 + self.width_phase/2 + step*self.period_width
            step_rectangle = Rectangle3D(
                center=self.center + Point3D(X=x_offset, Y=0, Z=0),
                width=self.width_phase,
                length=self.length_grating,
                height=self.height,
                hatch_size=self.hatch_size,
                slice_size=slice_size_opt,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from step_rectangle.iterate_layers(coordinate_system)

        return program

