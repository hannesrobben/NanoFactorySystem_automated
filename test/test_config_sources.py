"""Tests for config sources, the built-in default and lazily resolved defaults."""
import json

import pytest

from nanofactorysystem.config import (
    CONFIG_ENV_VAR, DEFAULT_CONFIG, Config, ConfigDefaults, sysConfig, use_config)


def test_missing_file_falls_back_to_builtin_default(tmp_path):
    with pytest.warns(UserWarning, match="built-in default"):
        config = Config(tmp_path / "does_not_exist.json")

    assert config.path is None
    assert config.objectives() == ["Zeiss 20x", "Zeiss 63x"]
    assert config.users() == []
    assert config.section("attenuator") == {}


def test_env_var_selects_config_file(tmp_path, monkeypatch):
    path = tmp_path / "nf.json"
    path.write_text(json.dumps({"user:Env": {"name": "Env User"}}))
    monkeypatch.setenv(CONFIG_ENV_VAR, str(path))

    config = Config()

    assert config.path == path
    assert config.user("Env")["name"] == "Env User"


def test_missing_section_is_empty_dict():
    config = Config({"system": {"a": 1}})

    assert config.section("system") == {"a": 1}
    assert config.section("camera") == {}


def test_use_config_replaces_in_place_and_restores():
    before = sysConfig.config

    with use_config({"user:Test": {"name": "Test User"}}) as config:
        assert config is sysConfig
        assert sysConfig.user("Test") == {"name": "Test User", "key": "Test"}

    assert sysConfig.config is before


def test_use_config_restores_after_exception():
    before = sysConfig.config

    with pytest.raises(ValueError):
        with use_config({}):
            raise ValueError("boom")

    assert sysConfig.config is before


class _Dummy:
    _defaults = ConfigDefaults("section", {"local": 1, "shared": "local", "tasks": {}},
                               from_config=("fromcfg",))


def test_config_defaults_merge_order_and_from_config():
    with use_config({"section": {"shared": "config", "extra": 2, "fromcfg": "x"}}):
        defaults = _Dummy._defaults

    # Class defaults win over config items, as with the previous "section | {...}"
    assert defaults == {"shared": "local", "extra": 2, "local": 1, "tasks": {}, "fromcfg": "x"}


def test_config_defaults_follow_active_config():
    with use_config({"section": {"extra": 1}}):
        assert _Dummy._defaults["extra"] == 1
    with use_config({"section": {"extra": 2}}):
        assert _Dummy._defaults["extra"] == 2


def test_config_defaults_do_not_share_mutable_values():
    with use_config({}):
        first = _Dummy._defaults
        first["tasks"]["zline"] = 1
        assert _Dummy._defaults["tasks"] == {}
        assert _Dummy._defaults["fromcfg"] is None


def test_default_config_is_not_modified_by_load():
    config = Config(DEFAULT_CONFIG)
    config.config["controller"]["port"] = 1

    assert DEFAULT_CONFIG["controller"]["port"] == 8000
