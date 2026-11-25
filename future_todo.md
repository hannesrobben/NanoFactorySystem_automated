# Future todos

Ideas that are planned but not scheduled. They need more concept work or input from the maintainer.
IDs are F<number> and never reused. To schedule an item, the maintainer (or Claude on request) turns it
into one or more T-todos in `TODO.md` and marks it here as "→ T<n>".

Claude Code: do not implement anything from this file. If a todo in `TODO.md` names an extension point
for an item here, build only that extension point.

Each entry: **Goal** (what should be achieved), **Context**, **Prerequisites** (todos that must be done
first), **Watch out for** (pitfalls and constraints), **Open questions** (for the maintainer).

---

## F1: Restart an aborted print after an orientation check at the double corner
- **Goal:** Resume an aborted print, possibly after the substrate was removed and put back, by locating
  the double corner, checking position and rotation of the substrate, and correcting the coordinate
  system before printing continues.
- **Context:** The double corner marks the orientation of an experiment. Its position is stored from T50 on.
- **Prerequisites:** T47, T50 (stored double-corner position and orientation), T44 (single plane fit).
- **Watch out for:** Detection of the double corner in camera and/or DHM images; rotation and translation
  must be estimated from at least two features; the plane has to be fitted again; a wrong alignment
  prints into existing structures, so the user must confirm the estimated transform.
- **Open questions:** Which image source is used for detection? What accuracy is required? Manual or
  automatic confirmation?

## F2: Phase data as slicer input
- **Goal:** The slicer accepts phase data (e.g. from DHM or a DOE design) in addition to height data.
- **Context:** Today the slicer takes meshes and height maps (`aerobasic/slicer/pipeline.slice_geometry`).
  T51 introduces a program-source enum that can be extended.
- **Prerequisites:** T51, T54.
- **Watch out for:** Conversion phase → height needs wavelength and refractive index of the cured resin
  (depends on dose, see voxel database T53); phase wrapping; units and sign convention consistent with
  OffAxisHolo.
- **Open questions:** Is the conversion done in the slicer or before it? Which refractive-index model?

## F3: Camera video recording in a thread → T73, T93, T94, T95
- **Scheduled (2026-11-15):** camera live feed and recording are phase 9 of `TODO.md` (design T73).
- **Goal:** The camera records the printing process as video in a background thread.
- **Context:** Useful for illustration only, no value for production. Lowest priority.
- **Prerequisites:** T45 (camera capture only on request), T47.
- **Watch out for:** The camera must not be used by `measure()` at the same time (locking); the thread must
  stop cleanly on abort; file size (store video next to, not inside, the HDF5 file); timestamps to map
  frames to layers.
- **Open questions:** Frame rate, codec, storage location.

## F4: DHM reconstruction on the DHM PC and interplay of the two PCs → T71, T82–T87
- **Scheduled (2026-11-15):** phase 7 of `TODO.md`; reconstruction itself is OffAxisHolo (K-todos), transport and the DHM service are DHMConnect (DL-todos). See `docs/system/SOFTWARE_PLAN_OVERVIEW.md`.
- **Goal:** Holograms are reconstructed on the fly on the GPU of the PC that controls the DHM, using the
  OffAxisHolo library; the printing PC receives reconstructed data (phase, amplitude, derived values)
  instead of or in addition to the raw holograms.
- **Context:** The DHM is controlled by another PC. T47 already provides a generic method to store named
  DHM products with metadata; this is the receiving side of the interface.
- **Prerequisites:** T46, T47. Needs a separate concept session with input from the maintainer.
- **Watch out for:** Only the printing PC writes the experiment file (T42); transport (network share,
  socket, message queue), latency and what happens when the DHM PC is slow or offline; versioning of the
  reconstruction parameters; the DHM PC also orchestrates multiple captures (F5) and their alignment.
- **Open questions:** Transport protocol; which products are sent; who triggers a capture; where are raw
  holograms kept, and for how long?

## F5: Multiple holograms at shifted positions for speckle reduction → T85 (planning and capture)
- **Scheduled (2026-11-15):** capture planning is T85 here; registration and fusion moved to MIRA (MI-20–MI-31), group handling to DHMConnect (DL-B9). The open questions stay with T85 ("Decision:").
- **Goal:** Several holograms of the same structure are taken at slightly shifted stage positions, aligned
  and averaged after reconstruction to reduce speckle noise.
- **Context:** T46 stores the stage position of every capture and allows a list of capture offsets.
- **Prerequisites:** T46, F4 (reconstruction, alignment and averaging run on the DHM PC).
- **Watch out for:** The stage position is the reference for alignment; sub-pixel registration; the raw
  holograms may be deleted after reconstruction and averaging, but only after the result is stored;
  capture time per structure grows with the number of positions.
- **Open questions:** Number and pattern of positions; shift amplitude; which averaging (complex field or
  phase)?

## F6: DHM stitching for structures larger than the DHM field of view → T85 (planning and capture)
- **Scheduled (2026-11-15):** the raster is planned in T85 here; registration and stitching moved to MIRA (MI-20, MI-40–MI-42), group handling to DHMConnect (DL-B9).
- **Goal:** Structures larger than the DHM FOV (which is smaller than the production FOV) are captured as
  a grid of holograms and stitched, so that large structures can be evaluated.
- **Context:** Capture grid = structure size / (DHM FOV × (1 − overlap)); T46 provides positions per
  capture. Existing code to reuse: `tools/Stitch` and `aerobasic/programs/drawings/tile_manager.py`.
- **Prerequisites:** T46, F4.
- **Watch out for:** Overlap of 10–20 % for registration; phase offsets and tilt between tiles must be
  equalised before stitching; capture time and data volume grow with the square of the structure size;
  the stitched result and the tiles should both be stored.
- **Open questions:** Stitching on the DHM PC or offline? Required overlap?

## F7: Slicing, hatching and adaptive printing strategies (extension point → T81)
- **Scheduled (2026-11-15):** only the extension point (strategy name and parameters per structure) is scheduled as T81; the strategies stay here.
- **Goal:** The slicer offers several slicing and hatching strategies and adaptive printing (e.g. power
  or spacing adapted per layer or line).
- **Context:** Includes the open slicer roadmap items (formerly T40, N095): contour as polyline, tilted
  slicing, shell strategy (detailed in F12), experiment hierarchy, study framework, translator. T54 passes
  the voxel model to the hatching strategies; T31 enables power per layer and line.
- **Prerequisites:** T53, T54, T31.
- **Watch out for:** Strategies need a common interface (input: geometry + voxel model + laser
  parameters; output: toolpath IR); every strategy must be stored in the metadata to keep prints
  reproducible; compare strategies with the study framework.
- **Open questions:** Which strategies first? Which quality metric decides between them?

## F8: Dip-in as drop direction
- **Goal:** Besides drop direction UP and DOWN, the system supports dip-in lithography.
- **Context:** In dip-in the objective is immersed in the resin; interface detection, plane fitting and
  the z computation work differently. T43 documents all places that depend on the drop direction.
- **Prerequisites:** T43, T44.
- **Watch out for:** Different z sign and working distance; interface detection (focus/layer tools)
  sees the resin–substrate interface through the resin; zMax safety limits; objective-specific
  parameters in the config. There is no drop boundary in dip-in: the resin-drop outline check (T62) and
  its detection (F9) must be skipped.
- **Open questions:** Which objective? Which substrates?

## F9: Automatic detection of the resin-drop outline
- **Goal:** The outline of the resin drop is detected automatically (camera or DHM) instead of being
  entered as four edge points.
- **Context:** Maintainer decision 2026-10-01 (question on T62): for now the experiment areas are checked
  against an ellipse through the four edge points entered by hand; later the outline should be measured.
- **Prerequisites:** T62.
- **Watch out for:** For dip-in (F8) there is no drop boundary to detect, and touching the resin would
  destroy the setup, so no detection and no outline check there. Detection must not move the objective
  into the resin.
- **Open questions:** Which image source and magnification? How often is the outline measured (once per
  substrate, before every experiment)?

## F10: Rework the focus detection with known data
- **Goal:** A robust focus detection whose thresholds are justified by measured data.
- **Context:** Formerly T61 (N084, N010). The noise threshold `minDiffMax` in `tools/focus.py` was set to
  10 ad hoc, because noise gave values of 1.7–2.5. In practice artefacts, diffraction and bad focal spots
  caused wrong or missed detections. The maintainer will provide example scans; until then the current
  detection stays unchanged, because a change without data may make it worse (maintainer decision
  2026-10-01).
- **Prerequisites:** Example focus scans with known result (20x and 63x, with and without a real focus,
  with artefacts).
- **Watch out for:** Plane fitting and layer detection depend on it; compare old and new detection on the
  same data before switching; keep the old behaviour selectable.
- **Open questions:** Which examples are representative? Which failure is worse: a missed focus or a
  wrong one?

## F11: AeroBasic API and task handling with the A3200 manual
- **Goal:** The AeroBasic API is correct and complete for the commands in use, checked against the
  A3200 manual.
- **Context:** Formerly T32 (maintainer decision 2026-10-01: nothing is changed without the manual,
  because a wrong command can make the whole program run badly; the maintainer will provide the
  details). Items from `todo_notes.md`:
  - N029 `PROGRAM_ASSOCIATE` sends a wrong command syntax (`aerobasic/__init__.py`, about line 121).
  - N030 reading system parameters is not possible yet (`aerobasic/__init__.py`, about line 452).
  - N031 more compact program text (several variable declarations per line)
    (`aerobasic/programs/__init__.py`, about line 98).
  - N032 more metadata in the program header, e.g. experiment UUID, structure, layer, software version
    (`aerobasic/programs/__init__.py`, about line 102).
  - N033 check of modes such as `VELOCITY ON` and `ABSOLUTE` (`aerobasic/programs/__init__.py`, about
    line 146).
  - N044 IFOV setup: investigate the ramp types LINEAR, SINE, SCURVE (`programs/drawings/base.py`, about
    line 52); needs trials on the machine.
  - N045 IFOV: a justified threshold for the speed value F (`programs/drawings/base.py`, about line 137);
    needs trials on the machine.
  - N058 better choice of the task id (`programs/drawings/layered_objects.py:119`,
    `devices/aerotech/__init__.py:179`).
  - N073 `run_program_as_task`: the original author wanted to delete it; it is now the central way to
    print layers, so replace rather than delete (`devices/aerotech/__init__.py:159`).
  - N074 remove the previous program from the controller before loading the next one (bug of
    26.02.26) (`devices/aerotech/__init__.py:174`).
- **Prerequisites:** The A3200 manual pages for the commands concerned (from the maintainer).
- **Watch out for:** Every change needs a dummy-backend test and a check on the lab PC; golden programs
  change with the header (N032) and must be re-recorded deliberately; `FakeA3200Transport` has to learn
  every new command.
- **Open questions:** Which system parameters are needed (N030)? What was the symptom of the bug of
  26.02.26 (N074)?

## F12: Shell ("vector") printing in the slicer (extension point → T81)
- **Scheduled (2026-11-15):** only the extension point is scheduled as T81.
- **Goal:** A slicing strategy that first prints the outer shell of a part as continuous 3-D paths and
  then fills the inside with planar slices.
- **Context:** N068 "vector printing" (maintainer explanation 2026-10-01): the shell is written as one
  continuous 3-D line (e.g. a Bézier curve) in which every point also changes z, so no part of it lies
  at a constant height. Afterwards the space in between is filled by planar slicing. The number of outer
  shell layers is an argument. The shell applies in the axial and in the lateral direction. Part of the
  advanced slicing strategies (F7); the toolpath IR already has shell groups (`KIND_SHELL`), which
  `Model3D_Slicer` does not render yet.
- **Prerequisites:** F7, T54 (voxel size for the shell thickness), T31 (power per segment).
- **Watch out for:** Continuous z changes in IFOV mode (galvo plus z axis synchronisation); overlap
  between shell and planar infill; the drop direction decides the print order; time estimate for 3-D
  paths.
- **Open questions:** Which curve representation (Bézier, polyline with fine steps)? How is the shell
  thickness chosen (number of shells × voxel size)?

## F13: IFOV writing speed as a free parameter
- **Goal:** IFOV structures write with a chosen speed instead of the fixed objective speed.
- **Context:** Today IFOV programs write with `F=5` (63x) or `F=10` (20x) mm/s, because the coordination
  of stages and galvo works best at these speeds (maintainer decision 2026-10-01: keep it for IFOV; T35,
  T63). To be explored in detail later.
- **Prerequisites:** T35, T63, F11 (N045: F threshold).
- **Watch out for:** Programs need the speed in mm/s (a speed in µm/s is too large and the controller
  raises an error); the voxel size depends on the speed (T63).
- **Open questions:** Which speeds are stable in IFOV mode for each objective?

## F14: Camera offset in `System.zline`
- **Goal:** `System.zline` takes the camera offset into account itself (N071), instead of every caller adding
  `zCameraOffset` before and after the exposure.
- **Context:** From T36 (maintainer decision 2026-10-01: nothing may change the normal behaviour of the
  system or the plane fitting). `System.zline` is the exposure of the focus detection (`tools/focus.py`) and
  therefore of every plane fit, so the change was not made. N072 (global variables, no recompiling) was
  already done: the z-line program reads `$global[0..2]` and is loaded once per session.
- **Prerequisites:** F10 (focus detection reworked with known data), so that the change can be checked
  against measured focus scans.
- **Watch out for:** `Focus.zline` and the focal-point script both add the offset today; moving it must not
  apply it twice. The z-line is centred on z (z - dz/2 to z + dz/2).
- **Open questions:** Should the offset also be applied for dots (dz = 0)?

## F15: GUI for the whole system
- **Goal:** One application to define substrates, experiments and structures, see the layout, run
  and supervise prints, with live camera and DHM views.
- **Context:** Details follow separately from the maintainer. The core is prepared by T77, T80,
  T93–T97. The DHM analysis and live GUI is OffAxisHolo L0–L9, a pure observer (O9, 2026-11-18): the
  **operation of the DHM and the stage** (objective and parameter set, exposure, OPL scan, background,
  laser on / off, fringe contrast, snapshot — the former OffAxisHolo L6) belongs to this GUI.
- **Prerequisites:** T74, T96, T97; G3 decided 2026-11-18: PySide6 + pyqtgraph (same framework as the
  OffAxisHolo GUI); runner in a worker thread (P1).
- **Watch out for:** The GUI process must respect the single writer of `experiment.h5`; hardware
  stays the default backend; a GUI crash must not stop a running print uncontrolled.
- **Open questions:** Scope of the first version; one application with the DHM GUI or two.

## F16: Controller and operating mode `correct`
- **Goal:** A measured deviation changes the following layers: power or dose, z offset, local
  re-exposure, additional or skipped layer.
- **Context:** Masterplan phases P4 and P5. T88–T92 provide modes, targets, reports and the
  `Controller` protocol; `shadow` stores plans without applying them.
- **Prerequisites:** T91; a measured noise floor (N-study OffAxisHolo K13, speckle fusion MIRA MI-30);
  a process model from dose to in-situ phase to final height.
- **Watch out for:** Layer programs are built before the print today, so late generation per layer
  is needed; global corrections can use controller variables, local ones need a new layer program;
  over-exposure cannot be undone; every correction needs hard limits and a stop rule.
- **Open questions:** First demonstration structure and objective; comparison in the phase or in
  the height domain; does the print wait for the evaluation?

## F17: Dynamic slicing and hatching per structure
- **Goal:** Slicing and hatching adapt within a structure, for example to geometry or measured
  deviations.
- **Context:** Extension point T81; related to F7 and F12.
- **Prerequisites:** T78, T81, F7.
- **Watch out for:** Reproducibility: the algorithm, its version and parameters go into the metadata.
- **Open questions:** Which algorithms first, and which quality metric decides between them?

---

The entries F18–F37 come from the planning of the test print PTD-01 (2026-11-20 to 2026-11-25, design
`docs/design/TEST_PRINT_PTD01.md`). F18–F30 are improvements of **existing** code that were deliberately
kept out of PTD-01 (maintainer decision 2026-11-25: the PTD-01 implementation must not change existing
code); they were called improvement notes N1–N13 in the planning (renamed, because N-IDs are the code
markers of `todo_notes.md`). F31–F37 come from the open points of the PTD-01 concept, the import of the plan and
the decision session. **Every one of them must be discussed with the maintainer before it is scheduled.**

## F18: One shared IR → IFOV translation for `Model3D_Slicer` and `ParameterFieldStructure` (formerly N1)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** The translation toolpath IR → IFOV blocks (runs of equal power → `IFOV_PolyLines`/`IFOV_Lines`)
  exists once, used by `Model3D_Slicer.iterate_layers` (`aerobasic/programs/drawings/model3d.py`) and by
  `ParameterFieldStructure` (T137).
- **Context:** T137 duplicates about 40 lines on purpose. One place would hold power runs, block order and a
  future dwell after power changes (F28).
- **Prerequisites:** T137, T31.
- **Watch out for:** pure refactor; the golden programs must stay byte-identical (characterization tests).
- **Open questions:** When: right after PTD-01 or with the next slicer work (F7)?

## F19: Process-window table in the voxel database (formerly N2)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** A table `process_window` in the voxel database (material, objective, setup, velocity, P_th,
  P_dam + criterion in-situ/SEM, z0, plane-fit settings, source) and `ProcessCalibration.from_database()`,
  so that the calibration is queried like voxel sizes and materials are comparable.
- **Context:** PTD-01 stores the calibration as a JSON file (T140, design §7).
- **Prerequisites:** T53, T140, results of T149.
- **Watch out for:** schema migration (`voxel/migrations.py`); design addendum to `VOXEL_DATABASE.md`.
- **Open questions:** Which criterion is the default P_th (in-situ or SEM)? One row per print or per fit?

## F20: Store fitted voxel models in the voxel database (formerly N3)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** `VoxelFitModel`s (T150) are stored next to the raw measurements, versioned with their fit
  inputs; the fit model becomes the queried quantity, the raw points stay for refits.
- **Prerequisites:** T150, T151, same migration as F19.
- **Watch out for:** `DatabaseVoxelModel` interpolates raw points today; both must stay selectable.
- **Open questions:** Which model wins when raw points and a fit disagree?

## F21: Store the `BuildContext` of a run in the experiment file (formerly N4)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** The `BuildContext` (objective, setup, accelerations, drop direction, power range) is stored, e.g.
  under `/spec/build_context`, so that a factory can be re-evaluated offline exactly as in the lab.
- **Context:** Today only factory name and arguments are in `/spec`; PTD-01 avoids the need with pure
  builders (design §8).
- **Prerequisites:** T77.
- **Watch out for:** schema minor version of the experiment file; the power calibration object is not JSON.
- **Open questions:** Store the attenuator calibration too, or only its range?

## F22: One consistent way to pass the objective to IFOV structures (formerly N5)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** No silent 63x configuration in 20x experiments: either every IFOV structure takes `objective=`
  in its constructor, or `Experiment.build_programs()` passes it to `iterate_layers`.
- **Context:** `build_programs()` calls `iterate_layers(coordinate_system)` without objective
  (`experiment.py` ~l. 1469); `Model3D_Slicer`/`HeightMap_IFOV` store it, `IFOV_Lines`/`Rectangle*_IFOV` use
  the 63x default. Related: T114.
- **Prerequisites:** T114.
- **Watch out for:** touches every IFOV structure; golden files.
- **Open questions:** Constructor argument everywhere or experiment-provided?

## F23: Explicit velocity unit in `IFOV_Lines` (formerly N6)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Replace the velocity unit guessing of `IFOV_Lines` (500–25000 → divided by 1000, "to be
  reworked") with explicit `velocity_mm_s` / `velocity_um_s`.
- **Prerequisites:** F13.
- **Watch out for:** API change of a widely used class; old scripts and stored `to_json()` data.
- **Open questions:** Deprecation period with a warning, or a hard switch?

## F24: Measured layer overhead per objective and loader (formerly N7)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** `layer_overhead_s` (fixed 5 s) is measured on the lab PC (program load, task start, z settle) per
  objective and loader and stored in the config, so that time estimates of many-layer structures are
  realistic (PTD-01: about 160 layers).
- **Prerequisites:** T28, T129; actual times of T149.
- **Watch out for:** the library loader with prefetch (T129) changes the overhead.
- **Open questions:** One value per objective, or a model (constant + per line)?

## F25: Slice planes on a global aligned grid in the slicer (formerly N8)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** An option in `aerobasic/slicer/slicing.py` to put slice planes on a global grid `k · Δz` instead
  of `z_min + z_epsilon`, so that several parts of one job share layers.
- **Context:** PTD-01 reaches the same inside its cell primitives without a slicer change (T138).
- **Watch out for:** the default must stay unchanged (golden files); tangential cuts at z_min.
- **Open questions:** Grid origin: the substrate (z = 0) or the job?

## F26: Process-dependent material properties (formerly N9)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** A clear boundary material ↔ process: either material properties get optional objective/setup
  keys, or process data (thresholds) stay out of the registry explicitly (F19).
- **Prerequisites:** T75.
- **Open questions:** Which values are material properties and which are process properties?

## F27: Print order per structure (formerly N10)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** A per-structure option for the layer order (e.g. substrate side first for the 63x), to compare
  both orders for bridges and pillars.
- **Context:** DOWN always prints the highest layer first (PTD-01 decision D1, kept for PTD-01). Maintainer
  note 2026-11-25: the descending order relies on the viscous SZ2080; with other materials the print order
  may also change for the 63x, so the order may have to become a material (or structure) property, not a
  fixed property of the objective.
- **Watch out for:** restart and progress logic (`print_progress`, `reprint_layers`), the split parts of T125.
- **Open questions:** Only after the PTD-01 results of F2/F7?

## F28: Dwell after power changes in IFOV blocks (formerly N11)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** If the attenuator does not settle between `SET_POWER` and the first line (T148), an optional dwell
  after every power change in all IFOV structures, not only in the PTD-01 field structure.
- **Prerequisites:** T148 result; F18 (one place for it).
- **Open questions:** Fixed dwell or a dwell proportional to the power step?

## F29: Structure-specific metadata in the summary (formerly N12)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** A generic hook for structure-specific metadata (e.g. a cell table) in
  `/structures/<name>/metadata`, so that multi-parameter structures are visible in the summary.
- **Context:** The summary lists one power/hatch per structure; PTD-01 regenerates its cell table instead (T147).
- **Watch out for:** storage schema change.

## F30: Corner markers scaled to small experiments (formerly N13)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Scale the default `CornerSpec` with the experiment area, or document a "small experiment" preset,
  because the default corners (300 × 50 × 7 µm) dominate the time of experiments with small structures.
- **Context:** PTD-01 sets a reduced `CornerSpec` explicitly (decision D2).
- **Watch out for:** a default change affects existing scripts and the corner detection.

## F31: Follow-up standard test prints PTD-02 … PTD-08
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** The series of the PTD-01 concept, all with the same field format (50 × 50 µm, header, REF pad,
  metadata) and the `testprint` library: PTD-02 dose matrix P × v (P_th(v), dose exponent n); PTD-03
  resolution (pins/holes, Siemens star); PTD-04 hatching strategies; PTD-05 slicing and adaptive layers
  (z staircase, ramps, greyscale dose, shell + scaffold); PTD-06 mechanical limits (pillars Ø × height ×
  pitch, bridges up to 40 µm); PTD-07 dimensional accuracy (shrinkage, contour offset); PTD-08 optics
  validation (microlens, blazed prism, DOE grating).
- **Prerequisites:** phase 11 done; PTD-02 needs F13 (free IFOV speed).
- **Open questions:** Order of the follow-up prints; which ones are needed for the slicer work (F7, F17)?
- **Note 2026-11-25:** the effective nonlinearity n_eff of the voxel model is determined in the dose-matrix test (threshold over velocity, P_th ∝ v^(1/n)); the parameter tests of phase 11 use n_eff = 1 as placeholder (T156).

## F32: In-situ threshold detection from DHM phase time series
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Determine P_th (and microexplosions) in situ from the DHM phase of F0 (first row with Δφ > 0,
  phase/amplitude spikes), taken as a time series after the exposure (monomer diffusion changes the index
  over time). Would replace the development step between stage A and B. Not published in the literature
  reviewed: a research result of its own.
- **Prerequisites:** phase 7 (DHM service), T67, SEM reference data from T149.
- **Watch out for:** the line width at the threshold is below the lateral DHM resolution (≈ 240 nm); the phase
  of a 0.4 µm line is about 0.13 rad; calibrate against SEM.
- **Open questions:** Time points of the series; which signal defines the threshold?

## F33: PTD output for the material table
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Store the further results of the PTD-01 concept per material/objective/substrate/velocity:
  dynamic window DFW = (P_dam − P_th)/P_th, anisotropy w_x/w_y and w(θ), merge distance s_merge(P), proximity
  factor k_prox, hatch window (h/w)_min/max, layer window (Δz/l)_max(θ), overdose at crossings, L_max and
  AR_max, and two named working points "Fidelity" and "Robust" per material.
- **Prerequisites:** F19, F26, evaluation of T149.
- **Open questions:** Where do these values live (voxel database, material registry, own table)? How does the
  slicer use them (F7, F17)?

## F34: Line ends at the galvo reversal (laser gate or lead-in)
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Lines get a uniform dose up to their ends: either a laser gate (PSO) in the AeroBasic program, or
  lead-in/lead-out moves outside the cell with the laser off.
- **Context:** PTD-01 measures the line middle only (decision D12); F1 compares line end and middle.
- **Prerequisites:** F11 (A3200 manual), PTD-01 results of F1.
- **Open questions:** Does the controller offer PSO in IFOV mode?

## F35: Automatic recalibration rule
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** When a new calibration changes P_th by more than a threshold (proposal 10 %), the chain proposes
  to rerun F1, F3 and F4 (coupled parameters).
- **Context:** PTD-01 documents the rule only (decision D14).
- **Prerequisites:** T146, F19.

## F36: Substrate anchoring by repeating the first slice, as a general slicer option
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Every sliced structure (`Model3D_Slicer`, `HeightMap_IFOV`, slicer pipeline) can repeat its first
  slice (the one at the interface, z = 0) downwards with its layer distance until an anchor depth (typically
  1–2 µm into the substrate) is reached, so that it bonds to the substrate.
- **Context:** Maintainer note 2026-11-25. Today structures are shifted down as a whole (e.g. `HeightMap_IFOV`
  `center.Z = −1 µm`), which also lowers the top. PTD-01 implements the repetition inside its cell primitive
  (T138, decision D15).
- **Prerequisites:** T138 (lab result of the PTD-01 anchoring), F25.
- **Watch out for:** golden files (only as an opt-in parameter, default off); voxel-aware first slice (T54:
  first slice half a voxel height inside the part); DOWN prints the anchor layers last.
- **Open questions:** Default depth per objective; dose of the anchor layers (same power or higher)?

## F37: One corner frame around all experiments of a substrate
- **Status:** to be discussed with the maintainer before scheduling.
- **Goal:** Instead of corner markers and a QR code per experiment, one continuous corner frame (rectangle)
  is printed around all experiments of a substrate (or of a chain), as a common frame of reference.
- **Context:** Maintainer note 2026-11-25 (PTD-01 decision D2): PTD-01 uses reduced corners with QR code per
  field experiment for now. With eight small field experiments the corners cost much of the time.
- **Prerequisites:** T52/T76 (`run_substrate`, substrate index), T118 (substrate layout); F30.
- **Watch out for:** plane fit mode `CORNERS` and the overview capture use the corners of each experiment;
  every experiment still needs its UUID traceable (QR per experiment or one index QR with positions);
  restart of a single experiment must find the frame; the frame must stay inside the resin drop.
- **Open questions:** One QR code for the frame plus the positions in `substrate.json`, or small QR codes per
  experiment inside the frame? Is the frame printed before the first experiment of the chain?
