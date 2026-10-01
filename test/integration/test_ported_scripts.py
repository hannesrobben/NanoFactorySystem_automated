"""The experiment scripts ported to ExperimentSpec (T51) build valid experiments."""
import importlib.util
from types import SimpleNamespace
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.programs.drawings import DrawableObject
from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment import StructureType

EXPERIMENTS = Path(__file__).parents[2] / "mains" / "Experiments"
# script -> objectives with a complete parameter set
PORTED = {
    "Kailas/parametric_4q.py": ("Zeiss 20x", "Zeiss 63x"),
    "Kailas/Quadrants_line_power_gap.py": ("Zeiss 20x", "Zeiss 63x"),
    "Kailas/lens_surface_test.py": ("Zeiss 63x",),
    "Kailas/zoffset_voxel__dose_test.py": ("Zeiss 20x", "Zeiss 63x"),
    "Kailas/Voxel_row_on_pad.py": ("Zeiss 20x", "Zeiss 63x"),
    "parameter_study/parameter_testprint_power_speed.py": ("Zeiss 63x",),
    "parameter_study/parameter_testprint_power_speed_test4orientation.py": ("Zeiss 63x",),
    "parameter_study/parameter_testprint_slicing_hatching.py": ("Zeiss 20x", "Zeiss 63x"),
    "parameter_study/line_test/Power_speed_line_test.py": ("Zeiss 63x",),
    "refractive_index/refractive_index_vel_power.py": ("Zeiss 63x",),
    "DHM_tomography/hollow_rect_first_print_63xobj.py": ("Zeiss 20x", "Zeiss 63x"),
    "Kailas/power_z_pitch_lines.py": ("Zeiss 20x", "Zeiss 63x"),
    "Big_substrate_20x/grating_ifov_test.py": ("Zeiss 20x", "Zeiss 63x"),
}


def load(script):
    spec = importlib.util.spec_from_file_location(Path(script).stem, EXPERIMENTS / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeExperiment:
    """ The values the structure factories read from a running experiment. """

    accel_a_um = 500_000.0
    accel_x_um = 1_000_000.0
    accel_z_um = 100_000.0
    # power range of the attenuator calibration (checked by power_z_pitch_lines)
    system = SimpleNamespace(controller=SimpleNamespace(attenuator={"powerMin": 0.0, "powerMax": 20.0}))


@pytest.mark.parametrize("script", sorted(PORTED))
def test_ported_script_builds_its_experiment(script, test_config):
    module = load(script)
    for objective in ("Zeiss 20x", "Zeiss 63x"):
        if objective not in PORTED[script]:
            with pytest.raises(ValueError):
                module.experiment_spec(objective=objective, absolute_center=Point2D(1310, 19500))
            continue
        spec = module.experiment_spec(objective=objective, absolute_center=Point2D(1310, 19500)).resolved()

        assert spec.objective == objective and spec.drop_direction is not None
        assert sum(1 + s.repeat for s in spec.structures) <= spec.grid[0] * spec.grid[1]
        assert spec.camera_capture and spec.opl_start_um == 350.0
        assert spec.sys_args["attenuator"]["fitKind"] == "quadratic" and "orientation" not in spec.sys_args["sample"]
        for structure in spec.structures:
            drawable = structure.drawable(spec.program_source, spec.objective, FakeExperiment())
            if structure.structure_type == StructureType.DUMMY:
                assert drawable is None
            else:
                assert isinstance(drawable, DrawableObject)


@pytest.mark.slow
def test_ported_script_dry_run(test_config, dummy_backend, no_sleep, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import dataclasses
    module = load("DHM_tomography/hollow_rect_first_print_63xobj.py")
    # Smaller than on the lab PC, to keep the test fast: two coarse structures, no corners
    module.GRID = (1, 2)
    module.PARAMETERS["Zeiss 63x"].update({"hatch size": 2.0, "slice size": 1.0})
    build_spec = module.experiment_spec
    module.experiment_spec = lambda *args, **kwargs: dataclasses.replace(build_spec(*args, **kwargs), skip_corner=True)

    folder = module.print_file(Point2D(1310, 19500), [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]],
                               path=tmp_path / "out", objective="Zeiss 63x", user="Test", backend=dummy_backend,
                               plane=dummy_backend.world.sample.plane())

    from nanofactorysystem.storage import ExperimentStore
    assert folder == tmp_path / "out" / "hollow_rect_first_print_9x_NEW_position"
    record = ExperimentStore.open(folder).read()
    assert record.status == "finished" and record.parameters["drop_direction"] == "DOWN"
    assert [s.name for s in record.structures if s.type == "NORMAL"] == ["Hollow_rectangle_0", "Hollow_rectangle_1"]
    assert record.parameters["margin_um"] == 50.0 and record.system["sys_args"]["controller"]["zMax"] == 25480.0
