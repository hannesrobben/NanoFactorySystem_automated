"""Fit procedure of the voxel model from PTD measurements (T151)."""
import json
import math

import numpy as np
import pytest

from experiment_analysis.voxel_fit import (VoxelPoints, choose, fit_all, fit_power_law, fit_threshold_ln,
                                           plot_fit, points_from_rows, store_fit, write_calibration)
from nanofactorysystem.testprint.calibration import ProcessCalibration
from nanofactorysystem.voxel.materials import MissingPropertyError

TRUE = dict(p_th_mw=0.3, n_eff=2.5, w_scale_um=0.25, l_scale_um=0.75)


def synthetic_threshold(noise=0.02, seed=20261125, repeats=4):
    rng = np.random.default_rng(seed)
    power = np.repeat(np.geomspace(0.33, 1.0, 12), repeats)
    term = np.sqrt(TRUE["n_eff"] * np.log(power / TRUE["p_th_mw"]))
    w, l = TRUE["w_scale_um"] * term, TRUE["l_scale_um"] * term
    w_std, l_std = noise * w, noise * l
    return VoxelPoints(power, w + rng.normal(0, w_std), l + rng.normal(0, l_std), w_std, l_std)


def test_threshold_fit_recovers_p_th_and_n_eff_within_the_uncertainty():
    fit = fit_threshold_ln(synthetic_threshold(), 5000.0, w_scale_um=TRUE["w_scale_um"],
                           l_scale_um=TRUE["l_scale_um"])
    assert fit.n_eff_fitted
    for name in ("p_th_mw", "n_eff"):
        error = fit.uncertainties[name]
        assert 0 < error < 0.05 * TRUE[name]
        assert abs(fit.params[name] - TRUE[name]) <= 3 * error, name
    assert fit.residuals["w_rms_um"] < 0.02 and fit.model.valid_power_mw[0] > fit.params["p_th_mw"]


def test_without_scales_only_the_product_is_fitted():
    fit = fit_threshold_ln(synthetic_threshold(), 5000.0)
    assert not fit.n_eff_fitted and fit.params["n_eff"] == 1.0
    assert abs(fit.params["p_th_mw"] - TRUE["p_th_mw"]) <= 3 * fit.uncertainties["p_th_mw"]
    # d_scale² · n_eff is identifiable
    assert fit.params["w_scale_um"] ** 2 == pytest.approx(TRUE["w_scale_um"] ** 2 * TRUE["n_eff"], rel=0.05)


def test_model_comparison_prefers_the_generating_model():
    threshold = fit_all(synthetic_threshold(), 5000.0, w_scale_um=0.25, l_scale_um=0.75)
    assert choose(threshold).kind == "threshold_ln"
    rng = np.random.default_rng(7)
    power = np.repeat(np.linspace(0.35, 1.0, 12), 3)
    w, l = 0.6 * (power - 0.3) ** 1.0, 1.8 * (power - 0.3) ** 1.0
    linear = VoxelPoints(power, w + rng.normal(0, 0.003, power.size), l + rng.normal(0, 0.009, power.size),
                         np.full(power.size, 0.003), np.full(power.size, 0.009))
    fits = fit_all(linear, 5000.0)
    best = choose(fits)
    assert best.kind == "power_law" and best.params["w_b"] == pytest.approx(1.0, abs=0.1)
    assert fits["power_law"].aic < fits["threshold_ln"].aic
    assert fits["tabulated"].kind == "tabulated"


def test_points_from_rows_selects_fields_and_lengths():
    rows = [{"field_id": 0, "cell_id": "F0-r1c0", "power_mw": 0.4, "width_um": 0.2, "height_um": 0.6},
            {"field_id": 1, "cell_id": "F1-r0c0", "power_mw": 0.5, "width_um": 0.25, "height_um": 0.3},  # clipped
            {"field_id": 2, "cell_id": "F2-r0c0", "power_mw": 0.5, "width_um": "", "height_um": 0.8,
             "height_std_um": 0.05},
            {"field_id": 3, "cell_id": "F3-r0c0", "power_mw": 0.5, "width_um": 0.3},
            {"field_id": 0, "cell_id": "F0-r0c0", "power_mw": 0.3, "width_um": ""}]
    points = points_from_rows(rows)
    assert list(points.power_mw) == [0.4, 0.5, 0.5]
    assert np.isnan(points.length_um[1]) and points.length_um[2] == 0.8 and points.length_std_um[2] == 0.05
    with pytest.raises(ValueError, match="No measured"):
        points_from_rows(rows[3:])


def test_fits_need_widths_and_lengths():
    points = synthetic_threshold()
    no_length = VoxelPoints(points.power_mw, points.width_um, np.full(points.power_mw.size, np.nan),
                            points.width_std_um, points.length_std_um)
    fits = fit_all(no_length, 5000.0)
    assert all(isinstance(f, str) for f in fits.values())
    with pytest.raises(ValueError, match="No voxel model"):
        choose(fits)
    with pytest.raises(ValueError, match="widths and lengths"):
        fit_power_law(no_length, 5000.0)


def test_calibration_file_and_plot(tmp_path):
    points = synthetic_threshold()
    best = choose(fit_all(points, 5000.0, w_scale_um=0.25, l_scale_um=0.75, source="synthetic"))
    calibration = write_calibration(best, tmp_path / "calibration.json", material="SZ2080", objective="Zeiss 63x",
                                    setup="IFOV_on", z0_um=0.4, provisional=True, source="synthetic F0")
    again = ProcessCalibration.load(tmp_path / "calibration.json")
    assert again == calibration and again.p_th_mw == pytest.approx(best.params["p_th_mw"])
    assert again.voxel_model.residuals["w_rms_um"] == best.residuals["w_rms_um"]
    assert math.isclose(again.hatch_um(0.5, 0.6), 0.5 * best.model.width_um(0.6))
    with pytest.raises(MissingPropertyError):
        write_calibration(best, tmp_path / "c2.json", material="SZ2080", objective="Zeiss 63x", setup="IFOV_on",
                          z0_um=None)
    assert plot_fit(best, points, tmp_path / "fit.png").stat().st_size > 0


@pytest.mark.slow
def test_fit_stored_in_the_experiment_file(test_config, dummy_backend, no_sleep, tmp_path):
    from experiment_analysis import ExperimentFile
    from test_experiment import make_experiment

    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend) as experiment:
        experiment.plot_experiment()
    points = synthetic_threshold()
    fits = fit_all(points, 5000.0, w_scale_um=0.25, l_scale_um=0.75)
    location = store_fit(path, fits, points, choose(fits))
    assert location.endswith("ptd01_voxel_fit")
    data, attrs = ExperimentFile(path).load_result("ptd01_voxel_fit")
    assert attrs["chosen"] == "threshold_ln" and attrs["n_points"] == points.power_mw.size
    assert np.allclose(data["power_mw"], points.power_mw)
    report = json.loads(data["fits_json"] if isinstance(data["fits_json"], str) else data["fits_json"].decode())
    assert set(report) == {"threshold_ln", "power_law", "tabulated"}
