"""Timeouts and bounded waiting in the controller and DHM communication (T13)."""
import struct
import time

import pytest

import nanofactorysystem.dhm.dhmclient as dhmclient_module
from nanofactorysystem import A3200
from nanofactorysystem.aerobasic.ascii import AerotechAsciiInterface, TaskFailedError, recv_line
from nanofactorysystem.aerobasic.constants.tasks import TaskState
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.backends.dummy import FakeA3200Transport, SimulatedWorld
from nanofactorysystem.devices.aerotech import Aerotech3200
from nanofactorysystem.dhm.commands import C_GetVersion


def make_a3200(backend, **controller):
    return A3200("Test", transport=backend.transport, program_dir=backend.workdir,
                 controller={"zMax": 25000.0} | controller, attenuator=backend.attenuator_args())


def test_a3200_sets_connect_and_response_timeouts(test_config, dummy_backend):
    make_a3200(dummy_backend, connectTimeout=3.0, responseTimeout=60.0)

    assert dummy_backend.transport.timeouts == [3.0, 60.0]


def test_ascii_interface_sets_timeouts(dummy_backend):
    api = AerotechAsciiInterface(transport_factory=lambda: dummy_backend.transport, connect_timeout=2.0)
    api.connect()

    assert dummy_backend.transport.timeouts == [2.0, None]  # no response limit by default


@pytest.mark.parametrize("chunk_size", [1, 3])
def test_responses_split_into_chunks(test_config, tmp_path, chunk_size):
    world = SimulatedWorld()
    transport = FakeA3200Transport(world, chunk_size=chunk_size)
    api = AerotechAsciiInterface(transport_factory=lambda: transport)
    api.connect()
    world.stage["X"] = 1.25

    assert api.send("~VERSION") == "4.9.0.0"
    assert float(api.send("AXISSTATUS(X, DATAITEM_PositionFeedback)")) == 1.25

    from nanofactorysystem.backends import DummyBackend
    backend = DummyBackend(workdir=tmp_path)
    backend.transport.chunk_size = chunk_size
    a3200 = make_a3200(backend)
    assert a3200.position("Z") == pytest.approx(20000.0)


def test_closed_connection_raises():
    class Closed:
        def recv(self, bufsize):
            return b""

    with pytest.raises(ConnectionError, match="Connection closed"):
        recv_line(Closed())


def test_failed_command_with_unterminated_last_error_request(test_config, dummy_backend):
    a3200 = make_a3200(dummy_backend)
    dummy_backend.transport.fail_next(r"^LINEAR", error="Axis fault")

    with pytest.raises(RuntimeError, match="Axis fault"):
        a3200.moveabs(100.0, x=1.0)
    assert "~LASTERROR" in dummy_backend.calllog.commands()


def test_wait_for_axes_is_bounded(test_config, dummy_backend):
    a3200 = make_a3200(dummy_backend, waitTimeout=0.2)
    dummy_backend.transport.respond(r"DATAITEM_DriveStatus", "0")  # never in position

    t0 = time.monotonic()
    with pytest.raises(TimeoutError, match="not in position"):
        a3200.wait("XY")
    assert time.monotonic() - t0 < 5


def test_zline_is_bounded(test_config, dummy_backend):
    a3200 = make_a3200(dummy_backend, zlineTimeout=0.2)
    a3200.moveabs(1000.0, z=20000.0)
    dummy_backend.transport.running_polls = 10 ** 9  # the program never ends

    with pytest.raises(TimeoutError, match="z-line program still running"):
        a3200.zline(1.0, 100.0, 10.0, 10.0)


@pytest.fixture
def controller(dummy_backend, tmp_path, no_sleep):
    a3200 = Aerotech3200(transport_factory=lambda: dummy_backend.transport, program_dir=tmp_path)
    a3200.connect()
    return a3200


def test_stalled_task_raises(controller, dummy_backend):
    dummy_backend.transport.running_polls = 10 ** 9
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")
    task = controller.run_program_as_task(program, task_id=1)

    with pytest.raises(TaskFailedError, match="made no progress for 5.0 s"):
        task.wait_to_finish(stall_timeout=5.0)
    assert dummy_backend.world.clock.now >= 5.0  # waited on the virtual clock only


def test_finish_is_bounded(controller, dummy_backend):
    program = AeroBasicProgram()
    program.send("LINEAR X1 F1")
    task = controller.run_program_as_task(program, task_id=1)
    task.wait_to_finish()
    # The task never becomes idle after PROGRAM STOP
    dummy_backend.transport.respond(r"^~STATUS \(1, TaskMode\)", "2 4 0 0 0 1")

    with pytest.raises(TaskFailedError, match="not idle"):
        task.finish(timeout=1.0)
    assert task.task_state == TaskState.program_running


def test_dhm_client_connect_timeout(monkeypatch):
    calls = []

    class FakeSocket:
        def __init__(self, *args):
            self._out = b""

        def settimeout(self, value):
            calls.append(("settimeout", value))

        def connect(self, address):
            calls.append(("connect", address))

        def sendall(self, data):
            cmd = struct.unpack("i", data[:4])[0]
            assert cmd == C_GetVersion
            self._out += struct.pack("ii", cmd, 3)

        def recv(self, size):
            data, self._out = self._out[:size], self._out[size:]
            return data

    monkeypatch.setattr(dhmclient_module.socket, "socket", FakeSocket)

    dhmclient_module.DhmClient("192.0.2.1", 27182, timeout=4.0)

    assert calls == [("settimeout", 4.0), ("connect", ("192.0.2.1", 27182)), ("settimeout", None)]
