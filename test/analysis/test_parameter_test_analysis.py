"""Evaluation of the parameter tests on absolute axes (T163)."""
import math

import pytest

from experiment_analysis.ptd import add_relative_columns, voxel_lengths_from_gaps
from experiment_analysis.voxel_fit import fit_all, choose, points_from_parameter_tests
from nanofactorysystem.testprint.voxel_fit import VoxelFitModel

MODEL = VoxelFitModel("threshold_ln", dict(w_scale_um=0.25, l_scale_um=0.75, p_th_mw=0.3, n_eff=1.0), (0.31, 1.0),
                      5000.0)


def test_relative_columns_are_added_after_the_measurement():
    rows = [{"cell_id": "F4a-r4c1", "power_mw": 0.5, "hatch_um": 0.2},
            {"cell_id": "F3b-r0c0", "power_mw": 0.6, "spacing_um": 0.4},
            {"cell_id": "F5a-r0c3", "power_mw": 0.1, "slice_um": 0.5},       # below the model range
            {"cell_id": "F5b-r1c0", "power_mw": 0.7, "slice_um": 0.1}]
    result = add_relative_columns(rows, p_th_mw=0.3, voxel_model=MODEL)
    assert [r["p_rel"] for r in result] == pytest.approx([0.5 / 0.3, 2.0, 0.1 / 0.3, 0.7 / 0.3], abs=1e-6)
    assert result[0]["h_rel"] == pytest.approx(0.2 / MODEL.width_um(0.5), abs=1e-6)
    assert result[1]["s_rel"] == pytest.approx(0.4 / MODEL.width_um(0.6), abs=1e-6)
    assert "dz_rel" not in result[2]                                     # no extrapolation
    assert result[3]["dz_rel"] == pytest.approx(0.1 / MODEL.length_um(0.7), abs=1e-6)
    assert "p_rel" not in rows[0]                                        # input unchanged
    with pytest.raises(ValueError):
        add_relative_columns(rows, p_th_mw=0)


def gap_rows(limits, base=0.5):
    """ Rows of a filled gap test: the lid is present up to (and including) ``limits[power]``. """

    rows = []
    for power, limit in limits.items():
        for k in range(11):
            gap = round(0.2 * k, 1)
            rows.append({"power_mw": power, "gap_um": gap, "present": 1 if gap <= limit + 1e-9 else 0,
                         "base_power_mw": base})
    return rows


def test_voxel_lengths_from_the_gap_test():
    lengths = {r["power_mw"]: r for r in voxel_lengths_from_gaps(gap_rows({0.5: 0.6, 0.8: 1.0, 0.2: 0.2}))}
    base = lengths[0.5]
    assert base["g_attached_um"] == 0.6 and base["g_missing_um"] == 0.8 and base["g_max_um"] == pytest.approx(0.7)
    assert base["length_um"] == pytest.approx(0.7) and base["length_unc_um"] == pytest.approx(0.1)
    assert lengths[0.8]["length_um"] == pytest.approx(2 * 1.1 - 0.7)
    assert lengths[0.8]["length_unc_um"] == pytest.approx(0.3)
    assert lengths[0.2]["length_um"] == pytest.approx(2 * 0.3 - 0.7)


def test_gap_test_needs_the_base_power_experiment_and_values():
    with pytest.raises(ValueError, match="base power"):
        voxel_lengths_from_gaps(gap_rows({0.8: 1.0}))
    with pytest.raises(ValueError, match="present"):
        voxel_lengths_from_gaps([{"power_mw": 0.5, "gap_um": 0.0, "present": ""}])
    open_bracket = {r["power_mw"]: r for r in voxel_lengths_from_gaps(gap_rows({0.5: 0.6, 1.0: 2.0}))}
    assert open_bracket[1.0]["length_um"] is None                         # lid present up to the largest gap


def test_fit_points_from_walls_and_gap_lengths():
    walls = [{"cell_id": f"Q1b-r{i}c0", "power_mw": p, "width_um": MODEL.width_um(p), "width_std_um": 0.01}
             for i, p in enumerate([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])]
    walls.append({"cell_id": "Q1a-r0c0", "power_mw": 0.1, "width_um": ""})  # no wall: not a point
    gaps = [{"power_mw": p, "length_um": MODEL.length_um(p), "length_unc_um": 0.05} for p in (0.4, 0.6, 0.8, 1.0)]
    points = points_from_parameter_tests(walls, gaps)
    assert len(points.power_mw) == 11
    assert sum(math.isfinite(w) for w in points.width_um) == 7 and sum(math.isfinite(v) for v in points.length_um) == 4
    best = choose(fit_all(points, 5000.0))
    assert best.kind in ("threshold_ln", "power_law")
    assert best.model.width_um(0.7) == pytest.approx(MODEL.width_um(0.7), rel=0.05)
    with pytest.raises(ValueError, match="No measured"):
        points_from_parameter_tests([], [])
