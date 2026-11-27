"""Line pairs with power switches for the lab check T148 (decision D9)."""
import importlib
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit
from nanofactorysystem.testprint.power_switch import PowerSwitchLines

MAINS = Path(__file__).parents[2] / "mains"


def test_rows_one_line_without_pause_then_one_per_dwell_5um_apart():
    structure = PowerSwitchLines(Point3D(0, 0, 0), dwells_s=(0.005, 0.02, 0.1, 0.5))
    rows = structure.line_rows()
    assert [d for _, d in rows] == [None, 0.005, 0.02, 0.1, 0.5]
    assert [y for y, _ in rows] == pytest.approx([10, 5, 0, -5, -10])  # centred, 5 µm apart


def test_z_levels_from_minus_1_to_plus_1_in_0_2_um_steps():
    structure = PowerSwitchLines(Point3D(0, 0, 0))
    assert structure.z_levels_um() == pytest.approx([-1 + 0.2 * k for k in range(11)])


def test_one_ifov_block_per_layer_with_the_switch_at_the_middle(synthetic_attenuator):
    structure = PowerSwitchLines(Point3D(0, 0, 0), dwells_s=(0.005, 0.5), settle_s=0.5)
    system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=20000.0, unit=Unit.um)
    layers = [layer.to_text(add_timestamp=False).splitlines() for layer in structure.iterate_layers(system)]
    assert len(layers) == 11
    lines = layers[0]
    assert "LOOKAHEAD FAST" not in lines
    assert sum(line == "IFOV ON" for line in lines) == 1
    assert any(line.startswith("RAPID X") and "Z19.999" in line for line in lines)   # z = -1 µm
    # line without pause: LINEAR to x = 0, power, LINEAR to the end
    first = [i for i, line in enumerate(lines) if line.startswith("LINEAR A0.0000000000")][0]
    assert lines[first + 1].startswith("'") and lines[first + 2].startswith("$AO")
    assert lines[first + 3].startswith("LINEAR A0.0250000000")
    # dwell lines: LINEAR, WAIT MOVEDONE, power, DWELL, LINEAR
    switches = [i for i, line in enumerate(lines) if line.startswith("LINEAR A0.0000000000")][1:]
    for i, dwell in zip(switches, ("0.005", "0.500")):
        assert lines[i + 1] == "WAIT MOVEDONE X Y A B"
        assert lines[i + 3].startswith("$AO") and lines[i + 4] == f"DWELL {dwell}"
        assert lines[i + 5].startswith("LINEAR A0.0250000000")
    # before every line: wait for the previous motion, low power, settle
    assert sum(line == "WAIT MOVEDONE X Y A B" for line in lines) == 3 + 2 + 1      # before lines, dwells, end
    power_values = [line for line in lines if line.startswith("$AO")]
    assert len(power_values) == 6 and len(set(power_values)) == 2
    assert structure_from_json(structure.to_json()).dwells_s == [0.005, 0.5]


def test_invalid_arguments():
    with pytest.raises(ValueError):
        PowerSwitchLines(Point3D(0, 0, 0), dwells_s=())
    with pytest.raises(ValueError):
        PowerSwitchLines(Point3D(0, 0, 0), dwells_s=(0.0,))
    with pytest.raises(ValueError):
        PowerSwitchLines(Point3D(0, 0, 0), z_min_um=1, z_max_um=-1)


@pytest.mark.slow
def test_lab_script_layout_and_dry_run(test_config, dummy_backend, no_sleep, tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use("Agg")
    monkeypatch.syspath_prepend(str(MAINS))
    script = importlib.import_module("lab_checks.power_switch_check")
    monkeypatch.setattr(script, "USER", "Test")
    assert script.main(layout_only=True, data_root=tmp_path / "layout") == []

    [folder] = script.main(backend=dummy_backend, plane=dummy_backend.world.sample.plane(), data_root=tmp_path / "data")

    from nanofactorysystem.storage import ExperimentStore
    record = ExperimentStore.open(folder).read()
    assert record.status == "finished"
    names = [s.name for s in record.structures if s.type in ("IFOV", "REPEAT")]
    assert names == ["power_switch"] + [f"power_switch_rep{k}" for k in range(1, script.REPETITIONS)]
    assert all(s.status == "printed" for s in record.structures if s.name in names)
    with pytest.raises(ValueError):
        script.experiment_spec(repetitions=11)
