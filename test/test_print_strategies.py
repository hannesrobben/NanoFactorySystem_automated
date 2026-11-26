"""Extension point for dynamic slicing and hatching per structure (T81)."""
import numpy as np
import pytest

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment import ProgramSource
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec
from nanofactorysystem.print_strategies import (UnknownStrategyError, get_print_strategy, print_strategy_names,
                                                register_print_strategy)

pytest.importorskip("trimesh")
pytest.importorskip("shapely")


@register_print_strategy("test_finer_hatch", "halves the hatch distance (test only)")
def finer_hatch(slicer: dict, parameters: dict) -> dict:
    return dict(slicer, hatch_size=slicer["hatch_size"] / parameters.get("factor", 2.0))


def block_spec(**structure):
    height = np.zeros((10, 10))
    height[2:8, 2:8] = 1.0
    return ExperimentSpec(name="strategy", objective="Zeiss 63x", center=Point2D(0, 0), grid=(1, 1),
                          program_source=ProgramSource.SLICER, setup="IFOV_on",
                          structures=[StructureSpec("block", height_data=height, power_mw=0.3,
                                                    slicer={"hatch_size": 0.5, "slice_size": 0.5, "pixel_size": 1.0,
                                                            "unit": "um", "velocity": 5},
                                                    **structure)])


def test_static_is_built_in_and_unknown_names_are_refused():
    assert "static" in print_strategy_names()
    assert get_print_strategy("static").apply({"hatch_size": 0.5}, {}) == {"hatch_size": 0.5}
    with pytest.raises(UnknownStrategyError, match="registered: .*static"):
        get_print_strategy("adaptive_magic")
    with pytest.raises(ValueError, match="takes no parameters"):
        get_print_strategy("static").apply({}, {"x": 1})


def test_a_registered_strategy_changes_the_slicer_arguments_and_is_stored(tmp_path):
    spec = block_spec(strategy="test_finer_hatch", strategy_params={"factor": 4.0})
    [structure] = spec.resolved().structures
    slicer = structure.drawable(ProgramSource.SLICER, "Zeiss 63x")
    assert slicer.params.slicing.hatch_spacing_um == pytest.approx(0.125)
    assert structure.slicer["hatch_size"] == 0.5                       # the spec itself is not changed

    loaded = ExperimentSpec.load(spec.save(tmp_path / "spec" / "experiment_spec.json"))
    assert loaded.structures[0].strategy == "test_finer_hatch"
    assert loaded.structures[0].strategy_params == {"factor": 4.0}


def test_unknown_strategy_and_strategy_on_a_drawing_are_refused():
    with pytest.raises(UnknownStrategyError):
        block_spec(strategy="adaptive_magic").resolved()
    from nanofactorysystem.aerobasic.programs.drawings import Rectangle3D
    from nanofactorysystem.devices.coordinate_system import Point3D
    drawing = StructureSpec("rect", Rectangle3D(Point3D(0, 0, -1), 10, 10, 1, hatch_size=1, slice_size=1,
                                                velocity=1000, acceleration=500), strategy="test_finer_hatch")
    with pytest.raises(ValueError, match="needs program source SLICER"):
        drawing.print_strategy(ProgramSource.DRAWING)


def test_specs_without_strategy_are_written_as_before():
    data = block_spec().to_json()
    assert "strategy" not in data["structures"][0]["settings"]
