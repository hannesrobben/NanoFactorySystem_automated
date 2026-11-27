##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Lab check T148 (decision D9): does the attenuator settle before the line after a power change starts?

One IFOV experiment (Zeiss 63x) with three structures, one per dwell (``DWELLS_S``). Each structure writes
ten line pairs (``nanofactorysystem.testprint.power_switch.PowerSwitchLines``): every line has four 6 µm
segments alternating 0.25 / 0.75 mW, each segment its own IFOV block starting with ``$AO`` like the blocks of
the parameter tests; the first line of a pair switches without a pause, the line 2 µm below it pauses for the
structure's dwell after every power change; two reference lines at constant 0.25 and 0.75 mW follow.
Work order and evaluation: ``docs/design/POWER_SWITCH_CHECK.md``; guide: ``docs/guides/POWER_SWITCH_CHECK.md``.

Run with ``mains/`` as the working directory::

    cd mains
    python -m lab_checks.power_switch_check            # lab PC (message boxes before plane fit and printing)
    python -m lab_checks.power_switch_check --layout   # check the layout only
    python -m lab_checks.power_switch_check --dry-run  # simulated hardware
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource, StructureType
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, default_sys_args, messagebox_confirm
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec, check_layout, run_substrate
from nanofactorysystem.testprint.power_switch import PowerSwitchLines

# =================================================================================================
# SETTINGS (LAB: check before every run)
# =================================================================================================
USER = "Hannes"
OBJECTIVE = "Zeiss 63x"
RESIN = "SZ2080"
RESIN_EDGES = [[-2500, 17000], [-100, 27000], [5300, 21100], [-6000, 22000]]    # LAB: right, left, near, far (µm)
# RESIN_EDGES = [[-4900, -2300], [4300, -700], [-800, -5900], [-200, 3600]]  # LAB: right, left, near, far (µm)
CENTER = Point2D(-4000, 25000)                     # LAB: centre of the experiment (absolute stage µm)
SUBSTRATE_LABEL: Optional[str] = "SZ_2080_test"          # None: the next free label of the user
DWELLS_S = (0.01, 0.05, 0.2)                   # dwell after every power change of the second line of each pair
POWER_LOW_MW, POWER_HIGH_MW = 0.25, 0.75       # maintainer decision 2026-11-26
REPETITIONS = 10
Z_UM = 0.0                                     # writing plane relative to the fitted substrate surface
CORNER_POWER_MW = 0.7                          # corners, QR code and interface detection
ASK_EACH_STEP = True


def structure(dwell_s: float) -> PowerSwitchLines:
    """ The line pairs of one dwell level. """

    return PowerSwitchLines(Point3D(0, 0, Z_UM), power_low_mw=POWER_LOW_MW, power_high_mw=POWER_HIGH_MW,
                            dwell_s=dwell_s, repetitions=REPETITIONS, objective=OBJECTIVE)


def experiment_spec(center: Point2D = CENTER) -> ExperimentSpec:
    """ One IFOV experiment, one grid cell per dwell level.

    Returns
    -------
    ExperimentSpec
    """

    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"
    sys_args["layer"]["laserPower"] = CORNER_POWER_MW
    return ExperimentSpec(
        name="t148_power_switch", description="T148: line pairs with power switches, without and with dwell "
                                              f"({', '.join(f'{d * 1000:g} ms' for d in DWELLS_S)})",
        tags=["lab_check", "T148", "D9"], objective=OBJECTIVE, center=center, grid=(1, len(DWELLS_S)),
        structure_size_um=60.0, program_source=ProgramSource.DRAWING, setup="IFOV_on",
        default_power_mw=CORNER_POWER_MW, plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=False, camera_capture=True,
        materials={"resin": RESIN}, sys_args=sys_args,
        structures=[StructureSpec(f"dwell_{dwell * 1000:g}ms", structure(dwell), structure_type=StructureType.IFOV,
                                  axes="XYZ", power_mw=POWER_LOW_MW) for dwell in DWELLS_S])


def substrate_spec(data_root: Optional[Path] = None) -> SubstrateSpec:
    """ The substrate of the check (label ``SUBSTRATE_LABEL`` or the next free one). """

    return SubstrateSpec(user=USER, objective=OBJECTIVE, resin_edges=RESIN_EDGES, label=SUBSTRATE_LABEL,
                         material={"resin": RESIN}, notes="Lab check T148 (mains/lab_checks/power_switch_check.py)",
                         data_root=data_root)


def main(*, backend=None, plane=None, data_root: Optional[Path] = None, confirm=None, layout_only: bool = False):
    """ Check the layout and run the experiment.

    Returns
    -------
    list of Path
        The experiment folder (empty with ``layout_only``).
    """

    experiments = [SubstrateExperiment(experiment_spec())]
    if layout_only:
        for area in check_layout(substrate_spec(data_root), experiments):
            print(f"{area.name}: x {area.lower[0]:.0f} .. {area.upper[0]:.0f} µm, y {area.lower[1]:.0f} .. "
                  f"{area.upper[1]:.0f} µm")
        return []
    return run_substrate(substrate_spec(data_root), experiments, backend=backend, plane=plane, confirm=confirm,
                         show_plot=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--layout", action="store_true", help="check the layout only")
    parser.add_argument("--dry-run", action="store_true", help="simulated hardware")
    args = parser.parse_args()
    if args.dry_run:
        from nanofactorysystem.backends.dummy.dry_run import dry_run
        with dry_run(USER) as simulated:
            print(main(backend=simulated.backend, plane=simulated.plane, data_root=simulated.workdir / "data"))
    else:
        print(main(confirm=messagebox_confirm if ASK_EACH_STEP else None, layout_only=args.layout))
