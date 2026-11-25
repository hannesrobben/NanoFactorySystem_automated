# PTD-01 standard parameter test print (version 1, superseded)

> **Do not print these scripts.** They implement the two-stage plan (F0 first, then F1–F7 normalised with its
> results), which the maintainer replaced on 2026-11-25 by single-stage tests on absolute axes:
> `mains/parametertest/` (Quick PT, Full PT-01, Voxel PT-01; design `docs/design/PARAMETER_TESTS.md`). This folder
> stays until its removal is approved (attic procedure X-B, todo T164).

Scripts of the test print PTD-01 "voxel and line interaction" (phase 11, design
`docs/design/TEST_PRINT_PTD01.md`). Every field F0–F7 is its own experiment with its own
`experiment.h5`; `chain_ptd01.py` prints them one after another on one substrate. The fields are built
by the library `nanofactorysystem/testprint/` (named factories `ptd01.f0` … `ptd01.f7`).

Run every script with `mains/` as working directory, e.g. `python -m Experiments.ptd01.f3_line_pairs --dry-run`.

| File | Content |
|---|---|
| `common.py` | Substrate, resin, field positions (`CENTERS`), label power, reduced corners (D2), dwell after a power change (D9), spec helpers, CLI. Values marked `# LAB:` must be checked before printing. |
| `f0_interface.py` | Stage A: F0 interface & threshold (log power ladder × z offset). Input: `stage_a_<material>.json`. |
| `f1_lines.py` … `f7_pillars.py` | Stage B: F1 lines, F2 bridges, F3 line pairs, F4 squares, F5 layers, F6 crossings, F7 pillars. Input: the calibration file. |
| `chain_ptd01.py` | Chain of the fields (`--stage A`, `--stage B --calibration <file>`, `--stage all`, `--only`, `--replicates`, `--layout`, `--dry-run`). |
| `stage_a_SZ2080.json` | Start values of stage A for SZ2080 (decision D8: one file per material). **LAB: check p_min / p_max / label power.** |
| `calibration_example_SZ2080_Zeiss63x.json` | Example calibration (not measured) for dry runs and layout checks; refused for a real print. |

## Procedure

1. Lab check T148 (does `SET_POWER` wait for the attenuator?) → set `DWELL_AFTER_POWER_S` in `common.py`.
2. Stage A: `python -m Experiments.ptd01.chain_ptd01 --stage A` (prints F0). Develop, evaluate (SEM / DHM),
   fit the voxel model (`analysis/experiment_analysis/voxel_fit.py`, T151) and write
   `calibration_SZ2080_Zeiss63x.json` (`ProcessCalibration.save`, `provisional=True`).
3. Before stage B: measure the polarisation direction relative to x/y (D13) and enter it in the calibration.
4. Stage B: `python -m Experiments.ptd01.chain_ptd01 --stage B --calibration calibration_SZ2080_Zeiss63x.json`.
   The calibration file is copied into every stage-B experiment folder.
5. Evaluation: `analysis/experiment_analysis/ptd.py` regenerates the cell table of every field from its
   `experiment.h5` and exports a CSV template for the measured values (T147).

Recalibration rule (decision D14, documented only): if a new calibration changes P_th by more than 10 %,
print F1, F3 and F4 again (`--only F1,F3,F4`).

## Notes

- Replicates: 1 for the first print (D4); `--replicates 3` once the time per field is known.
- The 63x prints the highest layer first (D1); bridges and pillar tops are written before their supports.
- The number of layer programs dominates the time (each costs `layer_overhead_s`, 5 s): with the example
  calibration F5 has about 230 and F7 about 130 layers, because the slice distance follows l(P) of every row.
  The dry run of the chain prints the estimate per field.
