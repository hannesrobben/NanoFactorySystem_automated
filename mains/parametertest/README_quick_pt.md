# Quick PT

First experience values of a new material in one short experiment: where polymerisation starts, where damage
starts, how wide a line is and from which hatch distance a surface forms. Design: `docs/design/PARAMETER_TESTS.md` §4.

Script: `python -m parametertest.quick_pt [--layout | --dry-run]` (working directory `mains/`).
Builders: `quick_pt.walls`, `quick_pt.pads` in `nanofactorysystem/testprint/parameter_tests.py`.

## Layout

One experiment, 2 × 2 grid of 60 µm sub-fields:

| Grid cell | Sub-field | Powers (rows, bottom → top) |
|---|---|---|
| top left | Q1 walls a | 0.1 / 0.2 / 0.3 / 0.4 / 0.5 mW |
| top right | Q1 walls b | 0.6 / 0.7 / 0.8 / 0.9 / 1.0 mW |
| bottom left | Q2 pads a | 0.1 … 0.5 mW |
| bottom right | Q2 pads b | 0.6 … 1.0 mW |

Header of every sub-field: L mark, field number (Q1 = 1, Q2 = 2) as dots, sub-field dot for b, REF pad.

## Q1 walls

**Structure:** per power row two identical groups (left and right) of three walls. A wall is a line 8 µm long,
written in 9 layers from z = −1 µm to z = +1 µm (slice 0.25 µm): 1 µm in the substrate, 1 µm above. The three
walls of a group are 1.5 µm apart.

**What it examines:**

| Observation | Gives |
|---|---|
| lowest power at which walls are still there after development | polymerisation threshold P_th (to 0.1 mW) |
| highest power without bubbles, burns or deformation | damage threshold P_dam, dynamic window |
| wall width (SEM top view, DHM) per power | first values of the voxel width w(P) |
| walls merged / separate at 1.5 µm | first information on line proximity |
| wall height above the substrate (DHM, SEM 45°) | first information on the voxel length |
| difference between the two groups | scatter from the substrate surface (a wall missing in one group only points to the surface, not to the power) |

## Q2 pads

**Structure:** pads 5 × 5 µm from z = −1 µm to +1 µm (slice 0.25 µm), power (rows) × hatch distance
0.1 / 0.2 / 0.4 / 0.6 µm (columns), hatch lines along x.

**What it examines:**

| Observation | Gives |
|---|---|
| closed, smooth surface vs. visible hatch lines or gaps | hatch window per power: the largest hatch that still forms a surface |
| bulging, burns, swelling at small hatch and high power | overdose limit |
| pad height (DHM) | shrinkage / dose dependence of the height |

## Evaluation

`experiment_analysis.ptd.export_cell_table(<experiment folder>, "quick_cells.csv")` writes one row per cell
(power, group or hatch, sub-field, stage position) with empty columns for the measured values (`width_um`,
`height_um`, `present`, `merged`, …). The widths of Q1 are the first points for the voxel fit
(`experiment_analysis.voxel_fit`).
