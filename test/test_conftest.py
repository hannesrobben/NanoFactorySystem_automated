"""Tests for the shared fixtures and the hardware marker handling in conftest.py."""
from pathlib import Path

import pytest

from nanofactorysystem.backends import DummyBackend
from nanofactorysystem.config import sysConfig

pytest_plugins = ["pytester"]

CONFTEST = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")

HARDWARE_TEST = """
import pytest

@pytest.mark.hardware
def test_needs_lab():
    pass

def test_plain():
    pass
"""


def test_hardware_tests_are_skipped_by_default(pytester):
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(HARDWARE_TEST)

    result = pytester.runpytest("-rs", "-p", "no:cacheprovider")

    result.assert_outcomes(passed=1, skipped=1)
    result.stdout.fnmatch_lines(["*needs the lab hardware; run with --run-hardware*"])


def test_hardware_tests_run_with_option(pytester):
    pytester.makeconftest(CONFTEST)
    pytester.makepyfile(HARDWARE_TEST)

    result = pytester.runpytest("--run-hardware", "-m", "hardware", "-p", "no:cacheprovider")

    result.assert_outcomes(passed=1, deselected=1)


def test_test_config_fixture(test_config):
    assert test_config is sysConfig
    assert sysConfig.users() == ["Test"]
    assert sysConfig.objectives() == ["Zeiss 20x", "Zeiss 63x"]


def test_tmp_program_dir(tmp_program_dir, tmp_path):
    assert tmp_program_dir.is_dir()
    assert tmp_program_dir.parent == tmp_path
    assert list(tmp_program_dir.iterdir()) == []


def test_dummy_controller(dummy_controller, dummy_backend, tmp_program_dir):
    dummy_controller.api.ABSOLUTE()

    assert dummy_backend.calllog.commands() == ["ABSOLUTE"]
    assert dummy_controller.program_dir == tmp_program_dir


def test_dummy_system(dummy_system, dummy_backend):
    assert isinstance(dummy_system.backend, DummyBackend)
    assert dummy_system.backend is dummy_backend
    assert dummy_system.controller["zMax"] == 25000.0


def test_no_sleep_advances_virtual_clock(no_sleep, dummy_backend):
    import time

    time.sleep(3.0)

    assert dummy_backend.world.clock.now == pytest.approx(3.0)
