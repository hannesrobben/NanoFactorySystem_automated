##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""PTD-01 F7 pillars on bases: one experiment on the PTD-01 substrate (T145, design §5, §6.1).

p_rel 1.25 ... 2.0 (rows) x pillar height 2 / 4 / 6 / 8 / 10 um (columns), diameter 1.5 um on 6 x 6 x 1.4 um
bases. Gives AR_max(P) and adhesion.

Stage B; input: the stage-B calibration ``calibration_<material>_<objective>.json`` (``--calibration``).
Settings (substrate, field position, label power, corners) are in
``common.py``.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only (no hardware): ``python -m Experiments.ptd01.f7_pillars --layout``
- Dry run on simulated hardware:       ``python -m Experiments.ptd01.f7_pillars --dry-run``
- Lab PC (every step confirmed):       ``python -m Experiments.ptd01.f7_pillars --calibration <file>``
"""
from pathlib import Path
from typing import Optional

from Experiments.ptd01 import common

FIELD_ID = 7


def experiment_spec(*, calibration_path: Optional[Path] = None, stage_a_path: Optional[Path] = None,
                    replicates: int = 1, allow_example: bool = False):
    """ The experiment of field F7.

    Parameters
    ----------
    calibration_path, stage_a_path : Path, optional
        Input files (defaults in ``common``).
    replicates : int
        Copies of the field (decision D4: 1 for the first print).
    allow_example : bool
        Accept the example calibration (dry runs and layout checks).

    Returns
    -------
    ExperimentSpec
    """

    calibration = common.load_calibration(calibration_path, allow_example=allow_example)
    return common.experiments([FIELD_ID], calibration=calibration, replicates=replicates)[0].spec


def main(*, backend=None, plane=None, data_root: Optional[Path] = None, calibration_path: Optional[Path] =
None,
         stage_a_path: Optional[Path] = None, replicates: int = 1, axes: Optional[dict] = None,
         material_registry=None, allow_example: bool = False) -> list[Path]:
    """ Print field F7 as a one-experiment substrate run (so it is also in the substrate index).

    Parameters
    ----------
    backend, plane
        None: the lab hardware. A backend object and a known plane for a dry run.
    data_root : Path, optional
        Data root instead of the user's default location.
    calibration_path, stage_a_path : Path, optional
        Input files (defaults in ``common``).
    replicates : int
    axes : dict, optional
        Axis keyword arguments of the field (e.g. fewer levels for a quick dry run).
    material_registry : MaterialRegistry, optional
    allow_example : bool
        Accept the example calibration (dry runs only).

    Returns
    -------
    list of Path
        The experiment folder.
    """

    return common.run_fields([FIELD_ID], calibration_path=calibration_path, stage_a_path=stage_a_path,
                             replicates=replicates, axes={FIELD_ID: axes} if axes else None, backend=backend,
                             plane=plane, data_root=data_root, material_registry=material_registry,
                             allow_example=allow_example)


if __name__ == "__main__":
    common.field_cli(FIELD_ID, __doc__.splitlines()[0])
