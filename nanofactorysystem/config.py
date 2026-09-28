##########################################################################
# Copyright (c) 2024 Reinhard Caspary                                    #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module reads the configuration file of the NanoFactorySystem package
# as object sysConfig, which is an instance of the class Config. Without a
# config file, a built-in default is used. It also provides use_config() to
# switch the configuration temporarily, the descriptor ConfigDefaults for
# lazily resolved class defaults, and the helper function popargs, which
# takes one or more sections from a runtime configuration dictionary.
#
##########################################################################

import copy
import json
import os
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal


# def norm_orcid(orcid):

#     """ Return normalized ORCiD string if the given string is a valid ORCiD
#     and None otherwise. In fact, it currently only checks if the string is a
#     valid International Standard Name Identifier (ISNI). ORCiD uses a certain
#     ISNI number space, which is not tested here. """

#     assert isinstance(orcid, str)

#     # Pick all digits and normalize
#     orcid = orcid.replace("-", "").replace(" ", "").upper()
#     if len(orcid) != 16:
#         return None

#     # Calculate checksum product
#     R = 2
#     M = 11
#     try:
#         product = 0
#         for digit in orcid[:-1]:
#             product = ((int(digit) + product) * R) % M
#     except ValueError:
#         return None

#     # Calculate checksum digit
#     check = (M + 1 - product) % M
#     check = "0123456789X"[check]
#     if orcid[-1] != check:
#         return None

#     # Return pretty formatted ORCiD string
#     return orcid[:4] + "-" + orcid[4:8] + "-" + orcid[8:12] + "-" + orcid[12:]


def popargs(args, sections):
    """ Pop given sections from an arguments dictionary. """

    if isinstance(sections, str):
        sections = (sections,)

    return {k: args.pop(k, {}) for k in sections}


CONFIG_ENV_VAR = "NANOFACTORY_CONFIG"

# Built-in fallback configuration, used when no config file is found. It
# contains the lab defaults for devices and objectives, but no users and no
# attenuator calibration file.
DEFAULT_CONFIG: dict[str, Any] = {
    "title": "Nanofactory Config File (built-in default)",
    "version": "1.0",
    "encoding": "UTF-8",
    "system": {
        "manufacturer": "Femtika",
        "model": "Laser Nanofactory",
        "description": "Multi-purpose laser direct writing system",
        "laserWavelength": 0.515,
    },
    "attenuator": {},
    "camera": {},
    "dhm": {
        "host": "192.168.22.2",
        "port": 27182,
    },
    "controller": {
        "manufacturer": "Aerotech",
        "model": "A3200",
        "description": "Multi-axis motion controller system",
        "host": "127.0.0.1",
        "port": 8000,
        "cmdTerminatingChar": 10,
        "cmdSuccessChar": 37,
        "cmdInvalidChar": 33,
        "cmdFaultChar": 35,
    },
    "objective:Zeiss 20x": {
        "manufacturer": "Zeiss",
        "magnification": 20.0,
        "numericalAperture": 0.8,
        "immersion": False,
        "tubeLength": "infinity",
        "coverThickness": 0.17,
        "dhmId": 178,
        "cameraFocus": -6.0,
        "cameraPitch": [[0.2, 0.0], [0.0, -0.2]],
        "dcRadius": 304,
    },
    "objective:Zeiss 63x": {
        "manufacturer": "Zeiss",
        "magnification": 63.0,
        "numericalAperture": 1.4,
        "immersion": True,
        "tubeLength": "infinity",
        "coverThickness": 0.17,
        "dhmId": 180,
        "cameraFocus": -6.0,
        "cameraPitch": [[0.2, 0.0], [0.0, -0.2]],
        "dcRadius": 304,
    },
}


def default_config_path() -> Path:
    """ Return the path of the configuration file to load.

    Returns
    -------
    Path
        The path given by the environment variable ``NANOFACTORY_CONFIG``
        if it is set, otherwise ``~/nanofactory.json``.
    """

    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return Path(env_path)
    return Path.home() / "nanofactory.json"


class Config(object):
    """ Configuration of the Laser Nanofactory system.

    Parameters
    ----------
    path : str, Path or dict, optional
        Configuration file in JSON format, or a configuration dictionary.
        If omitted, the file returned by :func:`default_config_path` is
        used. If the file does not exist, a warning is issued and the
        built-in :data:`DEFAULT_CONFIG` is used.
    """

    def __init__(self, path=None):

        self.path: Path | None = None
        self.config: dict[str, Any] = {}
        self.load(path)

    def load(self, source: "str | Path | dict[str, Any] | Config | None" = None) -> None:
        """ Replace the configuration content in place.

        The object is modified in place, because modules keep references to
        the global object ``sysConfig``.

        Parameters
        ----------
        source : str, Path, dict, Config or None
            A config file path, a configuration dictionary, another
            ``Config`` object, or None for the default lookup (see
            :func:`default_config_path`).
        """

        if isinstance(source, Config):
            self.path = source.path
            self.config = copy.deepcopy(source.config)
            return

        if isinstance(source, dict):
            self.path = None
            self.config = copy.deepcopy(source)
            return

        path = Path(source) if source is not None else default_config_path()
        try:
            with open(path, "rb") as fp:
                config = fp.read()
            self.config = json.loads(config)
            self.path = path
        except FileNotFoundError:
            warnings.warn(f"Config file not found on system at {path}. Using the built-in default configuration.")
            self.config = copy.deepcopy(DEFAULT_CONFIG)
            self.path = None

    def section(self, key: str) -> dict[str, Any]:
        """ Return a copy of a configuration section.

        Parameters
        ----------
        key : str
            Name of the section, e.g. ``"controller"``.

        Returns
        -------
        dict
            A copy of the section, or an empty dictionary if the section is
            missing.
        """

        value = self.config.get(key, {})
        return dict(value) if isinstance(value, dict) else {}

    def keys(self):

        return [k for k, v in self.config.items() if not isinstance(v, dict)]

    def sections(self):

        return [k for k, v in self.config.items() if isinstance(v, dict)]

    def users(self) -> list[str]:

        return [k[5:] for k in self.config.keys() if k[:5] == "user:"]

    def objectives(self) -> list[str]:

        return [k[10:] for k in self.config.keys() if k[:10] == "objective:"]

    def user(self, key: str) -> dict[str, Any]:

        if key not in self.users():
            raise RuntimeError(f"Unknown user '{key}'!")
        return self.config[f"user:{key}"] | {"key": key}

    def objective(self, key: str) -> dict[str, Any]:

        if key not in self.objectives():
            raise RuntimeError(f"Unknown objective '{key}'!")
        return self.config[f"objective:{key}"] | {"key": key}

    def __getattr__(self, key: str):

        # Avoid infinite recursion while the object is not initialized yet
        # (e.g. during copy or unpickling)
        if key in ("config", "path") or key.startswith("__"):
            raise AttributeError(key)

        if key in self.keys():
            return self.config[key]
        elif key in self.sections():
            return dict(self.config[key])
        raise AttributeError(f"Unknown attribute '{key}'!")

    def __str__(self) -> str:

        lines = []
        for key in sorted(self.keys()):
            lines.append(f"{key} = {getattr(self, key)}")

        for skey in sorted(self.sections()):
            section = getattr(self, skey)

            lines.append(f"[{skey}]")
            for key in sorted(section):
                lines.append(f"    {key} = {section[key]}")

        return "\n".join(lines)


# Read the current config file
sysConfig = Config()


@contextmanager
def use_config(source: "str | Path | dict[str, Any] | Config") -> Iterator[Config]:
    """ Temporarily replace the content of the global ``sysConfig``.

    Parameters
    ----------
    source : str, Path, dict or Config
        Configuration to activate, see :meth:`Config.load`.

    Yields
    ------
    Config
        The global ``sysConfig`` object with the new content.

    Examples
    --------
    >>> with use_config({"user:Test": {"name": "Test User"}}):
    ...     sysConfig.user("Test")["name"]
    'Test User'
    """

    saved_path, saved_config = sysConfig.path, sysConfig.config
    sysConfig.load(source)
    try:
        yield sysConfig
    finally:
        sysConfig.path, sysConfig.config = saved_path, saved_config


class ConfigDefaults(object):
    """ Class attribute descriptor for lazily resolved parameter defaults.

    It replaces class attributes of the form
    ``_defaults = sysConfig.<section> | {...}``, which were evaluated at
    import time. The merge happens on every access instead, so the classes
    can be imported without a config file and follow :func:`use_config`.

    Parameters
    ----------
    section : str
        Name of the configuration section whose items are defaults.
    defaults : dict
        Class-specific defaults. They take precedence over the section
        items, as before.
    from_config : tuple of str, optional
        Keys whose default value is taken from the configuration section
        (None if missing), even though they are listed in ``defaults``.
    """

    def __init__(self, section: str, defaults: dict[str, Any], from_config: tuple[str, ...] = ()):

        self.section = section
        self.defaults = dict(defaults)
        self.from_config = tuple(from_config)

    def __get__(self, obj, owner=None) -> dict[str, Any]:

        section = sysConfig.section(self.section)
        # Deep copy, so that mutable defaults (e.g. A3200 "tasks") are not
        # shared between instances
        result = copy.deepcopy(section | self.defaults)
        for key in self.from_config:
            result[key] = section.get(key)
        return result
