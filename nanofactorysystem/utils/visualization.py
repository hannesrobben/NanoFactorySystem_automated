import abc
import re
import warnings
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.ticker import FuncFormatter, ScalarFormatter
from mpl_toolkits.mplot3d.art3d import Line3DCollection

from nanofactorysystem.devices.coordinate_system import Point3D

LASER_ON_PLOT_STYLE = {
    "c": "blue"
}
LASER_OFF_PLOT_STYLE = {
    "c": "red",
    "alpha": 0.2
}
LASER_ON_COLLECTION_STYLE = {
    "colors": LASER_ON_PLOT_STYLE["c"]
}
LASER_OFF_COLLECTION_STYLE = {
    "colors": LASER_OFF_PLOT_STYLE["c"],
    "alpha": LASER_OFF_PLOT_STYLE["alpha"]
}


# Attenuator setting in generated programs, e.g. "$AO[0].A=1.95"
ATTENUATOR_PATTERN = re.compile(r"^\$AO\[0\]\.A\s*=\s*([-+\d.eE]+)")


class Movement(abc.ABC):
    def __init__(self, *, laser_on: bool, attenuator: Optional[float] = None):
        self.laser_on = laser_on
        # Attenuator value set by the program before this movement ($AO[0].A); None if the program
        # does not set it (the power is then set by the controller before the program runs)
        self.attenuator = attenuator

    @staticmethod
    def get_ax(ax: Optional[plt.Axes]) -> plt.Axes:
        if ax is None:
            return plt.gca()
        return ax

    @abc.abstractmethod
    def as_line_segment(self):
        pass

    def plot(self, ax: Optional[plt.Axes] = None, **plot_kwargs):
        ax = self.get_ax(ax)

        line_segment = self.as_line_segment()
        xs = line_segment[:, 0]
        ys = line_segment[:, 1]
        zs = line_segment[:, 2]

        # Plot the arc
        if self.laser_on:
            ax.plot(xs, ys, zs, **LASER_ON_PLOT_STYLE, **plot_kwargs)
        else:
            ax.plot(xs, ys, zs, **LASER_OFF_PLOT_STYLE, **plot_kwargs)


class PointMovement(Movement):
    def __init__(self, location: Point3D, *, laser_on: bool, attenuator: Optional[float] = None):
        super().__init__(laser_on=laser_on, attenuator=attenuator)
        self.location = location

    def as_line_segment(self) -> np.ndarray:
        return np.asarray([self.location.as_tuple(), self.location.as_tuple()])

    def plot(self, ax: Optional[plt.Axes] = None, **plot_kwargs):
        ax = self.get_ax(ax)
        if self.laser_on:
            ax.scatter(*self.location.as_tuple(), **LASER_ON_PLOT_STYLE, **plot_kwargs)
        else:
            ax.scatter(*self.location.as_tuple(), **LASER_OFF_PLOT_STYLE, **plot_kwargs)


class LinearMovement(Movement):
    def __init__(self, start: Point3D, end: Point3D, *, laser_on: bool, attenuator: Optional[float] = None):
        super().__init__(laser_on=laser_on, attenuator=attenuator)
        self.start = start
        self.end = end

    def as_line_segment(self) -> np.ndarray:
        return np.asarray([self.start.as_tuple(), self.end.as_tuple()])


class ClockwiseMovement(Movement):
    def __init__(self, center: Point3D, start: Point3D, end: Point3D, *, laser_on: bool,
                 attenuator: Optional[float] = None):
        super().__init__(laser_on=laser_on, attenuator=attenuator)
        self.relative_center = center  # I, J: center relative to the start point
        self.center = center + start
        self.start = start
        self.end = end

    def as_line_segment(self) -> np.ndarray:
        # Compute the radius from the center to the start point
        radius = np.sqrt((self.start.X - self.center.X) ** 2 + (self.start.Y - self.center.Y) ** 2)

        # Compute angles for start and end points relative to the center
        start_angle = np.arctan2(self.start.Y - self.center.Y, self.start.X - self.center.X)
        end_angle = np.arctan2(self.end.Y - self.center.Y, self.end.X - self.center.X)

        # Ensure that the angles are in a clockwise (decreasing) direction; equal angles give a full circle
        if end_angle >= start_angle:
            end_angle -= 2 * np.pi

        # Generate points on the arc
        theta = np.linspace(start_angle, end_angle, 100)
        arc_x = self.center.X + radius * np.cos(theta)
        arc_y = self.center.Y + radius * np.sin(theta)
        arc_z = np.linspace(self.start.Z, self.end.Z, len(arc_x))
        return np.stack([arc_x, arc_y, arc_z], axis=1)


class CounterclockwiseMovement(Movement):
    def __init__(self, center: Point3D, start: Point3D, end: Point3D, *, laser_on: bool,
                 attenuator: Optional[float] = None):
        super().__init__(laser_on=laser_on, attenuator=attenuator)
        self.center = center + start
        self.start = start
        self.end = end

    def as_line_segment(self):
        # Compute the radius from the center to the start point
        radius = np.sqrt((self.start.X - self.center.X) ** 2 + (self.start.Y - self.center.Y) ** 2)

        # Compute angles for start and end points relative to the center
        start_angle = np.arctan2(self.start.Y - self.center.Y, self.start.X - self.center.X)
        end_angle = np.arctan2(self.end.Y - self.center.Y, self.end.X - self.center.X)

        # Ensure that the angles are in a counterclockwise direction
        if start_angle >= end_angle:
            end_angle += 2 * np.pi

        # Generate points on the arc
        theta = np.linspace(start_angle, end_angle, 100)
        arc_x = self.center.X + radius * np.cos(theta)
        arc_y = self.center.Y + radius * np.sin(theta)
        arc_z = np.linspace(self.start.Z, self.end.Z, len(arc_x))
        return np.stack([arc_x, arc_y, arc_z], axis=1)


def read_file(path) -> list[Movement]:
    path = Path(path)
    return read_text(path.read_text())


def read_text(text: str) -> list[Movement]:
    """ Read the movements of an AeroBasic program.

    Every movement records whether the laser was on and the attenuator
    value set before it by ``$AO[0].A=<value>`` (None while the program has
    not set one).

    Parameters
    ----------
    text : str
        Program text.

    Returns
    -------
    list of Movement
    """

    movements = []

    laser_on = False
    attenuator = None
    x, y, z, a, b = 0, 0, 0, 0, 0
    for line in text.split("\n"):
        new_x, new_y, new_z, new_a, new_b = x, y, z, a, b
        power_match = ATTENUATOR_PATTERN.match(line.strip())
        if line.startswith("'"):
            # Skip comments
            continue
        elif power_match:
            attenuator = float(power_match.group(1))
        elif "GALVO LASEROVERRIDE A ON" in line:
            laser_on = True
        elif "GALVO LASEROVERRIDE A OFF" in line:
            laser_on = False
        elif line.startswith("LINEAR") or line.startswith("RAPID"):
            op, *args = line.strip().split(" ")

            for arg in args:
                ax = arg[0]
                try:
                    pos = float(arg[1:])
                except ValueError:
                    continue  # variables (e.g. "$dz") are not evaluated

                if ax == "X":
                    new_x = pos
                elif ax == "Y":
                    new_y = pos
                elif ax == "Z":
                    new_z = pos
                elif ax == "A":
                    new_a = pos
                elif ax == "B":
                    new_b = pos
                elif ax == "E":
                    continue
                elif ax == "F":
                    continue
                else:
                    raise RuntimeError(f"Did not recognize axis: {ax}")
            if (x + a) != 0 and (y + b) != 0 and z != 0:
                movements.append(LinearMovement(
                    Point3D(x + a, y + b, z),
                    Point3D(new_x + new_a, new_y + new_b, new_z),
                    laser_on=laser_on,
                    attenuator=attenuator,
                ))

        elif line.startswith("CW") or line.startswith("CCW"):
            op, *args = line.strip().split(" ")
            new_x, new_y, new_z, new_a, new_b = x, y, z, a, b
            circle_center = Point3D(0, 0, 0)
            axes = []
            for arg in args:
                ax = arg[0]
                try:
                    pos = float(arg[1:])
                except ValueError:
                    continue  # variables (e.g. "$r") are not evaluated

                if ax == "X":
                    new_x = pos
                    axes.append("X")
                elif ax == "Y":
                    new_y = pos
                    axes.append("Y")
                elif ax == "Z":
                    new_z = pos
                    axes.append("Z")
                elif ax == "A":
                    new_a = pos
                    axes.append("X")
                elif ax == "B":
                    new_b = pos
                    axes.append("Y")
                elif ax == "I":
                    # First axis
                    setattr(circle_center, axes[0], pos)
                elif ax == "J":
                    # Second axis
                    setattr(circle_center, axes[1], pos)
                elif ax == "E":
                    continue  # Speed doesnt matter atm
                elif ax == "F":
                    continue  # Speed doesnt matter atm
                elif ax == "R":
                    warnings.warn("Circle with radius not yet implemented and are skipped")
                else:
                    raise RuntimeError(f"Did not recognize axis: {ax}")
            if op == "CW":
                movements.append(
                    ClockwiseMovement(
                        circle_center,
                        Point3D(x + a, y + b, z),
                        Point3D(new_x + new_a, new_y + new_b, new_z),
                        laser_on=laser_on,
                        attenuator=attenuator,
                    )
                )
            elif op == "CCW":
                movements.append(
                    CounterclockwiseMovement(
                        circle_center,
                        Point3D(x + a, y + b, z),
                        Point3D(new_x + new_a, new_y + new_b, new_z),
                        laser_on=laser_on,
                        attenuator=attenuator,
                    )
                )
            else:
                raise RuntimeError("Something bad happened...")
        elif line.startswith("DWELL"):
            if laser_on:
                movements.append(
                    PointMovement(Point3D(x + a, y + b, z), laser_on=laser_on, attenuator=attenuator)
                )
        x, y, z, a, b = new_x, new_y, new_z, new_a, new_b

    return movements


def plot_movements(movements, *, use_mu_m=True, calibration=None):
    """ Plot movements in 3-D (real and uneven scale); see :func:`plot_movements_fast`. """

    return plot_movements_fast(movements, use_mu_m=use_mu_m, calibration=calibration)


def _axis_formatter(use_mu_m: bool):
    """ Tick formatter for program coordinates in mm: shown in µm, or in mm without offset and scientific notation. """

    if use_mu_m:
        return FuncFormatter(lambda x, pos: f"{x * 1000:.1f}")
    formatter = ScalarFormatter(useOffset=False)
    formatter.set_scientific(False)
    return formatter


def plot_movements_slow(movements, *, use_mu_m=True):
    fig = plt.figure(dpi=400)
    ax1 = fig.add_subplot(121, projection='3d')
    ax2 = fig.add_subplot(122, projection='3d')

    for movement in movements:
        movement.plot(ax1)
        movement.plot(ax2, linewidth=1)

    for ax in [ax1, ax2]:
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_major_formatter(_axis_formatter(use_mu_m))
        unit = "$\mu$m" if use_mu_m else "mm"
        ax.set_xlabel(f"X [{unit}]")
        ax.set_ylabel(f"Y [{unit}]")
        ax.set_zlabel(f"Z [{unit}]")
    ax1.set_title("Real scale")
    ax2.set_title("Uneven scale")

    def on_move(event):
        if event.inaxes == ax1:
            azim, elev = ax1.azim, ax1.elev
            ax2.view_init(elev=elev, azim=azim)
        elif event.inaxes == ax2:
            azim, elev = ax2.azim, ax2.elev
            ax1.view_init(elev=elev, azim=azim)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('motion_notify_event', on_move)

    fig.canvas.draw()
    xs, ys, zs = ax1.get_xlim(), ax1.get_ylim(), ax1.get_zlim()
    ax1.set_box_aspect((np.ptp(xs), np.ptp(ys), np.ptp(zs)))
    ax2.set_box_aspect((1, 1, 1))

    return fig


def plot_movements_fast(movements, *, use_mu_m=True, calibration=None):
    """ Plot movements in 3-D, once in real scale and once with equal axis lengths.

    Movements with the laser on are drawn in blue, or, if the program sets
    the attenuator, coloured by the laser power with a colour bar;
    movements with the laser off are drawn in light red.

    Parameters
    ----------
    movements : list of Movement
        Result of :func:`read_text` or :func:`read_file`.
    use_mu_m : bool
        Label the axes in µm (the programs use mm); otherwise in mm.
    calibration : PowerCalibration, optional
        Converts attenuator values into mW for the colour scale; without it
        the colour bar shows the attenuator value.

    Returns
    -------
    matplotlib.figure.Figure
    """

    fig = plt.figure(dpi=400)
    ax1 = fig.add_subplot(121, projection='3d')
    ax2 = fig.add_subplot(122, projection='3d')

    lines_laser_on = []
    lines_laser_off = []
    powers = []
    for movement in movements:
        if movement.laser_on:
            lines_laser_on.append(movement.as_line_segment())
            powers.append(np.nan if movement.attenuator is None else movement.attenuator)
        else:
            lines_laser_off.append(movement.as_line_segment())
    powers = np.asarray(powers, dtype=float)
    if calibration is not None and np.any(~np.isnan(powers)):
        known = ~np.isnan(powers)
        powers[known] = np.asarray(calibration.atop(powers[known]), dtype=float)
    color_by_power = bool(len(powers)) and not np.all(np.isnan(powers))

    # Axis limits from all points; segments have different numbers of points
    if lines_laser_on or lines_laser_off:
        all_points = np.vstack(lines_laser_on + lines_laser_off)
        lower, upper = all_points.min(axis=0), all_points.max(axis=0)
    else:
        lower, upper = np.zeros(3), np.zeros(3)  # program without movement
    # Avoid zero-width axes, which matplotlib cannot project
    pad = np.where(upper - lower > 0, 0.0, 0.5e-3)
    xs, ys, zs = np.stack((lower - pad, upper + pad)).T

    norm = Normalize(np.nanmin(powers), np.nanmax(powers)) if color_by_power else None
    power_collection = None
    for ax in [ax1, ax2]:
        if lines_laser_on and color_by_power:
            power_collection = Line3DCollection(lines_laser_on, linewidths=1, cmap="viridis", norm=norm)
            power_collection.set_array(powers)
            ax.add_collection3d(power_collection)
        elif lines_laser_on:
            ax.add_collection3d(Line3DCollection(lines_laser_on, linewidths=1, **LASER_ON_COLLECTION_STYLE))
        if lines_laser_off:
            ax.add_collection3d(Line3DCollection(lines_laser_off, linewidths=1, **LASER_OFF_COLLECTION_STYLE))
        ax.set_xlim(*xs)
        ax.set_ylim(*ys)
        ax.set_zlim(*zs)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.set_major_formatter(_axis_formatter(use_mu_m))
        unit = "$\mu$m" if use_mu_m else "mm"
        ax.set_xlabel(f"X [{unit}]")
        ax.set_ylabel(f"Y [{unit}]")
        ax.set_zlabel(f"Z [{unit}]")
    if power_collection is not None:
        label = "Laser power [mW]" if calibration is not None else "Attenuator value"
        fig.colorbar(power_collection, ax=ax2, shrink=0.5, label=label)
    ax1.set_title("Real scale")
    ax2.set_title("Uneven scale")

    def on_move(event):
        if event.inaxes == ax1:
            azim, elev = ax1.azim, ax1.elev
            ax2.view_init(elev=elev, azim=azim)
        elif event.inaxes == ax2:
            azim, elev = ax2.azim, ax2.elev
            ax1.view_init(elev=elev, azim=azim)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('motion_notify_event', on_move)

    ax1.set_box_aspect((np.ptp(xs), np.ptp(ys), np.ptp(zs)))
    ax2.set_box_aspect((1, 1, 1))

    return fig
