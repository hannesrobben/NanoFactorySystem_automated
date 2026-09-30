"""Dry run of a substrate main file: two experiments on one substrate (T52)."""
from pathlib import Path

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec
from nanofactorysystem.storage import ExperimentStore
from nanofactorysystem.storage.substrate_store import SubstrateStore, find_experiments
from nanofactorysystem.substrate_plan import (LayoutError, SubstrateExperiment, SubstrateSpec, existing_areas,
                                              experiment_area, run_substrate)

RESIN_EDGES = [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]]


def experiments():
    def rectangle(name, x):
        structure = Rectangle3D(Point3D(0, 0, -1), 20, 20, 2, hatch_size=2.0, slice_size=1.0, velocity=1000,
                                acceleration=500)
        return ExperimentSpec(name=name, objective="Zeiss 20x", center=Point2D(x, 20000), grid=(1, 1),
                              skip_corner=True, structures=[StructureSpec("rect", structure)])
    return [SubstrateExperiment(rectangle("left", 0)), SubstrateExperiment(rectangle("right", 1500))]


@pytest.fixture
def substrate(tmp_path):
    return SubstrateSpec(user="Test", objective="Zeiss 20x", resin_edges=RESIN_EDGES, label="TU-26-007",
                         material={"substrate": "glass"}, data_root=tmp_path / "root")


def test_two_experiments_on_one_substrate(test_config, dummy_backend, no_sleep, tmp_path, substrate):
    import matplotlib
    matplotlib.use("Agg")
    planned = experiments()

    folders = run_substrate(substrate, planned, backend=dummy_backend, plane=dummy_backend.world.sample.plane())

    # Two experiment files in the substrate folder, one substrate index
    root = tmp_path / "root"
    assert [f.parent for f in folders] == [root / "TU-26-007"] * 2
    records = [ExperimentStore.open(f).read() for f in folders]
    assert all(r.status == "finished" and r.substrate_label == "TU-26-007" for r in records)
    assert [r.label for r in records] == ["TU-26-007-A", "TU-26-007-B"]
    record = SubstrateStore(root).get("TU-26-007")
    assert record.material == {"substrate": "glass"}
    assert record.resin_drops[0]["edges_um"] == RESIN_EDGES
    index = find_experiments(root, substrate="TU-26-007")
    assert [(e["label"], e["status"]) for e in index] == [("TU-26-007-A", "finished"), ("TU-26-007-B", "finished")]
    assert [Path(e["folder"]) for e in index] == folders

    # The planned area is the rectangle of the experiment as printed
    for experiment, stored in zip(planned, records):
        area = experiment_area(experiment.spec)
        rectangle = np.asarray(stored.layout.rectangle_um)
        assert np.allclose(rectangle.min(axis=0), area.lower) and np.allclose(rectangle.max(axis=0), area.upper)

    # Running the main file again is refused before anything is printed: the areas are taken
    assert [a.name for a in existing_areas(root, "TU-26-007")] == ["TU-26-007-A", "TU-26-007-B"]
    with pytest.raises(LayoutError, match="left overlaps experiment TU-26-007-A already on the substrate"):
        run_substrate(substrate, planned, backend=dummy_backend, plane=dummy_backend.world.sample.plane())
    assert len(SubstrateStore(root).get("TU-26-007").experiments) == 2


def test_optional_folder_and_confirmation_between_experiments(test_config, dummy_backend, no_sleep, tmp_path,
                                                              substrate):
    import matplotlib
    matplotlib.use("Agg")
    planned = experiments()
    planned[0].path = tmp_path / "elsewhere"
    questions = []

    def stop(question):
        questions.append(question)
        return False

    # confirm=... stops each experiment before its plane fit; confirm_between stops before the second one
    folders = run_substrate(substrate, planned, backend=dummy_backend, confirm=lambda question: False,
                            confirm_between=stop)

    assert folders == [tmp_path / "elsewhere" / "left"]
    assert questions == ["Start experiment right (2/2)?"]
    index = SubstrateStore(tmp_path / "root").get("TU-26-007").experiments
    assert [e["label"] for e in index] == ["TU-26-007-A"]
    assert Path(index[0]["path"]) == (tmp_path / "elsewhere" / "left").resolve()


def test_invalid_layout_creates_nothing(test_config, tmp_path, substrate):
    planned = experiments()
    planned[1].spec.center = Point2D(500, 20000)
    with pytest.raises(LayoutError, match="left overlaps right"):
        run_substrate(substrate, planned, backend="dummy")
    assert not (tmp_path / "root").exists()

