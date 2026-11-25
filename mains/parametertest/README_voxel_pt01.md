# Voxel PT-01 (gap test)

Measures the voxel height (length l along the beam) directly, without a tilted SEM view: a lid is written above a
base with a growing gap; once the gap is larger than the voxel can bridge, the lid is gone after development.
Design: `docs/design/PARAMETER_TESTS.md` §6.

Script: `python -m parametertest.voxel_pt01 [--only 0.3,0.5] [--layout | --dry-run]` (working directory `mains/`).
Builder: `voxel_pt01.gap` in `nanofactorysystem/testprint/parameter_tests.py`.

## Structure of a gap cell

```
   lid: 4 layers of 0.25 µm (1 µm) at z = 2.0 + gap + k · 0.25, power = the tested power
   ─────────────  ← gap 0 … 2.0 µm in steps of 0.2 µm (gap 0 = top layer of the base exposed twice)
   base: 20 × 20 µm, layers of 0.25 µm from z = 0 to 2.0 µm, support power 0.5 mW
   ═════════════  substrate (first layer repeated 1 µm into it)
```

Base and lid: hatch 0.2 µm, alternating x/y.

## Layout

- **One experiment per lid power** (0.1 … 1.0 mW, ten experiments), each can be repeated on its own.
- In an experiment every gap cell is its own structure, the cells **100 µm apart in a 3 × 4 grid**: gaps
  0 / 0.2 / … / 2.0 µm row by row, the twelfth place stays empty. Every cell lies on the optical axis of its
  grid cell and in its own DHM image; 20 µm leave room for DHM and SEM evaluation.

## What it examines

| Observation per experiment (power P) | Gives |
|---|---|
| largest gap with the lid still attached / smallest gap without lid | bracket of the bridgeable gap g_max(P) (to ±0.1 µm) |
| lid present but tilted or partly detached | transition region, adhesion of the lid |
| gap 0 (double exposure of the top layer) | overdose behaviour of a re-exposed layer |

The lid attaches as long as the lid voxel and the top layer of the base overlap: roughly
g_max(P) ≈ (l(P) + l_base) / 2. The experiment at the support power (0.5 mW: lid and base have the same power)
gives l_base = g_max(0.5 mW); then l(P) ≈ 2 · g_max(P) − l_base for every other power
(`experiment_analysis.ptd.voxel_lengths_from_gaps`).

## Evaluation

Mark in the exported cell table (`export_cell_table`) for every gap cell whether the lid is present
(`present` = 1 / 0); `voxel_lengths_from_gaps` turns the rows into l(P) values that go into the voxel fit
(`experiment_analysis.voxel_fit`). A finer gap series around the found limit is a follow-up test.
