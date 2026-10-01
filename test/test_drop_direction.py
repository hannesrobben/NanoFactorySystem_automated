"""The drop direction changes the print order and the interface choice, never the z coordinates (T43)."""
import re

import pytest

from nanofactorysystem.aerobasic.programs.drawings.qr_code import QRCode
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, DropDirection, Point3D, Unit
from nanofactorysystem.parameter import Interface, Result
from nanofactorysystem.storage import ExperimentStore
from nanofactorysystem.tools.detector import Scanner
from nanofactorysystem.tools.layer import Layer

from test_experiment import add_rectangle, make_experiment


def scanner(drop_direction):
    return Scanner(100.0, 10.0, 0.0, 200.0, drop_direction, Interface.BOTH, 1.5, 0.3, 0.5)


@pytest.mark.parametrize("drop_direction, kept, limit", [
    (DropDirection.DOWN, (45.0, 55.0), ("zmax", 145.0)),  # e.g. the oil interface above is ignored
    (DropDirection.UP, (145.0, 155.0), ("zmin", 55.0)),  # the interface with the higher z is decisive
])
def test_scanner_keeps_the_resin_layer(drop_direction, kept, limit):
    s = scanner(drop_direction)
    s.register(50.0, 10.0, Result.HIT)
    s.register(150.0, 10.0, Result.HIT)

    assert (s.hit.lowest.low, s.hit.lowest.high) == kept
    assert getattr(s, limit[0]) == limit[1]


def test_layer_default_keeps_the_former_behaviour():
    # Before T43 the scanner always kept the lowest range, which is the rule for DOWN
    assert Layer._defaults["dropDirection"] == "DOWN"


def test_experiment_passes_the_drop_direction_to_the_tools(test_config, dummy_backend, no_sleep, tmp_path):
    path = tmp_path / "experiment"
    path.mkdir()
    with make_experiment(path, dummy_backend, drop_direction=DropDirection.DOWN) as experiment:
        assert experiment.sys_args["layer"]["dropDirection"] == "DOWN"
    stored = ExperimentStore.open(path).read().system["sys_args"]
    assert stored["layer"]["dropDirection"] == "DOWN"

    from nanofactorysystem.experiment import Experiment
    given = {"attenuator": {"fitKind": "quadratic"}}
    assert Experiment._with_drop_direction(given, DropDirection.UP)["layer"] == {"dropDirection": "UP"}
    assert given == {"attenuator": {"fitKind": "quadratic"}}  # the caller's dictionary is not changed
    with pytest.raises(ValueError, match="dropDirection"):
        Experiment._with_drop_direction({"layer": {"dropDirection": "UP"}}, DropDirection.DOWN)


def print_order_and_programs(drop_direction, dummy_backend, tmp_path):
    path = tmp_path / drop_direction.name
    path.mkdir()
    with make_experiment(path, dummy_backend, drop_direction=drop_direction) as experiment:
        experiment.plane_fit(plane=dummy_backend.world.sample.plane())
        add_rectangle(experiment)
        experiment.build_programs()
        experiment.print_experiment()
        files = experiment.structure_configs[0]["layer_files"]
    store = ExperimentStore.open(path)
    order = [event["layer_id"] for event in store.read().progress["rect"]]
    # Program text without the header line with the creation time
    programs = ["\n".join(line for line in open(f).read().splitlines() if not line.startswith("'"))
                for f in files]
    return order, programs


def test_up_and_down_write_the_same_layers_in_opposite_order(test_config, dummy_backend, no_sleep, tmp_path):
    up_order, up_programs = print_order_and_programs(DropDirection.UP, dummy_backend, tmp_path)
    down_order, down_programs = print_order_and_programs(DropDirection.DOWN, dummy_backend, tmp_path)

    assert up_programs == down_programs  # identical z coordinates
    assert up_order == sorted(up_order) and len(up_order) > 1
    assert down_order == up_order[::-1]


def pixel_line_z(drop_direction):
    cs = CoordinateSystem(offset_x=0.0, offset_y=0.0, z_function=20000.0, drop_direction=drop_direction,
                          unit=Unit.um)
    qr = QRCode(Point3D(0, 0, -1), "NFS", pixel_pitch=2.0, base_height=1.0, anchor_height=1.0, pixel_height=1.0,
                hatch_size=1.0, slice_size=1.0, horizontal_velocity=1000, horizontal_acceleration=500,
                vertical_velocity=500, vertical_acceleration=100)
    text = qr.pixel_program(cs).to_text(add_timestamp=False)
    return [float(z) for z in re.findall(r"LINEAR .*Z([-\d.]+)", text)]


def test_qr_code_pixel_lines_follow_the_drop_direction():
    up, down = pixel_line_z(DropDirection.UP), pixel_line_z(DropDirection.DOWN)

    assert up and sorted(set(up)) == sorted(set(down))  # same heights
    assert up[0] > up[1] and down[0] < down[1]  # drawn downwards for UP, upwards for DOWN
