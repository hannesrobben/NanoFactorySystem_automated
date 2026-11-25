# Review: implementation plan PTD-01 (senior code advisor)

Translated from the German review of 2026-11-25. Basis: `docs/design/TEST_PRINT_PTD01.md` (draft) and the
todos T136–T151, checked against the code of `NanoFactorySystem_automated` (branch `main_HR`, 2026-11-25).
The improvement notes N1–N13 of the original are future todos F18–F30 in `future_todo.md`.

Addendum of the import into the repository (2026-11-25): the decisions D10–D16 and the corrections listed
at the end were added afterwards; see the WORKLOG entry of T136.

## TL;DR

- **Overall verdict: good, 8/10.** The plan uses the existing building blocks (ExperimentSpec, named
  factories, `run_substrate` chain, toolpath IR with power per element from T31) instead of inventing new
  ones. The central architecture decision "one field = one composite structure on the toolpath IR" is right.
- **Existing code stays unchanged (requirement of 2026-11-25).** The new field structure translates the
  toolpath into IFOV blocks itself, following the same pattern as `Model3D_Slicer` (about 40 lines
  duplicated). Merging them is future todo F18.
- **The voxel fit model w(P), l(P) is a required part** (T150 models, T151 fit). The normalised axes use the
  voxel size at the power of each cell.
- **Biggest lab risk:** power changes in the middle of a program (80 in F0). Whether `SET_POWER` waits until
  the attenuator has settled is unchecked (decision D9, check T148 before stage A).
- **Biggest time factor:** not the writing time (IFOV fixed at 5 mm/s), but `layer_overhead_s` × layers plus
  plane fit, corner markers and overview mosaic per experiment. Levers: smaller corner markers (D2) and an
  aligned z grid.

## Findings

### Wrong path (found in the draft and corrected)
| Problem | Where | Why it matters | Correction |
|---|---|---|---|
| The cell table was to be regenerated with a `BuildContext` stored in the file | design §8, T147 | `BuildContext` is **not** stored (only factory name + arguments in `/spec`) | field builders are pure functions of the factory arguments; the context serves only the power check and the objective |
| Objective implicit | §4.1 | `Experiment.build_programs()` calls `iterate_layers(coordinate_system)` **without** an objective (`experiment.py` ~l. 1469) | objective as a constructor argument, as in `Model3D_Slicer` (T114 shows what happens otherwise) |
| Always call `context.check_power` | §4.5, T144 | without hardware the range is unknown, then `check_power` raises (breaks `--layout` / offline builds) | take over the `_check_power` pattern of T113 |

### Correction of an earlier review recommendation
- The first version of this review dropped the fit model (`w_model`/`l_model`) as "YAGNI". That was wrong:
  the fit model is a central research result. It is back as its own `VoxelFitModel` (T150) with a fit
  procedure (T151), and it is bound more tightly than before: hatch and slice distance of every cell are
  computed with w and l **at the cell power**, and the model satisfies the existing slicer protocol
  `VoxelModel`.

### Unnecessary complexity (taken out of the plan)
- A database table for the process window in phase 11: a JSON file is enough for the first print. Now
  future todo F19.
- Serpentine order of the cells: with a 50 µm field and the galvo it brings nothing measurable. Rows one
  after another first, optimise only on a lab finding (*make it work, make it right, make it fast*).
  (Import addendum: the in-layer order is a named, exchangeable strategy, D16.)

### Underestimated complexity (added)
- **Explosion of z levels:** `slice_geometry` puts the first plane at `z_min + z_epsilon`. Cells with the
  same Δz could get slightly different planes. Every plane is its own layer program (own task load, 5 s
  overhead). Solution: aligned grid `k·Δz`, z rounded to 1 nm. (Import addendum: reached without a slicer
  change by starting every height map at z = 0 with `voxel_height_um = 0`, design §4.2.)
- **Side effects of the slicer:** preprocess and ground-truth GLB are not needed, so `run_preprocess=False`.
- **Print order 63x (DOWN):** the top layer comes first. The bridge line and the pillar tips "float" until
  the base follows. This works with SZ2080 today (T113), but must be in the design (§9.1). It also reverses
  the principle "critical features in the first slices" for volume fields (§9.2).
- **Reproducibility of z0:** z0 is only valid for the same interface detection (plane-fit mode, interface
  power, exposure). These settings therefore belong in the calibration file.
- **pytest trap:** classes named `TestField` are collected as test classes in test modules (warning).
  Renamed to `ParameterField…`.

### Fits as it is
- One experiment per field plus a chain via `run_substrate`: independent restart, one `experiment.h5` per
  field, substrate index, layout check before printing. Exactly the pattern of T113.
- Named factories with pure JSON arguments including the calibration: the complete parameter set is in
  `/spec`, no silent default (fits rule G7).
- Two stages with an explicit calibration file instead of an automatic database query: traceable and testable.
- The new library `nanofactorysystem/testprint/` does not depend on `experiment`. Everything is testable
  without a system (ports and adapters on a small scale).

## Alternatives to the core decision

| Option | Pro | Contra | Verdict |
|---|---|---|---|
| A: every cell its own `StructureSpec` in the experiment grid | no new translation code; the summary shows every cell | overhead per cell (camera image, layer overhead): F5 ≈ 20 min instead of ≈ 3 min; no shared layers, no header | rejected |
| **B: composite field on the toolpath IR** | shared layers, power per element exists already (T31), existing code unchanged | about 40 lines of translation duplicated (F18); cell table instead of summary | **chosen** |
| C: all fields in one experiment | one plane fit, one set of corners | contradicts the requirement; one failure stops everything | possible later without new code |

## Roadmap (order of the todos)

```
T136 design ──► approval
   ├─► T137 field structure IR → IFOV (new files only)
   ├─► T138 cell primitives ───────────┐
   └─► T150 fit models ─► T140 calibration ┤
                                       ▼
               T139 ParameterField ─► T141 F0–F2 ─► T142 F3–F5 / T143 F6–F7
                                                       ▼
                                 T144 factories ─► T145 field scripts ─► T146 chain
                                                       └─► T147 cell table ─► T151 fit
                                                                      ▼
                                          T148 attenuator check ─► T149 lab run (maintainer)
```

Effort: about 11–13 Claude Code working days (incl. T150/T151), plus the lab run. Every step ends testable:
after T139 a field can already be built dry as a program, after T145 every field runs on the dummy backend.

## Risks and early detection

| Risk | Early check |
|---|---|
| New translation deviates from the `Model3D_Slicer` behaviour | unit test with a hand-built job (power runs, block order); `git diff --stat` shows only new files |
| Fit model extrapolates unnoticed | models raise outside `valid_power_mw`; field validation reports cell powers outside (T139/T150) |
| Attenuator does not settle after `SET_POWER` (D9) | short lab test before stage A (T148): line pair with a power step, width at the line start |
| Too many layers, too long run time | time estimate per field in the dry run (T145/T146 acceptance), upper-bound tests for F5/F7 |
| Crosstalk between cells (proximity) | evaluate edge vs. inner cells and the REF pad (D5), only then increase replicates |
| DOWN order destroys bridges/pillars | is itself a measurement result; re-evaluate D1 after the lab run |
| Restart builds a different field | determinism test (build twice → identical programs) in T139/T144 |

## Note on the concept document

The print-time table in the concept first assumed 0.1–1 mm/s. In IFOV mode the 63x writes at a fixed
5 mm/s, so the pure writing time is seconds. The realistic total time for stage B is about 160 layers
(≈ 14 min layer overhead) plus 8 × experiment overhead (plane fit, corners, mosaic). The dry runs give the
real estimate. (The concept has been corrected.)

## Corrections made when importing the plan (2026-11-25)

1. T136 named only D1–D8; the design has D1–D16 → T136 refers to all decisions of design §12.
2. T139 named `ParameterFieldStructure(ToolpathStructure)` in `field.py`; the class lives in `structure.py`
   (T137) and derives from `DrawableObject` (no `ToolpathStructure` exists).
3. In-layer order: not fixed to row by row; a named, exchangeable ordering strategy (maintainer note, D16);
   "serpentine" removed from the test table.
4. F0 layer count: 8 layers + header with 80 IFOV blocks (§9.3 said "10 layers").
5. Substrate anchoring by repeating the first slice down to `anchor_depth_um` (maintainer note, D15, F36);
   aligned z grid without slicer change.
6. Space check: F7 (D10) and F2 (D11) do not fit 50 µm with the gaps of D5.
7. Concept open points turned into decisions D12 (line ends), D13 (polarisation), D14 (recalibration rule).
8. The D9 check is its own todo T148 (before T149).

## Further reading

- M. Fowler, *Refactoring* (2nd ed.): "Extract Function" (F18, not part of PTD-01)
- M. Feathers, *Working Effectively with Legacy Code*: characterization tests (golden programs as a safety net)
- A. Cockburn, *Hexagonal Architecture* / Ports and Adapters (testprint without a dependency on the system)
- Hunt & Thomas, *The Pragmatic Programmer*: tracer bullets (one small field, F3, end to end early)
