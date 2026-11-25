##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Shared settings of the PTD-01 field scripts and the chain (T145, T146, design §6).

Every field F0 … F7 is its own experiment (own ``experiment.h5``, restartable on its own); the chain
``chain_ptd01.py`` runs them one after another on one substrate. This module holds the substrate, the
field positions, the reduced corner markers and the helpers that build the experiment specs.

Values that depend on the substrate or the material in the lab are marked ``# LAB:``; check them before
printing. The stage-A start values are in ``stage_a_<material>.json`` (decision D8), the stage-B
calibration in ``calibration_<material>_<objective>.json`` (written after the evaluation of stage A).
``calibration_example_SZ2080_Zeiss63x.json`` holds example values for dry runs only; a real print
refuses it.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Optional, Sequence

from nanofactorysystem.devices.coordinate_system import Point2D
from nanofactorysystem.experiment import ProgramSource, StructureType
from nanofactorysystem.experiment_spec import CornerSpec, ExperimentSpec, StructureSpec, default_sys_args
from nanofactorysystem.plane_fitting import PlaneFitMode
from nanofactorysystem.substrate_plan import SubstrateExperiment, SubstrateSpec
from nanofactorysystem.testprint import ptd01
from nanofactorysystem.testprint.calibration import ProcessCalibration, StageAAxes
from nanofactorysystem.testprint.factories import FACTORIES

HERE = Path(__file__).resolve().parent

# ------------------------------------------------------------------------------------------------
# Substrate and placement (absolute stage coordinates in µm)
# ------------------------------------------------------------------------------------------------
USER = "Hannes"                                      # user key "user:<name>" of ~/nanofactory.json
OBJECTIVE = "Zeiss 63x"                              # IFOV setup and fixed writing speed of the 63x
SETUP = "IFOV_on"
RESIN = "SZ2080"                                     # LAB: registry name of the resin
# LAB: edges of the resin drop measured with the camera: right, left, near, far (as in T113)
RESIN_EDGES = [[-4900, -2300], [4300, -700], [-800, -5900], [-200, 3600]]
# LAB: centre of every field experiment, a 2 x 4 block (stage A: F0 only; stage B: F1 … F7)
CENTERS = {
    0: Point2D(-1050, 350), 1: Point2D(-350, 350), 2: Point2D(350, 350), 3: Point2D(1050, 350),
    4: Point2D(-1050, -350), 5: Point2D(-350, -350), 6: Point2D(350, -350), 7: Point2D(1050, -350),
}
SUBSTRATE_LABEL: Optional[str] = None                # LAB: e.g. "HR-26-003"; None = next free label
LABEL_POWER_MW = 0.7                                 # LAB: power of the header marks (as the T113 corners)
# Reduced corner markers with QR code for the 50 µm fields (decision D2)
FIELD_CORNER = CornerSpec(z_um=-2.0, width_um=20.0, length_um=150.0, height_um=4.0, hatch_um=0.3, slice_um=0.75)
DWELL_AFTER_POWER_S = 0.0                            # D9: set from the lab check T148
# Unattended run: set all three to False, then nothing waits for a click
ASK_EACH_STEP = True                                 # confirm plane fit and printing inside every experiment
ASK_BETWEEN = True                                   # confirm before starting the next experiment
SHOW_PLOTS = True                                    # layout plot windows (must be closed to continue)

STAGE_A_FILE = HERE / f"stage_a_{RESIN}.json"
CALIBRATION_FILE = HERE / f"calibration_{RESIN}_{OBJECTIVE.replace(' ', '')}.json"
EXAMPLE_CALIBRATION_FILE = HERE / f"calibration_example_{RESIN}_{OBJECTIVE.replace(' ', '')}.json"

STAGE_A_FIELDS = (0,)
STAGE_B_FIELDS = (1, 2, 3, 4, 5, 6, 7)


# ------------------------------------------------------------------------------------------------
# Input files
# ------------------------------------------------------------------------------------------------
def load_stage_a(path: Optional[Path] = None) -> StageAAxes:
    """ The stage-A start values of the resin (``stage_a_<material>.json``).

    Raises
    ------
    ValueError
        If the file is for another material.
    """

    axes = StageAAxes.load(path or STAGE_A_FILE)
    if axes.material != RESIN:
        raise ValueError(f"{path or STAGE_A_FILE} is for {axes.material!r}, the substrate uses {RESIN!r}.")
    return axes


def load_calibration(path: Optional[Path] = None, *, allow_example: bool = False) -> ProcessCalibration:
    """ The stage-B calibration; it must match resin, objective and setup of the substrate.

    Parameters
    ----------
    path : Path, optional
        Default ``CALIBRATION_FILE``.
    allow_example : bool
        Accept a file with example values (dry runs only).

    Raises
    ------
    FileNotFoundError
        If the file does not exist (stage A has not been evaluated yet).
    ValueError
        For a mismatching or an example calibration.
    """

    path = Path(path or CALIBRATION_FILE)
    if not path.is_file():
        raise FileNotFoundError(f"Calibration file {path} not found: evaluate stage A (F0) first and write it "
                                f"(ProcessCalibration.save).")
    calibration = ProcessCalibration.load(path)
    if not calibration.matches(RESIN, OBJECTIVE, SETUP):
        raise ValueError(f"{path} is for {calibration.material} / {calibration.objective} / {calibration.setup}, "
                         f"the substrate uses {RESIN} / {OBJECTIVE} / {SETUP}.")
    if calibration.is_example and not allow_example:
        raise ValueError(f"{path} holds example values (source {calibration.source!r}); a real print needs the "
                         f"evaluated stage-A calibration.")
    return calibration


# ------------------------------------------------------------------------------------------------
# Experiment specs
# ------------------------------------------------------------------------------------------------
def field_call(field_id: int, *, stage_a: Optional[StageAAxes] = None,
               calibration: Optional[ProcessCalibration] = None, **axes):
    """ The factory call of a field: F0 with the stage-A axes, F1 … F7 with the calibration.

    Raises
    ------
    ValueError
        If the needed input is missing.
    """

    factory = FACTORIES[field_id]
    if field_id == 0:
        if stage_a is None:
            raise ValueError("F0 needs the stage-A axes.")
        return factory(stage_a=stage_a.to_json(), dwell_after_power_s=DWELL_AFTER_POWER_S, **axes)
    if calibration is None:
        raise ValueError(f"F{field_id} needs the stage-B calibration.")
    return factory(calibration=calibration.to_json(), label_power_mw=LABEL_POWER_MW,
                   dwell_after_power_s=DWELL_AFTER_POWER_S, **axes)


def describe(field_id: int, calibration: Optional[ProcessCalibration] = None,
             stage_a: Optional[StageAAxes] = None) -> str:
    """ Description of a field experiment for the summary. """

    name = ptd01.FIELD_NAMES[field_id]
    if field_id == 0 and stage_a is not None:
        return (f"PTD-01 {name}: {stage_a.n_levels} powers {stage_a.p_min_mw:g}-{stage_a.p_max_mw:g} mW (log, rows) "
                f"x z offsets {list(stage_a.z_offsets_um)} um (columns), 4 um lines.")
    source = f"; calibration {calibration.source} ({calibration.date})" if calibration is not None else ""
    return f"PTD-01 {name} on normalised axes (P/P_th, h/w, dz/l){source}."


def field_spec(field_id: int, call, *, replicates: int = 1, center: Optional[Point2D] = None,
               description: str = "") -> ExperimentSpec:
    """ The experiment of one field (design §6.1).

    Parameters
    ----------
    field_id : int
        0 … 7.
    call : FactoryCall
        The field's factory call (:func:`field_call`).
    replicates : int
        Copies of the field in the next grid cells (``StructureType.REPEAT``, decision D4: 1 first).
    center : Point2D, optional
        Default ``CENTERS[field_id]``.
    description : str

    Returns
    -------
    ExperimentSpec
    """

    if replicates < 1:
        raise ValueError("replicates must be >= 1")
    name = ptd01.FIELD_NAMES[field_id]
    sys_args = default_sys_args()
    sys_args["attenuator"]["fitKind"] = "quadratic"
    sys_args["sample"]["name"] = f"ptd01_{name}"
    sys_args["focus"]["exposureValue"] = 120
    sys_args["layer"]["laserPower"] = 0.7               # LAB: power for the resin interface detection
    stage = "stage_A" if field_id in STAGE_A_FIELDS else "stage_B"
    return ExperimentSpec(
        name=f"ptd01_{name}",
        description=description or describe(field_id),
        tags=["ptd01", f"F{field_id}", stage],
        objective=OBJECTIVE,
        center=center if center is not None else CENTERS[field_id],
        grid=(1, replicates),
        structure_size_um=None,                         # grid cell = FOV (150 µm), field on the optical axis
        skip_corner=False,
        corner=FIELD_CORNER,
        structures=[StructureSpec(name, factory=call, power_mw=LABEL_POWER_MW, axes="XYZ",
                                  structure_type=StructureType.IFOV, repeat=replicates - 1)],
        program_source=ProgramSource.DRAWING,
        setup=SETUP,
        default_power_mw=LABEL_POWER_MW,                # corner markers and QR code
        plane_fit_mode=PlaneFitMode.CORNERS,
        dhm_usage=False,
        camera_capture=True,
        overview_capture=True,
        materials={"resin": RESIN},
        layer_overhead_s=5.0,
        sys_args=sys_args,
    )


def substrate_spec(data_root: Optional[Path] = None) -> SubstrateSpec:
    """ The substrate of the PTD-01 prints.

    Parameters
    ----------
    data_root : Path, optional
        Data root instead of ``dataRoot`` of the user (dry runs).
    """

    return SubstrateSpec(
        user=USER,
        objective=OBJECTIVE,
        resin_edges=RESIN_EDGES,
        label=SUBSTRATE_LABEL,
        # LAB: substrate and resin of this print
        material={"substrate": "boro-silicate glass", "thickness_um": 170.0, "resin": RESIN},
        substrate_type="cover_slip",
        dimensions={"shape": "round", "diameter_mm": 30.0, "thickness_um": 170.0},
        application="drop",
        notes="Standard parameter test print PTD-01 (mains/Experiments/ptd01/).",
        data_root=data_root,
    )


def experiments(field_ids: Sequence[int], *, calibration: Optional[ProcessCalibration] = None,
                stage_a: Optional[StageAAxes] = None, replicates: int = 1,
                axes: Optional[dict] = None) -> list[SubstrateExperiment]:
    """ The experiments of the given fields in print order.

    Parameters
    ----------
    field_ids : sequence of int
    calibration, stage_a
        Inputs of stage B and stage A.
    replicates : int
    axes : dict, optional
        ``field_id -> axis keyword arguments`` (e.g. fewer levels for a quick dry run).
    """

    axes = axes or {}
    return [SubstrateExperiment(field_spec(i, field_call(i, stage_a=stage_a, calibration=calibration,
                                                         **axes.get(i, {})),
                                           replicates=replicates, description=describe(i, calibration, stage_a)))
            for i in field_ids]


def copy_calibration(folders: Sequence[Path], calibration_path: Path) -> None:
    """ Copy the calibration file into every stage-B experiment folder (design §6.2). """

    for folder in folders:
        shutil.copy2(calibration_path, Path(folder) / Path(calibration_path).name)


def run_fields(field_ids: Sequence[int], *, calibration_path: Optional[Path] = None,
               stage_a_path: Optional[Path] = None, replicates: int = 1, axes: Optional[dict] = None,
               backend=None, plane=None, data_root: Optional[Path] = None, material_registry=None,
               allow_example: bool = False) -> list[Path]:
    """ Check the layout and print the given fields one after another on the substrate.

    The stage-A axes are read for F0, the calibration for F1 … F7; a stage-B field refuses a missing,
    mismatching or example calibration before anything moves (``allow_example`` for dry runs).

    Returns
    -------
    list of Path
        The experiment folders.
    """

    from nanofactorysystem.experiment_spec import messagebox_confirm
    from nanofactorysystem.substrate_plan import run_substrate

    stage_b = [i for i in field_ids if i in STAGE_B_FIELDS]
    stage_a = load_stage_a(stage_a_path) if any(i in STAGE_A_FIELDS for i in field_ids) else None
    calibration = None
    if stage_b:
        calibration_path = Path(calibration_path or CALIBRATION_FILE)
        calibration = load_calibration(calibration_path, allow_example=allow_example)
    interactive = backend is None
    folders = run_substrate(substrate_spec(data_root),
                            experiments(field_ids, calibration=calibration, stage_a=stage_a, replicates=replicates,
                                        axes=axes),
                            backend=backend, plane=plane,
                            confirm=messagebox_confirm if interactive and ASK_EACH_STEP else None,
                            confirm_between=messagebox_confirm if interactive and ASK_BETWEEN else None,
                            show_plot=interactive and SHOW_PLOTS, material_registry=material_registry)
    if stage_b:
        copy_calibration([f for i, f in zip(field_ids, folders) if i in STAGE_B_FIELDS], calibration_path)
    return folders


def check_fields(field_ids: Sequence[int], *, calibration_path: Optional[Path] = None,
                 stage_a_path: Optional[Path] = None, replicates: int = 1, show: bool = True,
                 allow_example: bool = True):
    """ Check the layout of the given fields on the resin drop and plot it, without hardware.

    The example calibration is accepted here: the layout does not depend on the calibration values.
    """

    from nanofactorysystem.substrate_plan import check_layout, plot_substrate
    stage_a = load_stage_a(stage_a_path) if any(i in STAGE_A_FIELDS for i in field_ids) else None
    calibration = None
    if any(i in STAGE_B_FIELDS for i in field_ids):
        path = calibration_path or (CALIBRATION_FILE if CALIBRATION_FILE.is_file() else EXAMPLE_CALIBRATION_FILE)
        calibration = load_calibration(path, allow_example=allow_example)
    substrate = substrate_spec()
    areas = check_layout(substrate, experiments(field_ids, calibration=calibration, stage_a=stage_a,
                                                replicates=replicates))
    for area in areas:
        print(f"  {area.name:22s} x {area.lower[0]:8.0f} .. {area.upper[0]:8.0f} µm, "
              f"y {area.lower[1]:8.0f} .. {area.upper[1]:8.0f} µm")
    plot_substrate(substrate, areas, show=show)
    return areas


def dry_run(field_ids: Sequence[int], **kwargs) -> list[Path]:
    """ Run the fields on simulated hardware (example calibration unless one is given). """

    import matplotlib
    matplotlib.use("Agg")
    from nanofactorysystem.backends.dummy.dry_run import dry_run as simulated_run
    if any(i in STAGE_B_FIELDS for i in field_ids):
        kwargs.setdefault("calibration_path", EXAMPLE_CALIBRATION_FILE)
    with simulated_run(USER) as simulated:
        return run_fields(field_ids, backend=simulated.backend, plane=simulated.plane,
                          data_root=simulated.workdir / "data", allow_example=True, **kwargs)


def field_cli(field_id: int, description: str) -> None:
    """ Command line of a single field script: ``--layout``, ``--dry-run``, ``--calibration``, ``--replicates``. """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true", help="run on simulated hardware")
    parser.add_argument("--layout", action="store_true", help="only check and plot the layout")
    parser.add_argument("--calibration", type=Path, help="stage-B calibration file")
    parser.add_argument("--stage-a", type=Path, help="stage-A axes file")
    parser.add_argument("--replicates", type=int, default=1)
    options = parser.parse_args()
    files = {"calibration_path": options.calibration, "stage_a_path": options.stage_a,
             "replicates": options.replicates}
    if options.layout:
        check_fields([field_id], **files)
        print("Layout OK: the field experiment lies inside the resin drop.")
    elif options.dry_run:
        folders = dry_run([field_id], **{k: v for k, v in files.items() if v is not None})
        print("Dry run finished:", *folders, sep="\n  ")
    else:
        run_fields([field_id], **files)
