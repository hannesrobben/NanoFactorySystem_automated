"""Tests for System on the dummy backend and for the backend switch."""
import socket

import pytest

import nanofactorysystem.devices.a3200 as a3200_module
import nanofactorysystem.devices.camera as camera_module
import nanofactorysystem.devices.dhm as dhm_module
from nanofactorysystem import System
from nanofactorysystem.backends import DummyBackend, RealBackend, protocols, resolve_backend
from nanofactorysystem.backends.dummy import DummyCameraDriver, DummyDhmClient, FakeA3200Transport



def sys_args():
    """ Fresh runtime arguments; Parameter pops keys from the caller's dicts. """

    return {"controller": {"zMax": 25000.0}}

STARTUP_COMMANDS = [
    "ACKNOWLEDGEALL",
    "~VERSION",
    "AXISSTATUS(X, DATAITEM_PositionFeedback)",
    "AXISSTATUS(Y, DATAITEM_PositionFeedback)",
    "AXISSTATUS(Z, DATAITEM_PositionFeedback)",
    "PROGRAM 1 STOP",
    # PROGRAM 1 LOAD "<program_dir>/__zline__.pgm" is checked separately
    "ABSOLUTE",
    "LINEAR A0.000000 B0.000000 F0.100000",
    "AXISSTATUS(X, DATAITEM_PositionFeedback)",
    "AXISSTATUS(Y, DATAITEM_PositionFeedback)",
    "AXISSTATUS(Z, DATAITEM_PositionFeedback)",
]


def _without_load(commands):
    return [c for c in commands if not c.startswith("PROGRAM 1 LOAD")]


def test_resolve_backend():
    assert isinstance(resolve_backend(None), RealBackend)
    assert isinstance(resolve_backend("real"), RealBackend)
    assert isinstance(resolve_backend("dummy"), DummyBackend)
    backend = DummyBackend()
    assert resolve_backend(backend) is backend
    with pytest.raises(ValueError, match="Unknown backend"):
        resolve_backend("simulated")


def test_system_startup_on_dummy_backend(test_config, backend, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with System("Test", "Zeiss 20x", backend=backend, **sys_args()) as system:
        assert system.backend is backend
        commands = backend.calllog.commands()
        assert _without_load(commands) == STARTUP_COMMANDS
        load = [c for c in commands if c.startswith("PROGRAM 1 LOAD")]
        assert load == [f'PROGRAM 1 LOAD "{backend.workdir / "__zline__.pgm"}"']
        assert system.dhm.device.Config == 178

    # Nothing is written to the working directory; logs and programs go to the backend workdir
    assert [p.name for p in tmp_path.iterdir()] == ["dummy"]
    assert (backend.workdir / "A3200.log").is_file()
    assert backend.transport.unhandled == []


def test_system_roles(test_config, backend):
    with System("Test", "Zeiss 20x", backend=backend, **sys_args()) as system:
        assert isinstance(system.controller, protocols.LegacyMotionController)
        assert isinstance(system.a3200_new, protocols.TaskController)
        assert isinstance(system.controller.attenuator, protocols.AttenuatorRole)
        assert isinstance(system.camera, protocols.CameraRole)
        assert isinstance(system.dhm, protocols.DhmRole)


def test_system_motion_zline_and_laser_state(test_config, backend):
    world = backend.world
    with System("Test", "Zeiss 20x", backend=backend, **sys_args()) as system:
        system.moveabs(x=100.0, y=50.0, z=20010.0)
        assert system.position("XYZ") == pytest.approx([100.0, 50.0, 20010.0])

        system.zline(1.0, 100.0, 10.0, 20.0)

    assert len(world.exposures) == 1
    exposure = world.exposures[0]
    assert exposure.start == pytest.approx((0.1, 0.05, 20.0))
    assert exposure.end == pytest.approx((0.1, 0.05, 20.02))
    assert exposure.power == pytest.approx(1.0, rel=1e-3)
    assert world.laser_on is False
    assert world.tasks[1].state == 7  # program_complete


def test_system_without_dhm(test_config, backend):
    with System("Test", "Zeiss 20x", backend=backend, dhm={"usage": False}, **sys_args()) as system:
        assert system.dhm is None
    assert not backend.calllog.filter(device="dhm")


def test_same_seed_gives_identical_runs(test_config, tmp_path):
    def run(seed, name):
        backend = DummyBackend(seed=seed, workdir=tmp_path / name)
        with System("Test", "Zeiss 20x", backend=backend, **sys_args()) as system:
            system.moveabs(z=20010.0)
            system.zline(1.0, 100.0, 10.0, 20.0)
            image = system.camera.getimage()
        records = [(r.device, r.call.replace(str(backend.workdir), "<workdir>"), r.args, r.result, r.t)
                   for r in backend.calllog]
        return records, image

    records_a, image_a = run(5, "a")
    records_b, image_b = run(5, "b")
    _, image_c = run(6, "c")

    assert records_a == records_b
    assert (image_a == image_b).all()
    assert not (image_a == image_c).all()


def test_real_backend_constructs_the_same_objects(test_config, tmp_path, monkeypatch):
    """ With the default backend, System opens the hardware exactly as before.

    The hardware constructors are patched to return simulated devices; the
    recorded construction arguments and commands must match the dummy backend.
    """

    monkeypatch.chdir(tmp_path)
    backend = DummyBackend(seed=0, workdir=tmp_path / "dummy")
    world = backend.world
    calls = {}

    def fake_socket(*args):
        calls["socket"] = args
        return FakeA3200Transport(world)

    def fake_camera_device(product, device_id):
        calls["camera"] = (product, device_id)
        return DummyCameraDriver(world)

    def fake_dhm_client(host, port):
        calls["dhm"] = (host, port)
        return DummyDhmClient(world, config_id=178)

    monkeypatch.setattr(a3200_module.socket, "socket", fake_socket)
    monkeypatch.setattr(camera_module, "CameraDevice", fake_camera_device)
    monkeypatch.setattr(dhm_module, "DhmClient", fake_dhm_client)
    calibration = backend.attenuator_args()

    with System("Test", "Zeiss 20x", attenuator=calibration, **sys_args()) as system:
        assert isinstance(system.backend, RealBackend)

    assert calls == {
        "socket": (socket.AF_INET, socket.SOCK_STREAM),
        "camera": (None, None),
        "dhm": ("192.168.22.2", 27182),
    }
    commands = world.calllog.commands()
    assert _without_load(commands)[:len(STARTUP_COMMANDS)] == STARTUP_COMMANDS
    assert f'PROGRAM 1 LOAD "{tmp_path / "__zline__.pgm"}"' in commands  # current working directory, as before
    assert (tmp_path / "A3200.log").is_file()
