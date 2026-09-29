from nanofactorysystem.aerobasic.programs.drawings.lines import Corner
from nanofactorysystem.aerobasic.programs.setups import DefaultSetup
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, DropDirection, Unit, Point3D
from ..test_program import AeroBasicProgramTest


class TestCorners(AeroBasicProgramTest):
    def test_top_left_corner(self):
        self.program(DefaultSetup())
        self.program.send("$AO[0].A=3.0")
        coordinate_system = CoordinateSystem(
            offset_x=1750,
            offset_y=21000,
            z_function=25214,
            drop_direction=DropDirection.UP,
            unit=Unit.um
        )

        corner = Corner(
            Point3D(0, 0, -2),
            length=300,
            width=20,
            height=7,
            hatch_size=0.5,
            slice_size=0.75,
            F=2000
        )
        self.program(corner.draw_on(coordinate_system))

    def test_diagonal_corner(self):
        self.program(DefaultSetup())
        self.program.send("$AO[0].A=3.0")
        coordinate_system = CoordinateSystem(
            offset_x=1750,
            offset_y=21000,
            z_function=25214,
            drop_direction=DropDirection.UP,
            unit=Unit.um
        )

        corner = Corner(
            Point3D(0, 0, -2),
            length=300,
            width=20,
            height=7,
            hatch_size=0.5,
            slice_size=0.75,
            rotation_degree=45,
            F=2000
        )
        self.program(corner.draw_on(coordinate_system))
