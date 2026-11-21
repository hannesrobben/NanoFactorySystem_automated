"""Project-file form of ExperimentSpec / StructureSpec and named structure factories (T77)."""
import json
import math
from types import SimpleNamespace

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings.lines import Rectangle3D
from nanofactorysystem.devices.coordinate_system import DropDirection, Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource, StructureType
from nanofactorysystem.experiment_spec import (SPEC_SCHEMA, CornerSpec, ExperimentSpec, SpecSerialisationError,
                                               StructureSpec)
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.structure_factories import (BuildContext, FactoryCall, _REGISTRY, factory_from_json,
                                                   factory_names, structure_factory)


@structure_factory("test.rectangle")
def rectangle(context: BuildContext, *, hatch: float, slice_size: float = 1.0):
    """ A rectangle whose acceleration comes from the context. """

    return Rectangle3D(Point3D(0, 0, -1), 20, 20, 2, hatch_size=hatch, slice_size=slice_size, velocity=1000,
                       acceleration=context.accel_a_um)


RECT = Rectangle3D(Point3D(0, 0, 0), 1, 1, 1, hatch_size=0.5, slice_size=0.5, velocity=1000, acceleration=500)


def full_spec(**kwargs) -> ExperimentSpec:
    values = dict(
        name="full", objective="Zeiss 63x", center=Point2D(1200.0, -350.0), grid=(2, 3),
        description="all fields", tags=["test"], drop_direction=DropDirection.DOWN, plane_fit_mode=PlaneFitMode.GRID,
        corner=CornerSpec(width_um=30.0), fov_um=150.0, dhm_usage=True, camera_capture=True, opl_start_um=350.0,
        materials={"resin": "SZ2080"}, voxel_material="SZ2080",
        structures=[
            StructureSpec("rect", Rectangle3D(Point3D(0, 0, -1), 20, 20, 2, hatch_size=2.0, slice_size=1.0,
                                              velocity=1000, acceleration=500), power_mw=1.2, axes="XYZ",
                          repeat=1, layer_power=[1.0, 1.1]),
            StructureSpec.empty(),
            StructureSpec("made", factory=rectangle(hatch=0.5), structure_type=StructureType.NORMAL),
        ])
    values |= kwargs
    return ExperimentSpec(**values)


def test_round_trip_keeps_every_field():
    spec = full_spec()
    data = json.loads(json.dumps(spec.to_json()))
    assert data["schema"] == SPEC_SCHEMA and data["center_um"] == [1200.0, -350.0]
    assert data["placement"]["drop_direction"] == "DOWN" and data["placement"]["margin_um"] is None
    assert data["structures"][1]["geometry"] == {"kind": "empty"}
    assert data["structures"][2]["geometry"]["name"] == "test.rectangle"

    again = ExperimentSpec.from_json(data)

    assert json.loads(json.dumps(again.to_json())) == data
    assert (again.center, again.grid, again.drop_direction, again.corner) == \
           (spec.center, spec.grid, DropDirection.DOWN, spec.corner)
    assert again.margin_um is None  # "default of the objective" survives as null
    assert again.structures[1].structure_type == StructureType.DUMMY
    assert isinstance(again.structures[2].factory, FactoryCall)
    assert again.structures[0].layer_power == [1.0, 1.1]


def test_named_factory_builds_with_the_context_of_the_experiment():
    experiment = SimpleNamespace(objective="Zeiss 63x", setup="IFOV_off", accel_a_um=123.0)
    call = rectangle(hatch=0.5)
    assert call == FactoryCall("test.rectangle", {"hatch": 0.5})
    assert "test.rectangle" in factory_names()

    built = StructureSpec("s", factory=call).drawable(ProgramSource.DRAWING, "Zeiss 63x", experiment)
    assert built.acceleration == 123.0 and built.hatch_size == 0.5
    context = BuildContext.from_experiment(experiment)
    assert context.objective == "Zeiss 63x" and math.isnan(context.accel_x_um) and context.power_max_mw is None
    with pytest.raises(TypeError, match="test.rectangle"):
        rectangle(hatchsize=0.5)  # wrong argument name, caught when the spec is written
    with pytest.raises(ValueError, match="already registered"):
        structure_factory("test.rectangle")(lambda context: None)


def test_context_power_check():
    context = BuildContext(power_min_mw=0.1, power_max_mw=2.0)
    context.check_power(0.1, 2.0)
    with pytest.raises(ValueError, match=r"\[3.0\]"):
        context.check_power(1.0, 3.0)
    with pytest.raises(ValueError, match="unknown"):
        BuildContext().check_power(1.0)


def test_factory_is_imported_when_not_registered():
    data = rectangle(hatch=0.5).to_json()
    entry = _REGISTRY.pop("test.rectangle")
    try:
        call = factory_from_json(dict(data, module="not.a.module"))  # falls back to the source file
        assert call.arguments == {"hatch": 0.5} and "test.rectangle" in _REGISTRY
        _REGISTRY.pop("test.rectangle")
        with pytest.raises(KeyError, match="not registered"):
            factory_from_json(dict(data, module="not.a.module", file=""))
    finally:
        _REGISTRY["test.rectangle"] = entry


@pytest.mark.parametrize("structure, field", [
    (StructureSpec("plain", factory=lambda experiment: None), "factory"),
    (StructureSpec("fn", RECT, layer_power=lambda layer: 1.0), "layer_power"),
    (StructureSpec("obj", height_data=np.zeros((2, 2)), slicer={"power_map": lambda z, role: 1.0}), "slicer.power_map"),
    (StructureSpec("both", RECT, factory=rectangle(hatch=1.0)), "factory"),
    (StructureSpec("none"), "geometry"),
    (StructureSpec("bad", factory=FactoryCall("test.rectangle", {"hatch": object()})), "factory"),
])
def test_unstorable_fields_are_named(structure, field):
    with pytest.raises(SpecSerialisationError, match=rf"Structure '{structure.name}', field '{field}'"):
        full_spec(structures=[structure]).to_json()


def test_unstorable_sys_args_are_named():
    spec = full_spec(sys_args={"focus": {"callback": print}})
    with pytest.raises(SpecSerialisationError, match="sys_args.focus"):
        spec.to_json()


def test_reading_refuses_typos_and_other_major_versions():
    data = full_spec().to_json()
    with pytest.raises(SpecSerialisationError, match="Unknown keys \\['gird'\\]"):
        ExperimentSpec.from_json(dict(data, gird=[1, 1]))
    with pytest.raises(SpecSerialisationError, match="placement"):
        ExperimentSpec.from_json(dict(data, placement=dict(data["placement"], margin=1.0)))
    with pytest.raises(SpecSerialisationError, match="Unsupported schema"):
        ExperimentSpec.from_json(dict(data, schema="nanofactory.experiment_spec/2"))
    assert ExperimentSpec.from_json(dict(data, schema="nanofactory.experiment_spec/1.3")).name == "full"
    # unknown keys inside sys_args are passed on untouched
    runtime = dict(data["runtime"], sys_args={"future_tool": {"x": 1}})
    assert ExperimentSpec.from_json(dict(data, runtime=runtime)).sys_args == {"future_tool": {"x": 1}}


def test_slicer_inputs_inline_in_folder_and_as_file(tmp_path):
    height = np.arange(12.0).reshape(3, 4)
    spec = full_spec(structures=[StructureSpec("block", height_data=height, slicer={"pixel_size": 1.0})])

    inline = spec.to_json()["structures"][0]["geometry"]
    assert "inline" in inline["source"] and inline["slicer"] == {"pixel_size": 1.0}
    assert np.array_equal(ExperimentSpec.from_json(spec.to_json()).structures[0].height_data, height)

    path = spec.save(tmp_path / "project" / "experiment_spec.json")
    assert json.loads(path.read_text())["structures"][0]["geometry"]["source"]["array"] == "inputs/block_height.npy"
    assert np.array_equal(ExperimentSpec.load(path).structures[0].height_data, height)

    np.save(tmp_path / "project" / "inputs" / "block_height.npy", height + 1, allow_pickle=False)
    with pytest.raises(SpecSerialisationError, match="differs"):
        ExperimentSpec.load(path)

    mesh = tmp_path / "lens.stl"
    mesh.write_text("solid lens\nendsolid lens\n")
    by_file = full_spec(structures=[StructureSpec("lens", height_data=mesh)])
    assert by_file.to_json()["structures"][0]["geometry"]["source"]["file"] == str(mesh.resolve())
    copied = by_file.save(tmp_path / "other" / "experiment_spec.json")
    assert ExperimentSpec.load(copied).structures[0].height_data == tmp_path / "other" / "inputs" / "lens.stl"


def test_structure_file_on_its_own():
    data = dict(full_spec().structures[0].to_json(), schema="nanofactory.structure_spec/1")
    structure = StructureSpec.from_json(data)
    assert (structure.name, structure.axes, structure.power_mw, structure.repeat) == ("rect", "XYZ", 1.2, 1)
    with pytest.raises(SpecSerialisationError, match="unknown geometry kind"):
        StructureSpec.from_json(dict(data, geometry={"kind": "mesh"}))


def test_center_given_as_pair_becomes_point2d():
    """A center written as a plain (x, y) tuple is converted, so substrate_plan can use it."""
    from nanofactorysystem.substrate_plan import experiment_area

    spec = ExperimentSpec(name="pair", objective="Zeiss 20x", center=(500, -25000), grid=(1, 1))
    assert spec.center == Point2D(500.0, -25000.0)
    area = experiment_area(spec)
    assert area.name == "pair"
    with pytest.raises(TypeError, match="center"):
        ExperimentSpec(name="bad", objective="Zeiss 20x", center=500, grid=(1, 1))
