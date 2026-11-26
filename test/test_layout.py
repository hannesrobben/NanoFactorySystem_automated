"""Layout of an experiment as data and its figure without pyplot (T80)."""
import json

import matplotlib
import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings import Rectangle3D
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import Experiment
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec
from nanofactorysystem.layout import experiment_layout, grid_geometry, layout_figure, spec_layout
from nanofactorysystem.runtime import getLogger

RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


def rectangle():
    return Rectangle3D(Point3D(0, 0, -1), 10, 10, 2, hatch_size=1.0, slice_size=1.0, velocity=1000, acceleration=500)


def spec(skip_corner=False):
    return ExperimentSpec(name="layout", objective="Zeiss 20x", center=Point2D(1310, 21000), grid=(2, 3),
                          skip_corner=skip_corner,
                          structures=[StructureSpec("a", rectangle(), repeat=1), StructureSpec.empty(),
                                      StructureSpec("b", rectangle())])


def test_grid_geometry_rows_along_y_columns_along_x():
    rectangle_um, cells = grid_geometry((0, 0), (2, 3), 100, 10, 20)
    assert rectangle_um[0] == pytest.approx((-180, -125)) and rectangle_um[2] == pytest.approx((180, 125))
    assert cells[0] == pytest.approx((-110, -55)) and cells[1] == pytest.approx((0, -55))
    assert cells[3] == pytest.approx((-110, 55))


def test_spec_layout_is_plain_data():
    layout = spec_layout(spec())
    assert [c.structures for c in layout.cells] == [["a"], ["a_rep1"], [], ["b"], [], []]
    assert [c.position for c in layout.corners] == ["TL", "TR", "BR", "BL"] and layout.corners[0].double
    assert layout.qrcode_um[1] == pytest.approx(layout.rectangle_um[0][1])
    assert layout.plane_fit_points_um
    json.dumps(layout.to_json())
    assert spec_layout(spec(skip_corner=True)).corners == []


def test_spec_layout_equals_the_layout_of_the_experiment(test_config, dummy_backend, no_sleep, tmp_path):
    matplotlib.use("Agg")
    written = spec()
    (tmp_path / "exp").mkdir()
    arguments = written.experiment_arguments(user="Test", resin_edges=RESIN_EDGES, logger=getLogger(),
                                             backend=dummy_backend, path=tmp_path / "exp")
    with Experiment(**arguments) as experiment:
        from_experiment = experiment_layout(experiment)
    from_spec = spec_layout(written)
    assert np.allclose(from_experiment.rectangle_um, from_spec.rectangle_um)
    assert np.allclose([c.center_um for c in from_experiment.cells], [c.center_um for c in from_spec.cells])
    assert np.allclose(from_experiment.plane_fit_points_um, from_spec.plane_fit_points_um)
    if from_experiment.corners:                                    # corner structures are added with the experiment
        assert {c.position for c in from_experiment.corners} == {c.position for c in from_spec.corners}
        assert from_experiment.qrcode_um == pytest.approx(from_spec.qrcode_um)


def test_layout_figure_opens_no_window():
    import matplotlib.pyplot as plt
    before = plt.get_fignums()
    figure = layout_figure(spec_layout(spec()))
    assert plt.get_fignums() == before and figure.axes[0].patches
