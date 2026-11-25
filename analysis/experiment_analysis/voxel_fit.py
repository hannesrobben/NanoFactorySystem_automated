##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Fit the voxel model w(P), l(P) to PTD measurements (T151, design docs/design/TEST_PRINT_PTD01.md §4.4, §7).

Input are the filled cell tables of the PTD-01 evaluation (:mod:`.ptd`): widths ``width_um`` and
lengths over the power ``power_mw``. Stage A fits F0 (provisional calibration), stage B refines with F1
and F2. Heights of lines lying on the substrate are clipped by it, so by default only heights of F0
(ascending scan) and F2 (free-standing bridge) are used as voxel lengths.

Every model kind of ``nanofactorysystem.testprint.voxel_fit`` is fitted with weighted least squares
(weights ``1/std²`` where a standard deviation is given): ``threshold_ln`` and ``power_law`` share P_th
between w and l; ``tabulated`` interpolates the mean per power level (fallback). The kinds are compared
with the AIC of the weighted residuals; :func:`choose` takes the lowest AIC of the analytic kinds.

Identifiability of ``threshold_ln``: ``d = d_scale · sqrt(n_eff · ln(P/P_th))`` depends only on
``d_scale² · n_eff``. ``n_eff`` is therefore fitted only when the scales ``w_scale_um`` and
``l_scale_um`` are given (e.g. from the optics of the objective); without them ``n_eff`` is fixed to 1
and the scales are fitted (result ``n_eff_fitted = False``).

Example::

    from experiment_analysis.voxel_fit import points_from_csv, fit_all, choose, write_calibration
    points = points_from_csv(["F0_cells.csv"])
    results = fit_all(points, velocity_um_s=5000.0)
    best = choose(results)
    write_calibration(best, "calibration_SZ2080_Zeiss63x.json", material="SZ2080", objective="Zeiss 63x",
                      setup="IFOV_on", z0_um=0.4, provisional=True, source="HR-26-003-A F0")
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence, Union

import numpy as np
from scipy.optimize import least_squares

from nanofactorysystem.testprint.calibration import ProcessCalibration
from nanofactorysystem.testprint.voxel_fit import VoxelFitModel

__all__ = ["VoxelPoints", "FitResult", "points_from_rows", "points_from_csv", "points_from_parameter_tests",
           "fit_threshold_ln", "fit_power_law",
           "fit_tabulated", "fit_all", "choose", "write_calibration", "plot_fit", "store_fit"]

PathLike = Union[str, Path]
LENGTH_FIELDS = (0, 2)          # heights of these fields are voxel lengths (not clipped by the substrate)


@dataclass
class VoxelPoints:
    """ Measured voxel sizes: one entry per measured cell.

    Attributes
    ----------
    power_mw : np.ndarray
    width_um, length_um : np.ndarray
        NaN where not measured.
    width_std_um, length_std_um : np.ndarray
        Standard deviations, NaN if unknown (weight 1 then).
    source : list of str
        Cell ids / files.
    """

    power_mw: np.ndarray
    width_um: np.ndarray
    length_um: np.ndarray
    width_std_um: np.ndarray
    length_std_um: np.ndarray
    source: list = field(default_factory=list)

    def to_json(self) -> dict:
        """ JSON form (NaN as None). """

        def clean(values):
            return [None if not np.isfinite(v) else float(v) for v in values]
        return {"power_mw": clean(self.power_mw), "width_um": clean(self.width_um),
                "length_um": clean(self.length_um), "width_std_um": clean(self.width_std_um),
                "length_std_um": clean(self.length_std_um), "source": list(self.source)}


@dataclass
class FitResult:
    """ The fit of one model kind.

    Attributes
    ----------
    kind : str
    model : VoxelFitModel
        The fitted model (``residuals`` and ``source`` filled).
    params, uncertainties : dict
        Fitted parameters and their standard errors (fixed parameters have no uncertainty).
    residuals : dict
        RMS and maximum absolute residual of w and l in µm.
    aic : float
        Akaike information criterion of the weighted residuals (lower = better).
    n_points, n_params : int
    n_eff_fitted : bool
        ``threshold_ln`` only: False if the scales were fitted and ``n_eff`` fixed to 1.
    """

    kind: str
    model: VoxelFitModel
    params: dict
    uncertainties: dict
    residuals: dict
    aic: float
    n_points: int
    n_params: int
    n_eff_fitted: bool = True

    def to_json(self) -> dict:
        """ JSON form (for the experiment file and the report). """

        return {"kind": self.kind, "params": self.params, "uncertainties": self.uncertainties,
                "residuals": self.residuals, "aic": self.aic, "n_points": self.n_points, "n_params": self.n_params,
                "n_eff_fitted": self.n_eff_fitted, "model": self.model.to_json()}


# ----------------------------------------------------------------------------------------------
# Input
# ----------------------------------------------------------------------------------------------
def _value(row: dict, key: str) -> float:
    value = row.get(key)
    if value is None or str(value).strip() == "":
        return math.nan
    return float(value)


def points_from_rows(rows: Sequence[dict], *, fields: Sequence[int] = (0, 1, 2),
                     length_fields: Sequence[int] = LENGTH_FIELDS) -> VoxelPoints:
    """ Voxel points from filled cell-table rows (dicts with ``field_id``, ``power_mw``, ``width_um``, …).

    Parameters
    ----------
    rows : sequence of dict
    fields : sequence of int
        Fields whose rows are used.
    length_fields : sequence of int
        Fields whose ``height_um`` is a voxel length (default F0 and F2).

    Returns
    -------
    VoxelPoints

    Raises
    ------
    ValueError
        If no row has a measured size.
    """

    data = []
    for row in rows:
        field_id = int(float(row.get("field_id", -1)))
        if field_id not in fields:
            continue
        width = _value(row, "width_um")
        length = _value(row, "height_um") if field_id in length_fields else math.nan
        if math.isnan(width) and math.isnan(length):
            continue
        data.append((_value(row, "power_mw"), width, length, _value(row, "width_std_um"),
                     _value(row, "height_std_um") if field_id in length_fields else math.nan,
                     f"{row.get('experiment_label', '')} {row.get('cell_id', '')}".strip()))
    if not data:
        raise ValueError("No measured widths or lengths in the given rows.")
    columns = list(zip(*data))
    return VoxelPoints(*(np.asarray(c, dtype=float) for c in columns[:5]), source=list(columns[5]))


def points_from_csv(paths: Sequence[PathLike], **kwargs) -> VoxelPoints:
    """ Voxel points from filled cell-table CSV files (:func:`experiment_analysis.ptd.export_cell_table`). """

    rows = []
    for path in paths:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            rows += list(csv.DictReader(handle))
    return points_from_rows(rows, **kwargs)


def points_from_parameter_tests(width_rows: Sequence[dict], gap_lengths: Sequence[dict] = ()) -> VoxelPoints:
    """ Voxel points of the parameter tests (version 2): widths and lengths at their powers.

    Parameters
    ----------
    width_rows : sequence of dict
        Filled cell-table rows with ``power_mw`` and ``width_um`` (e.g. Quick PT walls, Full PT-01 F1 / F2);
        ``width_std_um`` is used as weight where given.
    gap_lengths : sequence of dict
        Output of :func:`experiment_analysis.ptd.voxel_lengths_from_gaps` (``power_mw``, ``length_um``,
        ``length_unc_um``).

    Returns
    -------
    VoxelPoints

    Raises
    ------
    ValueError
        Without any width or length.
    """

    data = []
    for row in width_rows:
        width = _value(row, "width_um")
        if not math.isnan(width):
            data.append((_value(row, "power_mw"), width, math.nan, _value(row, "width_std_um"), math.nan,
                         str(row.get("cell_id", ""))))
    for item in gap_lengths:
        if item.get("length_um") is not None:
            unc = item.get("length_unc_um")
            data.append((float(item["power_mw"]), math.nan, float(item["length_um"]), math.nan,
                         float(unc) if unc else math.nan, f"gap test {item['power_mw']} mW"))
    if not data:
        raise ValueError("No measured widths or lengths.")
    columns = list(zip(*data))
    return VoxelPoints(*(np.asarray(c, dtype=float) for c in columns[:5]), source=list(columns[5]))


# ----------------------------------------------------------------------------------------------
# Fitting
# ----------------------------------------------------------------------------------------------
def _weights(std: np.ndarray) -> np.ndarray:
    return np.where(np.isfinite(std) & (std > 0), 1.0 / np.where(std > 0, std, 1.0), 1.0)


def _residual_stats(points: VoxelPoints, model: VoxelFitModel) -> dict:
    stats = {}
    for name, values, evaluate in (("w", points.width_um, model.width_um), ("l", points.length_um, model.length_um)):
        mask = np.isfinite(values)
        if not mask.any():
            stats.update({f"{name}_rms_um": None, f"{name}_max_um": None})
            continue
        residual = np.array([evaluate(p) for p in points.power_mw[mask]]) - values[mask]
        stats.update({f"{name}_rms_um": float(np.sqrt(np.mean(residual ** 2))),
                      f"{name}_max_um": float(np.max(np.abs(residual)))})
    return stats


def _least_squares(points: VoxelPoints, predict, x0: Sequence[float], lower: Sequence[float],
                   upper: Sequence[float]) -> tuple[np.ndarray, np.ndarray, float, int]:
    """ Weighted joint fit of w and l. Returns parameters, standard errors, chi², number of residuals. """

    w_mask, l_mask = np.isfinite(points.width_um), np.isfinite(points.length_um)
    w_weight, l_weight = _weights(points.width_std_um)[w_mask], _weights(points.length_std_um)[l_mask]

    def residuals(x):
        w_model, l_model = predict(x, points.power_mw)
        return np.concatenate([(w_model[w_mask] - points.width_um[w_mask]) * w_weight,
                               (l_model[l_mask] - points.length_um[l_mask]) * l_weight])

    fit = least_squares(residuals, np.asarray(x0, dtype=float), bounds=(lower, upper), x_scale="jac")
    n, k = fit.fun.size, len(x0)
    chi2 = float(np.sum(fit.fun ** 2))
    try:
        covariance = np.linalg.inv(fit.jac.T @ fit.jac) * (chi2 / max(n - k, 1))
        errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    except np.linalg.LinAlgError:
        errors = np.full(k, np.nan)
    return fit.x, errors, chi2, n


def _aic(chi2: float, n: int, k: int) -> float:
    return float(n * math.log(max(chi2, 1e-300) / n) + 2 * k)


def _valid_range(points: VoxelPoints, p_th: Optional[float] = None) -> tuple[float, float]:
    low, high = float(np.min(points.power_mw)), float(np.max(points.power_mw))
    if p_th is not None and low <= p_th:
        low = p_th * 1.0001
    return low, high


def fit_threshold_ln(points: VoxelPoints, velocity_um_s: float, *, w_scale_um: Optional[float] = None,
                     l_scale_um: Optional[float] = None, source: str = "") -> FitResult:
    """ Fit ``d = d_scale · sqrt(n_eff · ln(P/P_th))`` to w and l with a common P_th.

    With both scales given, P_th and n_eff are fitted; otherwise the scales and P_th are fitted with
    ``n_eff = 1`` (only ``d_scale² · n_eff`` is identifiable).

    Raises
    ------
    ValueError
        Without width or length data.
    """

    if not np.isfinite(points.width_um).any() or not np.isfinite(points.length_um).any():
        raise ValueError("threshold_ln needs widths and lengths.")
    p_min = float(np.min(points.power_mw))
    fixed_scales = w_scale_um is not None and l_scale_um is not None

    def log_term(p_th, n_eff, power):
        return np.sqrt(np.clip(n_eff * np.log(np.maximum(power / p_th, 1.0)), 0.0, None))

    if fixed_scales:
        def predict(x, power):
            term = log_term(x[0], x[1], power)
            return w_scale_um * term, l_scale_um * term
        x, errors, chi2, n = _least_squares(points, predict, [0.8 * p_min, 2.0], [1e-6, 0.1], [p_min, 20.0])
        params = {"w_scale_um": float(w_scale_um), "l_scale_um": float(l_scale_um), "p_th_mw": float(x[0]),
                  "n_eff": float(x[1])}
        uncertainties = {"p_th_mw": float(errors[0]), "n_eff": float(errors[1])}
    else:
        w_guess = float(np.nanmax(points.width_um)) / 1.5
        l_guess = float(np.nanmax(points.length_um)) / 1.5

        def predict(x, power):
            term = log_term(x[0], 1.0, power)
            return x[1] * term, x[2] * term
        x, errors, chi2, n = _least_squares(points, predict, [0.8 * p_min, w_guess, l_guess], [1e-6, 1e-6, 1e-6],
                                            [p_min, 100.0, 100.0])
        params = {"w_scale_um": float(x[1]), "l_scale_um": float(x[2]), "p_th_mw": float(x[0]), "n_eff": 1.0}
        uncertainties = {"p_th_mw": float(errors[0]), "w_scale_um": float(errors[1]), "l_scale_um": float(errors[2])}
    model = VoxelFitModel("threshold_ln", params, _valid_range(points, params["p_th_mw"]), velocity_um_s,
                          source=source)
    residuals = _residual_stats(points, model)
    model = VoxelFitModel(model.kind, model.params, model.valid_power_mw, velocity_um_s, source=source,
                          residuals=residuals)
    k = len(uncertainties)
    return FitResult("threshold_ln", model, params, uncertainties, residuals, _aic(chi2, n, k), n, k, fixed_scales)


def fit_power_law(points: VoxelPoints, velocity_um_s: float, *, source: str = "") -> FitResult:
    """ Fit ``d = a · (P - P_th)^b`` to w and l with a common P_th.

    Raises
    ------
    ValueError
        Without width or length data.
    """

    if not np.isfinite(points.width_um).any() or not np.isfinite(points.length_um).any():
        raise ValueError("power_law needs widths and lengths.")
    p_min = float(np.min(points.power_mw))

    def predict(x, power):
        base = np.maximum(power - x[0], 1e-12)
        return x[1] * base ** x[2], x[3] * base ** x[4]

    x, errors, chi2, n = _least_squares(points, predict, [0.8 * p_min, 1.0, 0.5, 2.0, 0.5],
                                        [1e-6, 1e-6, 0.05, 1e-6, 0.05], [p_min * 0.9999, 100.0, 3.0, 100.0, 3.0])
    names = ("p_th_mw", "w_a", "w_b", "l_a", "l_b")
    params = {name: float(v) for name, v in zip(names, x)}
    uncertainties = {name: float(e) for name, e in zip(names, errors)}
    model = VoxelFitModel("power_law", params, _valid_range(points, params["p_th_mw"]), velocity_um_s, source=source)
    residuals = _residual_stats(points, model)
    model = VoxelFitModel("power_law", params, model.valid_power_mw, velocity_um_s, source=source,
                          residuals=residuals)
    return FitResult("power_law", model, params, uncertainties, residuals, _aic(chi2, n, len(names)), n, len(names))


def fit_tabulated(points: VoxelPoints, velocity_um_s: float, *, source: str = "") -> FitResult:
    """ Mean width and length per power level, interpolated linearly (fallback without an analytic model).

    Raises
    ------
    ValueError
        If fewer than 2 power levels have both a width and a length.
    """

    levels = []
    for power in np.unique(points.power_mw):
        mask = points.power_mw == power
        w, l = points.width_um[mask], points.length_um[mask]
        if np.isfinite(w).any() and np.isfinite(l).any():
            levels.append((float(power), float(np.nanmean(w)), float(np.nanmean(l))))
    if len(levels) < 2:
        raise ValueError("tabulated needs at least 2 power levels with width and length.")
    power, width, length = (list(v) for v in zip(*levels))
    params = {"power_mw": power, "width_um": width, "length_um": length}
    model = VoxelFitModel("tabulated", params, (power[0], power[-1]), velocity_um_s, source=source)
    residuals = _residual_stats(points, model)
    model = VoxelFitModel("tabulated", params, model.valid_power_mw, velocity_um_s, source=source,
                          residuals=residuals)
    w_mask, l_mask = np.isfinite(points.width_um), np.isfinite(points.length_um)
    chi2 = float(sum((model.width_um(p) - w) ** 2 for p, w in zip(points.power_mw[w_mask], points.width_um[w_mask]))
                 + sum((model.length_um(p) - v) ** 2 for p, v in zip(points.power_mw[l_mask], points.length_um[l_mask])))
    n, k = int(w_mask.sum() + l_mask.sum()), 2 * len(power)
    return FitResult("tabulated", model, params, {}, residuals, _aic(chi2, n, k), n, k)


def fit_all(points: VoxelPoints, velocity_um_s: float, *, w_scale_um: Optional[float] = None,
            l_scale_um: Optional[float] = None, source: str = "") -> dict[str, Union[FitResult, str]]:
    """ Fit every model kind; a kind that cannot be fitted maps to its error message.

    Returns
    -------
    dict
        ``kind -> FitResult`` or ``kind -> "error text"``.
    """

    fits: dict[str, Union[FitResult, str]] = {}
    for kind, run in (("threshold_ln", lambda: fit_threshold_ln(points, velocity_um_s, w_scale_um=w_scale_um,
                                                                l_scale_um=l_scale_um, source=source)),
                      ("power_law", lambda: fit_power_law(points, velocity_um_s, source=source)),
                      ("tabulated", lambda: fit_tabulated(points, velocity_um_s, source=source))):
        try:
            fits[kind] = run()
        except (ValueError, RuntimeError, np.linalg.LinAlgError) as error:
            fits[kind] = str(error)
    return fits


def choose(fits: dict[str, Union[FitResult, str]]) -> FitResult:
    """ The analytic fit with the lowest AIC; ``tabulated`` only if no analytic kind could be fitted.

    Raises
    ------
    ValueError
        If no kind could be fitted.
    """

    analytic = [f for k, f in fits.items() if isinstance(f, FitResult) and k != "tabulated"]
    if analytic:
        return min(analytic, key=lambda f: f.aic)
    if isinstance(fits.get("tabulated"), FitResult):
        return fits["tabulated"]
    raise ValueError(f"No voxel model could be fitted: {fits}")


# ----------------------------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------------------------
def write_calibration(result: FitResult, path: PathLike, *, material: str, objective: str, setup: str,
                      z0_um: float, p_th_mw: Optional[float] = None, p_dam_mw: Optional[float] = None,
                      p_ref_factor: float = 1.5, plane_fit: Optional[dict] = None,
                      polarisation_deg: Optional[float] = None, provisional: bool = True, source: str = "",
                      date: str = "") -> ProcessCalibration:
    """ Write a ``ProcessCalibration`` JSON with the chosen model.

    ``p_th_mw`` defaults to the fitted threshold of the model; ``z0_um`` (interface working point) comes
    from the evaluation of F0 and has no default.

    Returns
    -------
    ProcessCalibration

    Raises
    ------
    MissingPropertyError
        Without P_th (tabulated model and no ``p_th_mw``) or z0.
    """

    threshold = p_th_mw if p_th_mw is not None else result.params.get("p_th_mw")
    calibration = ProcessCalibration(material, objective, setup, result.model.velocity_um_s, threshold, z0_um,
                                     result.model, p_dam_mw=p_dam_mw, p_ref_factor=p_ref_factor,
                                     plane_fit=dict(plane_fit or {}), polarisation_deg=polarisation_deg,
                                     provisional=provisional, source=source, date=date)
    calibration.save(path)
    return calibration


def plot_fit(result: FitResult, points: VoxelPoints, path: PathLike) -> Path:
    """ Plot measured w and l over P with the fitted model; written as PNG.

    Returns
    -------
    Path
    """

    from matplotlib.figure import Figure  # no pyplot: no GUI objects (T120)

    figure = Figure(figsize=(6, 4))
    ax = figure.add_subplot(111)
    low, high = result.model.valid_power_mw
    grid = np.linspace(low, high, 200)
    for name, values, std, evaluate, colour in (
            ("w", points.width_um, points.width_std_um, result.model.width_um, "tab:blue"),
            ("l", points.length_um, points.length_std_um, result.model.length_um, "tab:orange")):
        mask = np.isfinite(values)
        ax.errorbar(points.power_mw[mask], values[mask], yerr=np.where(np.isfinite(std[mask]), std[mask], 0.0),
                    fmt="o", ms=3, color=colour, label=f"{name} measured")
        ax.plot(grid, [evaluate(p) for p in grid], color=colour, label=f"{name} {result.kind}")
    ax.set_xlabel("P / mW")
    ax.set_ylabel("size / µm")
    ax.set_title(f"{result.kind}: AIC {result.aic:.1f}")
    ax.legend(fontsize=7)
    path = Path(path)
    figure.savefig(path, dpi=120, bbox_inches="tight")
    return path


def store_fit(experiment, fits: dict[str, Union[FitResult, str]], points: VoxelPoints, chosen: FitResult, *,
              wait_s: float = 0.0) -> str:
    """ Store fit inputs and results in the experiment file (``/analysis/experiment/ptd01_voxel_fit``).

    Parameters
    ----------
    experiment : path or ExperimentFile
    fits, points, chosen
        Results of :func:`fit_all`, the input points and the chosen fit.

    Returns
    -------
    str
        HDF5 path of the result.
    """

    from .access import ExperimentFile

    exp = experiment if isinstance(experiment, ExperimentFile) else ExperimentFile(experiment)
    report: dict[str, Any] = {k: (f.to_json() if isinstance(f, FitResult) else {"error": f}) for k, f in fits.items()}
    data = {"power_mw": points.power_mw, "width_um": points.width_um, "length_um": points.length_um,
            "width_std_um": points.width_std_um, "length_std_um": points.length_std_um,
            "fits_json": json.dumps(report)}
    return exp.save_result("ptd01_voxel_fit", data, attrs={"chosen": chosen.kind, "n_points": len(points.power_mw),
                                                            "sources": json.dumps(points.source)}, wait_s=wait_s)
