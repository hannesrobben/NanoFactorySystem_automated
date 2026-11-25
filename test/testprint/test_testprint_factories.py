"""Named structure factories ptd01.f0 … ptd01.f7 (T144)."""
import json

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("shapely")

from ptd_examples import EXAMPLE_CALIBRATION, EXAMPLE_STAGE_A  # noqa: E402
from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json  # noqa: E402
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point2D, Unit  # noqa: E402
from nanofactorysystem.experiment import ProgramSource, StructureType  # noqa: E402
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec  # noqa: E402
from nanofactorysystem.structure_factories import BuildContext, factory_names  # noqa: E402
from nanofactorysystem.testprint import factories  # noqa: E402
from nanofactorysystem.testprint.structure import ParameterFieldStructure  # noqa: E402

CONTEXT = BuildContext(objective="Zeiss 63x", setup="IFOV_on", power_min_mw=0.05, power_max_mw=2.0)
OFFLINE = BuildContext(objective="", setup="IFOV_on")


def programs(structure):
    coordinate_system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=0.0, unit=Unit.um)
    return ["\n".join(map(str, layer.lines)) for layer in structure.iterate_layers(coordinate_system)]


def spec_with(call):
    return ExperimentSpec(name="ptd01_test", objective="Zeiss 63x", center=Point2D(0, 0), grid=(1, 1),
                          structures=[StructureSpec("F3", factory=call, power_mw=0.7, axes="XYZ",
                                                    structure_type=StructureType.IFOV)],
                          program_source=ProgramSource.DRAWING, setup="IFOV_on")


def test_every_field_has_a_registered_factory():
    assert {f"ptd01.f{i}" for i in range(8)} <= set(factory_names())
    assert sorted(factories.FACTORIES) == list(range(8))


def test_spec_round_trip_rebuilds_identical_programs(synthetic_attenuator, test_config):
    call = factories.f3_line_pairs(calibration=EXAMPLE_CALIBRATION.to_json(), label_power_mw=0.7,
                                   dwell_after_power_s=0.02)
    spec = spec_with(call)
    again = ExperimentSpec.from_json(json.loads(json.dumps(spec.to_json())))
    assert again.to_json() == spec.to_json()
    built = [s.structures[0].drawable(s.program_source, s.objective, CONTEXT) for s in (spec, again)]
    assert all(isinstance(b, ParameterFieldStructure) for b in built)
    assert programs(built[0]) == programs(built[1])
    assert "DWELL 0.020" in programs(built[0])[0]
    # the structure itself round-trips too (restart from the experiment file)
    rebuilt = structure_from_json(json.loads(json.dumps(built[0].to_json())))
    assert programs(rebuilt) == programs(built[0])


def test_structure_arguments_are_the_field_arguments():
    structure = factories.f4_squares(calibration=EXAMPLE_CALIBRATION.to_json(), label_power_mw=0.7,
                                     h_rel=[0.5, 1.0]).build(CONTEXT)
    assert structure.builder == "ptd01.f4" and structure.objective == "Zeiss 63x"
    assert structure.arguments["h_rel"] == [0.5, 1.0] and structure.arguments["calibration"]["p_th_mw"] == 0.3
    assert structure.power_mw == 0.7 and len(structure.field.cells) == 4 * 2


def test_out_of_range_power_raises_before_any_program():
    narrow = BuildContext(objective="Zeiss 63x", setup="IFOV_on", power_min_mw=0.05, power_max_mw=0.6)
    with pytest.raises(ValueError, match="outside the attenuator calibration range"):
        factories.f1_lines(calibration=EXAMPLE_CALIBRATION.to_json(), label_power_mw=0.7).build(narrow)
    with pytest.raises(ValueError, match="outside the attenuator calibration range"):
        factories.f0_interface(stage_a=EXAMPLE_STAGE_A.to_json()).build(narrow)


def test_offline_build_without_a_known_range():
    structure = factories.f0_interface(stage_a=EXAMPLE_STAGE_A.to_json()).build(OFFLINE)
    assert structure.objective == "Zeiss 63x"           # default objective when the context has none
    assert len(structure.field.cells) == 80
