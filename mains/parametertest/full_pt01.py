##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Full PT-01: fields F1-F7 on absolute axes, one experiment per field (design docs/design/PARAMETER_TESTS.md §5).

Every experiment holds the sub-fields a (0.1-0.5 mW) and b (0.6-1.0 mW) of one field. What the structures
examine: see README_full_pt01.md.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only:     ``python -m parametertest.full_pt01 --layout``
- Dry run of F3 and F5 only: ``python -m parametertest.full_pt01 --dry-run --only F3,F5``
- Lab PC, all fields:        ``python -m parametertest.full_pt01``
"""
from pathlib import Path
from typing import Optional, Sequence

from parametertest import common


def experiment_spec(field_id: int, inputs_path: Optional[Path] = None):
    """ The Full PT-01 experiment of field ``field_id`` (1 … 7). """

    return common.full_spec(int(field_id), common.load_inputs(inputs_path))


def main(*, fields: Optional[Sequence[int]] = None, backend=None, plane=None, data_root: Optional[Path] = None,
         inputs_path: Optional[Path] = None, material_registry=None) -> list[Path]:
    """ Print the Full PT-01 fields (default all, F1 … F7) one after another.

    Parameters
    ----------
    fields : sequence of int, optional
        Field numbers, e.g. ``[3, 5]``.
    backend, plane, data_root, inputs_path, material_registry
        As in ``quick_pt.main``.

    Returns
    -------
    list of Path
    """

    return common.run(["full"], inputs_path=inputs_path, only=fields, backend=backend, plane=plane,
                      data_root=data_root, material_registry=material_registry)


if __name__ == "__main__":
    common.cli(["full"], __doc__.splitlines()[0], selection_help="fields, e.g. F3,F5")
