"""Shared fixtures of the test-print tests (phase 11)."""
import pytest

from nanofactorysystem.testprint.calibration import ProcessCalibration, StageAAxes
from nanofactorysystem.testprint.voxel_fit import VoxelFitModel

# Example values (not measured): threshold 0.3 mW, w ≈ 0.22 µm and l ≈ 0.68 µm at P_ref = 0.45 mW
EXAMPLE_MODEL = VoxelFitModel("threshold_ln", dict(w_scale_um=0.25, l_scale_um=0.75, p_th_mw=0.3, n_eff=2.0),
                              (0.33, 1.2), 5000.0, source="example")
EXAMPLE_CALIBRATION = ProcessCalibration("SZ2080", "Zeiss 63x", "IFOV_on", 5000.0, p_th_mw=0.3, z0_um=0.4,
                                         voxel_model=EXAMPLE_MODEL, p_dam_mw=1.5, source="example (tests)",
                                         date="2026-11-25")
EXAMPLE_STAGE_A = StageAAxes("SZ2080", p_min_mw=0.1, p_max_mw=1.0, label_power_mw=0.7, source="example (tests)")


@pytest.fixture
def example_calibration() -> ProcessCalibration:
    return EXAMPLE_CALIBRATION


@pytest.fixture
def example_stage_a() -> StageAAxes:
    return EXAMPLE_STAGE_A


@pytest.fixture
def synthetic_attenuator(tmp_path):
    """ Activate the deterministic attenuator calibration of the simulated world (for SET_POWER values). """

    from nanofactorysystem.backends.dummy.attenuator import write_calibration_file
    from nanofactorysystem.backends.dummy.world import SimulatedWorld
    from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration

    path = write_calibration_file(tmp_path / "attenuator.dat", SimulatedWorld())
    with power_calibration(PowerCalibration.from_file(path)):
        yield
