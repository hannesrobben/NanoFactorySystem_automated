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


def test_attenuator_value_is_read_and_shown_as_colour():
    from pathlib import Path

    from nanofactorysystem.backends.dummy import SimulatedWorld, write_calibration_file
    from nanofactorysystem.devices.power_calibration import PowerCalibration

    text = "\n".join([
        "' Power set to 1.0 mW", "$AO[0].A=1.9577056263619101",
        "RAPID X1.31 Y19.5 Z20.0", "GALVO LASEROVERRIDE A ON", "LINEAR X1.32 Y19.5 Z20.0",
        "GALVO LASEROVERRIDE A OFF", "$AO[0].A=0.5", "RAPID X1.31 Y19.51 Z20.0",
        "GALVO LASEROVERRIDE A ON", "LINEAR X1.32 Y19.51 Z20.0", "GALVO LASEROVERRIDE A OFF"])

    movements = read_text(text)

    values = [m.attenuator for m in movements if m.laser_on]
    assert values == pytest.approx([1.9577056263619101, 0.5])
    assert read_text("LINEAR X1 Y1 Z1\nLINEAR X2 Y2 Z2")[0].attenuator is None

    # Without a calibration the colour bar shows the attenuator value, with one the power in mW
    fig = plot_movements(movements)
    assert fig.axes[-1].get_ylabel() == "Attenuator value"
    import tempfile
    calibration = PowerCalibration.from_file(write_calibration_file(Path(tempfile.mkdtemp()) / "c.dat",
                                                                    SimulatedWorld()))
    fig = plot_movements(movements, calibration=calibration)
    assert fig.axes[-1].get_ylabel() == "Laser power [mW]"
    # Programs without attenuator setting keep the single laser-on colour and no colour bar
    assert len(plot_movements(read_text("GALVO LASEROVERRIDE A ON\nLINEAR X1 Y1 Z1\nLINEAR X2 Y2 Z2")).axes) == 2


def test_mm_axes_without_offset_or_scientific_notation():
    movements = [LinearMovement(Point3D(19.5, 21.25, 25.1), Point3D(19.5003, 21.2504, 25.1002), laser_on=True)]

    fig = plot_movements(movements, use_mu_m=False)
    fig.canvas.draw()

    for axis in (fig.axes[0].xaxis, fig.axes[0].yaxis, fig.axes[0].zaxis):
        assert axis.get_offset_text().get_text() == ""
        labels = [t.get_text() for t in axis.get_ticklabels() if t.get_text()]
        assert labels and not any("e" in label for label in labels)
