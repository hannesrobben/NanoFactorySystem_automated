"""Test of the interactive DHM helper test/manual/dhm/DHMUserBackend.py on the dummy DHM (T39)."""
import importlib.util
from pathlib import Path

import pytest

HELPER = Path(__file__).parents[1] / "manual" / "dhm" / "DHMUserBackend.py"


@pytest.fixture
def helper_module(test_config, dummy_backend, no_sleep):
    """ The helper module with its Dhm class bound to the simulated DHM of ``dummy_backend``. """

    spec = importlib.util.spec_from_file_location("dhm_user_backend", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    real_dhm = module.Dhm
    clients = []

    def dummy_dhm(user, objective, logger=None, **kwargs):
        driver = dummy_backend.dhm_driver(objective)
        clients.append(driver)
        return real_dhm(user, objective, logger, driver=driver, **kwargs)

    module.Dhm = dummy_dhm
    module.clients = clients
    return module


def test_reset_restores_the_initial_state(helper_module, tmp_path):
    helper = helper_module.DHMBackend(objective="Zeiss 20x", user="Test", save_path=str(tmp_path / "out"))
    first = helper.client
    helper.motor_pos, helper.opl_scan_done, helper.continuous_saving_variable = 555.0, True, 7

    helper.reset()

    assert not helper_module.clients[0].opened  # the old connection is closed
    assert helper.client is not None and helper.client is not first
    assert (helper.motor_pos, helper.opl_scan_done, helper.continuous_saving_variable) == (100.0, False, 0)
    assert helper.objective_name == "Zeiss 20x"

    helper.reset(reconnect=False)
    assert helper.client is None and not helper_module.clients[1].opened


def test_reset_keeps_a_given_start_position(helper_module, tmp_path):
    helper = helper_module.DHMBackend(objective="Zeiss 63x", user="Test", motor_pos=190.0,
                                      save_path=str(tmp_path / "out"))
    helper.motor_pos = 1234.0

    helper.reset(reconnect=False)

    assert helper.motor_pos == 190.0
    with pytest.raises(NotImplementedError):
        helper_module.DHMBackend.default_motor_pos("Unknown 5x")
