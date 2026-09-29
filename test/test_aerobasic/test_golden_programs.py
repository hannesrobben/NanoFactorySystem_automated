"""Golden-file tests for the generated AeroBasic programs.

Each case builds a setup program (DefaultSetup or SetupIFOV) plus the layer
programs of one representative structure, as Experiment.build_programs()
writes them, and compares the text (without the timestamp header) with
test/golden/<case>.txt.

To record an intended change, run
    python -m pytest test/test_aerobasic/test_golden_programs.py --update-golden
and review the diff of test/golden/ before committing.
"""
import pytest

from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import IFOV_Lines
from nanofactorysystem.backends.dummy import SimulatedWorld, write_calibration_file
from nanofactorysystem.aerobasic.programs.drawings import (
    BinaryGrating_IFOV, Corner, Rectangle2D_IFOV, Rectangle3D, Stair)
from nanofactorysystem.aerobasic.programs.drawings.circle import FilledCircle2D
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.aerobasic.programs.drawings.qr_code import QRCode
from nanofactorysystem.aerobasic.programs.setups import DefaultSetup, SetupIFOV
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, DropDirection, Point3D, Unit


def coordinate_system(drop_direction=DropDirection.UP):
    """ Experiment-like coordinate system: µm in, mm out, fixed substrate height. """

    return CoordinateSystem(offset_x=1310.0, offset_y=19500.0, z_function=20000.0,
                            drop_direction=drop_direction, unit=Unit.um)


def render(setup, structure=None, drop_direction=DropDirection.UP) -> str:
    """ Text of the setup program followed by every layer program of the structure. """

    parts = ["' ==== setup ====", setup.to_text(add_timestamp=False)]
    if structure is not None:
        for i, layer in enumerate(structure.iterate_layers(coordinate_system(drop_direction))):
            parts += [f"' ==== layer {i} ====", layer.to_text(add_timestamp=False)]
    return "\n".join(parts)


@pytest.fixture(autouse=True)
def synthetic_ifov_calibration(tmp_path, monkeypatch):
    """ IFOV structures read the lab calibration file (hardcoded, see T14); use a synthetic one. """

    path = write_calibration_file(tmp_path / "calibration.dat", SimulatedWorld())
    monkeypatch.setattr(IFOV_Lines, "calibrationFile", str(path))


CASES = {
    "setup_default": lambda: render(DefaultSetup()),
    "setup_ifov_20x": lambda: render(SetupIFOV(objective="Zeiss 20x")),
    "setup_ifov_63x": lambda: render(SetupIFOV(objective="Zeiss 63x")),
    "corner_default": lambda: render(
        DefaultSetup(),
        Corner(Point3D(0, 0, -2), length=60, width=10, height=3, hatch_size=0.5, slice_size=1.0, F=2000)),
    "corner_rotated_default": lambda: render(
        DefaultSetup(),
        Corner(Point3D(0, 0, -2), length=60, width=10, height=3, hatch_size=0.5, slice_size=1.0,
               rotation_degree=45, F=2000)),
    "rectangle3d_default": lambda: render(
        DefaultSetup(),
        Rectangle3D(Point3D(10, -5, 0), 10, 20, 2, hatch_size=1.0, slice_size=1.0, velocity=1000, acceleration=500)),
    "stair_default": lambda: render(
        DefaultSetup(),
        Stair(Point3D(0, 0, -1), n_steps=3, step_height=1.0, step_length=5.0, step_width=10.0, socket_height=1.0,
              hatch_size=1.0, slice_size=1.0, velocity=1000, acceleration=500),
        DropDirection.DOWN),
    "filled_circle_default": lambda: render(
        DefaultSetup(),
        FilledCircle2D(Point3D(0, 0, 0), radius_start=5, radius_end=0, hatch_size=1.0, velocity=2)),
    "qrcode_default": lambda: render(
        DefaultSetup(),
        QRCode(Point3D(0, 0, -1), "NFS", pixel_pitch=2.0, base_height=1.0, anchor_height=1.0, pixel_height=1.0,
               hatch_size=1.0, slice_size=1.0, horizontal_velocity=1000, horizontal_acceleration=500,
               vertical_velocity=500, vertical_acceleration=100)),
    "rectangle2d_ifov_20x": lambda: render(
        SetupIFOV(objective="Zeiss 20x"),
        Rectangle2D_IFOV(Point3D(0, 0, 0), 20, 10, hatch_size=1.0, velocity=5, power=1.0,
                         hatching_direction=HatchingDirection.X)),
    "binary_grating_ifov_63x": lambda: render(
        SetupIFOV(objective="Zeiss 63x"),
        BinaryGrating_IFOV(Point3D(0, 0, 0), x_dim=10, y_dim=10, period=4, height=1.0, hatch_size=0.5,
                           slice_size=0.5, velocity=5, power=1.0),
        DropDirection.DOWN),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_program_matches_golden(case, golden):
    golden(case, CASES[case]())


@pytest.mark.parametrize("case", sorted(CASES))
def test_program_generation_is_deterministic(case):
    assert CASES[case]() == CASES[case](), "program text differs between two runs"


def test_render_without_timestamp():
    text = render(DefaultSetup())

    assert "Created on" not in text
    assert isinstance(DefaultSetup(), AeroBasicProgram)
