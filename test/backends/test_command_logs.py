"""Golden command logs: the exact AeroBasic commands sent to the controller in typical flows.

Recorded with the dummy backend before the controller merge (T20), so that
refactorings of the controller classes can be checked for identical
behaviour on the machine. Regenerate deliberately with --update-golden.
"""
import pytest

from nanofactorysystem import System
from nanofactorysystem.backends import DummyBackend


def command_log(backend, tmp_path) -> str:
    """ Controller commands in order, with temporary paths replaced by <tmp>. """

    text = "\n".join(backend.calllog.commands()) + "\n"
    for path in sorted({str(tmp_path), str(tmp_path.resolve())}, key=len, reverse=True):
        text = text.replace(path, "<tmp>")
    return text.replace(chr(92), "/")  # platform-independent path separators


def run_system_flow(tmp_path):
    backend = DummyBackend(seed=0, workdir=tmp_path / "dummy")
    with System("Test", "Zeiss 20x", backend=backend, controller={"zMax": 25000.0}) as system:
        system.moveabs(x=150.0, y=-50.0, z=20010.0)
        system.wait("XYZ")
        system.position("XYZ")
        system.controller.power(1.5)
        system.pulse(1.0, 0.01)
        system.polylines(20005.0, [[(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)], [(1.0, 1.0), (1.05, 1.0)]],
                         power=2.0, speed=100.0, dia=0.5)
        system.dots(20005.0, [[1, 0], [0, 1]], pitch=2.0, power=1.0, dt=0.01)
        system.zline(1.0, 100.0, 10.0, 20.0)
        system.controller.moveinc(500.0, x=5.0, z=-2.0)
        system.home(wait=True)
    return backend


def run_experiment_flow(tmp_path, setup):
    import matplotlib
    from nanofactorysystem.aerobasic.programs.drawings import Rectangle3D
    from nanofactorysystem.devices.coordinate_system import Point3D
    from nanofactorysystem.experiment import StructureType
    from test_experiment import make_experiment

    matplotlib.use("Agg")
    backend = DummyBackend(seed=0, workdir=tmp_path / "dummy")
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, backend, dhm_usage=True, skip_corner=False, setup=setup) as experiment:
        experiment.plane_fit(plane=backend.world.sample.plane())
        experiment.opl_scan(m0=800.0)
        experiment.add_structure(
            StructureType.NORMAL, "rect", axes="XYZ", power=0.7,
            structure=Rectangle3D(Point3D(0, 0, -1), 10, 10, 2, hatch_size=1.0, slice_size=1.0,
                                  velocity=1000, acceleration=500))
        experiment.build_programs()
        experiment.print_experiment()
    return backend


FLOWS = {
    "commands_system": run_system_flow,
    "commands_experiment_ifov_off": lambda tmp_path: run_experiment_flow(tmp_path, "IFOV_off"),
    "commands_experiment_ifov_on": lambda tmp_path: run_experiment_flow(tmp_path, "IFOV_on"),
}
SLOW = pytest.mark.slow


@pytest.mark.parametrize("flow", [
    "commands_system",
    pytest.param("commands_experiment_ifov_off", marks=SLOW),
    pytest.param("commands_experiment_ifov_on", marks=SLOW),
])
def test_command_log_matches_golden(flow, test_config, no_sleep, tmp_path, golden):
    backend = FLOWS[flow](tmp_path)

    golden(flow, command_log(backend, tmp_path))


def test_command_log_is_deterministic(test_config, no_sleep, tmp_path):
    first = command_log(run_system_flow(tmp_path / "a"), tmp_path / "a")
    second = command_log(run_system_flow(tmp_path / "b"), tmp_path / "b")

    assert first == second
