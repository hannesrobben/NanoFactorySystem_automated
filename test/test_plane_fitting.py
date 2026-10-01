"""Plane-fit modes, sample points, checks and a plane fit outside Experiment (T44)."""
import json
import logging

import numpy as np
import pytest

from nanofactorysystem.devices.coordinate_system import DropDirection, Plane, PlaneFit, Point2D
from nanofactorysystem.experiment import Experiment
from nanofactorysystem.plane_fitting import (PlaneFitMode, interface_for, measure_plane, sample_points,
                                             structure_tilt)
from nanofactorysystem.storage import ExperimentStore

from test_experiment import make_experiment

LAYOUT = dict(top_left=(0.0, 0.0), margin=200.0, padding=100.0, structure_size=500.0, grid=(2, 3))


def test_mode_names_and_old_integers():
    assert PlaneFitMode.parse(0) is PlaneFitMode.GRID and PlaneFitMode.parse("1") is PlaneFitMode.CORNERS
    assert PlaneFitMode.parse("border") is PlaneFitMode.BORDER
    assert PlaneFitMode.parse(PlaneFitMode.GRID) is PlaneFitMode.GRID
    with pytest.raises((KeyError, ValueError)):
        PlaneFitMode.parse(7)


@pytest.mark.parametrize("mode, expected", [
    # rows + 1 = 3 and cols + 1 = 4 grid lines at 150, 750, 1350 (y) and 150, 750, 1350, 1950 (x)
    (PlaneFitMode.GRID, [(x, y) for y in (150, 750, 1350) for x in (150, 750, 1350, 1950)]),
    (PlaneFitMode.CORNERS, [(150, 150), (150, 1350), (1950, 150), (1950, 1350)]),
    (PlaneFitMode.BORDER, [(x, y) for y in (150, 750, 1350) for x in (150, 750, 1350, 1950)
                           if y in (150, 1350) or x in (150, 1950)]),
])
def test_sample_points_per_mode(mode, expected):
    points = sample_points(mode, **LAYOUT)

    assert sorted(points) == sorted((float(x), float(y)) for x, y in expected)
    assert len(points) == {PlaneFitMode.GRID: 12, PlaneFitMode.CORNERS: 4, PlaneFitMode.BORDER: 10}[mode]


@pytest.mark.parametrize("mode", [0, 1, "BORDER"])
def test_experiment_stores_mode_and_sample_points(mode, test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, grid=(2, 3), plane_fit_mode=mode) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        expected = sample_points(mode, experiment.rectangle_tl, 200, 100, 500, (2, 3))

    record = ExperimentStore.open(path).read()
    assert record.parameters["plane_fit_mode"] == PlaneFitMode.parse(mode).name
    assert np.allclose(record.plane_fit.sample_points_um, expected)
    data = json.loads((path / "experiment_dictionary.json").read_text())
    assert data["plane_fit_mode"] == PlaneFitMode.parse(mode).name
    assert np.allclose(data["plane_fit"]["sample_points_um"], expected)
    assert Experiment.parameters_from_dictionary(path)["plane_fit_mode"] is PlaneFitMode.parse(mode)


def test_old_dictionary_with_integer_mode_is_read(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend):
        pass
    (path / "experiment.h5").unlink()
    data = json.loads((path / "experiment_dictionary.json").read_text())
    data["plane_fit_mode"] = 1
    (path / "experiment_dictionary.json").write_text(json.dumps(data))

    assert Experiment.parameters_from_dictionary(path)["plane_fit_mode"] is PlaneFitMode.CORNERS


def test_center_outside_the_resin_drop_is_refused(test_config, dummy_backend, no_sleep, tmp_path):
    with pytest.raises(ValueError, match="outside the resin"):
        make_experiment(tmp_path, dummy_backend, center=Point2D(9000, 19500))


def test_tilt_warning(test_config, dummy_backend, no_sleep, tmp_path, caplog):
    assert structure_tilt(Plane(np.array([0.01, 0.0, 20000.0])), (0.0, 0.0), 500.0)[0] == pytest.approx(5.0)
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, grid=(1, 2)) as experiment:
        with caplog.at_level(logging.WARNING):
            experiment.plane_fit(plane=Plane(np.array([0.0, 0.0, 20000.0])))
        assert "substrate height varies" not in caplog.text

        with caplog.at_level(logging.WARNING):
            experiment.plane_fit(plane=Plane(np.array([0.01, 0.0, 20000.0])))  # 5 um over 500 um
        assert "substrate height varies by up to 5.00 um" in caplog.text
        assert experiment._check_tilt(Plane(np.array([0.01, 0.0, 20000.0]))) == [(0, pytest.approx(5.0)),
                                                                              (1, pytest.approx(5.0))]


class FakePlane:
    """ Stand-in for tools.plane.Plane: interfaces at z = 20000 + x / 100 (high) and 19990 + x / 100 (low). """

    runs = []

    def __init__(self, zlo, zup, system, logger, **kwargs):
        self.layer = type("Layer", (), {"focus": type("Focus", (), {"imgBack": self})()})()

    def write(self, file):
        open(file, "wb").write(b"background")

    def run(self, x, y, path=None):
        FakePlane.runs.append((x, y))

    def container(self):
        from scidatacontainer import Container, load_config
        points = {name: [[x, y, z0 + x / 100] for x, y in FakePlane.runs] for name, z0 in
                  (("high", 20000.0), ("low", 19990.0))}
        return Container(items={"content.json": {"containerType": {"name": "Plane", "version": 1.1}},
                                "meta.json": {"title": "Plane"},
                                "meas/result.json": {k: {"points": v} for k, v in points.items()}},
                         config=load_config(author="Test User", email="test@example.org"))


def test_single_plane_fit_outside_experiment(monkeypatch, tmp_path):
    import nanofactorysystem.tools.plane as plane_module
    monkeypatch.setattr(plane_module, "Plane", FakePlane)
    FakePlane.runs = []
    system = type("System", (), {"objective": {"magnification": 20.0}, "z0": 20000.0})()
    points = sample_points(PlaneFitMode.CORNERS, **LAYOUT)

    fit, dc, source = measure_plane(system, points, DropDirection.DOWN, tmp_path / "planefit")

    assert source == "measured" and FakePlane.runs == points
    assert isinstance(fit, PlaneFit) and fit(1000.0, 0.0) == pytest.approx(19990.0 + 10.0)  # "low" for DOWN
    assert (tmp_path / "planefit" / "plane.zdc").is_file() and interface_for(DropDirection.UP) == "high"

    fit, _, source = measure_plane(system, points, DropDirection.UP, tmp_path / "planefit")  # loaded again
    assert source == "loaded" and fit(1000.0, 0.0) == pytest.approx(20010.0)
