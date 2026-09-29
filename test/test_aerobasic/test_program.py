import tempfile
from pathlib import Path
from unittest import TestCase

from nanofactorysystem.aerobasic import Axis
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.utils.visualization import read_file, plot_movements

FOLDER = Path(__file__).parent.parent / "_programs"


class TestAeroBasicProgramManual(TestCase):
    def test_simple_program(self):
        programm = AeroBasicProgram()

        programm.ENABLE(Axis.XY)
        programm.HOME(Axis.XY)

        programm.write(FOLDER / "manual.pgm")


class AeroBasicProgramTest(TestCase):
    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use('Agg')  # Use the Agg backend

    def setUp(self):
        self.desired_content = None
        self.program = AeroBasicProgram()

    def tearDown(self):
        # Check content. The timestamp header is not deterministic, and the
        # expected texts describe the compact program body.
        if self.desired_content is not None:
            content = self.program.to_text(add_timestamp=False, compact=True)
            self.assertEqual(self.desired_content, content)

        # Keep the program and a plot of its movements in test/_programs for manual inspection
        path = FOLDER / self.__class__.__name__ / f"{self._testMethodName}.txt"
        path.parent.mkdir(exist_ok=True, parents=True)
        content = self.program.write(path)
        print(f"{len(content.splitlines())} lines written")
        _write_plot(path)


def _write_plot(path: Path):
    """ Save a plot of the program movements next to the program, for manual inspection. """
    import matplotlib.pyplot as plt

    movements = read_file(path)
    fig = plot_movements(movements)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)


def _strip_timestamp(text: str) -> str:
    """ Remove the "' Created on ..." header line written by AeroBasicProgram.write(). """

    first, rest = text.split("\n", 1)
    assert first.startswith("' Created on "), first
    return rest


class TestSimpleAeroBasicProgram(AeroBasicProgramTest):
    def test_simple_program(self):
        self.program.ENABLE(Axis.XY)
        self.program.HOME(Axis.XY)

        self.desired_content = ("ENABLE X Y\n"
                                "HOME X Y\n"
                                "END PROGRAM\n")

    def test_write_simple_program_str(self):
        self.test_simple_program()
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/sub/{self._testMethodName}.pgm"
            self.program.write(path)  # creates the missing folder

            # Check content
            self.assertEqual(self.desired_content, _strip_timestamp(Path(path).read_text()))

    def test_write_simple_program_pathlib(self):
        self.test_simple_program()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / f"{self._testMethodName}.pgm"
            self.program.write(path)  # creates the missing folder

            # Check content
            self.assertEqual(self.desired_content, _strip_timestamp(path.read_text()))

    def test_simple_variable(self):
        my_var = self.program.create_variable("my_var")
        my_var.set(5)

        self.desired_content = ("DVAR $my_var\n"
                                "$my_var = 5\n"
                                "END PROGRAM\n")

    def test_variable_function(self):
        my_var = self.program.create_variable("complex_var")
        my_var.ENABLE(Axis.AB)

        self.desired_content = ("DVAR $complex_var\n"
                                "$complex_var = ENABLE A B\n"
                                "END PROGRAM\n")
