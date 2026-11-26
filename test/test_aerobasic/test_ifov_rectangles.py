"""Rectangle2D_IFOV / Rectangle3D_IFOV: objective of the IFOV configuration and stateless alternation (T114)."""
import pytest

from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json
from nanofactorysystem.aerobasic.programs.drawings.ifov_gratings import Rectangle2D_IFOV, Rectangle3D_IFOV
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.backends.dummy import SimulatedWorld, write_calibration_file
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration


@pytest.fixture(autouse=True)
def synthetic_ifov_calibration(tmp_path):
    path = write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(path)):
        yield


def programs(structure):
    system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=20000.0, unit=Unit.um)
    return [layer.to_text(add_timestamp=False) for layer in structure.iterate_layers(system)]


def block(**kwargs):
    # 3 layers (odd), 10 x 6 µm, hatch 2 µm
    return Rectangle3D_IFOV(Point3D(0, 0, 0), 10, 6, 1.0, hatch_size=2.0, slice_size=0.5, velocity=5, power=1.0,
                            **kwargs)


def test_alternating_hatch_gives_identical_programs_on_every_iteration():
    structure = block(alternate_hatching=True)

    first, second = programs(structure), programs(structure)

    assert first == second and len(first) == 3
    assert structure.hatching_direction == HatchingDirection.X           # the object is not changed
    assert [structure.layer_direction(i) for i in range(3)] == [HatchingDirection.X, HatchingDirection.Y,
                                                                HatchingDirection.X]
    assert structure_from_json(structure.to_json()).hatching_direction == HatchingDirection.X


def test_objective_selects_the_ifov_configuration():
    default = programs(block())[0]
    small = programs(block(objective="Zeiss 20x"))[0]

    assert "IFOV SIZE 0.150000" in default                               # 63x, as before T114
    assert "IFOV SIZE 0.500000" in small and "IFOV SIZE 0.150000" not in small   # IFOV_SIZE_20x of the layer
    assert structure_from_json(block(objective="Zeiss 20x").to_json()).objective == "Zeiss 20x"
    layer = Rectangle2D_IFOV(Point3D(0, 0, 0), 10, 6, hatch_size=2.0, velocity=5, power=1.0,
                             hatching_direction=HatchingDirection.Y, objective="Zeiss 20x")
    assert "IFOV SIZE 0.500000" in programs(layer)[0]
