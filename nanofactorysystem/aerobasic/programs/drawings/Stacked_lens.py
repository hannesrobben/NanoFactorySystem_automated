from typing import Optional, Literal, Iterator

import numpy as np

from nanofactorysystem.aerobasic.programs.drawings import DrawableAeroBasicProgram, DrawableObject
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Point2D
from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D
from nanofactorysystem.aerobasic.programs.drawings.lens import AsphericalLens, SphericalLens


class StackedSphericalLens(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            base_length: float,
            base_width: float,  # same as structure max_width
            lenses_heights: list,
            radius_of_curvature: list | float,
            height_in_between: float = 2.0,
            socket_height: float = 0.0,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float
    ):
        super().__init__()
        self.center = center
        self.number_of_lenses = len(lenses_heights)
        self.lenses_heights = lenses_heights
        self.base_x = base_width
        self.base_y = base_length
        self.socket_height = socket_height
        self.height_in_between = height_in_between

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

        self.radius_of_curvature = []
        if isinstance(radius_of_curvature, list):
            self.radius_of_curvature = radius_of_curvature
            assert len(self.radius_of_curvature) == len(
                self.lenses_heights), "Each lens needs a height and a radius of curvature."
        elif isinstance(radius_of_curvature, float):
            for i in range(self.number_of_lenses):
                self.radius_of_curvature.append(radius_of_curvature)
        else:
            raise ValueError("radius_of_curvature needs to be a list or a float.")

        assert self.number_of_lenses > 1, "Stacked lenses assumes more than one lens. Else refer to Spherical Lens."

    @property
    def structure_height(self) -> float:
        total_lens_height = self.socket_height
        for height in self.lenses_heights:
            total_lens_height += height
        return (self.number_of_lenses - 1) * self.height_in_between + total_lens_height

    @property
    def structure_width(self) -> float:
        return self.base_x

    @property
    def structure_length(self) -> float:
        return self.base_y

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

        for i in range(self.number_of_lenses):
            opt_slicing = self.lenses_heights[i] / round(self.lenses_heights[i] / self.slice_size)
            # slice_opt_lenses.append(opt_slicing)

            lens = SphericalLens(
                center=self.center + Point3D(X=0, Y=0, Z=0),
                max_height=self.lenses_heights[i],
                radius_of_curvature=self.radius_of_curvature[i],
                slice_size=opt_slicing,
                # circle_object_factory = FilledCircleFactory,
                hatch_size=self.hatch_size,
                velocity=self.velocity
            )

            yield from lens.iterate_layers(coordinate_system)

            # add connection to next lens
            current_height = self.structure_height + self.lenses_heights[i]
            rect = Rectangle3D(
                center=self.center + Point3D(X=0, Y=0, Z=current_height),
                width=self.structure_width,
                length=self.structure_length,
                height=self.structure_height,
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

        return program


class StackedAsphericalLens(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            base_length: float,
            base_width: float,  # same as structure max_width
            lenses_heights: list,
            radius_of_curvature: list | float,
            conic_constants: list | float,
            height_in_between: float = 2.0,
            socket_height: float = 0.0,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float
    ):
        super().__init__()
        self.center = center
        self.number_of_lenses = len(lenses_heights)
        self.lenses_heights = lenses_heights
        self.base_x = base_width
        self.base_y = base_length
        self.socket_height = socket_height
        self.height_in_between = height_in_between

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

        self.radius_of_curvature = []
        self.conic_constants = []

        if isinstance(radius_of_curvature, list):
            self.radius_of_curvature = radius_of_curvature
            assert len(self.radius_of_curvature) == len(
                self.lenses_heights), "Each lens needs a height and a radius of curvature."
        elif isinstance(radius_of_curvature, float):
            for i in range(self.number_of_lenses):
                self.radius_of_curvature.append(radius_of_curvature)
        else:
            raise ValueError("radius_of_curvature needs to be a list or a float.")

        if isinstance(conic_constants, list):
            self.conic_constants = conic_constants
            assert len(self.conic_constants) == len(
                self.lenses_heights), "Each lens needs a height and a radius of curvature."
        elif isinstance(conic_constants, float):
            for i in range(self.number_of_lenses):
                self.conic_constants.append(conic_constants)
        else:
            raise ValueError("radius_of_curvature needs to be a list or a float.")

        assert self.number_of_lenses > 1, "Stacked lenses assumes more than one lens. Else refer to Spherical Lens."

    @property
    def structure_height(self) -> float:
        total_lens_height = self.socket_height
        for height in self.lenses_heights:
            total_lens_height += height
        return (self.number_of_lenses - 1) * self.height_in_between + total_lens_height

    @property
    def structure_width(self) -> float:
        return self.base_x

    @property
    def structure_length(self) -> float:
        return self.base_y

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

        current_height = self.socket_height
        for i in range(self.number_of_lenses):
            opt_slicing = self.lenses_heights[i] / round(self.lenses_heights[i] / self.slice_size)
            # slice_opt_lenses.append(opt_slicing)

            aspherical_lens = AsphericalLens(
                center=self.center + Point3D(X=0, Y=0, Z=current_height),
                height=self.lenses_heights[i],  # z
                length=self.base_x,  # x
                width=self.base_y,  # y
                sphere_radius=self.radius_of_curvature[i],  # R
                conic_constant=self.conic_constants[i],  # k
                hatch_size=self.hatch_size,
                slice_size=opt_slicing,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            current_height += self.lenses_heights[i]

            yield from aspherical_lens.iterate_layers(coordinate_system)

            # add connection to next lens
            shift_x_1 = self.base_x/2 + 5
            overlap = 2
            rect_positive = Rectangle3D(
                center=self.center + Point3D(X=shift_x_1, Y=0, Z=current_height-overlap),
                width=10,  # assumed x
                length=self.base_y,  # assumed y
                height=self.height_in_between+overlap*2,  # *2 overlap for overlap at the top as well
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from rect_positive.iterate_layers(coordinate_system)

            rect_negative = Rectangle3D(
                center=self.center + Point3D(X=-shift_x_1, Y=0, Z=current_height-overlap),
                width=10,  # assumed x
                length=self.base_y,  # assumed y
                height=self.height_in_between+overlap*2,  #
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from rect_negative.iterate_layers(coordinate_system)

            current_height += self.height_in_between

        return program



class StackedRectangle(DrawableObject):
    def __init__(
            self,
            center: Point3D,
            height: float,
            length: float,
            width: float,  # same as structure max_width
            number_of_rectangle: int,  # amount of rectangles
            height_in_between: float = 2.0,
            socket_height: float = 0.0,
            *,
            hatch_size: float,
            slice_size: float,
            velocity: float,
            acceleration: float
    ):
        super().__init__()
        self.center = center
        self.height = height
        self.width = width
        self.length = length
        self.socket_height = socket_height
        self.height_in_between = height_in_between
        self.n_rect = number_of_rectangle

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

        self.radius_of_curvature = []
        self.conic_constants = []

    @property
    def structure_height(self) -> float:
        total_height = self.socket_height
        total_height += (self.height + self.height_in_between) * self.n_rect
        return total_height

    @property
    def structure_width(self) -> float:
        return self.width

    @property
    def structure_length(self) -> float:
        return self.length

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

        current_height = self.socket_height
        for i in range(self.n_rect):
            opt_slicing = self.height / round(self.height / self.slice_size)
            # slice_opt_lenses.append(opt_slicing)

            rect = Rectangle3D(
                center=self.center,
                width=self.structure_width,
                length=self.structure_length,
                height=self.socket_height,
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            current_height += self.height

            yield from rect.iterate_layers(coordinate_system)

            # add connection to next lens
            width_bridges = 15
            shift_x_1 = self.width/2 + 5
            overlap = 1
            rect_positive = Rectangle3D(
                center=self.center + Point3D(X=shift_x_1, Y=0, Z=current_height-overlap),
                width=width_bridges,  # assumed x
                length=self.length,  # assumed y
                height=self.height_in_between+overlap*2,  # *2 overlap for overlap at the top as well
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from rect_positive.iterate_layers(coordinate_system)

            rect_negative = Rectangle3D(
                center=self.center + Point3D(X=-shift_x_1, Y=0, Z=current_height-overlap),
                width=width_bridges,  # assumed x
                length=self.length,  # assumed y
                height=self.height_in_between+overlap*2,  #
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from rect_negative.iterate_layers(coordinate_system)

            current_height += self.height_in_between

        return program



class test_stack(DrawableAeroBasicProgram):

    def __init__(self,
                 center: Point3D,
                 ):
        super().__init__()
        self.center = center

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

        current_height = self.socket_height
        for i in range(self.number_of_lenses):
            opt_slicing = self.lenses_heights[i] / round(self.lenses_heights[i] / self.slice_size)
            # slice_opt_lenses.append(opt_slicing)

            aspherical_lens = AsphericalLens(
                center=self.center + Point3D(X=0, Y=0, Z=current_height),
                height=self.lenses_heights[i],  # z
                length=self.base_x,  # x
                width=self.base_y,  # y
                sphere_radius=self.radius_of_curvature[i],  # R
                conic_constant=self.conic_constants[i],  # k
                hatch_size=self.hatch_size,
                slice_size=opt_slicing,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            current_height += self.lenses_heights[i]

            yield from aspherical_lens.iterate_layers(coordinate_system)

            # add connection to next lens
            shift_x_1 = self.base_x/2 + 5
            overlap = 2
            rect_positive = Rectangle3D(
                center=self.center + Point3D(X=shift_x_1, Y=0, Z=current_height-overlap),
                width=10,  # assumed x
                length=self.base_y,  # assumed y
                height=self.height_in_between+overlap*2,  # *2 overlap for overlap at the top as well
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from rect_positive.iterate_layers(coordinate_system)

            rect_negative = Rectangle3D(
                center=self.center + Point3D(X=-shift_x_1, Y=0, Z=current_height-overlap),
                width=10,  # assumed x
                length=self.base_y,  # assumed y
                height=self.height_in_between+overlap*2,  #
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )

            yield from rect_negative.iterate_layers(coordinate_system)

            current_height += self.height_in_between

        return program
