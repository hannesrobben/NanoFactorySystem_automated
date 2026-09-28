##########################################################################
# Copyright (c) 2022-2025 Hannes Robben                                  #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################

import math
from collections import Counter
from typing import Iterator

from nanofactorysystem.aerobasic.programs.drawings import (
    DrawableObject, DrawableAeroBasicProgram, Rectangle3D_IFOV,
)
from nanofactorysystem.aerobasic.programs.drawings.lines import IFOV_Lines, HatchingDirection
from nanofactorysystem.aerobasic.programs.drawings.cell_geometry_2 import ANGLES, get_cell_points
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D


def lines_per_orientation(segments) -> Counter:
    """Segment count keyed by line direction in degrees, folded into [0, 180).

    get_cell_points concatenates the four quadrants with no group markers, but each has a
    unique angle (ANGLES), so the direction labels the quadrant.
    """
    counts = Counter()
    for (sx, sy), (ex, ey) in segments:
        counts[round(math.degrees(math.atan2(ey - sy, ex - sx)) % 180.0, 3)] += 1
    return counts


class CellLinesOnBase(DrawableObject):
    """Base pad + one layer of four-quadrant cell lines, offset from the pad's TOP surface.

    Geometry is get_cell_points: one quadrant per scan orientation (0/45/90/135 deg), lines
    spaced by distance_between_lines. The pad is the Rectangle3D_IFOV slab of the voxel
    z-offset experiment.

    line_z_offset is measured from the pad top (center.Z + base_height), not the substrate:
    positive stands proud of the pad, 0 is coplanar with its top hatch layer, negative is
    buried inside it.

    Add with axes="XYZ". Under "ABZ" the galvo coordinate system carries the negated
    structure centre and IFOV_AeroBasicProgram._apply_ifov_conversion ignores axis_mapping,
    so the reference RAPID collapses to "RAPID X0 Y0" and the stage writes at the machine
    origin instead of the grid slot.

    The line layer is yielded last on purpose: DropDirection.DOWN runs the layer files in
    reverse, so it is written first, into virgin resin, and the pad is built around it
    afterwards. Every line_z_offset therefore writes its lines under identical conditions;
    only the burial differs.

    velocity is inert here -- IFOV_Lines sets the feed rate from the objective and never
    reads its velocity argument. Pad and lines each emit their own SET_POWER, so base_power
    and line_power stay independent of the layer reversal.
    """

    def __init__(
            self,
            center: Point3D | Point2D,
            cellsize: float,
            *,
            distance_between_lines: float,
            line_z_offset: float,
            edge_margin: float = 3.0,
            velocity: float,
            line_power: float,
            base_power: float,
            base_height: float = 4.0,
            base_hatch: float = 0.3,
            base_slice: float = 0.25,
            objective: str = "Zeiss 63x",
            min_lines_per_quadrant: int = 2,
    ):
        super().__init__()

        if distance_between_lines <= 0:
            raise ValueError(f"distance_between_lines {distance_between_lines} um must be positive.")
        if base_height <= 0:
            raise ValueError(
                f"base_height {base_height} um must be positive. Without a pad there is no pad top "
                f"for line_z_offset to reference -- use CellGeometry for a bare cell."
            )
        if base_height + line_z_offset < 0:
            raise ValueError(
                f"line_z_offset {line_z_offset} um puts the line plane "
                f"{-(base_height + line_z_offset):.2f} um below the pad bottom (pad is "
                f"{base_height} um thick). The lines have to lie inside or above the pad."
            )

        # _quadrant() degenerates to a single centre line rather than an empty list once the
        # pitch exceeds the quadrant diagonal, and a lone line has no neighbour to merge with.
        counts = lines_per_orientation(get_cell_points(cellsize, distance_between_lines, edge_margin))
        if len(counts) < len(ANGLES) or min(counts.values(), default=0) < min_lines_per_quadrant:
            raise ValueError(
                f"cellsize {cellsize} um ({cellsize / 2.0} um quadrants) with "
                f"distance_between_lines {distance_between_lines} um and edge_margin "
                f"{edge_margin} um gives {dict(sorted(counts.items()))} lines per orientation, "
                f"below the required {min_lines_per_quadrant} in all {len(ANGLES)} quadrants."
            )

        self.center = center
        self.cellsize = cellsize
        self.distance_between_lines = distance_between_lines
        self.line_z_offset = line_z_offset
        self.edge_margin = edge_margin
        self.velocity = velocity
        self.line_power = line_power
        self.base_power = base_power
        self.base_height = base_height
        self.base_hatch = base_hatch
        self.base_slice = base_slice
        self.objective = objective
        self.min_lines_per_quadrant = min_lines_per_quadrant

    @property
    def center_point(self) -> Point2D:
        return self.center if isinstance(self.center, Point2D) else Point2D(self.center.X, self.center.Y)

    @property
    def base_z(self) -> float:
        return self.center.Z if isinstance(self.center, Point3D) else 0.0

    @property
    def pad_top(self) -> float:
        """Top surface of the pad -- the reference for line_z_offset."""
        return self.base_z + self.base_height

    @property
    def line_z(self) -> float:
        return self.pad_top + self.line_z_offset

    @property
    def segments(self) -> list:
        return get_cell_points(self.cellsize, self.distance_between_lines, self.edge_margin)

    @property
    def lines_per_quadrant(self) -> dict[float, int]:
        return dict(sorted(lines_per_orientation(self.segments).items()))

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        cx, cy = self.center.X, self.center.Y

        base = Rectangle3D_IFOV(
            center=Point3D(cx, cy, self.base_z),
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

        lines = [[Point2D(sx, sy), Point2D(ex, ey)] for (sx, sy), (ex, ey) in self.segments]
        cell_lines = IFOV_Lines(
            reference_point=Point3D(cx, cy, self.line_z),
            lines=lines,
            velocity=self.velocity,
            power=self.line_power,
        )
        yield from cell_lines.iterate_layers(coordinate_system, objective=self.objective)
