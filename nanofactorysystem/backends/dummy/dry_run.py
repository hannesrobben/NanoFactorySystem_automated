##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Dry runs of main scripts on simulated hardware (T110).

The tests get everything a dry run needs from fixtures (``dummy_backend``,
``no_sleep``, ``test_config``). A main script has no fixtures, so
:func:`dry_run` bundles the same four things in one context manager:

- a :class:`~nanofactorysystem.backends.dummy.DummyBackend`,
- the known substrate plane of its simulated sample (plane detection is not
  simulated, so it is passed to ``Experiment.plane_fit(plane=...)``),
- ``time.sleep`` replaced by the virtual clock, so waiting for the simulated
  controller does not take real time,
- a configuration that knows the user and both objectives, also on a PC
  whose ``~/nanofactory.json`` lacks them (the missing sections are added
  for the duration of the dry run only and reported in a warning).

Example
-------
>>> from nanofactorysystem.backends.dummy.dry_run import dry_run
>>> with dry_run("Hannes") as simulated:  # doctest: +SKIP
...     run_experiment(spec, user="Hannes", resin_edges=edges, path=simulated.workdir / "out",
...                    backend=simulated.backend, plane=simulated.plane)
"""
from __future__ import annotations

import copy
import tempfile
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from nanofactorysystem.backends.dummy import DummyBackend
from nanofactorysystem.config import DEFAULT_CONFIG, sysConfig, use_config
from nanofactorysystem.devices.coordinate_system import Plane

__all__ = ["DryRun", "dry_run", "dry_run_config", "DRY_RUN_USER"]

# User section added for a user that the configuration does not know (placeholders, dry run only)
DRY_RUN_USER = {"name": "", "email": "dry-run@example.org", "organization": "dry run",
                "orcid": "0000-0000-0000-0000"}


@dataclass(frozen=True)
class DryRun:
    """ What a dry run passes to ``run_experiment`` / ``run_substrate``.

    Attributes
    ----------
    backend : DummyBackend
        Simulated hardware; pass it as ``backend=``.
    plane : Plane
        Known substrate plane of the simulated sample; pass it as ``plane=``.
    workdir : Path
        Folder of the dry run (program files, synthetic calibration); a good
        place for the experiment output, too.
    """

    backend: DummyBackend
    plane: Plane
    workdir: Path


def dry_run_config(user: str, base: Optional[dict] = None) -> tuple[dict, list[str]]:
    """ Return a configuration that knows ``user`` and every objective of the built-in default.

    Parameters
    ----------
    user : str
        User key the dry run is started for.
    base : dict, optional
        Configuration to extend; default: the content of the active
        ``sysConfig``. It is not changed.

    Returns
    -------
    tuple of (dict, list of str)
        The extended configuration and the names of the sections that were
        added (empty if nothing was missing).
    """

    config = copy.deepcopy(sysConfig.config if base is None else base)
    added = []
    for key, section in DEFAULT_CONFIG.items():
        if key.startswith("objective:") and key not in config:
            config[key] = copy.deepcopy(section)
            added.append(key)
    if f"user:{user}" not in config:
        # System needs all four fields (scidatacontainer refuses missing ones)
        config[f"user:{user}"] = dict(DRY_RUN_USER, name=user)
        added.append(f"user:{user}")
    return config, added


@contextmanager
def dry_run(user: str, *, seed: int = 0, workdir: Optional[str | Path] = None,
            fast_sleep: bool = True) -> Iterator[DryRun]:
    """ Simulated hardware for running a main script without the lab PC.

    Parameters
    ----------
    user : str
        User key of the experiment; added to the configuration for the
        duration of the dry run if it is missing.
    seed : int
        Seed of the simulated image noise.
    workdir : str or Path, optional
        Folder of the dry run; default: a new temporary folder.
    fast_sleep : bool
        Replace ``time.sleep`` by the virtual clock of the simulation (the
        same as the ``no_sleep`` test fixture). The original is restored on
        exit.

    Yields
    ------
    DryRun
        Backend, known plane and folder of the dry run.
    """

    workdir = Path(workdir) if workdir is not None else Path(tempfile.mkdtemp(prefix="nanofactory_dry_run_"))
    backend = DummyBackend(seed=seed, workdir=workdir / "dummy")
    config, added = dry_run_config(user)
    if added:
        warnings.warn(f"Dry run: sections {added} are missing in the configuration and are added for this dry "
                      f"run only.", stacklevel=3)
    original_sleep = time.sleep
    with use_config(config):
        if fast_sleep:
            time.sleep = backend.world.clock.sleep
        try:
            yield DryRun(backend=backend, plane=backend.world.sample.plane(), workdir=workdir)
        finally:
            time.sleep = original_sleep
