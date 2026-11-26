"""ProcessCalibration with its JSON file (T140)."""
import json
import math

import pytest

from nanofactorysystem.experiment_spec import SpecSerialisationError
from nanofactorysystem.testprint.calibration import ProcessCalibration, as_calibration
from nanofactorysystem.testprint.voxel_fit import VoxelFitModel
from nanofactorysystem.voxel.materials import MissingPropertyError

MODEL = VoxelFitModel("threshold_ln", dict(w_scale_um=0.4, l_scale_um=1.2, p_th_mw=0.3, n_eff=2.0), (0.31, 1.0),
                      5000.0)


def calibration(**overrides):
    arguments = dict(material="SZ2080", objective="Zeiss 63x", setup="IFOV_on", velocity_um_s=5000.0, p_th_mw=0.3,
                     z0_um=0.4, voxel_model=MODEL, p_dam_mw=1.2, plane_fit={"mode": "CORNERS"},
                     polarisation_deg=0.0, source="test", date="2026-11-25")
    arguments.update(overrides)
    return ProcessCalibration(**arguments)


def test_conversions_use_the_voxel_size_at_the_cell_power():
    cal = calibration()
    assert cal.power_mw(1.5) == pytest.approx(0.45)
    assert cal.p_ref_mw == pytest.approx(0.45)
    w = 0.4 * math.sqrt(2 * math.log(0.6 / 0.3))
    l = 1.2 * math.sqrt(2 * math.log(0.6 / 0.3))
    assert cal.hatch_um(0.5, 0.6) == pytest.approx(0.5 * w)
    assert cal.slice_um(0.25, 0.6) == pytest.approx(0.25 * l)
    assert cal.hatch_um(0.5, 0.9) > cal.hatch_um(0.5, 0.6)  # wider voxel at higher power
    assert cal.w0_um == pytest.approx(MODEL.width_um(0.45)) and cal.l0_um == pytest.approx(MODEL.length_um(0.45))
    assert cal.matches("SZ2080", "Zeiss 63x", "IFOV_on") and not cal.matches("IP-Dip", "Zeiss 63x", "IFOV_on")


def test_power_outside_the_model_range_raises():
    with pytest.raises(ValueError, match="no extrapolation"):
        calibration().hatch_um(0.5, 1.5)
    with pytest.raises(ValueError, match="no extrapolation"):
        calibration().slice_um(0.5, 0.2)


def test_json_round_trip(tmp_path):
    cal = calibration()
    again = ProcessCalibration.from_json(json.loads(json.dumps(cal.to_json())))
    assert again == cal
    assert ProcessCalibration.load(cal.save(tmp_path / "calibration.json")) == cal
    assert as_calibration(cal.to_json()) == cal and as_calibration(cal) is cal


def test_missing_values_and_wrong_schema():
    with pytest.raises(MissingPropertyError, match="p_th_mw"):
        calibration(p_th_mw=None)
    with pytest.raises(MissingPropertyError, match="voxel_model"):
        calibration(voxel_model=None)
    data = calibration().to_json()
    del data["voxel_model"]
    with pytest.raises(MissingPropertyError, match="voxel model"):
        ProcessCalibration.from_json(data)
    with pytest.raises(SpecSerialisationError, match="schema"):
        ProcessCalibration.from_json({**calibration().to_json(), "schema": "nanofactory.process_calibration/2"})
    with pytest.raises(SpecSerialisationError, match="Unknown keys"):
        ProcessCalibration.from_json({**calibration().to_json(), "colour": "red"})


def test_inconsistent_values():
    with pytest.raises(ValueError, match="fitted at"):
        calibration(velocity_um_s=10000.0)
    with pytest.raises(ValueError, match="p_dam_mw"):
        calibration(p_dam_mw=0.2)
    assert calibration(source="example values for dry runs").is_example
    assert not calibration().is_example
