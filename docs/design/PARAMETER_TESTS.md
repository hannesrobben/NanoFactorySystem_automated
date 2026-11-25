# Design: Parameter tests Quick PT, Full PT-01, Voxel PT-01 (version 2)

Status: draft (waiting for maintainer approval)

Date: 2026-11-25. Todo: T157. Replaces the two-stage plan of `TEST_PRINT_PTD01.md` (version 1, approved
2026-11-25 and implemented in T137–T147, T150, T151). Decisions of the session of 2026-11-25 (afternoon)
are marked **[decided]**, proposals that still need the maintainer's confirmation **[proposal]**. The names
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
| Header | 5 µm strip: L mark, field number (3 bits) + sub-field bit (a = 0, b = 1) as dots, REF pad | **[proposal]** |
| Support power | 0.5 mW, hatch 0.2 µm, slice 0.25 µm for pedestals, bases, REF pad, gap-test bases | **[decided]** |
| Label power | 0.5 mW (same as the supports; version 1 had 0.7 mW) | **[proposal]** |
| Substrate anchoring | the first layer is repeated into the substrate: Quick PT 1 µm (decided with the walls), Full PT-01 and Voxel PT-01 also 1 µm (version 1: 1.5 µm) | **[proposal]** |
| Cell gaps | 2 µm between line cells, 4.5 µm between volume cells (D5) | **[decided]** (D5) |
| In-layer order | `row_by_row` (D16) | **[decided]** |
| Print order 63x | highest layer first (D1) | **[decided]** |
| Material start file | one JSON per material: power ladder and the axis lists of §4–§6, label and support power; replaces `stage_a_<material>.json`; no calibration file is needed for printing | **[proposal]** |

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
| Q1a / Q1b | 5 powers | 1 group of 3 walls (optionally 2 groups for statistics **[proposal]**) | 8 × 3 µm | yes |
| Q2a / Q2b | 5 powers | 4 hatches | 5 × 5 µm | yes (4 × 5 + 3 × 4.5 = 33.5 µm) |

## 5. Full PT-01

Fields F1–F7 of version 1, single-stage, absolute values; each field as sub-fields a and b (14 sub-fields,
7 experiments). The old F0 is replaced by Quick PT.

| Field | Rows (per sub-field) | Columns | Fixed | Status |
|---|---|---|---|---|
| F1 line test | 5 powers | passes 1 / 2 / 3 / 4 | 2 x-lines + 2 y-lines, 7 µm long, 2.5 µm apart, at z = 0 | **[proposal]** |
| F2 bridges | 5 powers | span 2 / 4 / 7 / 10 µm | pedestals 2 × 3 × 3 µm at the support power; the line 0.5 µm below the pedestal top (z = 2.5 µm); gap 2 µm between cells (D11) | **[decided]** |
| F3 line pairs | 5 powers | centre distance 0.2 / 0.4 / 0.6 / 0.8 / 1.0 / 1.2 µm | a pair above a group of five 6 µm lines, 1.5 µm between pair and group, at z = 0 (expected: 0.2 / 0.4 merged, 0.6 / 0.8 depend on power, 1.0 / 1.2 separate) | **[decided]** |
| F4 squares | 5 powers | hatch 0.1 / 0.2 / 0.4 / 0.6 µm | pad 6 × 6 µm, 3 layers of 0.3 µm, 1.6 µm ramp, hatch along x | **[decided]** |
| F5 layer test | 5 powers (wedges) + 1 row of caps | slice 0.1 / 0.2 / 0.3 / 0.5 µm | wedge 8 × 4 × 3 µm (20.6°), hatch 0.2 µm; caps Ø 8 µm, 2 µm high, at the support power | **[decided]** |
| F6 crossings | star / 3 × 3 grid / woodpile | 5 powers | star 0/45/90/135° and grid 6 µm, grid pitch 2.5 µm; woodpile 4 layers, rod pitch 1.5 µm, layer distance 0.4 µm | woodpile **[decided]**, star/grid **[proposal]** |
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
- 10 powers × 11 gaps = 110 cells. Layout **[proposal]**: sub-fields of 2 × 2 cells (2 powers × 2 gaps,
  cell pitch 24.5 µm, 49 µm per sub-field, one DHM image each) in a grid of 5 × 6 sub-fields with 150 µm
  pitch (about 0.75 × 0.9 mm); every sub-field is one structure of the experiment.
- Base hatch 0.2 µm **[proposal]**; lid hatch 0.2 µm **[proposal]**.
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

## 8. Open points for the review

1. [proposal] Label power 0.5 mW (§3).
2. [proposal] Anchoring depth 1 µm for all three tests (§3).
3. [proposal] Header: field number 3 bits + sub-field bit (§3).
4. [proposal] Quick PT Q1: one or two groups of three walls per power (§4).
5. [proposal] Full PT-01 F1 and F6 star/grid values (§5).
6. [proposal] Voxel PT-01 layout and hatches (§6).
7. [proposal] Material start file as the single input of all three tests (§3).
