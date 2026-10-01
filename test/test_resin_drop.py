"""Resin-drop outline: ellipse through the four edge points (T62)."""
import enum

import numpy as np
import pytest

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment_spec import ExperimentSpec
from nanofactorysystem.resin_drop import (Ellipse, drop_outline, ellipse_through, has_drop_boundary,
                                          rectangle_inside)
from nanofactorysystem.substrate_plan import LayoutError, SubstrateExperiment, SubstrateSpec, check_layout

EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]  # right, left, near, far


class FakeDropDirection(enum.Enum):
    """ Stand-in for the future dip-in drop direction (F8). """

    DIP_IN = 0


def test_ellipse_passes_through_the_edge_points():
    ellipse = ellipse_through(EDGES)
    values = [((x - ellipse.cx) / ellipse.a) ** 2 + ((y - ellipse.cy) / ellipse.b) ** 2 for x, y in EDGES]
    assert np.allclose(values, 1.0)
    assert ellipse.contains([1310, 19500])[0]
    # Inside the bounding box of the points, but outside the drop
    assert not ellipse.contains([5000, 18000])[0]


def test_circle_and_degenerate_points():
    circle = ellipse_through([[10, 0], [-10, 0], [0, -10], [0, 10]])
    assert circle == pytest.approx(Ellipse(0, 0, 10, 10))
    # Three points on a line define no ellipse: the ellipse inscribed in the bounding box is used
    fallback = ellipse_through([[0, 0], [10, 0], [20, 0], [10, 10]])
    assert fallback == Ellipse(10.0, 5.0, 10.0, 5.0)
    assert drop_outline([[0, 0], [10, 10]]) is None
    with pytest.raises(ValueError, match="Four edge points"):
        ellipse_through([[0, 0], [1, 1], [2, 0]])


def test_rectangle_inside():
    circle = Ellipse(0, 0, 10, 10)
    assert rectangle_inside(circle, (-7, -7), (7, 7))
    assert not rectangle_inside(circle, (-8, -8), (8, 8))  # corners outside, edges inside


def test_dip_in_has_no_drop_boundary():
    from nanofactorysystem.devices.coordinate_system import DropDirection
    assert has_drop_boundary(DropDirection.UP) and has_drop_boundary(DropDirection.DOWN)
    assert not has_drop_boundary(FakeDropDirection.DIP_IN)


def spec(name, x, y, **kwargs):
    return ExperimentSpec(name=name, objective="Zeiss 20x", center=Point2D(x, y), grid=(1, 1), skip_corner=True,
                          **kwargs)


def test_layout_is_checked_against_the_ellipse():
    substrate = SubstrateSpec(user="Test", objective="Zeiss 20x", resin_edges=EDGES)
    check_layout(substrate, [SubstrateExperiment(spec("center", 1200, 22200))])
    # In the bounding box (x -3333..5720, y 17212..27190), but in the lower right part outside the drop
    with pytest.raises(LayoutError, match="rim: .* leaves the resin drop \\(ellipse"):
        check_layout(substrate, [SubstrateExperiment(spec("rim", 4800, 18200))])
    # Dip-in: no drop boundary, no check
    check_layout(substrate, [SubstrateExperiment(spec("rim", 4800, 18200,
                                                      drop_direction=FakeDropDirection.DIP_IN))])

