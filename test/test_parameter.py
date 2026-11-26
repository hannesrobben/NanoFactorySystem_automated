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


def _probe_class():
    from nanofactorysystem.parameter import Parameter

    class Probe(Parameter):
        _defaults = {"value": 1}

    return Probe


def test_incomplete_user_section_names_the_user_and_the_missing_keys():
    from nanofactorysystem.config import DEFAULT_CONFIG, use_config

    incomplete = {"name": "Lab User", "email": "lab@example.org"}           # no organization, no orcid (T111)
    with use_config(DEFAULT_CONFIG | {"user:Lab": incomplete}):
        try:
            _probe_class()("Lab", probe={})
        except KeyError as error:
            message = str(error)
        else:
            raise AssertionError("no error for an incomplete user section")
    assert "user:Lab" in message and "misses the keys organization, orcid" in message


def test_complete_user_section_works(test_config):
    assert _probe_class()("Test", probe={"value": 2})["value"] == 2
