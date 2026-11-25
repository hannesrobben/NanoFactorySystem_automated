"""Tests for the controller health check and recovery level R0 (T133)."""
import pytest

from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface
from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
from nanofactorysystem.devices.aerotech.health import controller_health, parse_tasklist, recover_r0


@pytest.fixture
def transport():
    return FakeA3200Transport(SimulatedWorld(seed=0))


@pytest.fixture
def api(transport):
    api = AerotechAsciiInterface(transport_factory=lambda: transport)
    api.connect()
    return api


def with_axis_fault(transport, axis="Z", fault=4):
    original = transport._axis_item

    def axis_item(name, item):
        if name == axis and item == "AxisFault":
            return str(fault)
        return original(name, item)

    transport._axis_item = axis_item


def test_healthy_controller(api):
    report = controller_health(api, check_processes=False)

    assert report.ok and report.version == "4.9.0.0"
    assert report.tasks == {1: "idle", 2: "idle"}
    assert report.axes["Z"] == {"fault": 0, "enabled": True, "homed": True}
    assert "Controller health: ok" in report.text()


def test_axis_fault_and_task_error_are_problems(api, transport):
    with_axis_fault(transport)
    transport.world.task(2).state = 8

    report = controller_health(api, check_processes=False)

    assert not report.ok
    assert report.problems == ["task 2 is in the error state", "axis Z has fault 4"]


def test_unreachable_interface(transport):
    api = AerotechAsciiInterface(transport_factory=lambda: transport)  # never connected

    report = controller_health(api, check_processes=False)

    assert not report.ok and not report.ascii_ok and "ASCII interface not usable" in report.problems[0]


def test_recovery_level_r0_moves_nothing(api, transport):
    transport.world.task(1).state = 8
    position = dict(transport.world.stage)

    steps = recover_r0(api)

    assert steps == ["task 1 stopped", "task 2 stopped", "python_aerobasic_program.pgm removed",
                     "faults acknowledged"]
    assert transport.world.task(1).state == 2 and transport.world.stage == position


def test_parse_tasklist_in_any_locale():
    text = ('"A3200CallbackService.exe","7264","Services","0","1.845.120 K"\r\n'
            '"A3200AsciiInterface.exe","7712","Services","0","34,560 K"\r\n'
            'INFO: No tasks are running which match the specified criteria.\r\n')

    rows = parse_tasklist(text)

    assert rows == [{"name": "A3200CallbackService.exe", "pid": 7264, "working_set_gb": 1.76},
                    {"name": "A3200AsciiInterface.exe", "pid": 7712, "working_set_gb": 0.033}]


def test_controller_health_script_dry_run(capsys):
    import importlib.util
    from pathlib import Path

    script = Path(__file__).parents[2] / "mains" / "controller_health.py"
    spec = importlib.util.spec_from_file_location("controller_health", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main(["--dry-run", "--r0"]) == 0
    out = capsys.readouterr().out
    assert "R0: faults acknowledged" in out and "Controller health: ok" in out


def test_recovery_level_r0_removes_the_given_names(api, transport):
    """ T152: R0 removes the execution names the controller still lists and reports each removal. """

    removed = []

    steps = recover_r0(api, tasks=(1,), program_names=("nfs_abc123_0001_layer.pgm",), on_removed=removed.append)

    assert steps == ["task 1 stopped", "nfs_abc123_0001_layer.pgm removed", "faults acknowledged"]
    assert removed == ["nfs_abc123_0001_layer.pgm"]
    assert 'REMOVEPROGRAM "nfs_abc123_0001_layer.pgm"' in transport.world.calllog.commands()
