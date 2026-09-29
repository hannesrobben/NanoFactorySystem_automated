"""Tests for the Parameter base class (parameter.py)."""
import copy

from nanofactorysystem import System
from nanofactorysystem.backends import DummyBackend


def test_argument_dictionaries_are_not_modified(test_config, tmp_path):
    sys_args = {
        "attenuator": {"fitKind": "quadratic"},
        "controller": {"zMax": 25000.0},
        "camera": {"ExposureTime": 10000},
        "dhm": {"oplStep": 100.0},
        "system": {"speed": 1000.0},
    }
    original = copy.deepcopy(sys_args)

    for i in range(2):
        backend = DummyBackend(workdir=tmp_path / f"dummy{i}")
        with System("Test", "Zeiss 20x", backend=backend, **sys_args) as system:
            assert system.controller["zMax"] == 25000.0
            assert system.controller.attenuator["fitKind"] == "quadratic"
            assert system.camera["ExposureTime"] == 10000
            assert system["speed"] == 1000.0

    assert sys_args == original
