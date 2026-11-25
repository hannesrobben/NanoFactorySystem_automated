##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Quick PT: first experience values of a material, walls and pads (design docs/design/PARAMETER_TESTS.md §4).

One experiment with four 60 µm sub-fields: Q1 walls a/b and Q2 pads a/b (a = 0.1-0.5 mW, b = 0.6-1.0 mW).
What the structures examine: see README_quick_pt.md.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout only (no hardware): ``python -m parametertest.quick_pt --layout``
- Dry run on simulated hardware:       ``python -m parametertest.quick_pt --dry-run``
- Lab PC (every step confirmed):       ``python -m parametertest.quick_pt``
"""
from pathlib import Path
from typing import Optional

from parametertest import common


def experiment_spec(inputs_path: Optional[Path] = None):
    """ The Quick PT experiment (``ExperimentSpec``) for the material start file. """

    return common.quick_spec(common.load_inputs(inputs_path))


def main(*, backend=None, plane=None, data_root: Optional[Path] = None, inputs_path: Optional[Path] = None,
         material_registry=None) -> list[Path]:
    """ Print Quick PT (a one-experiment substrate run, so it is in the substrate index).

    Parameters
    ----------
    backend, plane
        None: the lab hardware. A backend object and a known plane for a dry run.
    data_root : Path, optional
        Data root instead of the user's default location.
    inputs_path : Path, optional
        Material start file (default ``parameter_tests_<resin>.json``).
    material_registry : MaterialRegistry, optional

    Returns
    -------
    list of Path
    """

    return common.run(["quick"], inputs_path=inputs_path, backend=backend, plane=plane, data_root=data_root,
                      material_registry=material_registry)


if __name__ == "__main__":
    common.cli(["quick"], __doc__.splitlines()[0])
