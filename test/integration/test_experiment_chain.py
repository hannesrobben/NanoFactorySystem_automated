"""The experiment chain mains/Experiments/chain_rectangle_doe_lens.py (T113)."""
import dataclasses
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.height_map import HeightMap_IFOV
from nanofactorysystem.aerobasic.programs.drawings.ifov_gratings import Rectangle3D_IFOV
from nanofactorysystem.experiment import StructureType
from nanofactorysystem.experiment_spec import ExperimentSpec
from nanofactorysystem.structure_factories import BuildContext
from nanofactorysystem.substrate_plan import check_layout

MAINS = Path(__file__).parents[2] / "mains"
CONTEXT = BuildContext(objective="Zeiss 63x", setup="IFOV_on", power_min_mw=0.0, power_max_mw=20.0)


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.syspath_prepend(str(MAINS))  # the scripts import Experiments.… from mains/
    spec = importlib.util.spec_from_file_location("chain_rectangle_doe_lens",
                                                  MAINS / "Experiments" / "chain_rectangle_doe_lens.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_three_experiments_with_a_power_by_hatch_grid(chain, test_config):
    experiments = chain.experiments()
    assert [e.spec.name for e in experiments] == ["chain_rectangle", "chain_doe", "chain_lens"]
    for experiment in experiments:
        spec = experiment.spec.resolved()
        assert spec.objective == "Zeiss 63x" and spec.setup == "IFOV_on" and spec.grid == (3, 3)
        assert len(spec.structures) == 9
        assert spec.overview_capture and spec.camera_capture and not spec.dhm_usage
        # print order row by row: one row per power, one column per hatch distance
        for index, structure in enumerate(spec.structures):
            row, column = divmod(index, 3)
            assert structure.power_mw == [0.25, 0.5, 0.75][row]
            assert structure.factory.arguments["power_mw"] == structure.power_mw
            assert structure.factory.arguments["hatch_um"] == [0.2, 0.4, 0.6][column]
            assert structure.structure_type == StructureType.IFOV and structure.axes == "XYZ"


def test_rectangle_geometry(chain):
    rectangle = chain.rectangle(power_mw=0.5, hatch_um=0.4).build(CONTEXT)
    assert isinstance(rectangle, Rectangle3D_IFOV)
    assert (rectangle.x_length, rectangle.y_length, rectangle.height) == (50.0, 50.0, 6.0)
    assert rectangle.center.Z == -1.0 and rectangle.slice_size == 0.25
    assert rectangle.hatch_size == 0.4 and rectangle.power == 0.5
    assert rectangle.alternate_hatching  # cross hatching


def test_doe_geometry(chain):
    doe = chain.doe(power_mw=0.25, hatch_um=0.2, levels=chain.DOE_LEVELS).build(CONTEXT)
    assert isinstance(doe, HeightMap_IFOV)
    assert doe.height_map.shape == (5, 5) and doe.pixel_pitch == (10.0, 10.0)  # 5 x 5 fields of 10 µm
    assert set(np.unique(doe.height_map)) == {0.0, 0.5, 1.0, 1.5, 2.0, 2.5}
    assert doe.socket_height == 3.5 and doe.center.Z == -1.0 and doe.slice_size == 0.25
    assert doe.width == doe.length == 50.0
    # cross hatching with the same hatch and slice distance in the base and the fields
    assert doe.alternating_hatch and doe.socket_hatch_size == doe.hatch_size == 0.2
    assert doe.socket_slice_size == 0.25
    # the levels are fixed in the script, not drawn anew
    assert np.array_equal(np.asarray(chain.DOE_LEVELS),
                          np.random.default_rng(20261120).integers(0, 6, size=(5, 5)))


def test_lens_geometry(chain):
    assert chain.lens_aperture_radius(30.0, 2.3, 6.0) == pytest.approx(15.5306, abs=1e-4)
    assert chain.asphere_sag(15.5306, 30.0, 2.3) == pytest.approx(6.0, abs=1e-3)
    lens = chain.lens(power_mw=0.75, hatch_um=0.6, radius_um=30.0, conic=2.3, sag_um=6.0, pixel_um=0.2).build(CONTEXT)
    assert isinstance(lens, HeightMap_IFOV)
    assert lens.center.Z == -1.0 and lens.socket_height == 0.0 and lens.slice_size == 0.25
    assert lens.max_height == pytest.approx(6.0, abs=0.01)
    assert 31.0 <= lens.width <= 31.4                     # aperture diameter 31.06 µm
    heights = lens.height_map
    assert heights[0, 0] == 0.0                           # outside the aperture
    assert np.allclose(heights, heights[::-1, ::-1])      # rotationally symmetric map
    with pytest.raises(ValueError, match="reaches at most"):
        chain.lens_aperture_radius(30.0, 2.3, 10.0)


def test_power_outside_the_attenuator_range_is_refused(chain):
    with pytest.raises(ValueError, match="outside the attenuator calibration range"):
        chain.rectangle(power_mw=0.75, hatch_um=0.2).build(dataclasses.replace(CONTEXT, power_max_mw=0.5))


def test_specs_round_trip(chain, test_config):
    for experiment in chain.experiments():
        spec = experiment.spec
        again = ExperimentSpec.from_json(json.loads(json.dumps(spec.to_json())))
        assert again.to_json() == spec.to_json()
        running = SimpleNamespace(objective="Zeiss 63x", setup="IFOV_on")  # what the factories read
        built = [s.drawable(spec.program_source, spec.objective, running)
                 for s in (spec.structures[4], again.structures[4])]
        assert built[0].to_json() == built[1].to_json()


def test_layout_is_valid(chain, test_config):
    areas = check_layout(chain.substrate_spec(), chain.experiments())
    assert [a.name for a in areas] == ["chain_rectangle", "chain_doe", "chain_lens"]


def test_other_objectives_are_refused(chain):
    with pytest.raises(ValueError, match="Zeiss 63x"):
        chain.experiment_spec("lens", objective="Zeiss 20x")


@pytest.mark.slow
def test_lens_experiment_dry_run(chain, test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    from nanofactorysystem.experiment_spec import run_experiment
    from nanofactorysystem.storage import ExperimentStore

    spec = chain.experiment_spec("lens")
    # Smaller than on the lab PC, to keep the test short: the first row only, no corners
    spec = dataclasses.replace(spec, grid=(1, 3), skip_corner=True, structures=spec.structures[:3])
    folder = run_experiment(spec, user="Test", resin_edges=chain.RESIN_EDGES, path=tmp_path / "out",
                            backend=dummy_backend, plane=dummy_backend.world.sample.plane(), show_plot=False)

    record = ExperimentStore.open(folder).read()
    assert record.status == "finished"
    assert [s.name for s in record.structures if s.type == "IFOV"] == \
           ["lens_p0.25_h0.2", "lens_p0.25_h0.4", "lens_p0.25_h0.6"]
