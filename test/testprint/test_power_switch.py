"""Line pairs with power switches for the lab check T148 (decision D9)."""
import importlib
from pathlib import Path

import pytest

from nanofactorysystem.aerobasic.programs.drawings.base import structure_from_json
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, Point3D, Unit
from nanofactorysystem.testprint.power_switch import PowerSwitchLines

MAINS = Path(__file__).parents[2] / "mains"


def program_lines(structure):
    system = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=20000.0, unit=Unit.um)
    [layer] = list(structure.iterate_layers(system))
    return layer.to_text(add_timestamp=False).splitlines()


def test_rows_pairs_2um_apart_and_reference_lines():
    structure = PowerSwitchLines(Point3D(0, 0, 0), repetitions=3)
    rows = structure.line_rows()
    kinds = [k for _, k in rows]
    assert kinds == ["switch", "dwell"] * 3 + ["reference_low", "reference_high"]
    assert rows[0][0] - rows[1][0] == pytest.approx(2.0) and rows[0][0] - rows[2][0] == pytest.approx(6.0)
    assert rows[0][0] == pytest.approx(-rows[-1][0])                     # centred


def test_one_block_per_segment_and_dwell_only_on_the_dwell_line(synthetic_attenuator):
    structure = PowerSwitchLines(Point3D(0, 0, 0), repetitions=2, dwell_s=0.05, n_segments=4)
    lines = program_lines(structure)

    power_lines = [line for line in lines if line.startswith("$AO[0].A=")]
    dwells = [line for line in lines if line.startswith("DWELL")]
    assert len(power_lines) == 2 * 2 * 4 + 2                            # segments of 4 lines + 2 references
    assert len(dwells) == 2 * 4 and all(float(line.split()[1]) == 0.05 for line in dwells)
    for index, line in enumerate(lines):
        if line.startswith("DWELL"):
            assert lines[index - 2].startswith("$AO[0].A=")             # comment line between power and dwell
    assert structure_from_json(structure.to_json()).dwell_s == 0.05


def test_invalid_arguments():
    with pytest.raises(ValueError):
        PowerSwitchLines(Point3D(0, 0, 0), n_segments=1)
    with pytest.raises(ValueError):
        PowerSwitchLines(Point3D(0, 0, 0), dwell_s=-1)


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
    assert [s.name for s in record.structures if s.type == "IFOV"] == ["dwell_10ms", "dwell_50ms", "dwell_200ms"]
