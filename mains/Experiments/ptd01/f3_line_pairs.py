##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""PTD-01 F3 line pairs: one experiment on the PTD-01 substrate (T145, design §5, §6.1).

p_rel 1.25 ... 2.25 (rows) x s_rel 0.5 ... 2.0 (columns); a pair above a group of five 6 um lines, centre
distance s_rel * w(P). Gives the merge distance and the widening by neighbours.

Stage B; input: the stage-B calibration ``calibration_<material>_<objective>.json`` (``--calibration``).
Settings (substrate, field position, label power, corners) are in
``common.py``.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only (no hardware): ``python -m Experiments.ptd01.f3_line_pairs --layout``
- Dry run on simulated hardware:       ``python -m Experiments.ptd01.f3_line_pairs --dry-run``
- Lab PC (every step confirmed):       ``python -m Experiments.ptd01.f3_line_pairs --calibration <file>``
"""
from pathlib import Path
from typing import Optional

from Experiments.ptd01 import common

FIELD_ID = 3


def experiment_spec(*, calibration_path: Optional[Path] = None, stage_a_path: Optional[Path] = None,
                    replicates: int = 1, allow_example: bool = False):
    """ The experiment of field F3.

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
    """ Print field F3 as a one-experiment substrate run (so it is also in the substrate index).

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
