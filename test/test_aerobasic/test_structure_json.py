"""Round trip of structures through DrawableObject.to_json() and structure_from_json() (T56)."""
import json
import warnings

import numpy as np
import pytest

from nanofactorysystem.aerobasic.programs.drawings import DrawableObject
from nanofactorysystem.aerobasic.programs.drawings.base import (decode_json_value, encode_json_value,
                                                                structure_from_json)
from nanofactorysystem.aerobasic.programs.drawings.lines import HatchingDirection
from nanofactorysystem.devices.coordinate_system import Point2D, Point3D

from test_aerobasic.test_golden_programs import CASES, render, synthetic_ifov_calibration  # noqa: F401 (fixture)

STRUCTURE_CASES = [case for case in sorted(CASES) if not case.startswith("setup_")]


def structure_of(case):
    """ The structure a golden case renders (the golden module builds it inside a lambda). """

    from test_aerobasic import test_golden_programs as golden
    captured = []
    original = golden.render

    def capture(setup, structure=None, drop_direction=None):
        captured.append(structure)
        return ""

    golden.render = capture
    try:
        CASES[case]()
    finally:
        golden.render = original
    return captured[0]


@pytest.mark.parametrize("case", STRUCTURE_CASES)
def test_structure_round_trip(case):
    structure = structure_of(case)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no argument may be lost
        data = json.loads(json.dumps(structure.to_json()))

    rebuilt = structure_from_json(data)

    assert type(rebuilt) is type(structure)
    assert "__missing__" not in data
    assert json.loads(json.dumps(rebuilt.to_json())) == data
    # The rebuilt structure writes exactly the same programs
    assert render(structure_setup(case), rebuilt) == render(structure_setup(case), structure)


def structure_setup(case):
    from nanofactorysystem.aerobasic.programs.setups import DefaultSetup
    return DefaultSetup()


def test_values_are_encoded_reversibly():
    values = [None, 1, 2.5, "text", HatchingDirection.X, Point3D(1.0, 2.0, 3.0), Point2D(4.0, 5.0),
              np.arange(6.0).reshape(2, 3), [HatchingDirection.Y, 1], {"a": Point2D(1.0, 2.0)}]
    for value in values:
        restored = decode_json_value(json.loads(json.dumps(encode_json_value(value))))
        if isinstance(value, np.ndarray):
            assert np.array_equal(restored, value) and restored.dtype == value.dtype
        else:
            assert restored == value
    with pytest.raises(TypeError):
        encode_json_value(object())


class _Lossy(DrawableObject):
    def __init__(self, center: Point2D, secret: float):
        super().__init__()
        self.center = center

    @property
    def center_point(self):
        return self.center

    def iterate_layers(self, coordinate_system):
        yield from ()


def test_lost_arguments_are_reported():
    with pytest.warns(UserWarning, match="secret"):
        data = _Lossy(Point2D(0.0, 0.0), 1.0).to_json()

    assert data["__missing__"] == ["secret"]
    with pytest.raises(ValueError, match="secret"):
        structure_from_json(data)
    with pytest.raises(ValueError, match="__module__"):
        structure_from_json({"__class__": "Stair", "__init__": {}})
