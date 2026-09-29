"""Tests for the merged controller (T20): one A3200 object for helpers and program tasks, zMax guard on .api."""
import pytest

from nanofactorysystem import A3200
from nanofactorysystem.aerobasic import SingleAxis
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, AerotechError, TaskFailedError
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
from nanofactorysystem.config import use_config
from nanofactorysystem.devices.aerotech import Aerotech3200, AerotechController


def test_system_uses_one_controller_object(dummy_system):
    assert dummy_system.a3200_new is dummy_system.controller
    assert isinstance(dummy_system.controller, A3200)
    assert isinstance(dummy_system.controller, AerotechController)
    assert dummy_system.controller.socket is dummy_system.controller.api.socket


def test_a3200_runs_program_tasks(dummy_system, dummy_backend):
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")

    task = dummy_system.controller.run_program_as_task(program, task_id=2)
    task.wait_to_finish()

    assert dummy_system.controller.xyz.X == pytest.approx(1.0)
    assert (dummy_backend.workdir / "python_aerobasic_program.pgm").is_file()


def test_z_limit_guards_immediate_api_moves(dummy_system, dummy_backend):
    api = dummy_system.controller.api
    z_max_mm = dummy_system.controller["zMax"] / 1000
    dummy_backend.calllog.clear()

    for move in (lambda: api.LINEAR(Z=z_max_mm + 0.001, F=1),
                 lambda: api.RAPID(X=0.0, Z=z_max_mm + 1),
                 lambda: api.MOVEABS(SingleAxis.Z, z_max_mm + 1, 1),
                 lambda: api.send(f"LINEAR X0 Z{z_max_mm + 0.5} F1")):
        with pytest.raises(AerotechError, match="exceeds the maximum z position"):
            move()
    assert dummy_backend.calllog.commands() == []  # nothing was sent

    api.LINEAR(Z=z_max_mm - 0.001, F=1)  # below the limit
    api.INCREMENTAL()
    api.LINEAR(Z=0.001, F=1)  # incremental moves are not checked
    api.ABSOLUTE()
    assert dummy_backend.world.stage["Z"] == pytest.approx(z_max_mm)


def test_legacy_helper_zmax_check_is_unchanged(test_config, dummy_backend):
    controller = A3200("Test", transport=dummy_backend.transport, controller={"zMax": 25000.0},
                       attenuator=dummy_backend.attenuator_args())

    with pytest.raises(RuntimeError, match="Maximum z position exceeded"):
        controller.moveabs(1000.0, z=25001.0)
    assert controller.opened is False  # the helper closes the connection, as before


def test_aerotech3200_without_config_and_with_optional_limit():
    world = SimulatedWorld()
    transport = FakeA3200Transport(world)
    with use_config({}):
        controller = Aerotech3200(transport_factory=lambda: transport, z_max=21000.0)
    controller.connect()

    controller.api.LINEAR(Z=20.5, F=1)
    with pytest.raises(AerotechError):
        controller.api.LINEAR(Z=21.5, F=1)
    assert Aerotech3200(transport_factory=lambda: transport).api.z_limit is None


def test_error_types():
    assert issubclass(AerotechError, RuntimeError)
    assert issubclass(TaskFailedError, AerotechError) and issubclass(TaskFailedError, ValueError)


def test_failed_connect_leaves_interface_closed():
    api = AerotechAsciiInterface(transport_factory=lambda: FakeA3200Transport(SimulatedWorld(),
                                                                              refuse_connection=True))
    with pytest.raises(ConnectionRefusedError):
        api.connect()

    assert not api.is_opened


def test_a3200_with_refused_connection(test_config, tmp_path):
    from nanofactorysystem.backends import DummyBackend
    backend = DummyBackend(workdir=tmp_path)
    backend.transport.refuse_connection = True

    controller = A3200("Test", transport=backend.transport, controller={"zMax": 25000.0},
                       attenuator=backend.attenuator_args())

    assert controller.opened is False
    with pytest.raises(RuntimeError, match="Not connected"):
        controller.run("~VERSION")
