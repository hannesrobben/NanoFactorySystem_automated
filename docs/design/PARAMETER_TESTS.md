# Design: Parameter tests Quick PT, Full PT-01, Voxel PT-01 (version 2)

Status: approved 2026-11-25 (all proposals decided in the review of 2026-11-25, §8)

Date: 2026-11-25. Todo: T157. Replaces the two-stage plan of `TEST_PRINT_PTD01.md` (version 1, approved
2026-11-25 and implemented in T137–T147, T150, T151). Decisions of the session of 2026-11-25 (afternoon)
are marked **[decided]** (no open proposals remain). The names
are provisional (the maintainer will rename the tests later).

## 1. Why version 2

Version 1 printed stage A (F0) first, evaluated it and printed stage B (F1–F7) on axes normalised with the
results of stage A (P/P_th, h/w(P), Δz/l(P)). In the review of the implementation the maintainer
clarified the intent:

- A parameter test is run on a **new, unknown material**. P_th, voxel width w and voxel length l are what
  the test measures; nothing about them may be needed before printing. A coarse ladder (F0) only gives
  P_th to one ladder step, so normalising stage B with it adds an evaluation round without real benefit.
- **The voxel database is never read** for a parameter test (also true in version 1); it is only the
  target of the evaluation.
- The first test is a broad overview; detailed tests (exact threshold, voxel height) follow as their own
  tests.

Hence **[decided]**: single-stage tests on **absolute axes**; every relative quantity (P/P_th, h/w, Δz/l)
is computed only in the evaluation, once P_th, w and l are measured.

## 2. The three tests

| Test (provisional name) | Purpose | Content |
|---|---|---|
| **Quick PT** | First experience value for a material: polymerisation threshold, surface formation | walls (stacked lines) × power; pads × hatch × power (§4) |
| **Full PT-01** | Line interaction, surfaces, layers, crossings, limits | F1–F7 of version 1 on absolute axes (§5) |
| **Voxel PT-01** | Voxel height (length l) | gap test: base, gap, lid (§6) |

All three are independent prints (each its own `experiment.h5`, restartable); they can be chained on one
substrate (`run_substrate`), but no test needs the result of another one.

## 3. Common rules

| Rule | Value | Status |
|---|---|---|
| Power ladder | 0.1 … 1.0 mW, linear, steps of 0.1 mW (10 levels); intermediate values are tested later, based on the results | **[decided]** |
| Field size | 60 × 60 µm: DHM field of view about 85 µm minus the propagation border and the centring error | **[decided]** |
| Power split | every field consists of two sub-fields: **a** = 0.1 / 0.2 / 0.3 / 0.4 / 0.5 mW, **b** = 0.6 … 1.0 mW (5 rows each), both in the same experiment side by side, each on the optical axis of its grid cell; identical layout for every field, so the evaluation needs no special cases | **[decided]** |
| Header | 5 µm strip: L mark, field number (3 bits) + sub-field bit (a = 0, b = 1) as dots, REF pad; the test itself is identified by the experiment (QR code) | **[decided]** |
| Support power | 0.5 mW, hatch 0.2 µm, slice 0.25 µm for pedestals, bases, REF pad, gap-test bases | **[decided]** |
| Label power | 0.5 mW (same as the supports; version 1 had 0.7 mW) | **[decided]** |
| Substrate anchoring | the first layer is repeated 1 µm into the substrate in all three tests (version 1: 1.5 µm) | **[decided]** |
| Cell gaps | 2 µm between line cells, 4.5 µm between volume cells (D5) | **[decided]** (D5) |
| In-layer order | `row_by_row` (D16) | **[decided]** |
| Print order 63x | highest layer first (D1) | **[decided]** |
| Material start file | one JSON per material (e.g. `parameter_tests_SZ2080.json`): power ladder, the axis lists of §4–§6, label and support power, anchoring depth; all three tests read it; the values are stored in `/spec` of every experiment; replaces `stage_a_<material>.json`; no calibration file is needed for printing | **[decided]** |

## 4. Quick PT

One experiment with four 60 µm sub-fields (Q1a, Q1b, Q2a, Q2b) **[decided]**.

**Q1 walls** **[decided]**: per power row three parallel walls, 8 µm long, 1.5 µm apart; every wall is a line
written in 9 layers from z = −1 µm to +1 µm (slice 0.25 µm), i.e. 1 µm in the substrate and 1 µm above.
Gives the polymerisation threshold (lowest power with a wall), damage (highest power without damage), the
wall width and, from the 1.5 µm spacing, whether neighbours merge.

**Q2 pads** **[decided]**: pads 5 × 5 µm from z = −1 µm to +1 µm (slice 0.25 µm), hatch 0.1 / 0.2 / 0.4 / 0.6 µm
(columns) × power (rows). Gives surface formation over hatch and power.

| Sub-field | Rows | Columns | Cell | Fits 60 × 55 µm |
|---|---|---|---|---|
| Q1a / Q1b | 5 powers | 2 identical groups of 3 walls side by side (statistics: a missing wall in one group only points to the surface, not the power) **[decided]** | 8 × 3 µm each | yes |
| Q2a / Q2b | 5 powers | 4 hatches | 5 × 5 µm | yes (4 × 5 + 3 × 4.5 = 33.5 µm) |

## 5. Full PT-01

Fields F1–F7 of version 1, single-stage, absolute values; each field as sub-fields a and b (14 sub-fields,
7 experiments). The old F0 is replaced by Quick PT.

| Field | Rows (per sub-field) | Columns | Fixed | Status |
|---|---|---|---|---|
| F1 line test | 5 powers | passes 1 / 2 / 3 / 4 | 2 x-lines + 2 y-lines, 7 µm long, 2.5 µm apart, at z = 0 | **[decided]** |
| F2 bridges | 5 powers | span 2 / 4 / 7 / 10 µm | pedestals 2 × 3 × 3 µm at the support power; the line 0.5 µm below the pedestal top (z = 2.5 µm); gap 2 µm between cells (D11) | **[decided]** |
| F3 line pairs | 5 powers | centre distance 0.2 / 0.4 / 0.6 / 0.8 / 1.0 / 1.2 µm | a pair above a group of five 6 µm lines, 1.5 µm between pair and group, at z = 0 (expected: 0.2 / 0.4 merged, 0.6 / 0.8 depend on power, 1.0 / 1.2 separate) | **[decided]** |
| F4 squares | 5 powers | hatch 0.1 / 0.2 / 0.4 / 0.6 µm | pad 6 × 6 µm, 3 layers of 0.3 µm, 1.6 µm ramp, hatch along x | **[decided]** |
| F5 layer test | 5 powers (wedges) + 1 row of caps | slice 0.1 / 0.2 / 0.3 / 0.5 µm | wedge 8 × 4 × 3 µm (20.6°), hatch 0.2 µm; caps Ø 8 µm, 2 µm high, at the support power | **[decided]** |
| F6 crossings | star / 3 × 3 grid / woodpile | 5 powers | star 0/45/90/135° and grid 6 µm, grid pitch 2.5 µm; woodpile 4 layers, rod pitch 1.5 µm, layer distance 0.4 µm | **[decided]** |
| F7 pillars | 5 powers (F7a 0.1–0.5 mW will mostly not stand; kept for the uniform scheme) | height 2 / 4 / 6 / 8 / 10 µm | Ø 1.5 µm, filled with hatch 0.2 / slice 0.25 µm; base 6 × 6 × 1.4 µm at the support power (D10) | **[decided]** |

F6 is transposed compared with the other fields (type in the rows, power in the columns); for the uniform
scheme each sub-field has the five powers of its half as columns.

Layer programs: with absolute slice distances all rows of a field share their layers, so the layer count is
small (version 1 needed ≈ 37 min of layer programs for F1–F7 because Δz followed l(P) per row; T155 is
obsolete). The time estimate is part of the dry run.

## 6. Voxel PT-01 (gap test)

**[decided]** by the maintainer: a base, then a gap, then a lid; the lid disappears after development once
the gap is larger than the voxel length can bridge.

```
   lid: 4 layers of 0.25 µm (1 µm) at z = 2.0 + gap + k · 0.25, power = the tested power
   ─────────────  ← gap 0 … 2.0 µm in steps of 0.2 µm (gap 0 = the top layer of the base exposed twice)
   base: 20 × 20 µm, layers of 0.25 µm up to 2.0 µm, support power
   ═════════════  substrate (first layer repeated into the substrate)
```

- Base 20 × 20 µm (fast to write, large enough for DHM and SEM evaluation) **[decided]**; base at the support
  power, lid at the tested power **[decided]**.
- **One power per experiment** **[decided]**: 10 experiments (0.1 … 1.0 mW), each with the 11 gaps; every
  experiment can be repeated on its own. Inside an experiment **[decided]**: every gap cell is its own structure;
  the cells lie 100 µm apart in a 3 × 4 grid (12 places, 11 used: gap 0 … 2.0 µm row by row), each cell on the
  optical axis of its grid cell and in its own DHM image.
- Base and lid hatch 0.2 µm, slice 0.25 µm **[decided]** (support values).
- Evaluation: per power the smallest gap without lid = upper bound of l(P), the largest gap with lid = lower
  bound; with 0.2 µm steps l is known to ±0.1 µm. A finer gap series around the found limit is a follow-up.

## 7. What changes in the code (todos T158–T163)

- `testprint`: the builders take absolute axis values from the material start file; no `ProcessCalibration`
  or fit model is needed to print. `ParameterField` gets the a/b split (sub-field bit in the header,
  `half` column in the cell table); field size 60 µm; label power as an argument.
- `ProcessCalibration` and `VoxelFitModel` stay, but as **results of the evaluation** (P_th, P_dam, w(P), l(P)
  and n_eff = 1 as placeholder, decided 2026-11-25; n_eff is determined in a later dose-matrix test with
  several velocities, future todo F31).
- Scripts: `mains/Experiments/parameter_tests/` (provisional) with `quick_pt.py`, `full_pt01_f1.py` …
  `full_pt01_f7.py`, `voxel_pt01.py` and a chain; the stage-B calibration checks disappear.
- Evaluation: the cell table holds absolute values; once P_th, w and l are known (Quick PT / Voxel PT-01),
  a function adds the relative columns (P/P_th, h/w, Δz/l) to every cell table.

## 8. Review of the proposals (2026-11-25)

All proposals of the draft were answered by the maintainer on 2026-11-25:

| # | Point | Decision |
|---|---|---|
| 1 | Label power | 0.5 mW, the same as the supports |
| 2 | Anchoring depth | 1 µm in all three tests |
| 3 | Header | 3 bits field number + 1 bit sub-field a/b |
| 4 | Quick PT walls | two groups of three walls per power |
| 5 | Full PT-01 F1 / F6 | F1: 2 x- + 2 y-lines of 7 µm, 2.5 µm apart, passes 1–4; F6: star and grid 6 µm, grid pitch 2.5 µm |
| 6 | Voxel PT-01 | one power per experiment (10 experiments × 11 gaps) |
| 7 | Input | one material start file per material |

Gap cells of Voxel PT-01: each cell its own structure, 100 µm apart in a 3 × 4 grid (§6). With this the design was approved.
