##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Voxel PT-01: gap test for the voxel height, one experiment per power (design docs/design/PARAMETER_TESTS.md §6).

Every experiment writes the 11 gap cells (base 20 × 20 µm to 2 µm, gap 0-2.0 µm, lid at the tested power) as
separate structures 100 µm apart in a 3 × 4 grid. What the structures examine: see README_voxel_pt01.md.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only:  ``python -m parametertest.voxel_pt01 --layout``
- Dry run at 0.5 mW only: ``python -m parametertest.voxel_pt01 --dry-run --only 0.5``
- Lab PC, all ten powers: ``python -m parametertest.voxel_pt01``
"""
from pathlib import Path
from typing import Optional, Sequence

from parametertest import common


def experiment_spec(power_mw: float, inputs_path: Optional[Path] = None):
    """ The Voxel PT-01 experiment of one lid power. """

    inputs = common.load_inputs(inputs_path)
    return common.voxel_spec(float(power_mw), inputs, index=inputs.powers_mw.index(round(float(power_mw), 6)))


def main(*, powers_mw: Optional[Sequence[float]] = None, backend=None, plane=None, data_root: Optional[Path] = None,
         inputs_path: Optional[Path] = None, material_registry=None) -> list[Path]:
    """ Print the Voxel PT-01 experiments (default every power of the ladder) one after another.

    Parameters
    ----------
    powers_mw : sequence of float, optional
        Lid powers, e.g. ``[0.3, 0.5]``.
    backend, plane, data_root, inputs_path, material_registry
        As in ``quick_pt.main``.

    Returns
    -------
    list of Path
    """

    return common.run(["voxel"], inputs_path=inputs_path, only=powers_mw, backend=backend, plane=plane,
                      data_root=data_root, material_registry=material_registry)


if __name__ == "__main__":
    common.cli(["voxel"], __doc__.splitlines()[0], selection_help="powers in mW, e.g. 0.3,0.5")
