"""Laser power per segment in slicer structures (T31)."""
import re

import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from nanofactorysystem.aerobasic.programs.drawings.model3d import Model3D_Slicer  # noqa: E402
from nanofactorysystem.aerobasic.slicer.toolpath import ROLE_CONTOUR  # noqa: E402
from nanofactorysystem.backends.dummy.attenuator import write_calibration_file  # noqa: E402
from nanofactorysystem.backends.dummy.world import SimulatedWorld  # noqa: E402
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit  # noqa: E402
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration  # noqa: E402


@pytest.fixture(autouse=True)
def synthetic_calibration(tmp_path):
    path = write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(path)):
        yield


def box():
    mesh = trimesh.creation.box(extents=(10.0, 10.0, 2.0))
    mesh.apply_translation([0, 0, 1.0])
    return mesh


def structure(**kwargs):
    return Model3D_Slicer(Point3D(0, 0, 0), box(), velocity=1000, hatch_size=1.0, slice_size=1.0,
                          num_contour_lines=1, **kwargs)


def programs(structure):
    coordinate_system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
    # The program lines without the header (it has a creation timestamp)
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system)]


def power_comments(text):
    return re.findall(r"Power set to ([0-9.]+) mW", text)


def test_without_overrides_the_programs_are_unchanged():
    plain = programs(structure(power=1.0))
    mapped = programs(structure(power=1.0, power_map=lambda z_um, role: None))
    assert mapped == plain
    assert all(power_comments(text) == ["1.0", "1.0"] for text in plain)  # contour block and infill block
    assert structure(power=1.0).element_powers_mw == [1.0]


def test_power_per_role_and_layer():
    def power_map(z_um, role):
        if role == ROLE_CONTOUR:
            return 2.0
        return 1.5 if z_um > 1.0 else None  # upper layers: infill at 1.5 mW, lower: structure power

    printed = structure(power=1.0, power_map=power_map)
    texts = programs(printed)
    assert [power_comments(t) for t in texts] == [["2.0", "1.0"], ["2.0", "1.5"]]
    assert printed.element_powers_mw == [1.0, 1.5, 2.0]
    assert printed.to_json()["element_powers_mw"] == [1.0, 1.5, 2.0]


def test_power_per_line_on_the_toolpath():
    # Adaptive strategies (F7) set the power of single elements in the IR; consecutive equal powers share a block
    printed = structure(power=1.0)
    infill = [e for e in printed.toolpath_job.groups[0].elements if e.role != ROLE_CONTOUR]
    infill[0].power_mw = 3.0
    texts = programs(printed)
    assert power_comments(texts[0]) == ["1.0", "3.0", "1.0"]


def test_overrides_need_the_structure_power():
    with pytest.raises(ValueError, match="power of the structure"):
        programs(structure(power_map=lambda z_um, role: 2.0 if role == ROLE_CONTOUR else None))
