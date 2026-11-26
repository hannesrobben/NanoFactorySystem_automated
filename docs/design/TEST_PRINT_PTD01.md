# Design: Standard parameter test print PTD-01 "voxel and line interaction"

Status: approved 2026-11-25 (decisions D1–D8, D10–D16 taken in the decision session of 2026-11-25, §12;
D9 is answered by the lab check T148). **Superseded in its two-stage plan by `PARAMETER_TESTS.md`
(version 2, T157):** single-stage tests on absolute axes (Quick PT, Full PT-01, Voxel PT-01). The library
architecture (§4) and the field geometry of F1–F7 stay valid where version 2 does not say otherwise.
The version-1 code (`ptd01`, `factories`, `StageAAxes`, `mains/Experiments/ptd01/`) is in the attic since
2026-11-26 (T164, `docs/ATTIC_INDEX.md`).

Date: 2026-11-25. Todo: T136 (this document). Used by: T137–T151. Review of the plan:
`docs/reviews/PTD01_PLAN_REVIEW_2026-11-25.md`. Improvement ideas for existing code found during the
planning are future todos F18–F30 in `future_todo.md` (not part of this design; each needs a maintainer
decision). Concept (German, with overview drawing and sources): Claude Docs "PTD-01 Parametertestdruck
Voxel und Linieninteraktion" (2026-11-20, maintainer).

## 0. Background (summary of the concept)

PTD-01 is the first of a series of standard test prints, modelled on the calibration prints of FDM and
resin printing. It measures voxel size, process window and the behaviour of neighbouring and crossing lines
at a fixed writing speed (IFOV mode), so that materials can be compared and the material table of this system
can be filled. Guiding questions:

- How large is the voxel (width w, length l) as a function of power, and where are the polymerisation and
  damage thresholds?
- From which distance do lines merge, and how much do neighbouring lines widen each other (dose accumulation)?
- Which ratios h/w (hatch) and Δz/l (layer) give dense, smooth surfaces without overdose?
- Where are the limits for bridges, pillars and crossing points?

Design principles taken from established calibration prints (no ISO/NIST standard exists for 2PP):
dependency order (process window first), coarse then fine, one axis = one parameter, normalised axes
(P/P_th, h/w, Δz/l), a reference pad in every field, self-labelling (ISO/ASTM 52902), counting instead of
estimating (line present / merged, pillar stands / falls), fields ≤ 50 µm on the optical axis.

Measurement methods (evaluation is outside this design, see T67/T147/T151): widths from SEM (F2 under 45°),
heights and phases from the DHM after development, in-situ thresholds from the DHM phase; both threshold
criteria (in-situ and SEM) are kept separately.

Follow-up prints PTD-02 … PTD-08 (dose matrix P × v, resolution, hatching strategies, slicing / adaptive
layers, mechanical limits, dimensional accuracy, optics validation) reuse the field format and the library
of this design (future todo F31).

## 1. Goals and non-goals

**Goals**
- Print the eight test fields F0–F7 of the PTD-01 concept, **one experiment per field** (own
  `experiment.h5`, restartable on its own), and a **chain** that runs all of them one after another on
  one substrate (`run_substrate`), like `mains/Experiments/chain_rectangle_doe_lens.py` (T113).
- Two stages: stage A = F0 only (process window, interface, start values of the voxel size); stage B =
  F1–F7 with axes **normalised** to the stage-A values (P/P_th, h/w, Δz/l).
- Every cell of a field has its own laser power, z, hatch or slice distance. One field is one
  `DrawableObject`, built by a named structure factory, stored in `experiment_spec.json` and rebuilt
  identically on restart.
- Every printed cell can be identified afterwards: a cell table (field, cell id, row, column, position,
  all parameters in absolute and normalised units) can be regenerated from the experiment file alone.
- The building blocks (cells, field, calibration, voxel fit model, IR → IFOV translation) are library code,
  so that the later test prints PTD-02 … PTD-08 reuse them without copying.
- **Existing code is not changed** by the PTD-01 implementation (maintainer decision 2026-11-25). Only new
  files are added; all golden files stay untouched.

**Non-goals**
- Automatic evaluation (SEM, DHM phase integration). PTD-01 produces the cell table that an evaluation
  joins with measurements (T147); the evaluation pipeline is T67. The voxel fit itself is T151.
- In-situ DHM captures per layer. The experiments run with `dhm_usage=False` until phase 7/8 is done;
  the field layout keeps the critical features where a later DHM capture can see them (§9.2).
- A free IFOV writing speed (F13). PTD-01 uses the fixed IFOV speed of the objective (5 mm/s for the
  63x), which is the "fixed velocity" of the concept.
- The Benchy (separate print project, maintainer decision 2026-11-25).

## 2. Terms and units

| Term | Meaning | Unit |
|---|---|---|
| field | One test area of 50 × 50 µm; one structure of one experiment | µm |
| cell | One parameter combination inside a field (one grid position) | – |
| header | The strip y = 45…50 µm of a field: L mark, 3-bit field id, REF pad | µm |
| P_th | Lowest power at which a line at the interface working point survives development (stage A) | mW |
| P_dam | Lowest power with visible damage (in-situ criterion and SEM criterion stored separately) | mW |
| z0 | Interface working point: local z of the line centre relative to the fitted plane | µm |
| w0, l0 | Voxel width and length at P_ref, start values from F0 | µm |
| P_ref | Working point `p_ref_factor · P_th` (start value of `p_ref_factor` 1.5, decision D3) | mW |
| relative power | `p_rel = P / P_th` | – |
| relative hatch | `h_rel = h / w(P)` | – |
| relative slice | `dz_rel = Δz / l(P)` | – |
| label power | Fixed power of header elements (L mark, id dots), independent of the calibration | mW |
| anchor depth | Depth below the interface (z = 0) down to which the first slice of a volume cell is repeated (§4.2, D15) | µm |

All lengths in the code carry `_um`, powers `_mw` (CLAUDE.md naming convention).

## 3. What the library already provides, and what is missing

| Need | Existing piece | Use in PTD-01 |
|---|---|---|
| One experiment per field, project file | `ExperimentSpec`, `StructureSpec`, `run_experiment` (T51/T77) | one spec per field |
| Chain on one substrate | `SubstrateSpec`, `SubstrateExperiment`, `check_layout`, `run_substrate` (T52/T76) | `chain_ptd01.py` |
| Structure built at run time, stored by name | `@structure_factory`, `BuildContext` (T77) | one factory per field |
| Several powers in one layer program | `Model3D_Slicer.iterate_layers`: runs of equal power → one IFOV block each (T31) | the same pattern in §4.1 (existing code unchanged) |
| Toolpath IR with per-element power | `slicer/toolpath.py` `PathElement(power_mw=…)`, `ElementGroup(z_um=…)`, `ToolpathJob` | cells produce IR |
| Volumetric cells (pads, wedges, caps, pedestals, pillars) | `slicer.pipeline.slice_geometry(np.ndarray, pixel_size=…)` with height maps; strategies `linear_x`, `linear_y`, `alternating`, `cross` | `sliced` cell (§4.2) |
| Power range check | `BuildContext.check_power` (raises when the range is unknown) | every factory, only when the range is known |
| Fixed IFOV speed | `lines.IFOV_WRITING_SPEED_MM_S` | metadata, time estimate |
| Time estimate | `time_estimate.py` (path / speed + `layer_overhead_s` per layer) | logged per field |
| Dry run | `backends/dummy/dry_run.dry_run`, `--dry-run` pattern of T113 | every script |
| Voxel results | `VoxelDatabase.add_measurement` / CSV import (T53) | F0/F1/F2 results (T147) |
| Material properties | `MaterialRegistry.add_property` (T75) | not suitable for P_th (no objective/setup key), see §7 |

Gaps (each closed by one todo):

1. **G1 – No structure that prints a prebuilt `ToolpathJob`.** The IR → IFOV translation lives inside
   `Model3D_Slicer.iterate_layers`. → T137: the new field structure has its own translation following the
   same pattern; existing code unchanged (merging both is future todo F18).
2. **G2 – No multi-cell field.** → T138 (cell primitives), T139 (`ParameterField`).
3. **G3 – No normalisation object and no voxel fit model.** → T140 (`ProcessCalibration`, JSON file),
   T150 (`VoxelFitModel`), T151 (fit from measurements).
4. **G4 – No storage for P_th, P_dam, z0.** → JSON file for PTD-01 (§7); a database table is future todo F19.
5. **G5 – No cell map in the experiment file.** → solved without a storage change: the cell table is a pure
   function of the factory arguments, which are stored in `/spec` (§8).
6. **G6 – No substrate anchoring by repetition of the first slice.** → done inside the `sliced` cell
   primitive (T138, §4.2); a general slicer option is future todo F36.

## 4. Architecture

New package `nanofactorysystem/testprint/` (library) and new folder `mains/Experiments/ptd01/` (scripts).

```
nanofactorysystem/testprint/
├── __init__.py          public API: ParameterField, CellSpec, ProcessCalibration, StageAAxes, ParameterFieldStructure
├── structure.py         ParameterFieldStructure: IR → IFOV blocks       (T137)
├── cells.py             cell primitives → ElementGroup fragments         (T138)
├── ordering.py          in-layer ordering strategies (registered by name) (T139)
├── field.py             ParameterField, CellSpec, header, merge, cell_table   (T139)
├── calibration.py       ProcessCalibration, StageAAxes, JSON schema      (T140)
├── voxel_fit.py         VoxelFitModel + model kinds (evaluation only)    (T150)
├── ptd01.py             field_f0() … field_f7(), axis levels             (T141–T143)
└── factories.py         @structure_factory("ptd01.f0") … ("ptd01.f7")    (T144)

mains/Experiments/ptd01/
├── README.md
├── common.py            USER, OBJECTIVE, RESIN_EDGES, CENTERS, CornerSpec, substrate_spec(), field_spec()
├── f0_interface.py … f7_pillars.py      experiment_spec(), main(), CLI --layout / --dry-run
└── chain_ptd01.py       --stage A|B|all, --calibration, --only, --layout, --dry-run
```

Dependency direction: `ptd01` → `field` → `cells`, `ordering` → slicer IR; `factories` → `ptd01`,
`structure`, `calibration` → `voxel_fit`; nothing in `testprint` imports `experiment` (keeps the builders
testable without a system).

### 4.1 Translation into IFOV programs (`structure.py`, T137)

"Translation" (called "emitter" in the first draft) is the step toolpath IR → AeroBasic: for every
layer (`ElementGroup` with a z), the elements are grouped into runs of equal power, and every run becomes
one `IFOV_PolyLines` (contours) or `IFOV_Lines` (infill) block that sets its power and writes its lines.
`Model3D_Slicer.iterate_layers` does exactly this today for sliced models (T31).

**Existing code stays unchanged.** `ParameterFieldStructure.iterate_layers` implements the same
translation itself, following the pattern of `Model3D_Slicer.iterate_layers` and calling the existing
leaf classes `IFOV_Lines` and `IFOV_PolyLines` (no change to `model3d.py`, `lines.py` or any golden
file). The duplication of about 40 lines is accepted for PTD-01; merging both into one shared function is
future todo F18.

- `iterate_layers` yields one `DrawableAeroBasicProgram` per z level in ascending z (the experiment
  reverses for DOWN); provides `element_powers_mw` and `statistics()` like `Model3D_Slicer`.
- The translation keeps the element order of the job (the order is decided in the field, §4.3); it only
  groups consecutive elements of equal power into one block.
- `Experiment.build_programs()` calls `structure.iterate_layers(coordinate_system)` **without** an objective
  (`experiment.py` ~l. 1469). The objective is therefore a constructor argument (as in `Model3D_Slicer`),
  filled by the factory from `BuildContext.objective`, and stored in `to_json()`.
- Every element carries its own power; the structure power is the label power (same rule as
  `Model3D_Slicer._apply_power_map`: per-element powers need a structure power).
- `dwell_after_power_s` (default 0): optional dwell after every power change, in case the attenuator does
  not settle in time (decision D9, measured in T148).

### 4.2 Cell primitives (`cells.py`, T138)

A cell primitive is a pure function returning `list[ElementGroup]` in **cell-local** µm coordinates
(origin = cell centre, z = 0 at the fitted plane), with `power_mw` set on every element and
`meta={"cell": cell_id, "part": …}`:

| Primitive | Elements | Used in |
|---|---|---|
| `line(length_um, direction, z_um, power_mw, passes=1)` | 2-point infill, repeated `passes` times | F0, F1 |
| `line_set(n, pitch_um, length_um, direction, …)` | parallel lines | F1 (replicates), F3 |
| `polyline(points, closed, …)` | one continuous laser-on path | header L mark, F6 star/grid |
| `dot(z_from_um, z_to_um, …)` | short z line (3-bit id dot) | header |
| `sliced(height_map_um, pixel_um, slicing: SlicingParameters, power_mw, anchor_depth_um)` | `slice_geometry` on a height map, all elements get `power_mw`; first slice repeated down to `−anchor_depth_um` | pads, wedges, caps, pedestals, bases, pillars |
| `suspended_line(span_um, z_um, …)` | 2-point infill between pedestals | F2 |
| `woodpile(n_layers, rod_pitch_um, rod_length_um, dz_um, …)` | alternating x/y rod layers | F6 |

**Height maps** are generated analytically (`numpy`, no files, no RNG) so that a rebuild after restart is
identical. Helpers: `pad_map`, `wedge_map`, `cap_map`, `pillar_on_base_map`, `pedestal_map`.
`run_preprocess=False` and no `ground_truth_path` (height maps need no repair; no side files).

**Aligned z grid without a slicer change.** `slice_geometry` puts the planes at
`z_min + z_epsilon_um + k · Δz`. Every height map of a primitive starts at z = 0 and the primitive uses
`voxel_height_um = 0`, so all cells with the same Δz get the same planes. Parts that stand on other parts
(pillar on base) are one height map, not two slicing runs. The field rounds every z to 1 nm when merging
(§4.3). Otherwise cells with the same Δz could get slightly different planes, and the union of z levels
(= number of layer programs, each costing `layer_overhead_s`) explodes. A global aligned-grid option in the
slicer itself is future todo F25.

**Substrate anchoring (maintainer note 2026-11-25).** Volume cells start at the interface (z = 0). To make
sure that they bond to the substrate, the **first slice (the one at z = 0) is repeated downwards** with the
cell's Δz (z = −Δz, −2Δz, …) until the anchor depth is reached (typically 1–2 µm into the substrate). The
anchor layers lie on the same aligned grid. Existing structures do this differently (e.g. `HeightMap_IFOV`
shifts the whole structure down with `center.Z = −1 µm`); PTD-01 implements the repetition inside `sliced`
(no slicer change), the general option is future todo F36. `anchor_depth_um` is stored per cell in the cell
table. Default and scope (decision D15): 1.5 µm below the interface; pads, wedges, caps, pedestals and
bases (F2, F4, F5, F7); not the interface lines of F0/F1, whose z position is the measured quantity, and
not F3/F6.

Every primitive validates its inputs (positive sizes, at least one element) and raises `ValueError` with
the cell id.

### 4.3 Field (`field.py`, `ordering.py`, T139)

```python
@dataclass(frozen=True)
class CellSpec:
    cell_id: str                 # "F3-r2c4"
    row: int; col: int
    center_um: tuple[float, float]
    params: dict                 # absolute values, e.g. {"power_mw": .., "spacing_um": ..}
    params_rel: dict             # normalised values, e.g. {"p_rel": 1.5, "s_rel": 1.0}
    primitive: str               # name of the cell primitive

@dataclass(frozen=True)
class ParameterField:
    field_id: int                # 0..7, written as 3-bit dots
    name: str                    # "F3_line_pairs"
    size_um: float = 50.0
    header_um: float = 5.0
    cells: tuple[CellSpec, ...]
    label_power_mw: float
    ref_pad: Optional[RefPad]    # 4 x 4 x 1 µm at P_ref (None in stage A)
    order: str = "row_by_row"    # in-layer ordering strategy (decision D16)
```

- `ParameterField.to_toolpath_job(objective)`: builds header + all cells, translates them to field
  coordinates, **merges groups with equal z** (z rounded to 1 nm) and orders the elements of one layer with
  the in-layer ordering strategy named by `order`.
- **In-layer order is subject to change (maintainer note 2026-11-25).** Future strategies may follow
  outline borders, write a cross-hatch pattern, group by power, etc. `ordering.py` therefore holds a small
  registry of named strategies (`register_ordering(name)`, input: the elements of one merged layer with
  their cell ids; output: the same elements in print order). PTD-01 ships `row_by_row` (cells row by row,
  inside a cell the order of the primitive); the strategy name is a field argument and is stored in
  `to_json()`, so a restart uses the same order. Power changes at most once per cell with `row_by_row`.
- Validation (raises `FieldLayoutError` listing every problem): every element inside the field;
  gap between cell bounding boxes ≥ `min_gap_um` (default 2 µm for line cells, 4.5 µm for volume cells,
  decision D5); header strip free of cells; z inside `[z_min_um, z_max_um]`; every cell power inside the
  validity range of the voxel fit model (stage B).
- `cell_table()` → `list[dict]` (one row per cell, absolute + relative parameters, anchor depth, bounding
  box); `write_cell_table(path)` → CSV. Used by the analysis helper (T147).
- `plot(ax)`: top view with cell ids (debugging, layout PNG next to `experiment.png`).

### 4.4 Calibration and voxel fit model (`calibration.py`, `voxel_fit.py`, T140, T150)

The voxel fit model w(P), l(P) is a central research result and a required part of PTD-01. The
normalised axes are defined with it: `h = h_rel · w(P_cell)` and `Δz = dz_rel · l(P_cell)` use the voxel
size **at the power of the cell**, not one constant.

```python
@dataclass(frozen=True)
class VoxelFitModel:
    kind: str                     # "threshold_ln" | "power_law" | "tabulated" (registered by name)
    params: dict                  # e.g. {"w_scale_um": .., "l_scale_um": .., "p_th_mw": .., "n_eff": ..}
    valid_power_mw: tuple[float, float]   # range of the data the fit is based on; no extrapolation
    velocity_um_s: float
    source: str                   # experiment UUIDs, fit date, residuals file
    residuals: dict               # RMS / max residual of w and l

    def width_um(self, power_mw: float) -> float: ...
    def length_um(self, power_mw: float) -> float: ...
    def voxel_size(self, power_mw: float, velocity_um_s: float):   # slicer VoxelModel protocol
        ...

@dataclass(frozen=True)
class ProcessCalibration:
    material: str; objective: str; setup: str; velocity_um_s: float
    p_th_mw: float; p_dam_mw: Optional[float]
    z0_um: float
    voxel_model: VoxelFitModel            # required, no default
    p_ref_factor: float = 1.5
    plane_fit: dict = field(default_factory=dict)   # interface detection settings: z0 depends on them
    provisional: bool = True              # True: model fitted from F0 data only
    source: str = ""; date: str = ""
```

- Model kinds (registered by name, extendable without changing the calibration class):
  - `threshold_ln`: threshold model `d(P) = d_scale · sqrt(ln((P/P_th)^n_eff))` for w and l, with a
    fitted effective nonlinearity `n_eff` (literature: n = 2 … 4 depending on the resin).
  - `power_law`: empirical `d = a · (P − P_th)^b` as a comparison model.
  - `tabulated`: piecewise-linear interpolation of measured points (no extrapolation), the fallback when
    no analytic model fits.
- `VoxelFitModel.voxel_size()` implements the existing slicer protocol `aerobasic/slicer/voxel.VoxelModel`
  (`voxel_size(power_mw, velocity_um_s)`), so the same model can later be passed to
  `Model3D_Slicer(voxel_model=…)` without changing the slicer.
- Outside `valid_power_mw` the model raises (no silent extrapolation); a cell power outside the range is
  reported by the field validation.
- Stage A → stage B: F0 delivers w and l over P (ascending scan), so a first (`provisional`) fit already
  exists for stage B. F1/F2 refine it; the refined model replaces the file.
- The fit itself (least squares, model comparison, residuals, plots) is analysis code (T151); the
  library only evaluates a fitted model.
- Methods of `ProcessCalibration`: `power_mw(p_rel)`, `p_ref_mw`, `hatch_um(h_rel, power_mw)`,
  `slice_um(dz_rel, power_mw)`, `to_json()` / `from_json()` (schema `nanofactory.process_calibration/1`,
  model included), `load(path)`, `save(path)`. Missing values raise `MissingPropertyError` (G7), a wrong
  schema `SpecSerialisationError`.
- `StageAAxes` (same module): `material`, `p_min_mw`, `p_max_mw`, `n_levels`, `z_offsets_um`,
  `label_power_mw`; JSON schema `nanofactory.ptd_stage_a/1`. One file per material
  (`mains/Experiments/ptd01/stage_a_<material>.json`, decision D8): the maintainer enters the start values
  of a new material there without changing code; they are checked against the attenuator range when it is
  known and stored in `/spec` as factory arguments.

### 4.5 Factories (`factories.py`, T144)

```python
@structure_factory("ptd01.f3")
def f3_line_pairs(context: BuildContext, *, calibration: dict, p_rel: list[float], s_rel: list[float],
                  label_power_mw: float, replicate: int = 0) -> ParameterFieldStructure: ...
```

- Arguments are JSON values only (calibration as dict). `experiment_spec.json` therefore holds the complete
  parameter set of the print, and a restart rebuilds the same field.
- Every factory converts the relative axes with the calibration and checks all powers with
  `context.check_power(*powers)` **only when the attenuator range is known** (pattern `_check_power` of
  `mains/Experiments/chain_rectangle_doe_lens.py`, T113; offline the range is unknown and `check_power`
  would raise). It passes `context.objective` to the structure and returns a
  `ParameterFieldStructure(field_args…)` whose `to_json()` round-trips with `structure_from_json`
  (constructor arguments are the field arguments, never a `ToolpathJob`).
- The field builders in `ptd01.py` do not take a `BuildContext` (it is not stored in the experiment file,
  see F21); the factories use the context only for the power check and the objective.

## 5. The eight fields

Axis levels are module constants in `ptd01.py`, so a later revision changes one place. "rel" values are
converted with the calibration; F0 uses absolute values.

| Field | Cells (rows × cols) | y axis | x axis | Fixed | Primitive | Layers (est.) |
|---|---|---|---|---|---|---|
| F0 interface & threshold | 10 × 8 | P absolute, log, 10 levels between `p_min_mw` and `p_max_mw` (stage-A file) | z offset −1.0 … +2.5 µm, step 0.5 | line length 4 µm | `line` | 8 + header |
| F1 line test | 6 × 4 | p_rel 1.0 … 2.5 | passes n = 1 … 4 | z = z0; per cell 2 x-lines + 2 y-lines, 7 µm / 6 µm | `line_set` | 1 + header |
| F2 bridges | 6 × 4 | p_rel 6 levels | span 2 / 4 / 7 / 10 µm | pedestals 2 × 3 × 3 µm at P_ref (D11); gap 2 µm between bridge cells; line z = 3 µm − l0/2 | `sliced`, `suspended_line` | ~11 + anchor |
| F3 line pairs | 5 × 6 | p_rel 5 levels | s_rel 0.5 … 2.0 | pair + 5-line group, 6 µm long | `line_set` | 1 + header |
| F4 squares | 4 × 4 | p_rel 4 levels | h_rel 0.3 / 0.5 / 0.75 / 1.0 | pad 6 × 6 µm, 3 layers, dz_rel 0.5, `linear_x`, ramp 1.6 µm | `sliced` | ~5 + anchor |
| F5 layer test | 3 × 4 wedges + 1 × 4 caps | p_rel 3 levels (+ caps at P_ref) | dz_rel 0.15 / 0.25 / 0.4 / 0.6 | wedge 20°, 8 × 6 × 3 µm; cap Ø 8 µm, 2 µm; h from F4 (`h_rel` constant) | `sliced` | union of z levels, ~35 + anchor |
| F6 crossings | 3 × 5 | star / grid / woodpile | p_rel 5 levels | one pass; woodpile 4 layers, dz = 0.6 l0 | `polyline`, `woodpile` | ~5 |
| F7 pillars | 4 × 5 | p_rel 4 levels | height 2 / 4 / 6 / 8 / 10 µm above the base (AR ≈ 1.3–6.7) | Ø 1.5 µm, base 6 × 6 × 1.4 µm at P_ref (D10) | `sliced` | ~40 + anchor |

"+ anchor" = the anchor layers of §4.2 (anchor depth / Δz per cell, shared where the grids coincide).

F0 in detail: 10 power rows × 8 z-offset columns. Every z offset is its own z level and therefore its own
layer program: 8 layers plus the header, each with 10 IFOV blocks (one per power), 80 blocks in total.

Header of every field: L mark (two polylines) and the 3-bit id as dots at `label_power_mw`; REF pad at
P_ref (stage B only). Field centre = centre of the experiment's grid cell (on the optical axis of the
IFOV block).

Space check with the gaps of D5 (usable height 45 µm below the header, width 50 µm):
- F7: with the planned 7 µm bases, 5 × 7 µm + 4 × 4.5 µm = 53 µm > 50 µm did not fit. Decided (D10):
  bases 6 × 6 µm → 5 × 6 µm + 4 × 4.5 µm = 48 µm; rows 4 × 6 µm + 3 × 4.5 µm = 37.5 µm. Pillar heights
  2 / 4 / 6 / 8 / 10 µm (maintainer, 2026-11-25): all pillars are lower than the pitch of 10.5 µm, so a
  falling pillar does not reach the next base; high aspect ratios follow in PTD-06 (F31).
- F2: with pedestals 2 × 4 µm the rows needed 46.5 µm > 45 µm and the columns 52.5 µm > 50 µm. Decided
  (D11): pedestals 2 × 3 × 3 µm and a 2 µm gap between bridge cells → rows 6 × 3 µm + 5 × 2 µm = 28 µm,
  columns 39 µm + 3 × 2 µm = 45 µm.
- F4 (4 × 7.6 µm + 3 × 4.5 µm = 43.9 µm) and F5 (4 × 8 µm + 3 × 4.5 µm = 45.5 µm; rows 3 × 6 + 8 + 3 × 4.5 =
  39.5 µm) fit.

## 6. Experiments and chain

### 6.1 One experiment per field (`mains/Experiments/ptd01/fN_*.py`, T145)

`common.field_spec(field_id, factory_call, *, replicates=1)` returns an `ExperimentSpec` with:

| Setting | Value | Reason |
|---|---|---|
| `objective` | `"Zeiss 63x"` (refuse others) | IFOV setup and fixed speed of the 63x |
| `grid` | `(1, replicates)`; replicates use `StructureType.REPEAT` | statistics and position dependence (decision D4) |
| `structure_size_um` | `None` (= FOV 150 µm) | field sits on the axis of its grid cell |
| `setup` | `"IFOV_on"`, `program_source=ProgramSource.DRAWING`, `structure_type=StructureType.IFOV` | |
| `corner` | `CornerSpec` reduced, e.g. 150 × 20 × 4 µm (decision D2) | default corners (300 × 50 × 7 µm) dominate the time of a 50 µm field |
| `plane_fit_mode` | `CORNERS` | as T113 |
| `camera_capture` / `overview_capture` | `True` / `True` | images per field for the evaluation |
| `dhm_usage` | `False` (until phase 7) | |
| `materials` | `{"resin": RESIN}` | material snapshot |
| `tags` | `["ptd01", "F<n>", "stage_A" or "stage_B"]` | `find_experiments` |
| `description` | generated from the axis levels | summary |
| `layer_overhead_s` | 5.0 | time estimate |

Each script has `experiment_spec()`, `main(*, backend=None, plane=None, data_root=None,
calibration_path=None)` and the CLI of T113 (`--layout`, `--dry-run`). `main()` of a single field runs a
one-experiment `run_substrate`, so that a field printed alone is also in the substrate index.

Note: the overview drawing of the concept shows the eight fields as a 4 × 2 block with 20 µm spacing
(260 × 130 µm). With one experiment per field (maintainer decision) every field has its own corners and
plane fit, so the field distance is set by the experiment area incl. corners (`CENTERS`, §6.2), not by the
drawing.

### 6.2 Chain (`chain_ptd01.py`, T146)

- `--stage A`: F0 only; writes nothing else.
- `--stage B --calibration <file>`: F1–F7 in the order F1, F2, F3, F4, F5, F6, F7; refuses to start
  without a valid calibration file whose material/objective/setup match the substrate.
- `--stage all --calibration <file>`: F0 and F1–F7 (only for repeat prints with a known calibration).
- `--only F3,F5`: subset; `--replicates n`.
- Layout: `CENTERS` in `common.py`, one position per field (2 × 4 block, spacing ≥ experiment area incl.
  corners); `check_layout` before anything is printed; `ASK_EACH_STEP` / `ASK_BETWEEN` as in T113.
- The calibration file is copied into every stage-B experiment folder and its dict is part of every
  factory call (so it is also in `/spec`).

## 7. Data flow between the stages

1. Before stage A: lab check T148 (does `SET_POWER` wait for the attenuator, D9); polarisation direction
   relative to x/y documented (D13).
2. Stage A prints F0 → development → SEM/DHM → the maintainer (later T67) determines P_th, P_dam, z0, w0,
   l0 → `calibration_<material>_<objective>.json` (`ProcessCalibration`, `provisional=True`, fit by T151).
3. Stage B reads that file. After evaluation, F1/F2 widths and heights go into the voxel database
   (`VoxelDatabase` CSV import, `method="SEM"`/`"DHM"`, `experiment_uuid`), and a refined calibration
   (`provisional=False`, voxel fit refined with F1/F2 data, T151) replaces the file.
4. Recalibration rule of the concept: if P_th changes clearly (proposal > 10 %), F1, F3 and F4 run again
   (decision D14).
5. Long term (future todos F19, F33, not part of phase 11): a `process_window` table in the voxel database
   (material, objective, setup, velocity, P_th, P_dam, criterion, z0, source) and the further material-table
   values of the concept (dynamic window, proximity factor, hatch / layer windows, named working points).
   The material registry is not the right place: its properties have no objective/setup key (F26).

## 8. Cell table and evaluation support (T147)

- `analysis/experiment_analysis/ptd.py`: `cell_table(experiment_h5) -> DataFrame` reads `/spec` and
  calls the pure field builder of `ptd01.py` with the stored factory arguments. No `BuildContext` is
  needed (it is **not** stored in the experiment file; the builders must not depend on it). It returns the
  cell table with the experiment UUID and field position in stage coordinates (from the layout record).
- `export_cell_table(h5, csv)` and a CSV template with empty columns for measured values (`width_um`,
  `height_um`, `present`, `merged`, `collapsed`, `method`, `notes`) that the maintainer fills during SEM.
- `import_voxel_measurements(csv, database)` maps filled rows of F0/F1/F2 to `VoxelDatabase` rows.
- Stores nothing in the experiment file except through `ExperimentFile` under `/analysis/ptd01`
  (design §5.9 of EXPERIMENT_STORAGE.md).

## 9. Constraints that the implementation must respect

### 9.1 Print order for the 63x (DropDirection.DOWN)
`Experiment.print_structure` prints layers in **descending** order for DOWN. For the fields this means:
the top of a pillar, the bridge line and the upper woodpile layers are written before the material below
them, and the anchor layers (§4.2) are written last. This is how all 63x prints work today (e.g. T113:
z = 5 µm first, z = −1 µm last) and relies on the viscous resin (SZ2080). It must be checked for:
- F2: the suspended line is written before its pedestals. The line z must lie inside the pedestal top
  (`z = 3 µm − l0/2`) so that the pedestal later polymerises into it.
- F7: pillars are written top first; a pillar that never reaches its base is a result, not a bug.
The descending order is a property of the resin, not only of the objective: with other materials the print
order may also change for the 63x (maintainer note 2026-11-25, F27).
- F0: lines far above the interface are written first and float; expected.
Decision D1 asks whether a per-structure ascending order is wanted later (would need an `Experiment`
change, future todo F27; not part of PTD-01).

### 9.2 In-situ readability
The concept asks for dose-critical features in the first slices. For DOWN the first printed slices are
the highest ones. Fields F0, F1, F3, F6 (stars/grids) are single-layer at the interface and therefore
independent of the order; for the volume fields the rule is dropped in PTD-01.

### 9.3 Program size and time
- IFOV writes at 5 mm/s: pure writing time per field is seconds. The time is dominated by
  `layer_overhead_s` × layers (§5: about 110–120 layers in F1–F7 incl. anchor layers after D10 → about
  10 min; the concept's 160 layers assumed pillars up to 24 µm), plane
  fit, corner markers and the overview mosaic per experiment. `build_programs()` logs the estimate; the dry
  run of the chain prints it per field (T146 acceptance). A measured `layer_overhead_s` is future todo F24.
- Power changes start a new IFOV block (RAPID to the reference point, START IFOV). F0 has 80 blocks in
  8 layers; the number of program lines stays far below `MAX_PROGRAM_LINES` (test in T141).

### 9.4 Determinism and restart
Field geometry must not depend on random numbers, wall-clock time or dict order. Building a field twice
gives identical programs (test), and `restart_experiment()` rebuilds it from `/spec`.

### 9.5 Line ends
The galvo reverses at every line end; without a laser gate (PSO) the line ends may get more dose. In
PTD-01 the line middle is the measured quantity (decision D12); a lead-in outside the cell or a PSO gate is
future todo F34.

## 10. Testing

| Level | What | Todo |
|---|---|---|
| unit | IR → IFOV translation of `ParameterFieldStructure` on a hand-made job (power runs, block order, optional dwell); all existing golden files untouched | T137 |
| unit | every cell primitive: element count, bounds, power on every element, aligned z grid, anchor layers, invalid input raises | T138 |
| unit | field: merge by z, ordering strategy registry (`row_by_row` and an unknown name), deterministic order, validation errors, header, cell table columns, determinism of the programs | T139 |
| unit | calibration: conversions, JSON round trip, missing value raises, wrong schema raises | T140 |
| unit | each field builder: cell count, axis levels, all powers within the given range, program lines, space check | T141–T143 |
| unit | factories: `FactoryCall` → spec `to_json`/`from_json` → same field; `structure_from_json` round trip | T144 |
| integration (`slow`) | dry run of every field script and of `chain_ptd01 --stage A` / `--stage B` on the dummy backend; every AeroBasic statement simulated | T145, T146 |
| integration | cell table regenerated from the dry-run `experiment.h5` equals the one of the factory | T147 |
| unit | fit models: known parameters reproduce points, no extrapolation, JSON round trip, slicer protocol | T150 |
| unit | fit procedure on synthetic data with noise recovers P_th and n_eff within tolerance | T151 |
| hardware | attenuator settling check (D9), then lab print of stage A, then stage B (maintainer) | T148, T149 |

`test/README.md` lists the new modules. No golden file changes except a new one for one small field
(F3) if the maintainer wants a program reference (decision D6).

## 11. Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| A: one cell = one `StructureSpec` in the experiment grid (small `structure_size_um`) | no new translation code; summary lists every cell with power automatically; restart per cell | per-structure overhead × cells: camera capture, `LINEAR` to the centre and `layer_overhead_s` per layer of every cell (F5: 16 cells × ~15 layers × 5 s ≈ 20 min instead of ~3 min); no shared layers, no header; grid spacing tied to FOV logic | rejected |
| B: one field = one composite structure on the toolpath IR (this design) | layers shared by all cells; per-element power already supported (T31); no change to existing code | ~40 lines of translation duplicated from `Model3D_Slicer` (F18); a cell table instead of the summary | **chosen** |
| C: all fields in one experiment (grid 2 × 4) | one plane fit, one set of corners: saves 7 × overhead | contradicts the requirement "one experiment per field"; one failure stops all fields | rejected for PTD-01; the factories allow it later without new code |

Naming: classes start with `Parameter…`, not `Test…`, because pytest tries to collect classes named
`Test*` that are imported into test modules (warning "cannot collect test class … because it has a
`__init__` constructor").

## 12. Decisions (maintainer)

D1–D9 come from the planning conversation, D10–D16 were found while importing the plan into the
repository. All except D9 were decided by the maintainer in the decision session of 2026-11-25.

### 12.1 Open

| ID | Question | Proposal | Blocks |
|---|---|---|---|
| D9 | Does a `SET_POWER` inside a running program wait until the attenuator has settled? | Lab check T148 before stage A; until then `dwell_after_power_s = 0`; if the attenuator does not settle, set the dwell found by T148. | T149 |
| D17 | Scales of `threshold_ln` for the fit (found during T151): `d = d_scale · sqrt(n_eff · ln(P/P_th))` depends only on `d_scale² · n_eff`, so n_eff is only identifiable with fixed `w_scale_um` / `l_scale_um`. | Fix the scales from the optics of the 63x (or from a reference measurement) and fit P_th and n_eff; until decided the fit uses free scales with n_eff = 1 (P_th is unaffected). | T151 result interpretation, F33 |
| D18 | Layer count of F4, F5, F7 (found during T142): Δz = dz_rel · l(P_cell) differs per row, so rows share no layers. Example calibration: F4 29, F5 229, F7 127 layer programs; F1–F7 ≈ 37 min of layer programs instead of ≈ 10 min. | Option a: keep (normalisation exact per cell). Option b: Δz per column from l(P_ref) (F5 ≈ 4 grids, about 60 layers), the cell table keeps the true dz_rel at the cell power. Option c: fewer dz_rel levels in F5. | T149 time budget |

### 12.2 Decided (2026-11-25)

| ID | Question | Decision | Used in |
|---|---|---|---|
| D1 | Print order of the 63x (DOWN, highest layer first) for all fields? | Kept as it is. Note for the future: with other materials the print order may also change for the 63x (F27). | T141–T143 |
| D2 | Corner markers per field experiment? | Reduced `CornerSpec` (e.g. 150 × 20 × 4 µm) with QR code. Future: one continuous corner frame around all experiments of a substrate instead of corners per experiment (F37). | T145 |
| D3 | `p_ref_factor` start value | 1.5; replaced by the measured working point after PTD-01. | T140 |
| D4 | Replicates per field | 1 for the first print; `--replicates 3` once the time per field is known. | T145, T146 |
| D5 | Minimum gap between cells | 2 µm for line cells, 4.5 µm for volume cells (except F2, D11); check with the edge-vs-inner comparison after the print. | T139 |
| D6 | Golden program for one field? | Yes, F3 (`test/golden/ptd01_f3.txt`). | T142 |
| D7 | Phase of the todos | New phase 11 "Standard test prints" **with priority** over the other open phases (lab blockers such as T134 excepted). | scheduling |
| D8 | Where do the F0 start values of stage A come from? | One `StageAAxes` JSON file per material (`stage_a_<material>.json`), checked against the attenuator range when it is known. | T140, T141 |
| D10 | F7 did not fit 50 µm. | Bases 6 × 6 × 1.4 µm; pillar heights 2 / 4 / 6 / 8 / 10 µm above the base (all below the pitch of 10.5 µm). | T143 |
| D11 | F2 did not fit with the volume gap. | Pedestals 2 × 3 × 3 µm, gap 2 µm between bridge cells. | T141 |
| D12 | Line ends at the galvo reversal | Measure the line middle only; line ends stay as written; lead-in / PSO gate is F34. | T138, T147 |
| D13 | Polarisation direction relative to x/y | Measured and documented on the lab PC before stage B (T149); stored in the calibration file. | T140, T149 |
| D14 | Recalibration rule (rerun F1, F3, F4 if P_th changes by more than 10 %) | Documented as a rule only; automation is F35. | T146 |
| D15 | Substrate anchoring of volume cells | 1.5 µm below the interface; pads, wedges, caps, pedestals, bases (F2, F4, F5, F7); not F0/F1 interface lines, not F3/F6. | T138 |
| D16 | Default in-layer ordering for PTD-01 | `row_by_row`; other strategies later as registered strategies. | T139 |

## 13. Implementation notes (2026-11-25, T137–T147, T150, T151)

Deviations from the text above, all within the approved decisions:

- `ParameterFieldStructure` lives in `structure.py` and is built from a registered field builder
  (name + JSON arguments); its translation keeps the element order of the job (the order is the field's
  strategy) instead of putting contours before infill as `Model3D_Slicer` does.
- `dot` is a short line (0.4 µm) in the layer plane, not a z line: IFOV blocks write in one plane.
  A 0 bit of the field id has no dot (field 0 has none).
- Fields that need w or l at the cell power (F3, F4, F5, F7) start at p_rel = 1.25 (levels F3 1.25 … 2.25,
  F4 1.25 … 2.0, F5 1.25 / 1.5 / 1.75, F7 1.25 … 2.0): the threshold model has zero size at P_th and is only
  valid above it. F1, F2 and F6 keep p_rel 1.0 … 2.5 / 1.0 … 2.0.
- F1 lines are 5 µm long with a 2.5 µm pitch (the concept's ~7 µm do not fit six rows of 7.5 µm).
- F3: s is the centre distance of neighbouring lines; the pair and the group are 1.5 µm apart.
- Supporting volumes (F2 pedestals, F7 bases, REF pad) use hatch 0.5 · w(P_ref) and slice 0.5 · l(P_ref);
  volume cells are packed with one pixel (0.05 µm) margin per side because sliced edges are interpolated.
- Cell parameters must not use the names of measurement columns (`width_um`, `height_um`, …); F3 stores
  `model_width_um`, F4 `pad_height_um`.
- The cell table is a list of dicts (no pandas). Analysis results go through `ExperimentFile` to
  `/analysis/experiment/ptd01_cell_table` and `/analysis/experiment/ptd01_voxel_fit` (ExperimentFile writes
  below `/analysis/experiment/`, not `/analysis/ptd01`).
- The voxel fit uses F0 and F2 heights as lengths; F1 heights lie on the substrate and are clipped.
