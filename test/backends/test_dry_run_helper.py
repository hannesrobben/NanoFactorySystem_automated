"""The dry-run helper for main scripts (nanofactorysystem.backends.dummy.dry_run, T110)."""
import time

import pytest

from nanofactorysystem.backends.dummy import DummyBackend
from nanofactorysystem.backends.dummy.dry_run import DRY_RUN_USER, dry_run, dry_run_config
from nanofactorysystem.config import DEFAULT_CONFIG, sysConfig, use_config


def test_dry_run_config_adds_missing_user_and_objectives():
    base = {"user:Known": {"name": "Known User"}, "objective:Zeiss 20x": {"magnification": 21.0}}
    config, added = dry_run_config("New", base)
    assert added == ["objective:Zeiss 63x", "user:New"]
    assert config["user:New"] == dict(DRY_RUN_USER, name="New")
    assert config["objective:Zeiss 63x"] == DEFAULT_CONFIG["objective:Zeiss 63x"]
    # Existing sections are kept unchanged, and the base is not modified
    assert config["objective:Zeiss 20x"] == {"magnification": 21.0}
    assert config["user:Known"] == {"name": "Known User"}
    assert "user:New" not in base


def test_dry_run_config_changes_nothing_for_a_known_user():
    base = DEFAULT_CONFIG | {"user:Test": {"name": "Test User"}}
    config, added = dry_run_config("Test", base)
    assert added == [] and config == base


def test_dry_run_restores_sleep_and_config(tmp_path):
    original_sleep = time.sleep
    with use_config(DEFAULT_CONFIG):
        with pytest.warns(UserWarning, match="user:Somebody"):
            with dry_run("Somebody", workdir=tmp_path) as simulated:
                assert isinstance(simulated.backend, DummyBackend)
                assert simulated.workdir == tmp_path
                assert sysConfig.user("Somebody")["email"] == DRY_RUN_USER["email"]
                assert simulated.plane(0.0, 0.0) == simulated.backend.world.sample.c
                before = simulated.backend.world.clock.now
                time.sleep(100.0)  # virtual: advances the simulated clock only
                assert simulated.backend.world.clock.now == before + 100.0
        assert time.sleep is original_sleep
        assert "Somebody" not in sysConfig.users()


def test_dry_run_restores_sleep_after_an_error(tmp_path):
    original_sleep = time.sleep
    with use_config(DEFAULT_CONFIG | {"user:Test": DRY_RUN_USER}):
        with pytest.raises(RuntimeError, match="boom"):
            with dry_run("Test", workdir=tmp_path):
                raise RuntimeError("boom")
    assert time.sleep is original_sleep
