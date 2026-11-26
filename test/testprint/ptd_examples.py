"""Example values of the test-print tests (not measured; source "example")."""
from nanofactorysystem.testprint.calibration import ProcessCalibration
from nanofactorysystem.testprint.voxel_fit import VoxelFitModel

# Threshold 0.3 mW, w ≈ 0.22 µm and l ≈ 0.68 µm at P_ref = 0.45 mW
EXAMPLE_MODEL = VoxelFitModel("threshold_ln", dict(w_scale_um=0.25, l_scale_um=0.75, p_th_mw=0.3, n_eff=2.0),
                              (0.33, 1.2), 5000.0, source="example")
EXAMPLE_CALIBRATION = ProcessCalibration("SZ2080", "Zeiss 63x", "IFOV_on", 5000.0, p_th_mw=0.3, z0_um=0.4,
                                         voxel_model=EXAMPLE_MODEL, p_dam_mw=1.5, source="example (tests)",
                                         date="2026-11-25")
