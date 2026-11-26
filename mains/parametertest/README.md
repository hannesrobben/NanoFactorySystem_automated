# Parameter tests

Standard parameter tests for a new resin / objective, design `docs/design/PARAMETER_TESTS.md` (version 2,
approved 2026-11-25). The names are provisional.

| Test | Script | README | Purpose |
|---|---|---|---|
| **Quick PT** | `quick_pt.py` | [README_quick_pt.md](README_quick_pt.md) | First experience values: polymerisation threshold, damage, surface formation |
| **Full PT-01** | `full_pt01.py` | [README_full_pt01.md](README_full_pt01.md) | Line interaction, surfaces, layers, crossings, mechanical limits (fields F1–F7) |
| **Voxel PT-01** | `voxel_pt01.py` | [README_voxel_pt01.md](README_voxel_pt01.md) | Voxel height (length) with a gap test |
| Chain | `chain.py` | – | Runs the selected tests one after another on one substrate |

## Principles

- **No prior knowledge.** The tests measure the threshold power, voxel width and voxel length; none of it is
  needed to print. No calibration file, no fit model, no voxel database is read. Relative quantities
  (P/P_th, hatch/width, slice/length) are computed in the evaluation.
- **Absolute axes.** Power ladder 0.1 … 1.0 mW in 0.1 mW steps; hatch, slice and spacing in µm.
- **60 × 60 µm fields** (DHM field of view ~85 µm minus border and centring error). Every field is split into
  **sub-field a** (0.1–0.5 mW) and **sub-field b** (0.6–1.0 mW), five power rows each, row 0 = lowest power at
  the bottom. Both lie in the same experiment, each on the optical axis of its grid cell. The layout is the same
  for every field, so the evaluation needs no special cases.
- **Header strip** (top 5 µm of each sub-field): L mark (orientation), field number as 3 dots (a dot for a 1 bit,
  most significant bit first), sub-field bit (dot = b), REF pad 4 × 4 × 1 µm at the support power (drift and
  comparison reference). Marks at 0.5 mW.
- **Supports** (pedestals, bases, caps, REF pad, gap-test bases): 0.5 mW, hatch 0.2 µm, slice 0.25 µm.
- **Anchoring:** the first layer of volume cells is repeated 1 µm into the substrate.
- **Minimum gaps:** 2 µm between line cells, 4.5 µm between volume cells.
- **QR code and corner markers** stay at least 20 µm away from every grid (margin 90 µm); `common.check_marker_clearance`
  refuses any layout that violates it.
- One experiment = one `experiment.h5`, restartable on its own; all experiments go into the substrate index.

## Input: the material start file

`parameter_tests_SZ2080.json` (schema `nanofactory.parameter_tests/1`) holds every value of all three tests:
power ladder, label and support power, anchoring depth and the axis lists. For a new material copy it to
`parameter_tests_<material>.json`, set `material` and adapt the values; missing sections take the defaults of
`nanofactorysystem/testprint/inputs.py`. Its content is stored in `/spec` of every experiment and the file is
copied into every experiment folder. **LAB:** check the power ladder and the support power for the material.

## Settings in `common.py`

`USER`, `RESIN`, `RESIN_EDGES`, `SUBSTRATE_LABEL`, `CENTERS` (position of all 18 experiments: Quick PT, F1–F7,
ten Voxel PT-01 powers), `CORNER_POWER_MW` (corners and QR code, 0.7 mW), `DWELL_AFTER_POWER_S` (0 until the lab
check T148), `ASK_EACH_STEP` / `ASK_BETWEEN` / `SHOW_PLOTS`. Values marked `# LAB:` must be checked before printing.

## Running (working directory `mains/`)

```
python -m parametertest.chain --test all --layout       # layout of all 18 experiments, no hardware
python -m parametertest.quick_pt --dry-run              # simulated hardware
python -m parametertest.full_pt01 --only F3,F5          # lab PC, two fields
python -m parametertest.voxel_pt01 --only 0.3,0.5       # lab PC, two powers
```

Before a lab session: `git pull`, restart the A3200 software, check the `# LAB:` values.

## Printing time (dummy estimate, layer programs only)

Quick PT about 3 min; Full PT-01 about 25 min for F1–F7 (F5 and F7 about 4 min per sub-field); Voxel PT-01 about
17 layers per gap cell. Plane fit, corners, QR code and overview images come on top. `common.time_summary` prints
the estimate after every run.

## Evaluation

`analysis/experiment_analysis/ptd.py` rebuilds the cell table of every field from `/spec` (absolute values,
sub-field, stage position of every cell), exports a CSV template for the measured values and adds the relative
columns once P_th, w and l are known. `analysis/experiment_analysis/voxel_fit.py` fits w(P), l(P).

## Version 1

The superseded two-stage PTD-01 scripts (F0 first, then F1–F7 normalised with its results) were moved to the local
attic on 2026-11-26 (T164); `docs/ATTIC_INDEX.md` lists them with the commit to restore them from.
