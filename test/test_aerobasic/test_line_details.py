"""Velocity units and zero or small heights of line structures (T35)."""
import logging
import re

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.DOE import DOEstep, Simple_DOE
from nanofactorysystem.aerobasic.programs.drawings.lines import (IFOV_Lines, IFOV_WRITING_SPEED_MM_S, Rectangle3D,
                                                                 step_slice_size)
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit


def coordinate_system():
    return CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)


def layers(structure):
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system())]


def rectangle(height, slice_size=1.0, velocity=1000):
    return Rectangle3D(Point3D(0, 0, 0), 10, 10, height, hatch_size=2.0, slice_size=slice_size, velocity=velocity,
                       acceleration=500)


def test_non_ifov_velocity_is_given_in_um_per_s_and_written_in_mm_per_s():
    # 1000 um/s in the structure -> F1 (mm/s) in the program; the coordinate system converts it
    speeds = {float(f) for text in layers(rectangle(1, velocity=1000)) for f in re.findall(r"F([0-9.]+)", text)}
    assert speeds == {1.0}
    speeds = {float(f) for text in layers(rectangle(1, velocity=2500)) for f in re.findall(r"F([0-9.]+)", text)}
    assert speeds == {2.5}


def test_rectangle_without_height_prints_nothing():
    assert layers(rectangle(0)) == []


def test_rectangle_lower_than_half_a_slice_has_one_layer():
    assert len(layers(rectangle(0.2, slice_size=1.0))) == 1
    assert len(layers(rectangle(3, slice_size=1.0))) == 4  # unchanged: 0, 1, 2, 3 um


def test_step_slice_size():
    assert step_slice_size(3.0, 0.8) == pytest.approx(0.75)  # 4 whole layers
    assert step_slice_size(0.0, 0.5) == 0.5
    assert step_slice_size(0.2, 1.0) == 1.0


def test_doe_with_zero_height_pixels():
    profile = np.array([[0.0, 1.0], [2.0, 0.0]])
    step = DOEstep(Point3D(0, 0, 0), 5.0, profile, hatch_size=1.0, slice_size=1.0, velocity=1000, acceleration=500)
    assert len(layers(step)) == 2 + 3  # the zero pixels print nothing
    simple = Simple_DOE(Point3D(0, 0, 0), 2, 2, profile, 5.0, hatch_size=1.0, slice_size=1.0, velocity=1000,
                        acceleration=500)
    assert len(layers(simple)) == 2 + 3


def test_ifov_lines_velocity(caplog):
    assert IFOV_Lines(Point3D(0, 0, 0), [], velocity=5000).velocity == 5  # um/s by mistake -> mm/s
    assert IFOV_Lines(Point3D(0, 0, 0), [], velocity=3).velocity == 3
    with caplog.at_level(logging.WARNING):
        assert IFOV_Lines(Point3D(0, 0, 0), [], velocity=100).velocity == 5  # was an exception before
    assert "too high" in caplog.text
    with pytest.raises(ValueError, match="exceeds 25 mm/s"):
        IFOV_Lines(Point3D(0, 0, 0), [], velocity=30_000)
    assert IFOV_WRITING_SPEED_MM_S == {"Zeiss 63x": 5, "Zeiss 20x": 10}
