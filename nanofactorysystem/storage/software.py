##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Version information of the software that writes an experiment."""
import platform
import subprocess
from importlib import metadata
from pathlib import Path

PACKAGE = "NanoFactorySystem"
LIBRARIES = ("numpy", "h5py", "SciDataContainer", "opencv-python", "scipy", "shapely")


def _version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return ""


def _git(*args: str) -> str:
    folder = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def software_info() -> dict:
    """ Return version information of this package and its main libraries.

    The git fields are empty if the package does not run from a git checkout
    or git is not installed.

    Returns
    -------
    dict
        ``package_version``, ``git_commit``, ``git_branch``, ``git_dirty``,
        ``python_version`` and ``versions`` (library → version).
    """

    commit = _git("rev-parse", "HEAD")
    return {
        "package_version": _version(PACKAGE),
        "git_commit": commit,
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD") if commit else "",
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")) if commit else False,
        "python_version": platform.python_version(),
        "versions": {name: _version(name) for name in LIBRARIES},
    }
