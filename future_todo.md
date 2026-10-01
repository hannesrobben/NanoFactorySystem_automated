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

## F3: Camera video recording in a thread
- **Goal:** The camera records the printing process as video in a background thread.
- **Context:** Useful for illustration only, no value for production. Lowest priority.
- **Prerequisites:** T45 (camera capture only on request), T47.
- **Watch out for:** The camera must not be used by `measure()` at the same time (locking); the thread must
  stop cleanly on abort; file size (store video next to, not inside, the HDF5 file); timestamps to map
  frames to layers.
- **Open questions:** Frame rate, codec, storage location.

## F4: DHM reconstruction on the DHM PC and interplay of the two PCs
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

## F5: Multiple holograms at shifted positions for speckle reduction
- **Goal:** Several holograms of the same structure are taken at slightly shifted stage positions, aligned
  and averaged after reconstruction to reduce speckle noise.
- **Context:** T46 stores the stage position of every capture and allows a list of capture offsets.
- **Prerequisites:** T46, F4 (reconstruction, alignment and averaging run on the DHM PC).
- **Watch out for:** The stage position is the reference for alignment; sub-pixel registration; the raw
  holograms may be deleted after reconstruction and averaging, but only after the result is stored;
  capture time per structure grows with the number of positions.
- **Open questions:** Number and pattern of positions; shift amplitude; which averaging (complex field or
  phase)?

## F6: DHM stitching for structures larger than the DHM field of view
- **Goal:** Structures larger than the DHM FOV (which is smaller than the production FOV) are captured as
  a grid of holograms and stitched, so that large structures can be evaluated.
- **Context:** Capture grid = structure size / (DHM FOV × (1 − overlap)); T46 provides positions per
  capture. Existing code to reuse: `tools/Stitch` and `aerobasic/programs/drawings/tile_manager.py`.
- **Prerequisites:** T46, F4.
- **Watch out for:** Overlap of 10–20 % for registration; phase offsets and tilt between tiles must be
  equalised before stitching; capture time and data volume grow with the square of the structure size;
  the stitched result and the tiles should both be stored.
- **Open questions:** Stitching on the DHM PC or offline? Required overlap?

## F7: Slicing, hatching and adaptive printing strategies
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

## F12: Shell ("vector") printing in the slicer
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
