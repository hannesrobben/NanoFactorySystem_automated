"""Shared fixtures of the test-print tests (phase 11)."""
import pytest

from ptd_examples import EXAMPLE_CALIBRATION


@pytest.fixture
def example_calibration():
    return EXAMPLE_CALIBRATION


@pytest.fixture
def synthetic_attenuator(tmp_path):
    """ Activate the deterministic attenuator calibration of the simulated world (for SET_POWER values). """

    from nanofactorysystem.backends.dummy.attenuator import write_calibration_file
    from nanofactorysystem.backends.dummy.world import SimulatedWorld
    from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration

    path = write_calibration_file(tmp_path / "attenuator.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(path)):
        yield
