# Full PT-01

The comprehensive test: how lines interact, how surfaces and layers form, what happens at crossings, and where
the mechanical limits are. Seven fields F1–F7, one experiment per field, each with sub-field a (0.1–0.5 mW) and
b (0.6–1.0 mW) side by side. Design: `docs/design/PARAMETER_TESTS.md` §5.

Script: `python -m parametertest.full_pt01 [--only F3,F5] [--layout | --dry-run]` (working directory `mains/`).
Builders: `full_pt01.f1` … `full_pt01.f7` in `nanofactorysystem/testprint/parameter_tests.py`.

In every field the rows are the five powers of the sub-field (bottom = lowest), except F6 (powers as columns).
All values are absolute; they can be changed in the material start file (section `full`).

## F1 line test

**Structure:** per cell two lines along x and two along y, 7 µm long, 2.5 µm apart, at the interface (z = 0);
columns: the lines are written 1 / 2 / 3 / 4 times (passes).

**Examines:** line width over power and number of passes (dose accumulation by repetition); width along x vs.
along y (polarisation, galvo direction); line end vs. line middle (dose peaks at the galvo reversal; the middle
is the measured value, decision D12). 2.5 µm keeps the lines separate.

## F2 bridges

**Structure:** a line between two pedestals (2 × 3 × 3 µm, support power), 0.5 µm below the pedestal top
(z = 2.5 µm), reaching to the pedestal centres; columns: free span 2 / 4 / 7 / 10 µm; 2 µm between cells.

**Examines:** true width and length of a free-standing line (SEM under 45°, no clipping by the substrate), sag,
the largest span that survives development. Note: the 63x prints the highest layer first, so the line is written
before the pedestals grow into it.

## F3 line pairs

**Structure:** a pair of lines above a group of five lines, 6 µm long, at z = 0; columns: centre distance
0.2 / 0.4 / 0.6 / 0.8 / 1.0 / 1.2 µm (1.5 µm between pair and group).

**Examines:** the merge distance s_merge(P), i.e. the resolution (expected: 0.2 / 0.4 µm merged, 0.6 / 0.8 µm
depending on the power, 1.0 / 1.2 µm separate); the widening of a line by its neighbours (pair vs. five-line
group, proximity effect).

## F4 squares

**Structure:** pads 6 × 6 µm, 3 layers of 0.3 µm, with a 1.6 µm ramp on the right side, hatch along x; columns:
hatch distance 0.1 / 0.2 / 0.4 / 0.6 µm; anchored 1 µm.

**Examines:** the hatch window: from which hatch a closed, smooth surface forms, where gaps appear, where overdose
starts; height, roughness and edge sharpness (DHM, SEM). The ramp helps the DHM phase unwrapping after
development.

## F5 layer test

**Structure:** wedges 8 × 4 × 3 µm (20.6°) at the row power and a top row of spherical caps Ø 8 µm × 2 µm at the
support power; columns: slice distance 0.1 / 0.2 / 0.3 / 0.5 µm; hatch 0.2 µm; anchored.

**Examines:** the layer window: steps on the inclined surfaces (staircase effect) over slice distance and power;
from which slice distance layers no longer connect; shape deviation of curved surfaces (caps, lens-like).

## F6 crossings

**Structure:** rows: star (4 lines 6 µm through one point, 0/45/90/135°), 3 × 3 grid (6 µm lines, 2.5 µm pitch,
9 crossings), woodpile (4 layers of rods 1.5 µm apart, alternating x/y, 0.4 µm between layers); columns: the five
powers.

**Examines:** line width over the scan angle; overdose at crossing points (star: four exposures in the centre,
grid: two); whether stacked rod layers fuse at the crossings (woodpile, layer distance below the expected voxel
length).

## F7 pillars

**Structure:** pillars Ø 1.5 µm on bases 6 × 6 × 1.4 µm (support power, anchored); columns: height above the base
2 / 4 / 6 / 8 / 10 µm (aspect ratio 1.3 … 6.7); pillars filled with hatch 0.2 / slice 0.25 µm.

**Examines:** the largest aspect ratio that stands per power, adhesion of the pillar to the base, bending /
collapse. All pillars are lower than the 10.5 µm pitch, so a falling pillar does not reach its neighbour. In
sub-field a (0.1–0.5 mW) most pillars are expected not to stand; it is kept for the uniform layout.

## Evaluation

`experiment_analysis.ptd.export_cell_table(<experiment folder>, "F3_cells.csv")` per experiment; columns
`present`, `merged`, `collapsed`, `width_um`, `height_um`, … are filled during SEM / DHM.
`add_relative_columns` adds P/P_th, h/w and Δz/l once the threshold and the voxel size are known (Quick PT,
Voxel PT-01).
