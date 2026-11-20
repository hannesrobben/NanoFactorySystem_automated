"""The main entry point mains/main.py and the default experiment mains/Experiments/default_experiment.py (T110)."""
import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.programs.drawings.lines import Stair
from nanofactorysystem.devices.coordinate_system import Point3D
from nanofactorysystem.experiment_spec import ExperimentSpec
from nanofactorysystem.storage import ExperimentStore
from nanofactorysystem.structure_factories import BuildContext, FactoryCall
from nanofactorysystem.substrate_plan import check_layout

MAINS = Path(__file__).parents[2] / "mains"


def load(monkeypatch, relative: str, name: str):
    monkeypatch.syspath_prepend(str(MAINS))  # the main files import Experiments.… from mains/
    spec = importlib.util.spec_from_file_location(name, MAINS / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def main_module(monkeypatch):
    return load(monkeypatch, "main.py", "nanofactory_main")


@pytest.fixture
def template(monkeypatch):
    return load(monkeypatch, "Experiments/default_experiment.py", "default_experiment")


def small(spec: ExperimentSpec) -> ExperimentSpec:
    """ The spec with a smaller stair and without corners, to keep the dry runs short. """

    structures = list(spec.structures)
    if structures[0].structure is not None:
        stair = Stair(Point3D(0, 0, -1), n_steps=2, step_height=1.0, step_length=10, step_width=20,
                      socket_height=1.0, hatch_size=2.0, slice_size=1.0, velocity=10_000, acceleration=500_000)
        structures[0] = dataclasses.replace(structures[0], structure=stair)
    return dataclasses.replace(spec, structures=structures, skip_corner=True)


def test_default_experiment_shows_every_spec_field(template):
    import inspect
    source = inspect.getsource(template.experiment_spec)
    missing = [f.name for f in dataclasses.fields(ExperimentSpec) if f"{f.name}=" not in source]
    assert missing == []


def test_default_experiment_specs_are_valid_and_round_trip(template, test_config):
    for spec in (template.experiment_spec(), template.slicer_spec()):
        resolved = spec.resolved()  # grid holds all structures, SLICER has IFOV_on
        assert resolved.fov_um is not None
        again = ExperimentSpec.from_json(json.loads(json.dumps(spec.to_json())))
        assert [s.name for s in again.structures] == [s.name for s in spec.structures]
        assert again.to_json() == spec.to_json()


def test_rectangle_factory_uses_the_acceleration_of_its_axes(template):
    context = BuildContext(objective="Zeiss 63x", accel_x_um=1e6, accel_a_um=5e7)
    call = template.rectangle(size_um=50, height_um=3, hatch_um=0.5, slice_um=0.5, velocity_um_s=1000, stages=True)
    assert isinstance(call, FactoryCall)
    assert call.build(context).acceleration == 1e6
    galvo = template.rectangle(size_um=50, height_um=3, hatch_um=0.5, slice_um=0.5, velocity_um_s=1000, stages=False)
    assert galvo.build(context).acceleration == 5e7


def test_main_substrate_layout_is_valid(main_module, test_config):
    areas = check_layout(main_module.substrate_spec(), main_module.substrate_experiments())
    assert [a.name for a in areas] == ["drawing", "slicer"]


def test_main_rejects_unknown_tasks_and_demo_on_hardware(main_module):
    with pytest.raises(ValueError, match="Unknown task"):
        main_module.main("print_everything", dry=False)
    with pytest.raises(ValueError, match="dry run"):
        main_module.main("demo", dry=False)


def test_main_layout_and_materials_dry_run(main_module, test_config, tmp_path, capsys):
    main_module.main("layout", dry=True, workdir=tmp_path / "layout")
    assert (tmp_path / "layout" / "out" / "substrate_layout.png").is_file()
    main_module.main("materials", dry=True, workdir=tmp_path / "materials")
    output = capsys.readouterr().out
    assert "n(SZ2080, 674.994 nm, cured_in_resin) = 1.52" in output
    assert "Voxel size SZ2080" in output and "None" not in output.split("Voxel size")[1]


@pytest.mark.slow
def test_default_experiment_dry_run(template, test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    folder = template.main(small(template.experiment_spec()), user="Test", path=tmp_path / "out",
                           backend=dummy_backend, plane=dummy_backend.world.sample.plane())

    record = ExperimentStore.open(folder).read()
    assert record.status == "finished" and all(s.status == "printed" for s in record.structures)
    assert [s.name for s in record.structures] == ["stair", "rect", "rect_rep1", "power_ramp", "galvo_rect"]
    assert record.structure("power_ramp").layer_powers_mw == [0.6, 0.7, 0.8, 0.9]
    assert record.structure("rect_rep1").repeat_of == "rect"
    assert {c.kind for c in record.captures} == {"camera"}
    # The named factories are stored, so the project file can be run again
    stored = ExperimentSpec.load(folder / "experiment_spec.json")
    assert stored.structures[1].factory == template.experiment_spec().structures[1].factory


@pytest.mark.slow
def test_main_restart_and_analyse_dry_run(main_module, test_config, tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use("Agg")
    monkeypatch.setattr(main_module, "experiment_spec", lambda: small(main_module.default_experiment.experiment_spec()))

    folder = main_module.main("restart", dry=True, workdir=tmp_path)

    record = ExperimentStore.open(folder).read()
    assert record.status == "finished" and all(s.status == "printed" for s in record.structures)
    monkeypatch.setattr(main_module, "ANALYSE_FOLDER", folder)
    unpacked = main_module.main("analyse", dry=True, workdir=tmp_path / "analyse")
    assert (unpacked / "summary.txt").is_file()
