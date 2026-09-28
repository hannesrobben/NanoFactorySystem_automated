from typing import Iterator

from nanofactorysystem.aerobasic import GalvoLaserOverrideMode, IFOV_Mode, WaitMode
from nanofactorysystem.aerobasic.programs.drawings import (
    DrawableAeroBasicProgram,
    DrawableObject,
    Rectangle3D_IFOV
)
from nanofactorysystem.aerobasic.programs.drawings.dots.cell_dot_grid import get_cell_dots
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D
from nanofactorysystem.aerobasic.programs.drawings import IFOV_AeroBasicProgram

MIN_DWELL_S = 0.001   # s   DWELL is emitted as "{:.3f}" seconds -> 1 ms hard floor
MIN_DOT_Z_OFFSET = 1e-9   # um  below this the dots share a plane with the pad's top hatch layer


class DotGridOnBase(DrawableObject):
    """Base pad at a fixed power, with a grid of stationary dots on top at the swept power.
    """

    def __init__(
            self,
            *,
            center: Point3D,
            cellsize: float,
            dwell_s: float,
            pitch: float,
            edge_margin: float,
            dot_z_offset: float,
            velocity: float,
            base_power: float,
            base_height: float,
            base_hatch: float,
            base_slice: float,
    ):
        super().__init__()
        if dwell_s < MIN_DWELL_S:
            raise ValueError(
                f"dwell {dwell_s} s is below the {MIN_DWELL_S} s floor. DWELL is emitted as "
                f"'{{:.3f}}' seconds, so this would silently become DWELL 0.000."
            )
        if base_height > 0 and abs(dot_z_offset) < MIN_DOT_Z_OFFSET:
            raise ValueError(
                f"dot_z_offset {dot_z_offset} um puts the dots in the plane of the pad's top "
                f"hatch layer (z = {center.Z + base_height} um), which is written straight over "
                f"them. Use a positive offset to sit the dots proud of the pad, or a negative "
                f"one to embed them deliberately."
            )
        if not get_cell_dots(cellsize, pitch, edge_margin):
            raise ValueError(
                f"No dots fit: cellsize {cellsize} um leaves nothing usable after 2 x "
                f"edge_margin {edge_margin} um."
            )
        self.center = center
        self.cellsize = cellsize
        self.dwell_s = dwell_s
        self.pitch = pitch
        self.edge_margin = edge_margin
        self.dot_z_offset = dot_z_offset
        self.velocity = velocity
        self.base_power = base_power
        self.base_height = base_height
        self.base_hatch = base_hatch
        self.base_slice = base_slice

    @property
    def center_point(self) -> Point2D:
        return Point2D(self.center.X, self.center.Y)

    @property
    def dot_offsets(self) -> list[tuple[float, float]]:
        return get_cell_dots(self.cellsize, self.pitch, self.edge_margin)

    @property
    def dot_z(self) -> float:
        return self.center.Z + self.base_height + self.dot_z_offset

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        if self.base_height > 0:
            base = Rectangle3D_IFOV(
                center=Point3D(self.center.X, self.center.Y, self.center.Z),
                x_length=self.cellsize,
                y_length=self.cellsize,
                height=self.base_height,
                hatch_size=self.base_hatch,
                slice_size=self.base_slice,
                velocity=self.velocity,
                power=self.base_power,
                angle=0.0,
                alternate_hatching=True,
                hatching_direction=HatchingDirection.X,
            )
            yield from base.iterate_layers(coordinate_system)

        yield self._dot_program(coordinate_system)

    def _dot_program(self, coordinate_system: CoordinateSystem) -> IFOV_AeroBasicProgram:
        program = DrawableAeroBasicProgram(coordinate_system)
        z = self.dot_z
        dots = self.dot_offsets
        program.comment(
            f"Dot grid: {len(dots)} dots, pitch {self.pitch} um, "
            f"dwell {self.dwell_s * 1000:.0f} ms, power inherited from structure"
        )

        program.send("SECONDS")
        program.ABSOLUTE()
        program.WAIT_MODE(WaitMode.AUTO)
        program.IFOV(IFOV_Mode.OFF)
        program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)

        for dx, dy in dots:
            program.LINEAR(X=self.center.X + dx, Y=self.center.Y + dy, Z=z, F=self.velocity)
            program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
            program.DWELL(self.dwell_s)
            program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)
        return program
