##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Chain of the parameter tests on one substrate (design docs/design/PARAMETER_TESTS.md §2).

``--test quick|full|voxel|all`` selects the tests; they are independent (no test needs another one's result)
and run one after another into one substrate index. The layout of all selected experiments is checked against
each other, the resin drop and the marker clearance before anything is printed.

Run (with ``mains/`` as working directory)
------------------------------------------
- Check the layout of all tests: ``python -m parametertest.chain --test all --layout``
- Dry run of Quick PT:            ``python -m parametertest.chain --test quick --dry-run``
- Lab PC:                         ``python -m parametertest.chain --test all``
"""
import argparse
from pathlib import Path

from parametertest import common


def tests_of(choice: str) -> list[str]:
    """ The tests of a ``--test`` choice.

    Raises
    ------
    ValueError
        For an unknown choice.
    """

    if choice == "all":
        return list(common.TESTS)
    if choice not in common.TESTS:
        raise ValueError(f"Unknown test {choice!r}; use one of {common.TESTS} or 'all'.")
    return [choice]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", default="all", choices=[*common.TESTS, "all"])
    parser.add_argument("--inputs", type=Path, help="material start file")
    parser.add_argument("--layout", action="store_true", help="only check and plot the layout")
    parser.add_argument("--dry-run", action="store_true", help="run on simulated hardware")
    options = parser.parse_args()
    tests = tests_of(options.test)
    if options.layout:
        common.check(tests, inputs_path=options.inputs)
        print("Layout OK.")
    elif options.dry_run:
        print("Dry run finished:", *common.dry_run(tests, inputs_path=options.inputs), sep="\n  ")
    else:
        common.run(tests, inputs_path=options.inputs)
