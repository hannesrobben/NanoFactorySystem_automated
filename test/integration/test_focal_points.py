"""Dry run of the focal-point script (z-lines for an AI classifier, T36)."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.storage import ExperimentStore

SCRIPT = Path(__file__).parents[2] / "mains" / "Experiments" / "focal_points" / "z_line_focal_points.py"
RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


def load():
    spec = importlib.util.spec_from_file_location("z_line_focal_points", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_random_points_and_lengths():
    module = load()
    rng = np.random.default_rng(1)
    points = module.random_points(20, (20.0, 20.0), ((0, 300), (0, 200)), rng)
    assert len(points) == 20 and all(0 <= x <= 300 and 0 <= y <= 200 for x, y in points)
    for i, (x, y) in enumerate(points):
        for px, py in points[:i]:
            assert abs(x - px) >= 20 or abs(y - py) >= 20
    with pytest.raises(ValueError, match="fit into"):
        module.random_points(50, (20.0, 20.0), ((0, 30), (0, 30)), rng)
    lengths = module.line_lengths(10, np.random.default_rng(2))
    assert all(abs(dz - 10.0) <= module.DZ_NOISE_UM for dz in lengths) and len(set(lengths)) == 10


@pytest.mark.slow
def test_focal_point_dry_run(test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    module = load()

    results = module.focal_point_matrix_maker(Point2D(1310, 19500), RESIN_EDGES, path=tmp_path, user="Test",
                                              backend=dummy_backend, plane=dummy_backend.world.sample.plane(),
                                              seed=7, n_points=3)

    data = json.loads((results / "focal_points.json").read_text())
    assert data["seed"] == 7 and len(data["points"]) == 3
    assert all((results / point["file"]).is_file() for point in data["points"])
    (x_min, x_max), (y_min, y_max) = data["boundary_um"]
    assert all(x_min <= p["x_um"] <= x_max and y_min <= p["y_um"] <= y_max for p in data["points"])
    # Three z-line programs ran on the controller, then the corners and the QR code were printed
    zline_runs = [r for r in dummy_backend.world.calllog.filter(device="program") if r.call.endswith("__zline__.pgm")]
    assert len(zline_runs) == 3
    record = ExperimentStore.open(tmp_path / "focal_point").read()
    assert record.status == "finished" and {s.type for s in record.structures} == {"CORNER", "QRCODE"}
