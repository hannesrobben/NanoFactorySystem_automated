from typing import Iterator, Any
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram, Rectangle3D
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection, PolyLines
from nanofactorysystem.devices.coordinate_system import Point3D, CoordinateSystem, Point2D


class HollowRectangle(DrawableObject):
    default_acceleration: float = 20_000
    default_power: float = 0.7  # µW

    def __init__(self,
                 center: Point3D,
                 base_height: float,
                 hollow_height: float,
                 top_height: float,
                 width: float,  # x coordinate
                 length: float,  # y coordinate
                 min_opening: float = 5,  # 5 µm minial opening for extraction of unpolymerized material
                 *,
                 hatch_size: float,
                 slice_size: float,
                 velocity: float,
                 acceleration: float = None,
                 power: float = None,
                 hatching_direction: HatchingDirection = HatchingDirection.X,
                 alternate_hatching_direction: bool = True,
                 ):
        super().__init__()
        self.center = center
        self.x_dim = width
        self.y_dim = length

        self.base_height = base_height
        self.hollow_height = hollow_height
        self.top_height = top_height

        self.min_opening = min_opening if min_opening >= 2 else 2

        self.hatch_size = hatch_size
        self.slice_size = slice_size
        self.velocity = velocity
        self.acceleration = acceleration if acceleration is not None else self.default_acceleration
        self.power = power if power is not None else self.default_power
        self.hatching_direction = hatching_direction
        self.alternating_hatch = alternate_hatching_direction

        self._lines_for_hollow_part_dict = None
        self._lines_for_hollow_part = None

        assert self.y_dim > self.min_opening, "length and width has to be larger than the required minimum opening!"

    @property
    def center_point(self) -> Point3D:
        return self.center

    @property
    def total_height(self) -> float:
        return self.base_height + self.hollow_height + self.top_height + self.center.Z

    @property
    def x_length(self) -> float:
        return self.x_dim

    @property
    def y_length(self) -> float:
        return self.y_dim

    @property
    def width(self):
        return self.x_dim

    @property
    def length(self):
        return self.y_dim

    @property
    def boundary_box(self):
        """
        returns four 2D Points representing the corners of the structure
        """
        bottom_left = Point2D(X=self.center_point.X - self.x_dim / 2, Y=self.center_point.Y - self.y_dim / 2)
        bottom_right = Point2D(X=bottom_left.X + self.x_dim, Y=bottom_left.Y)
        top_right = Point2D(X=bottom_left.X + self.x_dim, Y=bottom_left.Y + self.y_dim)
        top_left = Point2D(X=bottom_left.X, Y=bottom_left.Y + self.y_dim)
        return [bottom_left, bottom_right, top_right, top_left]

    @property
    def lines_hollow_part(self):
        if self._lines_for_hollow_part is None:
            return self.calculate_hollow_lines()
        else:
            return self._lines_for_hollow_part

    @property
    def lines_hollow_part_dict(self):
        if self._lines_for_hollow_part_dict is None or self._lines_for_hollow_part is None:
            self.calculate_hollow_lines()

        return self._lines_for_hollow_part_dict

    def analyze_structure(self):
        print("Analyzing structure...")
        print("Structure width: \t", self.x_dim, "\nStructure length: \t", self.y_dim, "\nStructure height: \t",
              self.total_height)
        print("Structure boundary box: \t", self.boundary_box)
        print(
            f"Base height: \t{self.base_height}\nHollow height:\t{self.hollow_height}\nTop height:\t{self.top_height}")
        aax = self.visualize_hollow_part()
        aax.show()

    def visualize_hollow_part(self, ax=None, color_by_index=True, close_polygon=False):
        """
        Plot the point groups of the hollow part (``lines_hollow_part``) as connected lines.

        Args:
            ax: Axes to plot into; a new figure is created if omitted.
            color_by_index: colour the paths from blue (early) to red (late)
            close_polygon: connect the last point with the first
        """
        fig = None
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 8))

        segments = []
        for group in self.lines_hollow_part():
            coords = [(p.X, p.Y) for p in group]
            if close_polygon:
                coords.append(coords[0])  # Close the polygon
            # LineCollection expects a list of (start, end) pairs
            seg = list(zip(coords[:-1], coords[1:]))
            segments.extend(seg)

        if color_by_index:
            # Colour gradient over all segments (time order)
            n = len(segments)
            colors = plt.cm.coolwarm(np.linspace(0, 1, n))
            lc = LineCollection(segments, colors=colors, linewidths=0.8)
        else:
            lc = LineCollection(segments, colors='steelblue', linewidths=0.8)

        ax.add_collection(lc)
        ax.autoscale()
        ax.set_aspect('equal')
        ax.set_xlabel('X [µm]')
        ax.set_ylabel('Y [µm]')
        ax.set_title(f'Toolpath — {len(self.lines_hollow_part)} groups')

        # Colour bar as time axis
        if color_by_index:
            sm = plt.cm.ScalarMappable(cmap='coolwarm', norm=plt.Normalize(0, len(self.lines_hollow_part)))
            plt.colorbar(sm, ax=ax, label='Gruppen-Index (Zeit →)')

        if fig is not None:
            return fig
        else:
            return ax

    def iterate_layers(self, coordinate_system: CoordinateSystem) -> Iterator[DrawableAeroBasicProgram]:
        program = DrawableAeroBasicProgram(coordinate_system)
        if self.base_height > 0:
            base_rectangle = Rectangle3D(
                center=self.center,
                width=self.x_dim,
                length=self.y_dim,
                height=self.base_height,
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            yield from base_rectangle.iterate_layers(coordinate_system=coordinate_system)

        start_z = self.center.Z + self.base_height

        n_layer = abs(round(self.hollow_height / self.slice_size)) + 1
        slice_size_opt = self.hollow_height / (n_layer - 1)

        if self.hollow_height < 2:
            self.hollow_height = 2
            print(f"Height of inner voids are set to be at least 2µm to assure good development.")

        for i, z_height in enumerate(np.arange(start_z, self.hollow_height + slice_size_opt / 2, slice_size_opt)):
            # calculation of multiple points
            """
            x------------------x    
            -o-----------------o
            ------
            ------
            -o-----------------o
            x------------------x
            
            first print line marked with x
            second print line marked with o
            """
            program.LINEAR(Z=z_height)

            hollow_part = PolyLines(self.lines_hollow_part_dict, F=self.velocity)
            program.add_programm(hollow_part.draw_on(coordinate_system))
            yield program

        if self.top_height > 0:
            z_start_top = self.center.Z + self.base_height + self.hollow_height
            center_top = Point3D(X=self.center.X, Y=self.center.Y, Z=z_start_top)
            top_rectangle = Rectangle3D(
                center=center_top,
                width=self.x_dim,
                length=self.y_dim,
                height=self.top_height,
                hatch_size=self.hatch_size,
                slice_size=self.slice_size,
                velocity=self.velocity,
                acceleration=self.acceleration
            )
            yield from top_rectangle.iterate_layers(coordinate_system=coordinate_system)

    def calculate_hollow_lines(self) -> list[Any]:
        bottom_left = self.boundary_box[0]
        bottom_right = self.boundary_box[1]
        top_right = self.boundary_box[2]
        top_left = self.boundary_box[3]

        order = 1
        lines = []
        mapped_lines = []

        n_lines = int(np.ceil(((self.y_dim - self.min_opening) / 2) / self.hatch_size))
        opt_hatching = ((self.y_dim - self.min_opening) / 2) / n_lines
        if self.x_dim < self.y_dim:
            assert (self.x_dim - self.min_opening) > 0

        for n in range(n_lines):
            bl = Point2D(X=bottom_left.X, Y=bottom_left.Y + opt_hatching * n)
            br = Point2D(X=bottom_right.X - opt_hatching * n, Y=bottom_right.Y + opt_hatching * n)
            tr = Point2D(X=top_right.X - opt_hatching * n, Y=top_right.Y - opt_hatching * n)
            tl = Point2D(X=top_left.X, Y=top_left.Y - opt_hatching * n)

            lines.append([bl, br, tr, tl][::order])
            mapped_lines.append([bl.as_dict(), br.as_dict(), tr.as_dict(), tl.as_dict()][::order])

            order *= -1

        self._lines_for_hollow_part_dict = mapped_lines
        self._lines_for_hollow_part = lines
        return lines

    # def map_lines(self, lines=None):
    #     if lines is None:
    #         lines = self._lines_for_hollow_part
    #     mapped_lines = []
    #     for line in lines:
    #         mapped_lines.append({}) for p in line


if __name__ == "__main__":
    centering = Point3D(X=0, Y=0, Z=-2)
    test = HollowRectangle(center=centering,
                           width=50,
                           length=50,
                           base_height=3,
                           hollow_height=2,
                           top_height=1,
                           min_opening=20,
                           hatch_size=0.2,
                           slice_size=0.2,
                           velocity=10_000)

    test.analyze_structure()
