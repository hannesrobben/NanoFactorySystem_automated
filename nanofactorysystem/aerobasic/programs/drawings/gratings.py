import numpy as np
from typing import Iterator

from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram, SinusoidalGrating
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection, Rectangle3D, PolyLines, step_slice_size
from nanofactorysystem.aerobasic.programs.drawings.new.tile_creator import TileCalculator
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D, CoordinateSystem


class StepGrating(DrawableObject):
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
        self.width_phase = width_phase  # width of the step (higher end)
        self.period_width = period  # period_width along max_width of grating
        self.height = height  # height of grating
        self.base_height = base_height  # height of base-rectangle

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration

        self.need_stitching = False

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
        if not self.need_stitching:
            self.fov_program(program, coordinate_system)
        else:  # stitching is required
            # need seperation of whole structure
            # self.fov -> needed for maximum possible printing
            self.width_phase
            period_per_fov = np.round(self.fov / self.period_width)
            self.stitching_program()

    def fov_program(self, program, coordinate_system):
        # Add socket
        if self.base_height > 0:
            slice_size_opt = step_slice_size(self.base_height, self.slice_size)
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
        slice_size_opt = step_slice_size(self.height, self.slice_size)
        n_grating = self.full_width_grating / self.period_width
        number_of_periods = int(np.floor(n_grating))
        for step in range(number_of_periods):
            # check for max_width difference
            assert self.width_phase < self.period_width, "max_width of period has to be bigger than the max_width of grating"

            x_offset = -self.full_width_grating / 2 + self.width_phase / 2 + step * self.period_width
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

    def stitching_program(self, program, coordinate_system):
        fov = (150, 150)
        usable_fov = 0.85
        boundaries_structure = (-self.structure_width / 2, self.structure_width / 2,
                                -self.structure_length / 2, self.structure_length / 2)
        tile_array = TileCalculator(fov_size=fov, usable_fov_fraction=usable_fov).get_tile_boundaries(
            boundaries_structure)

        slicing_opt_base = step_slice_size(self.base_height, self.slice_size)
        slicing_opt = step_slice_size(self.height, self.slice_size)

        for tile_boundaries in tile_array:
            # printing base
            socket = Rectangle3D(
                center=self.center,
                width=fov[0] * usable_fov,
                length=fov[1] * usable_fov,
                height=self.base_height,
                hatch_size=self.hatch_size,
                slice_size=slicing_opt_base,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            yield from socket.iterate_layers(coordinate_system)

            for z_height in np.arange(self.base_height + slicing_opt, self.height + self.base_height + slicing_opt,
                                      slicing_opt):
                program.LINEAR(Z=z_height + self.center_point.Z)
                # HatchingStrategy
                points_structure = self.get_structure_points(z_height, tile_boundaries)

                poly_lines = PolyLines(points_structure, F=self.velocity, E=self.acceleration)
                program.add_programm(poly_lines.draw_on(coordinate_system))

    def get_structure_points(self, z_height, tile_boundaries):
        (x_start, x_end, y_start, y_end) = tile_boundaries


# class BinaryGrating(DrawableObject):
#     def __init__(self,
#                  center: Point2D | Point3D,
#                  max_width: float,
#                  max_length: float,
#                  width_phase: float,
#                  period: float,
#                  height: float,
#                  base_height: float = 0,
#                  rotation_angle: float = 0.0,
#                  *,
#                  hatch_size: float,
#                  slice_size: float,
#                  velocity: float,
#                  acceleration: float
#                  ):
#         super().__init__()
#         self.center = center
#         self.full_width_grating = max_width
#         self.length_grating = max_length  # max_length of grating - no
#         self.width_phase = width_phase
#         self.period_width = period  # period_width along max_width of grating
#         self.height = height  # height of grating
#         self.base_height = base_height  # height of base-rectangle
#         self.rotation_angle = rotation_angle
#
#         self.hatch_size = hatch_size
#         self.slice_size = slice_size
#         self.velocity = velocity
#         self.acceleration = acceleration
#
#         grating = BinaryGrating(
#             center=Point3D(0, 0, 0),
#             width=100,
#             length=100,
#             period=2.0,
#             height=1.0,
#             grating_angle_deg=rotation_angle,
#             hatch_size=hatch_size,
#             slice_size=slice_size,
#             velocity=velocity,
#             acceleration=acceleration
#         )



#
# if z_layer <= base_height:
#     # Hatching direction --> Rectangle code for x or y lines
#
# elif z_layer > base_height and z_layer <=(base_height+phase_height):
#     #
#
# else:
#     # end of program
