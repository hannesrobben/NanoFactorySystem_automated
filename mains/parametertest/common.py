##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Shared settings of the parameter tests Quick PT, Full PT-01 and Voxel PT-01 (T162, design
docs/design/PARAMETER_TESTS.md).

All three tests are single-stage prints on absolute axes; their only input is the material start file
``parameter_tests_<material>.json`` (``ParameterTestInputs``). No calibration, fit model or voxel database is
needed. This module holds the substrate, the position of every experiment on it, the reduced corner markers,
the margin that keeps the QR code out of the grid, and the helpers that build the experiment specs.

Values that depend on the substrate in the lab are marked ``# LAB:``; check them before printing.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional, Sequence

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment import QR_CODE_WIDTH_UM, ProgramSource, StructureType
from nanofactorysystem.experiment_spec import CornerSpec, ExperimentSpec, StructureSpec, default_sys_args
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec
from nanofactorysystem.testprint import ParameterTestInputs, pt_factories
from nanofactorysystem.testprint.parameter_tests import FULL_FIELDS, QUICK_FIELDS

HERE = Path(__file__).resolve().parent

# ------------------------------------------------------------------------------------------------
# Substrate and placement (absolute stage coordinates in µm)
# ------------------------------------------------------------------------------------------------
USER = "Hannes"                                      # user key "user:<name>" of ~/nanofactory.json
OBJECTIVE = "Zeiss 63x"                              # IFOV setup and fixed writing speed of the 63x
SETUP = "IFOV_on"
RESIN = "SZ2080"                                     # LAB: registry name of the resin
INPUTS_FILE = HERE / f"parameter_tests_{RESIN}.json"  # material start file (one per material)
# LAB: edges of the resin drop measured with the camera: right, left, near, far (as in T113)
RESIN_EDGES = [[-2500, 17000], [-100, 27000], [5300, 21100], [-6000, 22000]]
SUBSTRATE_LABEL: Optional[str] = "SZ_2080_test"          # None: the next free label of the user
CORNER_POWER_MW = 0.7                                # corners and QR code (as in T113)
# Reduced corner markers with QR code (D2) and a margin that keeps the markers out of the grid: the QR code
# (140 µm, centred on the upper edge of the rectangle) reaches 70 µm inside; maintainer requirement
# 2026-11-25: at least 20 µm between every marker and the grid
FIELD_CORNER = CornerSpec(z_um=-2.0, width_um=20.0, length_um=150.0, height_um=4.0, hatch_um=0.3, slice_um=0.75)
MARKER_CLEARANCE_UM = 20.0
MARGIN_UM = 90.0
DWELL_AFTER_POWER_S = 0.0                            # D9: set from the lab check T148
# Unattended run: set all three to False, then nothing waits for a click
ASK_EACH_STEP = False                                 # confirm plane fit and printing inside every experiment
ASK_BETWEEN = False                                   # confirm before starting the next experiment
SHOW_PLOTS = False                                    # layout plot windows (must be closed to continue)

# LAB: centre of every experiment (columns 800 µm apart, rows 900 µm; checked by check_layout)
# _COLUMNS = [-2800, -2000, -1200, -400, 400, 1200, 2000, 2800]
# CENTERS = {"quick": Point2D(_COLUMNS[0], 1200)}
# CENTERS.update({f"full_f{i}": Point2D(_COLUMNS[i], 1200) for i in range(1, 8)})
# CENTERS.update({f"voxel_{i}": Point2D(_COLUMNS[i % 8], 300 if i < 8 else -600) for i in range(10)})
_COLUMNS = [-2000, -1000, 0, 1000, 2000]
CENTERS = {"quick": Point2D(_COLUMNS[2], 20000)}
CENTERS.update({f"full_f{i}": Point2D(_COLUMNS[i%4], 21000 if i < 5 else 22000) for i in range(8)})
CENTERS.update({f"voxel_{i}": Point2D(_COLUMNS[i % 5], 23000 if i < 5 else 24000) for i in range(10)})

TESTS = ("quick", "full", "voxel")


# ------------------------------------------------------------------------------------------------
# Input file and checks
# ------------------------------------------------------------------------------------------------
def load_inputs(path: Optional[Path] = None) -> ParameterTestInputs:
    """ The material start file; it must be for the resin of the substrate.

    Raises
    ------
    ValueError
        If the file is for another material.
    """

    inputs = ParameterTestInputs.load(path or INPUTS_FILE)
    if inputs.material != RESIN:
        raise ValueError(f"{path or INPUTS_FILE} is for {inputs.material!r}, the substrate uses {RESIN!r}.")
    return inputs


def check_marker_clearance(spec: ExperimentSpec, clearance_um: float = MARKER_CLEARANCE_UM) -> None:
    """ Refuse a layout in which the QR code or a corner marker comes closer than ``clearance_um`` to the grid.

    The QR code (``QR_CODE_WIDTH_UM``) is centred on the upper edge of the experiment rectangle and reaches half
    its width inside; a corner marker reaches at most its width inside. Both lie in the margin, so the margin
    must be at least ``max(QR width / 2, corner width) + clearance``.

    Raises
    ------
    ValueError
        If the margin is too small.
    """

    resolved = spec.resolved()
    if resolved.skip_corner:
        return
    required = max(QR_CODE_WIDTH_UM / 2, resolved.corner.width_um) + clearance_um
    if resolved.margin_um < required - 1e-9:
        raise ValueError(f"{resolved.name}: margin {resolved.margin_um:g} um lets the QR code / corner markers reach "
                         f"closer than {clearance_um:g} um to the grid; it must be at least {required:g} um.")


# ------------------------------------------------------------------------------------------------
# Experiment specs
# ------------------------------------------------------------------------------------------------
def _sys_args(name: str) -> dict:
    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"
    sys_args["sample"]["name"] = name
    sys_args["focus"]["exposureValue"] = 120
    sys_args["layer"]["laserPower"] = 0.7               # LAB: power for the resin interface detection
    return sys_args


def _spec(name: str, test: str, tags: list, center: Point2D, grid: tuple, structures: list, description: str,
          structure_size_um: Optional[float] = None, padding_um: Optional[float] = None) -> ExperimentSpec:
    spec = ExperimentSpec(
        name=name, description=description, tags=["parameter_test", test, *tags], objective=OBJECTIVE, center=center,
        grid=grid, structure_size_um=structure_size_um, padding_um=padding_um, margin_um=MARGIN_UM,
        skip_corner=False, corner=FIELD_CORNER, structures=structures, program_source=ProgramSource.DRAWING,
        setup=SETUP, default_power_mw=CORNER_POWER_MW, plane_fit_mode=PlaneFitMode.CORNERS, dhm_usage=False,
        camera_capture=True, overview_capture=True, materials={"resin": RESIN}, layer_overhead_s=5.0,
        sys_args=_sys_args(name))
    check_marker_clearance(spec)
    return spec


def _sub_field_spec(name: str, factory, inputs: ParameterTestInputs) -> list[StructureSpec]:
    return [StructureSpec(f"{name}_{half}", factory=factory(inputs=inputs.to_json(), half=half,
                                                            dwell_after_power_s=DWELL_AFTER_POWER_S),
                          power_mw=inputs.label_power_mw, axes="XYZ", structure_type=StructureType.IFOV)
            for half in "ab"]


def quick_spec(inputs: ParameterTestInputs, center: Optional[Point2D] = None) -> ExperimentSpec:
    """ Quick PT: one experiment with Q1 walls a/b and Q2 pads a/b (2 × 2 grid of 60 µm sub-fields). """

    structures = (_sub_field_spec(QUICK_FIELDS[1], pt_factories.quick_walls, inputs)
                  + _sub_field_spec(QUICK_FIELDS[2], pt_factories.quick_pads, inputs))
    return _spec("quick_pt", "quick_pt", ["Q1", "Q2"], center or CENTERS["quick"], (2, 2), structures,
                 f"Quick PT: walls and pads at {inputs.powers_mw[0]:g}-{inputs.powers_mw[-1]:g} mW "
                 f"(sub-fields a/b) for {inputs.material}.")


def full_spec(field_id: int, inputs: ParameterTestInputs, center: Optional[Point2D] = None) -> ExperimentSpec:
    """ Full PT-01: one experiment per field F1 … F7 with the sub-fields a and b side by side. """

    name = FULL_FIELDS[field_id]
    return _spec(f"full_pt01_{name}", "full_pt01", [f"F{field_id}"], center or CENTERS[f"full_f{field_id}"], (1, 2),
                 _sub_field_spec(name, pt_factories.FULL_FACTORIES[field_id], inputs),
                 f"Full PT-01 {name}: absolute axes, sub-fields a/b ({inputs.material}).")


def voxel_spec(power_mw: float, inputs: ParameterTestInputs, index: int = 0,
               center: Optional[Point2D] = None) -> ExperimentSpec:
    """ Voxel PT-01: one experiment per lid power; every gap cell is its own structure, 100 µm apart, 3 × 4 grid. """

    voxel = inputs.voxel
    rows, cols = (int(v) for v in voxel["grid"])
    gaps = [float(g) for g in voxel["gaps_um"]]
    if len(gaps) > rows * cols:
        raise ValueError(f"{len(gaps)} gaps do not fit a {rows} x {cols} grid.")
    structures = [StructureSpec(f"V_p{power_mw:.2f}_g{gap:.2f}",
                                factory=pt_factories.voxel_gap(inputs=inputs.to_json(), power_mw=float(power_mw),
                                                               gap_um=gap, dwell_after_power_s=DWELL_AFTER_POWER_S),
                                power_mw=float(power_mw), axes="XYZ", structure_type=StructureType.IFOV) for gap in gaps]
    structures += [StructureSpec(f"empty_{i}", structure_type=StructureType.DUMMY)
                   for i in range(rows * cols - len(gaps))]
    return _spec(f"voxel_pt01_p{power_mw:.2f}", "voxel_pt01", [f"P{power_mw:.2f}mW"],
                 center or CENTERS[f"voxel_{index}"], (rows, cols), structures,
                 f"Voxel PT-01 gap test at {power_mw:g} mW: gaps {gaps[0]:g}-{gaps[-1]:g} um ({inputs.material}).",
                 structure_size_um=float(voxel["cell_pitch_um"]), padding_um=0.0)


def experiments(test: str, inputs: ParameterTestInputs, *, only: Optional[Sequence] = None) -> list[SubstrateExperiment]:
    """ The experiments of a test in print order.

    Parameters
    ----------
    test : {"quick", "full", "voxel"}
    inputs : ParameterTestInputs
    only : sequence, optional
        Full PT-01: field numbers (e.g. ``[3, 5]``); Voxel PT-01: powers in mW (e.g. ``[0.3, 0.5]``).

    Raises
    ------
    ValueError
        For an unknown test or a selection outside the test.
    """

    if test == "quick":
        return [SubstrateExperiment(quick_spec(inputs))]
    if test == "full":
        fields = sorted(FULL_FIELDS) if not only else [int(str(f).upper().lstrip("F")) for f in only]
        unknown = [f for f in fields if f not in FULL_FIELDS]
        if unknown:
            raise ValueError(f"Full PT-01 has no fields {unknown}.")
        return [SubstrateExperiment(full_spec(f, inputs)) for f in fields]
    if test == "voxel":
        powers = list(inputs.powers_mw)
        chosen = powers if not only else [round(float(p), 6) for p in only]
        unknown = [p for p in chosen if p not in powers]
        if unknown:
            raise ValueError(f"Powers {unknown} mW are not in the power ladder {powers}.")
        return [SubstrateExperiment(voxel_spec(p, inputs, index=powers.index(p))) for p in chosen]
    raise ValueError(f"Unknown test {test!r}; use one of {TESTS}.")


def substrate_spec(data_root: Optional[Path] = None) -> SubstrateSpec:
    """ The substrate of the parameter tests (``data_root`` for dry runs). """

    return SubstrateSpec(
        user=USER, objective=OBJECTIVE, resin_edges=RESIN_EDGES, label=SUBSTRATE_LABEL,
        # LAB: substrate and resin of this print
        material={"substrate": "boro-silicate glass", "thickness_um": 170.0, "resin": RESIN},
        substrate_type="cover_slip", dimensions={"shape": "round", "diameter_mm": 30.0, "thickness_um": 170.0},
        application="drop", notes="Parameter tests Quick PT / Full PT-01 / Voxel PT-01 (mains/parametertest/).",
        data_root=data_root)


# ------------------------------------------------------------------------------------------------
# Running
# ------------------------------------------------------------------------------------------------
def time_summary(folders: Sequence[Path]) -> list[tuple[str, float]]:
    """ Print the estimated printing time of every experiment folder and the sum. """

    from nanofactorysystem.storage import ExperimentStore
    rows = []
    for folder in folders:
        record = ExperimentStore.open(folder).read()
        rows.append((f"{record.label} {Path(folder).name}", float((record.time_estimate or {}).get("total_s", 0.0))))
    for name, seconds in rows:
        print(f"  {name:48s} {seconds / 60:7.1f} min")
    print(f"  {'sum':48s} {sum(s for _, s in rows) / 60:7.1f} min (incl. corners and QR code; plane fit and "
          f"overviews come on top)")
    return rows


def run(tests: Sequence[str], *, inputs_path: Optional[Path] = None, only: Optional[Sequence] = None, backend=None,
        plane=None, data_root: Optional[Path] = None, material_registry=None) -> list[Path]:
    """ Check the layout and print the given tests one after another on the substrate.

    The material start file is copied into every experiment folder (its values are also in ``/spec``).

    Returns
    -------
    list of Path
        The experiment folders.
    """

    from nanofactorysystem.experiment_spec import messagebox_confirm
    from nanofactorysystem.substrate_plan import run_substrate

    inputs_path = Path(inputs_path or INPUTS_FILE)
    inputs = load_inputs(inputs_path)
    planned = [e for test in tests for e in experiments(test, inputs, only=only)]
    interactive = backend is None
    folders = run_substrate(substrate_spec(data_root), planned, backend=backend, plane=plane,
                            confirm=messagebox_confirm if interactive and ASK_EACH_STEP else None,
                            confirm_between=messagebox_confirm if interactive and ASK_BETWEEN else None,
                            show_plot=interactive and SHOW_PLOTS, material_registry=material_registry)
    for folder in folders:
        shutil.copy2(inputs_path, Path(folder) / inputs_path.name)
    time_summary(folders)
    return folders


def check(tests: Sequence[str], *, inputs_path: Optional[Path] = None, only: Optional[Sequence] = None,
          show: bool = True):
    """ Check the layout of the given tests on the resin drop (and the marker clearance) without hardware. """

    from nanofactorysystem.substrate_plan import check_layout, plot_substrate
    inputs = load_inputs(inputs_path)
    planned = [e for test in tests for e in experiments(test, inputs, only=only)]
    substrate = substrate_spec()
    areas = check_layout(substrate, planned)
    for area in areas:
        print(f"  {area.name:30s} x {area.lower[0]:8.0f} .. {area.upper[0]:8.0f} µm, "
              f"y {area.lower[1]:8.0f} .. {area.upper[1]:8.0f} µm")
    plot_substrate(substrate, areas, show=show)
    return areas


def dry_run(tests: Sequence[str], **kwargs) -> list[Path]:
    """ Run the tests on simulated hardware. """

    import matplotlib
    matplotlib.use("Agg")
    from nanofactorysystem.backends.dummy.dry_run import dry_run as simulated_run
    with simulated_run(USER) as simulated:
        return run(tests, backend=simulated.backend, plane=simulated.plane, data_root=simulated.workdir / "data",
                   **kwargs)


def cli(tests: Sequence[str], description: str, *, selection_help: str = "") -> None:
    """ Command line of a test script: ``--layout``, ``--dry-run``, ``--inputs``, ``--only``. """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true", help="run on simulated hardware")
    parser.add_argument("--layout", action="store_true", help="only check and plot the layout")
    parser.add_argument("--inputs", type=Path, help="material start file (default parameter_tests_<resin>.json)")
    if selection_help:
        parser.add_argument("--only", help=selection_help)
    options = parser.parse_args()
    only = options.only.split(",") if getattr(options, "only", None) else None
    if options.layout:
        check(tests, inputs_path=options.inputs, only=only)
        print("Layout OK: no overlap, inside the resin drop, markers at least "
              f"{MARKER_CLEARANCE_UM:g} um away from every grid.")
    elif options.dry_run:
        folders = dry_run(tests, inputs_path=options.inputs, only=only)
        print("Dry run finished:", *folders, sep="\n  ")
    else:
        run(tests, inputs_path=options.inputs, only=only)
