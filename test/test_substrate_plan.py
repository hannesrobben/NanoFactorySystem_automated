"""Layout checks of a substrate main file (T52)."""
import uuid

import pytest

from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment_spec import ExperimentSpec
from nanofactorysystem.substrate_plan import (QR_CODE_WIDTH_UM, Area, LayoutError, SubstrateExperiment,
                                              SubstrateSpec, check_layout, experiment_area, marker_clearance,
                                              plot_substrate)

RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


def spec(name, x, y, *, grid=(1, 1), objective="Zeiss 20x", skip_corner=True):
    return ExperimentSpec(name=name, objective=objective, center=Point2D(x, y), grid=grid, skip_corner=skip_corner)


def substrate():
    return SubstrateSpec(user="Test", objective="Zeiss 20x", resin_edges=RESIN_EDGES)


def test_experiment_area_matches_the_experiment_geometry():
    # 20x defaults: structure 500, padding 100, margin 200; 2 rows (y) x 3 columns (x):
    # width 3 * 600 - 100 + 2 * 200 = 2100, height 2 * 600 - 100 + 2 * 200 = 1500
    area = experiment_area(spec("a", 1000, 20000, grid=(2, 3)))
    assert area == Area("a", (1000 - 1050, 20000 - 750), (1000 + 1050, 20000 + 750))


def test_markers_widen_the_area():
    plain = experiment_area(spec("a", 0, 20000))
    marked = experiment_area(spec("a", 0, 20000, skip_corner=False))
    assert marker_clearance(spec("a", 0, 20000, skip_corner=False)) == QR_CODE_WIDTH_UM / 2
    assert marked.lower == (plain.lower[0] - 70, plain.lower[1] - 70)


def test_qr_code_width_of_an_experiment_uuid():
    from nanofactorysystem.aerobasic.programs.drawings.qr_code import QRCode, QrErrorCorrection

    # Same settings as Experiment.add_qrcode_structure; every UUID text has 36 characters
    qrcode = QRCode(Point3D(0, 0, -2), text=str(uuid.uuid4()), version=None, error_correction=QrErrorCorrection.Q,
                    pixel_pitch=4.0, base_height=7.0, anchor_height=2.0, pixel_height=5.0, slice_size=0.75,
                    hatch_size=0.5, horizontal_velocity=5000, horizontal_acceleration=1e6, vertical_velocity=300,
                    vertical_acceleration=1e5)
    assert qrcode.structure_width == QR_CODE_WIDTH_UM


def test_valid_layout():
    areas = check_layout(substrate(), [SubstrateExperiment(spec("a", 0, 20000)),
                                       SubstrateExperiment(spec("b", 1000, 20000))])
    assert [a.name for a in areas] == ["a", "b"]


def test_every_problem_is_reported():
    experiments = [SubstrateExperiment(spec("a", 0, 20000)),
                   SubstrateExperiment(spec("b", 800, 20000)),  # 900 um wide: overlaps a
                   SubstrateExperiment(spec("c", 5500, 20000)),  # right half outside the drop
                   SubstrateExperiment(spec("d", 0, 25000, objective="Zeiss 63x")),
                   SubstrateExperiment(spec("d", 3000, 25000))]
    with pytest.raises(LayoutError) as error:
        check_layout(substrate(), experiments, existing=[Area("TU-26-001-A", (-100, 24900), (100, 25100))])
    message = str(error.value)
    assert "used more than once: ['d']" in message
    assert "a overlaps b" in message
    assert "c: area" in message and "leaves the resin drop" in message
    assert "objective 'Zeiss 63x' differs" in message
    assert "d overlaps experiment TU-26-001-A already on the substrate" in message
    assert "a overlaps c" not in message


def test_touching_areas_do_not_overlap():
    assert not Area("a", (0, 0), (10, 10)).overlaps(Area("b", (10, 0), (20, 10)))
    assert Area("a", (0, 0), (10, 10)).overlaps(Area("b", (9, 9), (20, 20)))


def test_plot_substrate():
    import matplotlib
    matplotlib.use("Agg")
    figure = plot_substrate(substrate(), [experiment_area(spec("a", 0, 20000))],
                            existing=[Area("old", (1000, 20000), (1500, 20500))])
    assert len(figure.axes[0].patches) == 4  # drop box, drop ellipse (T62), planned and existing area
