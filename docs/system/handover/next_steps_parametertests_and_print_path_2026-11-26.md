# Handover: next steps for the parameter tests (AP2) and the print path (AP3), 2026-11-26

For: the maintainer and later Claude Code sessions in this repository. Source: the cross-repository
planning of 2026-11-26 (work packages AP0–AP10). The maintainer did AP0 (branch consolidation, merge
`b77aed7`) and runs AP1 (lab session 3b, P5, T148) on the lab PC. AP2 and AP3 are **not started**; this file
describes them so that they can be taken into `TODO.md` or a session prompt unchanged. `main_HR` at
`b77aed7` is the reference state.

## Order

```
AP1 (lab, maintainer)                       AP2                         AP3
session 3b: T153 (+T101, T102, T154) ──┬──> T149 Quick PT ──> Full PT-01 + Voxel PT-01 ──> voxel DB
P5: one real layer with the laser ─────┼──> R9 default switch (T129) ──> T131 .ogm cache
T148: SET_POWER line pairs (D9) ───────┘    T165 task 2 (lab) · T167 lab day (replaces T69) · T130 default?
```

## AP2 — Print the parameter tests and close the voxel model

| # | Step | Needs | Done when | Where |
|---|---|---|---|---|
| 2.1 | T148 result entered: settling time of the attenuator, `dwell_after_power_s` (decision D9) | T148 lab run (script on `main_HR` since `33ee66f`) | value in `docs/design/TEST_PRINT_PTD01.md` §12 / `PARAMETER_TESTS.md` and in the material start file `mains/parametertest/parameter_tests_SZ2080.json` | WORKLOG |
| 2.2 | T149 Quick PT | 2.1, a fresh substrate, layout check (`chain.py --test quick --layout`, then `--dry-run`) | Quick PT printed, measured (SEM / camera), cell table filled, start file updated | `mains/parametertest/quick_pt.py`, `analysis/experiment_analysis/ptd.py` |
| 2.3 | T149 Full PT-01 (F1–F7, sub-fields a 0.1–0.5 mW / b 0.6–1.0 mW) and Voxel PT-01 | 2.2 | printed and evaluated; actual vs. estimated time per experiment in WORKLOG | `full_pt01.py`, `voxel_pt01.py`, `chain.py` |
| 2.4 | Polarisation direction relative to x/y (D13) | before 2.3 | documented in WORKLOG and the design | – |
| 2.5 | Voxel fit | 2.3 | `voxel_fit.py` fit of w(P), l(P) with n_eff = 1 (T156 placeholder); result written as `ProcessCalibration` JSON | `analysis/experiment_analysis/voxel_fit.py` |
| 2.6 | Measured voxel sizes into the voxel database | 2.3 | `ptd.import_voxel_measurements(csv, VoxelDatabase(...), fields=...)` imports the rows; **check first:** its default `VOXEL_FIELDS = (0, 1, 2)` comes from PTD-01 version 1; in version 2 the field ids are reused per test (Quick PT 1 = walls, 2 = pads; Full PT-01 1–7), so `fields=` must be given per test or the function extended to filter by test name. If it needs a code change, that is a new todo. | `analysis/experiment_analysis/ptd.py:180`, `nanofactorysystem/voxel/database.py` |
| 2.7 | Slicer uses the measured voxels | 2.6 | a dry run with `voxel_model="database"` (T54) gives the measured w/l for SZ2080 at 63x | `nanofactorysystem/voxel/` |

Open decisions on the way: none beyond D9. Problems found on the lab PC become todos `(found during T149)`.
What it gives: the first measured material data set (SZ2080 at 63x), needed for voxel-aware slicing, the
process model (T92) and later the controller (F16).

## AP3 — Finish the print path

| # | Step | Needs | Done when | Where |
|---|---|---|---|---|
| 3.1 | **R9 decision:** library loader as default? Maintainer decision 2026-11-26: possible later, the ASCII path stays selectable; no switch and no change of add-ahead before session 3b shows that add-ahead works | AP1 (session 3b `runner`, P5 real layer) | decision recorded in `TODO.md` "Decided" and `docs/design/PROGRAM_LOADING.md` §7 | T129 |
| 3.2 | T129 closed | 3.1 | if switched: `Experiment(program_loader=...)` default changed with a dummy test, the T125 split used only for the ASCII path, golden command logs re-recorded with the reason; if not: T129 closed as "opt-in, validated" | `devices/aerotech/loader.py`, `experiment.py`, `aerobasic/programs/split.py` |
| 3.3 | T131 `.ogm` cache per part | 3.2 (loader runs robustly) | parts compiled ahead and loaded as `.ogm`; cache key = program hash + controller software version / configuration; removal under `<stem>.pgm` verified; dummy loader simulates the cache; lab check of one layer | `devices/aerotech/` |
| 3.4 | T130 as default build step? | maintainer decision | T130 is done as opt-in (`Experiment(optimize_programs=)`, `1adf8b4`); a default needs the golden files re-recorded on purpose | `aerobasic/programs/optimize.py` |
| 3.5 | T165 task-2 parameters = task 1, base programs (z-line, corners, QR code) on task 2 | lab PC; parameter file backed up | time ratio task 1 / task 2 = 1.0 ± 2 %; base programs never on the task of a print part; golden command logs re-recorded with the reason | controller parameter file, `devices/a3200.py`, `experiment.py` |
| 3.6 | T167 intensive lab day (replaces T69) | T112 (done), T148 | work order, guide and scripts for the new features (overview in focus, captures, power per layer, repetition, restart after Ctrl+C) and program types (CW/CCW arcs, velocity on fine structures, laser on/off timing); run by the maintainer; T69 closed | `docs/design/`, `docs/guides/`, `mains/lab_checks/` |

Lab result folders under `mains/lab_checks/` are test data and stay out of the repository (`.gitignore`).

## Prompt for a later session

> Read `docs/system/handover/next_steps_parametertests_and_print_path_2026-11-26.md`. AP1 results are in
> WORKLOG.md (session 3b, P5, T148). Continue with AP2 step <n> / AP3 step <n>; follow CLAUDE.md (branch,
> commits, WORKLOG, TODO).
