##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Chain of the PTD-01 fields on one substrate, stage A and stage B (T146, design §6.2).

- ``--stage A``: F0 only (interface and threshold); input ``stage_a_<material>.json``.
- ``--stage B --calibration <file>``: F1 … F7 in this order; refuses a missing, mismatching or example
  calibration before anything moves and copies the file into every stage-B experiment folder.
- ``--stage all --calibration <file>``: F0 and F1 … F7 (repeat prints with a known calibration).
- ``--only F3,F5``: a subset of the stage; ``--replicates n`` copies per field (D4: 1 first).
- ``--layout``: check and plot the layout of the stage on the resin drop (no hardware).
- ``--dry-run``: run on simulated hardware (example calibration unless ``--calibration`` is given).

After printing, the estimated time of every field and the sum are printed. Recalibration rule
(decision D14): if a new calibration changes P_th by more than 10 %, print F1, F3 and F4 again
(``--stage B --only F1,F3,F4``).

Run with ``mains/`` as working directory: ``python -m Experiments.ptd01.chain_ptd01 --stage A --dry-run``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from Experiments.ptd01 import common

STAGES = {"A": common.STAGE_A_FIELDS, "B": common.STAGE_B_FIELDS,
          "all": common.STAGE_A_FIELDS + common.STAGE_B_FIELDS}


def field_ids(stage: str, only: Optional[str | Sequence] = None) -> list[int]:
    """ The fields of a stage in print order, optionally restricted to ``only``.

    Parameters
    ----------
    stage : {"A", "B", "all"}
    only : str or sequence, optional
        E.g. ``"F3,F5"`` or ``[3, 5]``; every field must belong to the stage.

    Raises
    ------
    ValueError
        For an unknown stage or a field outside the stage.
    """

    if stage not in STAGES:
        raise ValueError(f"Unknown stage {stage!r}; use one of {sorted(STAGES)}.")
    fields = list(STAGES[stage])
    if only is None or only == "":
        return fields
    items = only.split(",") if isinstance(only, str) else list(only)
    wanted = [int(str(item).strip().upper().lstrip("F")) for item in items]
    outside = [f for f in wanted if f not in fields]
    if outside:
        raise ValueError(f"Fields {['F%d' % f for f in outside]} do not belong to stage {stage}.")
    return [f for f in fields if f in wanted]


def check_inputs(stage: str, calibration_path: Optional[Path]) -> None:
    """ Stage B and ``all`` need an explicit calibration file.

    Raises
    ------
    ValueError
        If the calibration is missing for stage B / all.
    """

    if stage in ("B", "all") and calibration_path is None:
        raise ValueError(f"Stage {stage} needs the calibration of stage A (--calibration <file>).")


def time_summary(folders: Sequence[Path]) -> list[tuple[str, float]]:
    """ Estimated printing time of every experiment folder and the sum, printed as a table.

    Returns
    -------
    list of (str, float)
        Experiment label with field name, and estimated time in seconds.
    """

    from nanofactorysystem.storage import ExperimentStore
    rows = []
    for folder in folders:
        record = ExperimentStore.open(folder).read()
        estimate = (record.time_estimate or {}).get("total_s", 0.0)
        fields = [s.name for s in record.structures if s.type == "IFOV"]
        rows.append((f"{record.label} {fields[0] if fields else Path(folder).name}", float(estimate)))
    for name, seconds in rows:
        print(f"  {name:32s} {seconds / 60:7.1f} min")
    print(f"  {'sum':32s} {sum(s for _, s in rows) / 60:7.1f} min (layer programs incl. corners and QR code; "
          f"plane fit and overviews come on top)")
    return rows


def main(stage: str = "A", *, calibration_path: Optional[Path] = None, stage_a_path: Optional[Path] = None,
         only: Optional[str | Sequence] = None, replicates: int = 1, axes: Optional[dict] = None, backend=None,
         plane=None, data_root: Optional[Path] = None, material_registry=None,
         allow_example: bool = False) -> list[Path]:
    """ Check the layout and print the fields of a stage one after another on the substrate.

    Parameters
    ----------
    stage : {"A", "B", "all"}
    calibration_path : Path, optional
        Stage-B calibration (required for B and all).
    stage_a_path : Path, optional
        Stage-A axes (default ``common.STAGE_A_FILE``).
    only : str or sequence, optional
        Subset of the stage, e.g. ``"F3,F5"``.
    replicates : int
    axes : dict, optional
        ``field_id -> axis keyword arguments`` (fewer levels for a quick dry run).
    backend, plane, data_root, material_registry
        As in ``common.run_fields``.
    allow_example : bool
        Accept the example calibration (dry runs only).

    Returns
    -------
    list of Path
        The experiment folders.
    """

    fields = field_ids(stage, only)
    check_inputs(stage, calibration_path)
    folders = common.run_fields(fields, calibration_path=calibration_path, stage_a_path=stage_a_path,
                                replicates=replicates, axes=axes, backend=backend, plane=plane, data_root=data_root,
                                material_registry=material_registry, allow_example=allow_example)
    time_summary(folders)
    return folders


def check(stage: str = "all", *, calibration_path: Optional[Path] = None, only=None, replicates: int = 1,
          show: bool = True):
    """ Check the layout of a stage on the resin drop and plot it, without hardware. """

    return common.check_fields(field_ids(stage, only), calibration_path=calibration_path, replicates=replicates,
                               show=show)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", choices=sorted(STAGES), default="A")
    parser.add_argument("--calibration", type=Path, help="stage-B calibration file")
    parser.add_argument("--stage-a", type=Path, help="stage-A axes file")
    parser.add_argument("--only", help="subset of the stage, e.g. F3,F5")
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--layout", action="store_true", help="only check and plot the layout")
    parser.add_argument("--dry-run", action="store_true", help="run on simulated hardware")
    options = parser.parse_args()
    if options.layout:
        check(options.stage, calibration_path=options.calibration, only=options.only, replicates=options.replicates)
        print("Layout OK: no overlap, every field experiment inside the resin drop.")
    elif options.dry_run:
        import matplotlib
        matplotlib.use("Agg")
        from nanofactorysystem.backends.dummy.dry_run import dry_run
        calibration = options.calibration or (common.EXAMPLE_CALIBRATION_FILE if options.stage != "A" else None)
        with dry_run(common.USER) as simulated:
            result = main(options.stage, calibration_path=calibration, stage_a_path=options.stage_a,
                          only=options.only, replicates=options.replicates, backend=simulated.backend,
                          plane=simulated.plane, data_root=simulated.workdir / "data", allow_example=True)
        print("Dry run finished:", *result, sep="\n  ")
    else:
        main(options.stage, calibration_path=options.calibration, stage_a_path=options.stage_a, only=options.only,
             replicates=options.replicates)
