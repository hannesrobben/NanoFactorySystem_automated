"""The T117 lab test mains/Experiments/ifov_laser_test.py: four program variants of one IFOV square."""
import importlib.util
import re
from pathlib import Path

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.ifov_gratings import Rectangle3D_IFOV
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Unit
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.structure_factories import BuildContext

MAINS = Path(__file__).parents[2] / "mains"
CONTEXT = BuildContext(objective="Zeiss 63x", setup="IFOV_on", power_min_mw=0.0, power_max_mw=20.0)
CALIBRATION = PowerCalibration(np.array([[0.0, 0.0], [5.0, 5.0], [10.0, 10.0]]), "polynomial")
COORDINATES = CoordinateSystem(offset_x=1000, offset_y=20000, z_function=25000, unit=Unit.um)


@pytest.fixture
def ifov_test(monkeypatch):
    monkeypatch.syspath_prepend(str(MAINS))
    spec = importlib.util.spec_from_file_location("ifov_laser_test", MAINS / "Experiments" / "ifov_laser_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def first_layer(module, variant, direction="y", power=0.25) -> list[str]:
    structure = module.rectangle(variant=variant, power_mw=power, line_direction=direction).build(CONTEXT)
    with power_calibration(CALIBRATION):
        programs = list(structure.iterate_layers(COORDINATES))
    assert len(programs) == 13  # 3 µm / 0.25 µm + 1
    return [str(line) for line in programs[0].lines if str(line).strip()]


def written_lines(program: list[str]) -> list[tuple]:
    """ (start, end) galvo coordinates of every LINEAR after a RAPID (the written lines of an IFOV program). """

    points = [(line.split()[0], tuple(map(float, re.findall(r"[AB](-?[\d.]+)", line)))) for line in program
              if re.match(r"(RAPID|LINEAR) A", line)]
    return [(points[i][1], points[i + 1][1]) for i in range(1, len(points) - 1)
            if points[i][0] == "RAPID" and points[i + 1][0] == "LINEAR"]


def test_four_experiments_of_four_squares(ifov_test, test_config):
    experiments = ifov_test.experiments()
    assert [e.spec.name for e in experiments] == ["ifov_test_a_current", "ifov_test_b_laser_on_off",
                                                  "ifov_test_c_config_march", "ifov_test_d_galvo_only"]
    for experiment in experiments:
        spec = experiment.spec.resolved()
        assert spec.grid == (2, 2) and spec.setup == "IFOV_on" and spec.objective == "Zeiss 63x"
        assert [s.power_mw for s in spec.structures] == [0.25, 0.25, 0.7, 0.7]
        assert [s.factory.arguments["line_direction"] for s in spec.structures] == ["x", "y", "x", "y"]
    galvo = experiments[-1].spec.structures
    assert all(s.axes == "ABZ" and s.structure_type == StructureType.NORMAL for s in galvo)
    assert all(s.structure_type == StructureType.IFOV for e in experiments[:3] for s in e.spec.structures)


def test_layout_inside_the_drop_without_overlap(ifov_test, test_config):
    assert len(ifov_test.check(show=False)) == 4


@pytest.mark.parametrize("direction", ["x", "y"])
def test_current_is_the_unchanged_library_rectangle(ifov_test, direction):
    structure = ifov_test.rectangle(variant="current", power_mw=0.25, line_direction=direction).build(CONTEXT)
    assert isinstance(structure, Rectangle3D_IFOV) and structure.hatch_size == 0.2
    program = first_layer(ifov_test, "current", direction)
    assert "RAMP RATE 0" in program and "GALVO LASEROVERRIDE A AUTO" in program
    assert "GALVO LASEROVERRIDE A ON" not in program


@pytest.mark.parametrize("direction", ["x", "y"])
def test_ifov_variants_write_the_same_lines(ifov_test, direction):
    reference = written_lines(first_layer(ifov_test, "current", direction))
    assert len(reference) == 251  # 50 µm / 0.2 µm + 1
    along = 1 if direction == "y" else 0
    assert all(start[1 - along] == end[1 - along] for start, end in reference)  # lines along the given axis
    assert {abs(start[along]) for start, _ in reference} == {0.025}            # full 50 µm length
    for variant in ("laser_on_off", "config_march"):
        assert written_lines(first_layer(ifov_test, variant, direction)) == reference


def test_laser_on_off_switches_the_laser_around_every_line(ifov_test):
    program = first_layer(ifov_test, "laser_on_off")
    assert program.count("GALVO LASEROVERRIDE A ON") == program.count("GALVO LASEROVERRIDE A OFF") == 251
    on = program.index("GALVO LASEROVERRIDE A ON")
    assert program[on - 1].startswith("RAPID A") and program[on + 1].startswith("LINEAR A")
    assert program[:on] == first_layer(ifov_test, "current")[:on]  # same header


def test_config_march_uses_the_configuration_of_march(ifov_test):
    program = first_layer(ifov_test, "config_march")
    for command in ("IFOV SIZE 75.000000", "IFOV TRACKINGSPEED 10000.000000", "IFOV TRACKINGACCEL 20000.000000",
                    "GALVO ROTATION A -0.600000", "GALVO ROTATION B -1.100000", "GALVO LASEROVERRIDE A AUTO"):
        assert command in program
    for command in ("RAMP RATE 0", "LOOKAHEAD FAST", "CRITICAL START", "IFOV SYNCAXES Z"):
        assert command not in program
    assert program[-1] == "IFOV OFF"


def test_galvo_only_writes_without_ifov(ifov_test):
    program = first_layer(ifov_test, "galvo_only")
    assert not any(line.startswith("IFOV") for line in program)
    assert program.count("GALVO LASEROVERRIDE A ON") == 251
    assert all("F5.000000" in line for line in program if line.startswith("LINEAR") and "F" in line)


@pytest.mark.slow
def test_dry_run_of_one_variant(ifov_test, tmp_path):
    import dataclasses

    from nanofactorysystem.backends.dummy.dry_run import dry_run
    from nanofactorysystem.experiment_spec import run_experiment
    from nanofactorysystem.storage import ExperimentStore

    spec = ifov_test.experiment_spec("laser_on_off")
    spec = dataclasses.replace(spec, overview_capture=False, camera_capture=False)
    with dry_run("Hannes", workdir=tmp_path) as simulated:
        folder = run_experiment(spec, user="Hannes", resin_edges=ifov_test.RESIN_EDGES, path=tmp_path / "out",
                                backend=simulated.backend, plane=simulated.plane)
    record = ExperimentStore(folder).read()
    assert {s.name for s in record.structures} >= {s.name for s in spec.structures}
