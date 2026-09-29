"""Tests for reading and plotting program movements (utils/visualization.py)."""
import matplotlib
import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.circle import FilledCircle2D
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit
from nanofactorysystem.utils.visualization import (
    ClockwiseMovement, CounterclockwiseMovement, LinearMovement, plot_movements, read_text)

matplotlib.use("Agg")


def test_clockwise_arc_geometry():
    # From (1, 0) around the origin (I=-1, J=0 relative to the start) clockwise to (0, -1)
    arc = ClockwiseMovement(Point3D(-1, 0, 0), Point3D(1, 0, 0), Point3D(0, -1, 0), laser_on=True)

    points = arc.as_line_segment()

    assert points.shape == (100, 3)
    assert np.hypot(points[:, 0], points[:, 1]) == pytest.approx(np.ones(100))
    assert points[0, :2] == pytest.approx([1, 0]) and points[-1, :2] == pytest.approx([0, -1], abs=1e-12)
    assert np.all(points[:, 1] <= 1e-12), "a clockwise quarter arc stays below the x axis"


def test_counterclockwise_arc_geometry():
    arc = CounterclockwiseMovement(Point3D(-1, 0, 0), Point3D(1, 0, 0), Point3D(0, 1, 0), laser_on=True)

    points = arc.as_line_segment()

    assert points.shape == (100, 3)
    assert np.all(points[:, 1] >= -1e-12)


def test_read_text_linear_rapid_arcs_and_variables():
    text = "\n".join([
        "ABSOLUTE",
        "RAPID X1 Y1 Z1",
        "GALVO LASEROVERRIDE A ON",
        "LINEAR X2 Y1 Z1 F1",
        "LINEAR Z $dz F $slow",  # variables are ignored
        "CW X2 Y1 I-0.5 J0 F1",
        "GALVO LASEROVERRIDE A OFF",
    ])

    movements = read_text(text)

    assert [type(m) for m in movements] == [LinearMovement, LinearMovement, ClockwiseMovement]
    assert [m.laser_on for m in movements] == [True, True, True]


def test_plot_program_without_movement():
    fig = plot_movements([])

    assert len(fig.axes) == 2


def test_plot_filled_circle_program():
    cs = CoordinateSystem(offset_x=17.5, offset_y=21.0, z_function=25.2, unit=Unit.mm)
    circle = FilledCircle2D(Point3D(0, 0, 0), radius_start=0.2, radius_end=0.0, hatch_size=0.02, velocity=2)
    text = "\n".join(layer.to_text(add_timestamp=False) for layer in circle.iterate_layers(cs))

    movements = read_text(text)
    fig = plot_movements(movements)

    assert any(isinstance(m, (ClockwiseMovement, CounterclockwiseMovement)) for m in movements)
    assert len(fig.axes) == 2
