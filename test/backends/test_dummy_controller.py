"""Tests for the simulated A3200 controller (FakeA3200Transport)."""
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic import AxisStatusDataItem, SingleAxis
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError, TaskFailedError
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
    # T152: the execution copy is deleted once the program has been removed
    assert a3200.exec_programs == {} and list(tmp_path.glob("nfs_*.pgm")) == []
    runs = world.calllog.filter(device="program")
    assert runs[0].result["not_simulated"] == 0


def test_loading_missing_program_fails(api):
    with pytest.raises(AerotechError, match="Program file not found"):
        api.PROGRAM_LOAD(1, "does_not_exist.pgm")


def test_program_error_while_running(tmp_path, transport, world, no_sleep):
    """ A task error surfaces as TaskFailedError (an AerotechError and a ValueError). """

    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    transport.program_error_next(error_code=42, running_polls=2)
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    task = a3200.run_program_as_task(program, task_id=1)
    assert task.task_state == TaskState.program_running

    with pytest.raises(TaskFailedError, match="42"):
        task.wait_to_finish()
    assert task.task_state == TaskState.error


def test_task_error_keeps_code_and_axis_faults_when_errordecode_is_refused(tmp_path, transport, world, no_sleep):
    # Lab 2026-11-28 (T169): the real ASCII interface refuses ERRORDECODE, so the message showed only
    # "Compiler Error" of that refused command; the task error code and the axis fault must still be reported,
    # read before R0 acknowledges the fault
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    transport.program_error_next(error_code=51, error_location=5, running_polls=2)
    transport.fail_next(r"ERRORDECODE", code="INVALID", error="Compiler Error: The program failed to compile.")
    original = transport._axis_item
    transport._axis_item = lambda axis, item: "1" if (axis, item) == ("X", "AxisFault") else original(axis, item)
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    task = a3200.run_program_as_task(program, task_id=1)
    with pytest.raises(TaskFailedError) as error:
        task.wait_to_finish()

    message = str(error.value)
    assert "task error 51 at location 5" in message
    assert "ERRORDECODE not available" in message
    assert "axis faults: X PositionError" in message


def test_program_error_before_start(tmp_path, transport, world, no_sleep):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    transport.program_error_next(error_code=7, running_polls=0)
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    # The task is in error right after START: reported as TaskFailedError with the task state and the decoded
    # error code (T128), and the task is cleaned up
    with pytest.raises(TaskFailedError, match=r"did not start .*\(task state error\): 7: Simulated error 7"):
        a3200.run_program_as_task(program, task_id=1, program_start_running_timeout=1)
    assert transport.loaded_programs == {} and TaskState(world.task(1).state) == TaskState.idle


def test_program_is_removed_under_its_loaded_name(tmp_path, transport, world):
    # T127: the program is loaded under its execution name, so it must be removed under that name
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    layer = tmp_path / "program_rect.000.txt"
    layer.write_text("LINEAR X1 F1\n")

    task = a3200.run_program_as_task(layer, task_id=1)
    name = f"nfs_{a3200.exec_session}_0001_program_rect.000.pgm"
    assert task.program_name == name and set(transport.loaded_programs) == {name.lower()}
    task.wait_to_finish()
    task.finish()

    assert transport.loaded_programs == {} and transport.unknown_removals == []
    assert f'REMOVEPROGRAM "{name}"' in world.calllog.commands()


def test_early_complete_is_a_failure(tmp_path, transport, world, no_sleep):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    program = AeroBasicProgram()
    for i in range(10):
        program.send(f"LINEAR X{i} F1")
    transport.program_incomplete_next(4)

    task = a3200.run_program_as_task(program, task_id=1)
    with pytest.raises(TaskFailedError, match=r"ended early: task 1 reported complete at line 4 of 1\d"):
        task.wait_to_finish()


def test_trailing_empty_lines_do_not_count_as_early_end(tmp_path, transport, world):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    path = tmp_path / "layer.pgm"
    path.write_text("LINEAR X1 F1\nEND PROGRAM\n\n\n")
    transport.program_incomplete_next(2)  # the controller reports the END PROGRAM line

    task = a3200.run_program_as_task(path, task_id=1)
    task.wait_to_finish()
    task.finish()


def test_refused_load_reports_the_controller_reason_and_cleans_up(tmp_path, transport, world):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    transport.fail_next(r"PROGRAM 1 LOAD", code="INVALID", error="An out of memory error occurred.")
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    with pytest.raises(AerotechError, match=r"Could not load program .* on task 1: .*out of memory"):
        a3200.run_program_as_task(program, task_id=1)
    commands = world.calllog.commands()
    name = Path(next(c for c in commands if c.startswith("PROGRAM 1 LOAD")).split('"')[1]).name
    stop, remove = commands.index("PROGRAM 1 STOP"), commands.index(f'REMOVEPROGRAM "{name}"')
    assert stop < remove and "PROGRAM 1 START" not in commands
    assert a3200.exec_programs == {} and not (tmp_path / name).exists()  # the execution copy is cleaned up


def test_load_without_reply_times_out_and_reconnects(tmp_path, transport, world):
    # 2026-11-24: a PROGRAM LOAD over ASCII got no reply within 600 s
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    a3200.api.load_timeout = 5.0
    transport.hang_next(r"PROGRAM 1 LOAD")
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    with pytest.raises(AerotechError, match=r"No reply to 'PROGRAM 1 LOAD .*' within 5.0 s"):
        a3200.run_program_as_task(program, task_id=1)

    # The connection was reopened and works; the response timeout is back to "no limit"
    assert a3200.api.VERSION().major == "4"
    assert transport.timeout is None


def test_failed_removal_does_not_raise(tmp_path, transport, world):
    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")
    task = a3200.run_program_as_task(program, task_id=1)
    task.wait_to_finish()
    transport.fail_next(r"^REMOVEPROGRAM", error="Program is not loaded")

    task.finish()  # logged, not raised

    assert task.task_state == TaskState.idle


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


def test_send_one_falls_back_without_recursion(api, transport):
    assert api.send_one("~VERSION") == "4.9.0.0"

    transport.fail_next(r"^ABSOLUTE$")
    assert api.send_one("ABSOLUTE") == ""  # retried with the fallback


def test_exec_program_name():
    from nanofactorysystem.devices.aerotech import exec_program_name

    assert exec_program_name("a1b2c3", 7, "program_surface_16bit.068") == "nfs_a1b2c3_0007_program_surface_16bit.068.pgm"
    assert exec_program_name("a1b2c3", 1, "layer 1/ä") == "nfs_a1b2c3_0001_layer_1__.pgm"
    assert len(exec_program_name("a1b2c3", 12345, "x" * 200)) == len("nfs_a1b2c3_12345_.pgm") + 60


def test_every_load_gets_a_fresh_name(tmp_path, transport, world):
    """ T152: two loads of the same file use two names; each copy is deleted after its removal. """

    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    layer = tmp_path / "layer.pgm"
    layer.write_text("LINEAR X1 F1\n")

    names = []
    for _ in range(2):
        task = a3200.run_program_as_task(layer, task_id=1)
        names.append(task.program_name)
        task.wait_to_finish()
        task.finish()

    assert names[0] != names[1] and all(name.startswith(f"nfs_{a3200.exec_session}_") for name in names)
    assert a3200.exec_programs == {} and sorted(p.name for p in tmp_path.iterdir()) == ["layer.pgm"]
    assert Aerotech3200(transport_factory=lambda: transport).exec_session != a3200.exec_session


def test_refused_load_blocks_only_its_name(tmp_path, transport, world):
    """ T152: like the real controller (lab session 2), a refused LOAD blocks its name, not the next program. """

    a3200 = Aerotech3200(transport_factory=lambda: transport, program_dir=tmp_path)
    a3200.connect()
    layer = tmp_path / "layer.pgm"
    layer.write_text("LINEAR X1 F1\n")
    transport.fail_next(r"PROGRAM 1 LOAD", code="INVALID", error="An out of memory error occurred.")

    with pytest.raises(AerotechError, match="out of memory"):
        a3200.run_program_as_task(layer, task_id=1)
    blocked, = transport.blocked_programs

    # The same content loads under the next name and runs
    task = a3200.run_program_as_task(layer, task_id=1)
    task.wait_to_finish()
    task.finish()
    assert task.program_name.lower() != blocked and world.stage["X"] == pytest.approx(1.0)

    # The blocked name itself stays refused, also with valid content
    (tmp_path / blocked).write_text("LINEAR X2 F1\n")
    with pytest.raises(AerotechError, match="failed to compile"):
        a3200.api.PROGRAM_LOAD(1, tmp_path / blocked)
