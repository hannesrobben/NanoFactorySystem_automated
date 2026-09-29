import math
from typing import Type, Iterator

import numpy as np
import matplotlib.pyplot as plt

from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.circle import DrawableCircle, FilledCircle2D, FilledCircleFactory
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection, XLines, YLines
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Point2D


class SphericalLens(DrawableObject):

    def __init__(
            self,
            center: Point2D | Point3D,
            max_height,  # maximum thickness of lens
            radius_of_curvature: float,  # Radius of Curvature
            slice_size: float,
            *,
            circle_object_factory: FilledCircleFactory,
            hatch_size: float,
            velocity: float
    ):
        super().__init__()
        self.circle_object_factory = circle_object_factory
        self.hatch_size = hatch_size
        self.velocity = velocity

        self.center = center
        self.radius_of_curvature = radius_of_curvature
        self.slice_size = slice_size
        self.offset = self.radius_of_curvature - max_height
        self.max_height = max_height
        self.N = int(np.ceil(max_height / slice_size))

        # optimised hatching and slicing parameter
        # self.hatch_size_opt =
        self.slicing_height = self.max_height / self.N

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)

        if self.offset >= self.radius_of_curvature:
            raise Exception(
                f"Lens is not printable. Height of Offset ({self.offset}) exceeds the radius of curvature ({self.radius_of_curvature}).")

        for i in range(self.N + 1):
            z_i = i * self.slicing_height
            if (z_i + self.offset) <= self.radius_of_curvature:  # Ensure z_i does not exceed R
                r_i = np.sqrt(self.radius_of_curvature ** 2 - (z_i + self.offset) ** 2)
            else:
                r_i = 0  # If height exceeds R, radius is zero

            point = self.center + Point3D(X=0, Y=0, Z=z_i)
            layer = self.circle_object_factory(point, r_i, hatch_size=self.hatch_size)

            yield layer.draw_on(coordinate_system)

        return program


class AsphericalLens(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            height: float,  # z
            length: float,  # x
            width: float,  # y
            sphere_radius: float,  # R
            conic_constant: float,  # k
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float,
    ):
        super().__init__()
        self.center = center
        self.height = float(height)
        self.length = float(length)
        self.width = float(width)
        self.sphere_radius = float(sphere_radius)
        self.conic_constant = float(conic_constant)

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

        self.n_layer = round(self.height / self.slice_size + 0.95)  # woher kommt die 0.95?
        self.slice_size_opt = self.height / (self.n_layer - 0.95)

    @property
    def structure_length(self) -> float:
        return self.length

    @property
    def structure_width(self) -> float:
        return self.width

    @property
    def structure_height(self) -> float:
        return self.height

    @property
    def center_point(self) -> Point2D:
        return self.center

    def layer_to_z(self, layer_id: int) -> float:

        assert layer_id >= 0 and layer_id < self.n_layer
        return self.slice_size_opt * layer_id

    def layer_program(self, coordinate_system: CoordinateSystem, layer_id: int) -> DrawableAeroBasicProgram:

        program = DrawableAeroBasicProgram(coordinate_system)
        z = self.layer_to_z(layer_id)
        lens_sag = self.height - z
        circle_radius = lens_sag * math.sqrt(2 * self.sphere_radius / lens_sag - 1 - self.conic_constant)
        hatching_direction = [HatchingDirection.X, HatchingDirection.Y][layer_id % 2]

        if hatching_direction == HatchingDirection.X:
            line_program = XLines
            max_lateral_size = self.width
            max_line_length = self.length
        elif hatching_direction == HatchingDirection.Y:
            line_program = YLines
            max_lateral_size = self.length
            max_line_length = self.width
        else:
            raise ValueError(f"HatchingDirection not found: {hatching_direction}")

        size = min(2 * circle_radius, max_lateral_size)
        n_hatch = round(size / self.hatch_size) + 1
        hatch_size_opt = size / (n_hatch - 1)
        order = 1
        for i in range(n_hatch):
            line_position = hatch_size_opt * (i - n_hatch / 2 + 0.5)

            # Skip very short lines and avoid error when line_position becomes slightly larger than circle_radius
            if abs(circle_radius - abs(line_position)) < 0.2 * hatch_size_opt:
                continue

            line_start = min(math.sqrt(circle_radius ** 2 - line_position ** 2), max_line_length / 2)
            lines = [[-line_start, line_start][::order]]
            line = line_program(line_position,
                                z=z,
                                lines=lines,
                                velocity=self.velocity,
                                acceleration=self.acceleration)
            program.add_programm(line.draw_on(coordinate_system))
            order *= -1

        return program

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)

        for layer_id in range(self.n_layer):
            yield self.layer_program(coordinate_system, layer_id)

        return program

    def plot_surface(self, resolution: int = 300):
        """
        Plot the aspherical lens surface.
        """

        # Coordinate grid
        x = np.linspace(-self.length / 2, self.length / 2, resolution)
        y = np.linspace(-self.width / 2, self.width / 2, resolution)

        X, Y = np.meshgrid(x, y)

        # Radial coordinate
        r2 = X ** 2 + Y ** 2

        R = self.sphere_radius
        k = self.conic_constant

        # Aspheric sag equation
        denominator = 1 + np.sqrt(1 - (1 + k) * r2 / R ** 2)

        Z = r2 / (R * denominator)

        # Normalize to desired height
        Zmax = np.nanmax(Z)
        if Zmax > 0:
            Z = Z / Zmax * self.height

        # Clip outside aperture
        aperture_mask = (
                (np.abs(X) <= self.length / 2)
                & (np.abs(Y) <= self.width / 2)
        )

        Z[~aperture_mask] = np.nan

        # Plot
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection='3d')

        surf = ax.plot_surface(
            X,
            Y,
            Z,
            linewidth=0,
            antialiased=True,
        )

        ax.set_xlabel("X [µm]")
        ax.set_ylabel("Y [µm]")
        ax.set_zlabel("Z [µm]")

        ax.set_title(
            f"Aspherical Lens\n"
            f"R={R:.2f} µm, k={k:.2f}, h={self.height:.2f} µm"
        )

        ax.set_box_aspect((1, 1, 0.3))

        plt.tight_layout()
        plt.show()


class Cylinder(DrawableObject):
    def __init__(
            self,
            center: Point2D | Point3D,
            radius: float,
            total_height: float,
            slice_size: float,
            *,
            circle_object_factory: FilledCircleFactory,
            hatch_size: float,
            velocity: float
    ):
        super().__init__()
        self.circle_object_factory = circle_object_factory
        self.hatch_size = hatch_size
        self.velocity = velocity

        self.center = center
        self.radius = radius
        self.slice_size = slice_size
        self.height = total_height
        # Number of layers to be printed
        self.N = int(np.ceil(self.height / self.slice_size))

    @property
    def center_point(self) -> Point2D:
        return self.center

    def iterate_layers(self, coordinate_system: CoordinateSystem):
        program = DrawableAeroBasicProgram(coordinate_system)

        for i in range(self.N + 1):
            z_i = i * self.slice_size
            point = self.center + Point3D(X=0, Y=0, Z=z_i)
            layer = self.circle_object_factory(point, self.radius, hatch_size=self.hatch_size)

            yield layer.draw_on(coordinate_system)

        return program


if __name__ == "__main__":
    pass
