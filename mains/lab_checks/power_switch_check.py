##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Lab check T148 (decision D9): where along a line does a power change take effect, and how long does the
attenuator need to settle?

One IFOV experiment (Zeiss 63x). Each grid cell is one repetition of
``nanofactorysystem.testprint.power_switch.PowerSwitchLines``: five 50 µm lines, 5 µm apart, that switch from
0.25 to 0.75 mW at their middle (x = 0). The first line switches without a pause (``LINEAR`` → ``$AO`` →
``LINEAR``), the other four wait for the motion (``WAIT MOVEDONE``) and dwell 5 / 20 / 100 / 500 ms after the
power command. Every line is written on 11 z levels from -1 to +1 µm around the interface (0.2 µm steps), so it
becomes a small wall. ``REPETITIONS`` (5-10) grid cells repeat the pattern.
Work order and evaluation: ``docs/design/POWER_SWITCH_CHECK.md``; guide: ``docs/guides/POWER_SWITCH_CHECK.md``.

Run with ``mains/`` as the working directory::

    cd mains
    python -m lab_checks.power_switch_check            # lab PC (message boxes before plane fit and printing)
    python -m lab_checks.power_switch_check --layout   # check the layout only
    python -m lab_checks.power_switch_check --dry-run  # simulated hardware
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional

from nanofactorysystem.devices.coordinate_system import Point2D, Point3D
from nanofactorysystem.experiment import ProgramSource, StructureType
from nanofactorysystem.experiment_spec import ExperimentSpec, StructureSpec, default_sys_args, messagebox_confirm
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec, check_layout, run_substrate
from nanofactorysystem.testprint.power_switch import DEFAULT_DWELLS_S, PowerSwitchLines

# =================================================================================================
# SETTINGS (LAB: check before every run)
# =================================================================================================
USER = "Hannes"
OBJECTIVE = "Zeiss 63x"
RESIN = "SZ2080"
RESIN_EDGES = [[-4900, -2300], [4300, -700], [-800, -5900], [-200, 3600]]  # LAB: right, left, near, far (µm)
CENTER = Point2D(0, -1500)                     # LAB: centre of the experiment (absolute stage µm)
SUBSTRATE_LABEL: Optional[str] = None          # None: the next free label of the user
DWELLS_S = DEFAULT_DWELLS_S                    # 5 / 20 / 100 / 500 ms after the power command (WAIT MOVEDONE first)
POWER_LOW_MW, POWER_HIGH_MW = 0.25, 0.75       # first half / second half of every line
LINE_LENGTH_UM, LINE_GAP_UM = 50.0, 5.0        # switch at the middle of the line
Z_MIN_UM, Z_MAX_UM, SLICE_UM = -1.0, 1.0, 0.2  # z levels around the fitted interface (z = 0)
REPETITIONS = 6                                # grid cells with the same pattern (5-10)
CORNER_POWER_MW = 0.7                          # corners, QR code and interface detection
ASK_EACH_STEP = True


def structure() -> PowerSwitchLines:
    """ The line group of one grid cell. """

    return PowerSwitchLines(Point3D(0, 0, 0), power_low_mw=POWER_LOW_MW, power_high_mw=POWER_HIGH_MW,
                            dwells_s=DWELLS_S, line_length_um=LINE_LENGTH_UM, line_gap_um=LINE_GAP_UM,
                            z_min_um=Z_MIN_UM, z_max_um=Z_MAX_UM, slice_um=SLICE_UM, objective=OBJECTIVE)


def experiment_spec(center: Point2D = CENTER, repetitions: int = REPETITIONS) -> ExperimentSpec:
    """ One IFOV experiment, one grid cell per repetition (two rows).

    Raises
    ------
    ValueError
        For fewer than 5 or more than 10 repetitions.

    Returns
    -------
    ExperimentSpec
    """

    if not 5 <= repetitions <= 10:
        raise ValueError(f"REPETITIONS must be between 5 and 10, not {repetitions}")
    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"
    sys_args["layer"]["laserPower"] = CORNER_POWER_MW
    return ExperimentSpec(
        name="t148_power_switch",
        description=f"T148: {LINE_LENGTH_UM:g} um lines switching {POWER_LOW_MW:g} -> {POWER_HIGH_MW:g} mW at the "
                    f"middle, no pause and dwell {', '.join(f'{d * 1000:g} ms' for d in DWELLS_S)}, "
                    f"z {Z_MIN_UM:g}..{Z_MAX_UM:g} um, {repetitions} repetitions",
        tags=["lab_check", "T148", "D9"], objective=OBJECTIVE, center=center, grid=(2, math.ceil(repetitions / 2)),
        structure_size_um=60.0, program_source=ProgramSource.DRAWING, setup="IFOV_on",
        default_power_mw=CORNER_POWER_MW, plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=False, camera_capture=True,
        materials={"resin": RESIN}, sys_args=sys_args,
        structures=[StructureSpec("power_switch", structure(), structure_type=StructureType.IFOV, axes="XYZ",
                                  power_mw=POWER_LOW_MW, repeat=repetitions - 1)])


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
