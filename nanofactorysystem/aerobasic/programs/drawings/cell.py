from typing import Optional, Iterator

from nanofactorysystem.aerobasic.programs.drawings.cell_geometry_2 import get_cell_points
from nanofactorysystem.aerobasic.programs.drawings import DrawableAeroBasicProgram, DrawableObject, IFOV_AeroBasicProgram
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Point2D


class CellGeometry(DrawableObject):
    def __init__(
            self,
            center: Point3D | Point2D,
            fov: float,
            *,
            distance_between_lines: Optional[float] = 10.0,
            edge_margin: Optional[float] = 0.5,
            velocity: float,
            objective: str = "Zeiss 63x",
            height: float = 3.0,        # µm; >0 => stacked 3D cell, 0 => single flat layer
            slice_size: float = 0.2,   # µm; keep height an integer multiple (3/0.75 = 4 -> 5 layers)
    ):
        super().__init__()
        self.center = center
        self.fov = fov
        self.velocity = velocity
        self.objective = objective
        self.height = height
        self.slice_size = slice_size
        self.distance_between_lines = distance_between_lines
        self.edge_margin = edge_margin

    @property
    def center_point(self) -> Point2D:
        return self.center if isinstance(self.center, Point2D) else Point2D(self.center.X, self.center.Y)

    def _ifov_layer(self, coordinate_system, segments, velocity_mm_s, z_layer, label):
        """One IFOV program drawing the four-quadrant pattern at a single z."""
        cx, cy = self.center.X, self.center.Y

        program = IFOV_AeroBasicProgram(coordinate_system)
        program.comment(f"\n[CellGeometry] {label}, fov={self.fov}, v={self.velocity} um/s")
        program.initialise_IFOV_configuration(objective=self.objective)
        program.SET_SPEED(F=velocity_mm_s)
        program.SET_SPEED(F=velocity_mm_s, ax="A")
        program.SET_SPEED(F=velocity_mm_s, ax="B")
        program.SET_SPEED(F=1, ax="Z")
        program.ABSOLUTE()

        # Move stage to cell center (+ this layer's z), reset galvo, enter IFOV mode
        if z_layer is not None:
            program.RAPID(X=cx, Y=cy, Z=z_layer)
        else:
            program.RAPID(X=cx, Y=cy)
        program.RESET_GALVO()
        program.START_IFOV()

        for (sx, sy), (ex, ey) in segments:
            program.RAPID(A=cx + sx, B=cy + sy)   # position galvo to line start (no laser)
            program.LINEAR(A=cx + ex, B=cy + ey)  # draw line (laser on)

        program.end_ifov_program()
        return program

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        segments = get_cell_points(self.fov, self.distance_between_lines, self.edge_margin)
        z = self.center.Z if isinstance(self.center, Point3D) else None
        velocity_mm_s = self.velocity / 1000.0 if self.velocity >= 500 else self.velocity

        # Flat cell: single layer at the centre's z
        if self.height <= 0 or z is None:
            yield self._ifov_layer(coordinate_system, segments, velocity_mm_s, z, "flat cell")
            return

        # 3D cell: stack the pattern over `height`, slice by slice.
        # n_layer = intervals + 1; with height a whole multiple of slice_size the spacing is exact.
        n_layer = abs(round(self.height / self.slice_size)) + 1
        slice_size_opt = self.height / (n_layer - 1)
        for i in range(n_layer):
            z_layer = z + i * slice_size_opt
            yield self._ifov_layer(
                coordinate_system, segments, velocity_mm_s, z_layer,
                f"layer {i + 1}/{n_layer} (z={z_layer:.2f} um)"
            )