"""Tests for the laser power calibration used by IFOV structures (devices/power_calibration.py)."""
import json
import re

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings import IFOV_Lines
from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json
from nanofactorysystem.backends.dummy import SimulatedWorld, write_calibration_file
from nanofactorysystem.config import DEFAULT_CONFIG, use_config
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, DropDirection, Point2D, Point3D, Unit
from nanofactorysystem.devices.power_calibration import (
    PowerCalibration, active_power_calibration, power_calibration)

LINES = [(Point2D(0.0, 0.0), Point2D(10.0, 0.0)), (Point2D(0.0, 1.0), Point2D(10.0, 1.0))]


@pytest.fixture
def calibration_file(tmp_path):
    return write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld(max_power=20.0))


def set_power_value(structure):
    cs = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=20000.0, drop_direction=DropDirection.UP,
                          unit=Unit.um)
    text = "\n".join(layer.to_text(add_timestamp=False) for layer in structure.iterate_layers(cs))
    return float(re.search(r"\$AO\[0\]\.A=([-\d.e]+)", text).group(1))


def test_from_file_round_trip(calibration_file):
    calibration = PowerCalibration.from_file(calibration_file, "spline")

    assert calibration.data.shape == (101, 2)
    assert float(calibration.ptoa(calibration.atop(6.0))) == pytest.approx(6.0, abs=1e-3)


def test_ifov_lines_with_explicit_calibration(calibration_file):
    calibration = PowerCalibration.from_file(calibration_file)
    lines = IFOV_Lines(Point3D(0, 0, 0), LINES, velocity=5, power=5.0, calibration=calibration)

    assert set_power_value(lines) == pytest.approx(float(calibration.ptoa(5.0)))
    # Stored with its class, so that the structure can be rebuilt with the same calibration (T56)
    stored = lines.to_json()["__init__"]["calibration"]
    assert stored == {"__object__": "nanofactorysystem.devices.power_calibration.PowerCalibration",
                      "value": calibration.to_json()}
    rebuilt = structure_from_json(json.loads(json.dumps(lines.to_json())))
    assert set_power_value(rebuilt) == pytest.approx(set_power_value(lines))


def test_active_calibration_is_used(calibration_file):
    calibration = PowerCalibration.from_file(calibration_file)
    lines = IFOV_Lines(Point3D(0, 0, 0), LINES, velocity=5, power=5.0)

    with power_calibration(calibration):
        value = set_power_value(lines)

    assert value == pytest.approx(float(calibration.ptoa(5.0)))


def test_configured_file_is_the_fallback(calibration_file):
    lines = IFOV_Lines(Point3D(0, 0, 0), LINES, velocity=5, power=5.0)

    with use_config(DEFAULT_CONFIG | {"attenuator": {"calibrationFile": str(calibration_file)}}):
        value = set_power_value(lines)

    assert value == pytest.approx(float(PowerCalibration.from_file(calibration_file).ptoa(5.0)))


def test_missing_calibration_gives_clear_error():
    lines = IFOV_Lines(Point3D(0, 0, 0), LINES, velocity=5, power=5.0)

    with use_config(DEFAULT_CONFIG), pytest.raises(RuntimeError, match="No laser power calibration"):
        set_power_value(lines)


def test_no_power_needs_no_calibration():
    lines = IFOV_Lines(Point2D(0, 0), LINES, velocity=5)

    with use_config(DEFAULT_CONFIG):
        cs = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
        assert list(lines.iterate_layers(cs))


def test_active_calibration_is_refitted_for_other_fit_kind(calibration_file):
    polynomial = PowerCalibration.from_file(calibration_file, "polynomial")

    with power_calibration(polynomial):
        spline = active_power_calibration("spline")

    assert spline.fit_kind == "spline"
    assert np.array_equal(spline.data, polynomial.data)


def test_experiment_uses_calibration_of_its_attenuator(test_config, dummy_backend, no_sleep, tmp_path):
    """ Experiment.build_programs() converts IFOV powers with the attenuator of the running system. """

    import matplotlib
    from nanofactorysystem.aerobasic.programs.drawings import BinaryGrating_IFOV
    from nanofactorysystem.experiment import StructureType
    from test_experiment import make_experiment

    matplotlib.use("Agg")
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        experiment.add_structure(StructureType.IFOV, "grating", axes="ABZ", power=1.0, structure=BinaryGrating_IFOV(
            Point3D(0, 0, 0), x_dim=10, y_dim=10, period=4, height=1.0, hatch_size=0.5, slice_size=0.5,
            velocity=5, power=1.0))

        experiment.build_programs()  # the test configuration has no calibration file

        layer = experiment.structure_configs[0]["layer_files"][0]
        text = open(layer).read()
        attenuator = experiment.system.controller.attenuator
        expected = float(PowerCalibration(attenuator.data).ptoa(1.0))
        value = float(re.search(r"\$AO\[0\]\.A=([-\d.e]+)", text).group(1))
        assert value == pytest.approx(expected)
