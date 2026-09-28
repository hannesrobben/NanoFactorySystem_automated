from typing import Iterator, Sequence

from nanofactorysystem.aerobasic import GalvoLaserOverrideMode, IFOV_Mode, WaitMode
from nanofactorysystem.aerobasic.programs.drawings import (
    DrawableAeroBasicProgram,
    DrawableObject,
    IFOV_AeroBasicProgram,
    Rectangle3D_IFOV
)
from nanofactorysystem.aerobasic.programs.drawings.dots.cell_dot_grid_1 import get_cell_dot_rows, get_cell_dots
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Point3D

MIN_DWELL_S = 0.001   # s   DWELL is emitted as "{:.3f}" seconds -> 1 ms hard floor
MIN_DOT_Z_OFFSET = 1e-9   # um  below this the dots share a plane with the pad's top hatch layer
MAX_VELOCITY_UM_S = 15_000   # um/s  SET_SPEED rejects F >= 15 mm/s


class DotGridOnBase(DrawableObject):
    """Base pad at a fixed power, with a grid of stationary dots on top at the swept power.

    dot_z_offset takes either a single float, which puts every dot in one plane, or one value per
    dot row, which sweeps z inside the pad. Row 0 is the most negative Y, i.e. the bottom row in a
    view where +Y runs up, and the row order is the print order.

    Add this with axes="XYZ". Both halves emit IFOV_AeroBasicProgram, and
    IFOV_AeroBasicProgram._apply_ifov_conversion ignores CoordinateSystem.axis_mapping, so X/Y
    are always absolute stage axes there. Under axes="ABZ" Experiment.structure_program hands
    over the galvo coordinate system, whose offsets are the negated structure centre, and the
    pad's reference RAPID collapses to "RAPID X0 Y0" -- the stage leaves the grid slot and
    writes the pad at the machine origin.
    """

    def __init__(
            self,
            *,
            center: Point3D,
            cellsize: float,
            dwell_s: float,
            pitch: float,  # distances between dots
            edge_margin: float,
            dot_z_offset: float | Sequence[float],
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
        rows = get_cell_dot_rows(cellsize, pitch, edge_margin)
        if not rows:
            raise ValueError(
                f"No dots fit: cellsize {cellsize} um leaves nothing usable after 2 x "
                f"edge_margin {edge_margin} um."
            )

        # One offset per dot row. A single float is broadcast over all rows, which is the old
        # single-plane behaviour. A zero entry inside a list is left alone on purpose: that row is
        # coplanar with the pad's top hatch layer and is written over by it, which is a usable
        # control row. A bare zero is still refused, since there it can only be an oversight.
        if isinstance(dot_z_offset, (int, float)):
            if base_height > 0 and abs(dot_z_offset) < MIN_DOT_Z_OFFSET:
                raise ValueError(
                    f"dot_z_offset {dot_z_offset} um puts the dots in the plane of the pad's top "
                    f"hatch layer, which is written straight over them. Use a positive offset to sit "
                    f"them proud of the pad, or a negative one to embed them deliberately."
                )
            dot_z_offsets = [float(dot_z_offset)] * len(rows)
        else:
            dot_z_offsets = [float(offset) for offset in dot_z_offset]
            if len(dot_z_offsets) != len(rows):
                raise ValueError(
                    f"dot_z_offset has {len(dot_z_offsets)} values, but cellsize {cellsize} um with "
                    f"pitch {pitch} um and edge_margin {edge_margin} um gives {len(rows)} dot rows. "
                    f"Pass one offset per row, bottom row (most negative Y) first, or a single "
                    f"float to put every row in one plane."
                )
        if not 0 < velocity < MAX_VELOCITY_UM_S:
            raise ValueError(
                f"velocity {velocity} um/s is outside (0, {MAX_VELOCITY_UM_S}) um/s. The dot "
                f"program sets the feed rate with SET_SPEED, which rejects F >= 15 mm/s."
            )
        self.center = center
        self.cellsize = cellsize
        self.dwell_s = dwell_s
        self.pitch = pitch
        self.edge_margin = edge_margin
        self.dot_z_offsets = dot_z_offsets
        self.velocity = velocity
        self.base_power = base_power  # investigation of power in dot program 
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
    def dot_rows(self) -> list[list[tuple[float, float]]]:
        return get_cell_dot_rows(self.cellsize, self.pitch, self.edge_margin)

    @property
    def dot_zs(self) -> list[float]:
        """Absolute dot plane per row, in the same order as dot_rows."""
        return [self.center.Z + self.base_height + offset for offset in self.dot_z_offsets]

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
        """Park the stage on the slot centre, then write each dot as a galvo A/B offset.

        IFOV_AeroBasicProgram rather than DrawableAeroBasicProgram: under the stage coordinate
        system that axes="XYZ" selects, CoordinateSystem.convert silently drops A/B keys, so a
        DrawableAeroBasicProgram cannot emit a galvo move at all. IFOV_AeroBasicProgram passes
        A/B through unit-scaled and gives X/Y/Z the absolute stage offsets.

        initialise_IFOV_configuration() is deliberately not called: it sets
        GALVO LASEROVERRIDE A AUTO, under which the approach move to each dot would be written.
        """
        program = IFOV_AeroBasicProgram(coordinate_system)
        rows = self.dot_rows
        zs = self.dot_zs
        n_dots = sum(len(row) for row in rows)
        velocity_mm_s = self.velocity / 1000.0
        offsets = " / ".join(
            f"{offset:+.2f}" + (" (coplanar with pad top)" if abs(offset) < MIN_DOT_Z_OFFSET else "")
            for offset in self.dot_z_offsets
        )
        program.comment(
            f"Dot grid: {n_dots} dots, pitch {self.pitch} um, dwell {self.dwell_s * 1000:.0f} ms, "
            f"z offset per row (bottom->top) {offsets} um, power inherited from structure"
        )

        program.send("SECONDS")  # DWELL is emitted in seconds
        program.ABSOLUTE()
        program.WAIT_MODE(WaitMode.AUTO)
        program.IFOV(IFOV_Mode.OFF)
        program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)

        # LINEAR/RAPID discard F in an IFOV program, so the feed rate has to be modal.
        program.SET_SPEED(F=velocity_mm_s)
        program.SET_SPEED(F=velocity_mm_s, ax="A")
        program.SET_SPEED(F=velocity_mm_s, ax="B")
        program.SET_SPEED(F=1, ax="Z")

        # X=0/Y=0, not self.center: the coordinate system offset already carries
        # slot centre + structure centre. The dots are galvo offsets from that parked position.
        program.RAPID(X=0, Y=0, Z=zs[0])

        # Z is repeated on every dot rather than moved once per row: the emitted program keeps the
        # shape that has already been verified on the machine, and only changes value at a row edge.
        for row, z in zip(rows, zs):
            for dx, dy in row:
                program.LINEAR(A=dx, B=dy, Z=z)
                program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.ON)
                program.DWELL(self.dwell_s)
                program.GALVO_LASER_OVERRIDE(GalvoLaserOverrideMode.OFF)
        return program
