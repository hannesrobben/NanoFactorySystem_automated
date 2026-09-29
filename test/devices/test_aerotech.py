"""Tests for the A3200 controller class (devices/a3200.py).

Converted from a script that only logged the stage position of the real
controller: the dummy tests check the generated commands and the parsing of
the responses; the hardware test checks the real controller.
"""
import pytest

from nanofactorysystem import A3200

CONTROLLER_ARGS = {"zMax": 25000.0}


@pytest.fixture
def controller(test_config, dummy_backend):
    """ A3200 connected to the simulated controller. """

    a3200 = A3200("Test", transport=dummy_backend.transport, program_dir=dummy_backend.workdir,
                  controller=dict(CONTROLLER_ARGS), attenuator=dummy_backend.attenuator_args())
    yield a3200
    a3200.close()


def test_connect_sends_reset_and_reads_state(controller, dummy_backend):
    assert controller.opened
    assert dummy_backend.calllog.commands()[:2] == ["ACKNOWLEDGEALL", "~VERSION"]
    assert controller["softwareVersion"] == "4.9.0.0"
    assert (controller["xInit"], controller["yInit"], controller["zInit"]) == (0.0, 0.0, 20000.0)


def test_moveabs_command_and_position_in_um(controller, dummy_backend):
    dummy_backend.calllog.clear()

    controller.moveabs(1000.0, x=1234.5, z=20001.0)

    assert dummy_backend.calllog.commands() == ["ABSOLUTE", "LINEAR X1.234500 Z20.001000 F1.000000"]
    assert controller.position("XYZ") == pytest.approx([1234.5, 0.0, 20001.0])
    assert controller.position("x") == pytest.approx(1234.5)


def test_decimal_comma_positions(test_config, tmp_path):
    from nanofactorysystem.backends import DummyBackend
    backend = DummyBackend(workdir=tmp_path, decimal_comma=True)
    a3200 = A3200("Test", transport=backend.transport, controller=dict(CONTROLLER_ARGS),
                  attenuator=backend.attenuator_args())

    assert a3200.position("Z") == pytest.approx(20000.0)


def test_zmax_safety(controller, dummy_backend):
    with pytest.raises(RuntimeError, match="Maximum z position exceeded"):
        controller.moveabs(1000.0, z=25001.0)
    assert not any(c.startswith("LINEAR") for c in dummy_backend.calllog.commands())


def test_power_sets_attenuator(controller, dummy_backend):
    controller.power(5.0)

    assert dummy_backend.calllog.commands()[-1].startswith("$AO[0].A=")
    assert dummy_backend.world.power == pytest.approx(5.0, rel=1e-3)


def test_zline_task(controller, dummy_backend):
    controller.moveabs(1000.0, z=20000.0)
    controller.zline(2.0, 100.0, 10.0, 10.0)

    commands = dummy_backend.calllog.commands()
    assert "$global[0] = 0.100000" in commands
    assert "$global[2] = 0.010000" in commands
    assert "PROGRAM 1 START" in commands
    assert (dummy_backend.workdir / "__zline__.pgm").is_file()
    exposure, = dummy_backend.world.exposures
    assert exposure.power == pytest.approx(2.0, rel=1e-3)


def test_failed_command_raises_with_last_error(controller, dummy_backend):
    dummy_backend.transport.fail_next(r"^LINEAR", error="Axis X fault")

    with pytest.raises(RuntimeError, match="Axis X fault"):
        controller.moveabs(100.0, x=1.0)


def test_container(controller):
    dc = controller.container()

    assert dc["data/controller.json"]["zMax"] == CONTROLLER_ARGS["zMax"]


@pytest.mark.hardware
def test_real_controller_position(lab_user):
    with A3200(lab_user, controller=dict(CONTROLLER_ARGS), attenuator={"fitKind": "quadratic"}) as controller:
        assert controller.opened
        x, y, z = controller.position("XYZ")
        assert all(isinstance(v, float) for v in (x, y, z))
        assert z <= controller["zMax"]
        assert controller["softwareVersion"]


def test_home_default_and_selected_axes(controller, dummy_backend):
    dummy_backend.calllog.clear()

    controller.home()
    controller.home("z")

    assert dummy_backend.calllog.commands() == ["HOME X", "HOME Y", "HOME Z", "HOME Z"]


def test_container_with_registered_task(controller):
    controller.init_zline()

    dc = controller.container()

    assert "LINEAR Z $dz F $slow" in dc["data/zline.pgm"]


def test_moveinc_and_zline_before_absolute_z_move(controller, dummy_backend):
    controller.moveinc(1000.0, z=10.0)
    assert dummy_backend.world.stage["Z"] == pytest.approx(20.010)

    with pytest.raises(RuntimeError, match="Maximum z position exceeded"):
        controller.moveinc(1000.0, z=5000.0)


def test_zline_before_absolute_z_move(test_config, dummy_backend):
    a3200 = A3200("Test", transport=dummy_backend.transport, program_dir=dummy_backend.workdir,
                  controller=dict(CONTROLLER_ARGS), attenuator=dummy_backend.attenuator_args())

    a3200.zline(1.0, 100.0, 10.0, 10.0)

    assert len(dummy_backend.world.exposures) == 1
