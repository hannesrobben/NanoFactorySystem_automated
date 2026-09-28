"""Tests for the simulated A3200 controller (FakeA3200Transport)."""
import pytest

from nanofactorysystem.aerobasic import AxisStatusDataItem, SingleAxis
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
from nanofactorysystem.devices.aerotech import Aerotech3200


@pytest.fixture
def world():
    return SimulatedWorld(seed=0)


@pytest.fixture
def no_sleep(monkeypatch, world):
    """ Replace time.sleep by the virtual clock, so polling loops are instant. """

    import time
    monkeypatch.setattr(time, "sleep", world.clock.sleep)


@pytest.fixture
def transport(world):
    return FakeA3200Transport(world)


@pytest.fixture
def api(transport):
    api = AerotechAsciiInterface(transport_factory=lambda: transport)
    api.connect()
    return api


def test_frames_are_protocol_correct(transport):
    transport.connect(("127.0.0.1", 8000))
    transport.send(b"~VERSION\n")

    assert transport.recv(4096) == b"%4.9.0.0\n"


def test_recv_without_pending_response_raises(transport):
    with pytest.raises(RuntimeError, match="without pending response"):
        transport.recv(4096)


def test_refused_connection(world):
    transport = FakeA3200Transport(world, refuse_connection=True)
    api = AerotechAsciiInterface(transport_factory=lambda: transport)

    with pytest.raises(ConnectionRefusedError):
        api.connect()


def test_linear_moves_update_position(api, world):
    api.ABSOLUTE()
    api.LINEAR(X=1.5, Y=-2.0, F=10)
    api.INCREMENTAL()
    api.LINEAR(X=0.5, F=10)

    assert world.stage["X"] == pytest.approx(2.0)
    assert world.stage["Y"] == pytest.approx(-2.0)
    assert float(api.AXISSTATUS(SingleAxis.X, AxisStatusDataItem.PositionFeedback)) == pytest.approx(2.0)


def test_status_query_and_xyz(transport, world):
    world.stage.update(X=1.0, Y=2.0, Z=3.0)
    a3200 = Aerotech3200(transport_factory=lambda: transport)
    a3200.connect()

    point = a3200.xyz

    assert (point.X, point.Y, point.Z) == (1.0, 2.0, 3.0)


def test_decimal_comma_is_parsed_by_clients(world):
    transport = FakeA3200Transport(world, decimal_comma=True)
    world.stage["X"] = 1.25
    a3200 = Aerotech3200(transport_factory=lambda: transport)
    a3200.connect()

    assert transport.execute("AXISSTATUS(X, DATAITEM_PositionFeedback)") == "1,250000"
    assert a3200.xyz.X == 1.25


def test_laser_power_and_exposure(api, world):
    api.send("$AO[0].A=5.0")
    api.ABSOLUTE()
    api.send("GALVO LASEROVERRIDE A ON")
    api.LINEAR(X=0.1, F=1)
    api.send("GALVO LASEROVERRIDE A OFF")
    api.LINEAR(X=0.2, F=1)

    assert world.power == pytest.approx(world.max_power * 0.25)
    assert len(world.exposures) == 1
    assert world.exposures[0].end[0] == pytest.approx(0.1)


def test_unknown_command_lenient_and_strict(world):
    lenient = FakeA3200Transport(world)
    api = AerotechAsciiInterface(transport_factory=lambda: lenient)
    api.connect()
    api.send("FOOBAR 1")
    assert lenient.unhandled == ["FOOBAR 1"]

    strict = FakeA3200Transport(world, strict=True)
    api = AerotechAsciiInterface(transport_factory=lambda: strict)
    api.connect()
    with pytest.raises(AerotechError, match="invalid syntax"):
        api.send("FOOBAR 1")


def test_fault_injection_and_last_error(api, transport):
    transport.fail_next(r"^LINEAR", error="Axis fault X")

    with pytest.raises(AerotechError, match="Axis fault X"):
        api.LINEAR(X=1.0, F=1)
    api.LINEAR(X=1.0, F=1)  # only the next command fails


def test_response_override(api, transport):
    transport.respond(r"^~VERSION$", "1.2.3.4")

    assert api.send("~VERSION") == "1.2.3.4"


def test_program_task_runs_and_records_exposure(tmp_path, transport, world):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    program = AeroBasicProgram()
    program.send("DVAR $dz")
    program.send("$dz = 0.02")
    program.send("INCREMENTAL")
    program.send("GALVO LASEROVERRIDE A ON")
    program.send("LINEAR Z $dz F 0.1")
    program.send("GALVO LASEROVERRIDE A OFF")
    program.send("ABSOLUTE")

    task = a3200.run_program_as_task(program, task_id=2)
    task.wait_to_finish()
    task.finish()

    assert task.task_state == TaskState.idle
    assert len(world.exposures) == 1
    assert world.exposures[0].end[2] - world.exposures[0].start[2] == pytest.approx(0.02)
    assert (tmp_path / "python_aerobasic_program.pgm").is_file()
    runs = world.calllog.filter(device="program")
    assert runs[0].result["not_simulated"] == 0


def test_loading_missing_program_fails(api):
    with pytest.raises(AerotechError, match="Program file not found"):
        api.PROGRAM_LOAD(1, "does_not_exist.pgm")


def test_program_error_while_running(tmp_path, transport, world, no_sleep):
    """ A task error surfaces as ValueError from Task.wait_to_finish (current behaviour, see T10). """

    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    transport.program_error_next(error_code=42, running_polls=2)
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    task = a3200.run_program_as_task(program, task_id=1)
    assert task.task_state == TaskState.program_running

    with pytest.raises(ValueError, match="42"):
        task.wait_to_finish()
    assert task.task_state == TaskState.error


def test_program_error_before_start(tmp_path, transport, world, no_sleep):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    transport.program_error_next(error_code=7, running_polls=0)
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    with pytest.raises(RuntimeError, match="Program did not start"):
        a3200.run_program_as_task(program, task_id=1, program_start_running_timeout=1)


def test_call_log_records_commands_and_responses(api, world):
    api.ABSOLUTE()
    api.LINEAR(X=1.0, F=2)

    assert world.calllog.commands() == ["ABSOLUTE", "LINEAR X1.0000000000 F2.000000"]
    assert world.calllog[1].result == "%"
    assert world.clock.now == pytest.approx(0.5)


def test_deprecated_dummy_flag_answers_queries():
    a3200 = Aerotech3200(dummy=True)

    assert a3200.xyz.Z == 20.0
    assert a3200.version.major == "4"
