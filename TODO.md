# TODO

<!--
Format rules (for humans and Claude):
- ID: T<number>, never reused. Follow-ups reference their origin: "(follow-up of T3)" or "(found during T3)".
- Phase: every open todo carries "[phase: <n>]" (see "Phase plan"). Backlog todos carry "[phase: B]".
- Priority: high | medium | low
- Depends on: IDs or "–"
- Done when: one line or sub-bullets; every criterion must be verifiable.
- Sort "Open" by phase, then by blockers/dependencies, then priority.
- "Done" is a staging area: the status review routine moves entries to ARCHIVE.md.
- Ideas that are not scheduled yet live in `future_todo.md` (F<number>). Never implement them
  unless they are moved into this file.
-->

## Phase plan

Target state: one `main.py` per substrate lists several experiments. Each experiment is stored in a
self-contained HDF5 file (plus redundant JSON copies) under a default location, can be restarted, and
has a short summary. Structures are sliced with measured voxel dimensions from a voxel database.

| Phase | Topic | Todos | Gate before the dependent todos start |
|---|---|---|---|
| 0 | Concept: metadata audit, storage and substrate design | T41, T42 | T42 approved by the maintainer |
| 1 | Consistent execution parameters (independent of phase 0) | T43, T44, T45, T46, T58 | – |
| 2 | Experiment storage | T47, T48, T49, T50, T55, T56, T57, T59 | – |
| 3 | Experiment scripts and substrate main | T51, T52 | – |
| 4 | Voxel database and voxel-aware slicing (independent of phases 2–3) | T53, T54, T31 | T53 design approved by the maintainer |
| B | Backlog from T19 (`todo_notes.md`) | T32, T37, T28, T35, T36, T38, T39, T60 | – |

### Working rules for Claude Code (in addition to CLAUDE.md)
1. Pick the first open todo of the lowest unfinished phase whose dependencies are done. Phase 1 may be
   worked on while phase 0 waits for approval. Phase 4 may run in parallel to phases 2–3 once T53 is
   approved. Take phase B todos only when nothing else is available or the maintainer names one.
2. Design todos (T42, first part of T53) end with a document in `docs/design/`. After writing it, move the
   todo to "Blocked" with "Blocked by: waiting for maintainer approval". Implementation that depends on it
   starts only when the document contains the line `Status: approved <date>` written by the maintainer.
3. If a todo leaves a decision open (marked "Decision:"), propose an answer in the todo or design
   document and ask the maintainer before implementing the part that depends on it.
4. The real-hardware path stays the default. Every behaviour change gets a dummy-backend test; golden
   files may only change when the todo says so, and the reason goes into WORKLOG.md.
5. Keep extension points that a todo names (e.g. for DHM products, dip-in, phase data), but do not
   implement items from `future_todo.md`.
6. At the end of each phase run `python -m pytest` (incl. the dry run in `test/integration/`) and append a
   WORKLOG.md entry "[Phase <n>] Phase summary" with the finished todos, open follow-ups and anything the
   maintainer has to check on the lab PC.

## Open

### Phase 0 — Concept

### Phase 1 — Consistent execution parameters

### Phase 2 — Experiment storage

### Phase 3 — Experiment scripts and substrate main

- [ ] T51: New template for experiment scripts [phase: 3]
      Goal: One parameterised experiment script replaces the copied scripts; it takes its programs either from stored AeroBasic programs or from the slicer.
      Priority: high | Depends on: T43, T44, T45, T47
      Done when:
        - The experiment is described by one parameter object (e.g. an `ExperimentSpec` dataclass: label, center, grid, structure size, objective, setup, drop direction, plane-fit mode, DHM usage, camera capture, power and speeds, program source) instead of values edited in the script (N001, N006–N008, N013); hardcoded values such as the DHM-paper value are passed or determined (N021).
        - Program source is an explicit enum: stored hand-written AeroBasic programs, or the slicer with height data (`aerobasic/slicer/pipeline.slice_geometry`); the enum can be extended later (phase data, F2); the source is stored in the metadata.
        - Dummy dry runs pass for both program sources.
        - `mains/Experiments/`: scripts the maintainer still uses are migrated (Decision: list from the maintainer); the others are moved to `mains/Experiments/historical/` or listed as historical in a README; German text in migrated scripts is translated.
      Notes: Replaces T26.

- [ ] T52: Substrate-specific `main.py` [phase: 3]
      Goal: The main file describes one substrate and the list of experiments printed on it.
      Priority: high | Depends on: T48, T51
      Done when:
        - The main file defines the substrate (label, resin edges, user, objective) and a list of experiments, each with its `ExperimentSpec` and an optional storage path (default location otherwise).
        - Before printing, experiment areas are checked for overlap with each other and against the resin edges.
        - Experiments run one after another and are entered into the substrate index; an optional confirmation between experiments.
        - Dummy dry run: two experiments on one substrate give two experiment files and one substrate index.

### Phase 4 — Voxel database and voxel-aware slicing

- [ ] T54: Voxel-aware slicing and hatching [phase: 4]
      Goal: With voxel data, the printed geometry matches the designed geometry as closely as possible instead of being enlarged by the voxel size.
      Priority: high | Depends on: T53, T51
      Done when:
        - A `VoxelModel` interface returns voxel width and height for laser parameters; one implementation uses T53, a second one ("no data") reproduces today's behaviour exactly (golden files unchanged when no material is given).
        - With data: contours are offset inward by half the voxel width (`SlicingParameters.contour_offset_um`), first and last slice are shifted by half the voxel height so that top and bottom surfaces match the design, and a gap between neighbouring lines or layers causes a warning (or spacing is derived from an overlap ratio; Decision in the todo).
        - The hatching strategies (`hatching.available_strategies()`) receive the voxel model, so that later strategies (F7) can use it.
        - The voxel model and the values used are stored in the experiment metadata and the summary.
        - Tests: for a box and a cylinder the envelope of toolpath plus voxel stays within a tolerance of the design; the no-data path is unchanged.

- [ ] T31: Laser power per structure, layer and line (from T19) [phase: 4]
      Goal: Program generation can change the laser power between structures, layers and lines; this enables adaptive slicing and printing strategies (F7).
      Priority: medium | Depends on: T54
      Done when:
        - Parameter test prints can change the power between structures (N012).
        - `print_structure` supports a power per layer, and slicer toolpaths can carry a power per segment that the AeroBasic generation emits (N083).
        - The powers used are stored in the metadata.

### Phase B — Backlog from T19 (details in `todo_notes.md`)

- [ ] T32: Clean up the AeroBasic API and task handling (from T19) [phase: B]
      Goal: The AeroBasic API is correct and complete for the commands in use.
      Priority: medium | Depends on: –
      Done when:
        - `PROGRAM_ASSOCIATE` sends the correct syntax (N029); reading system parameters is possible (N030).
        - Program text: compact variable declarations, header metadata, and a mode check for VELOCITY/ABSOLUTE (N031–N033).
        - IFOV setup: ramp types and the F threshold are investigated and documented (N044, N045).
        - `run_program_as_task`: better task-id choice, cleanup of the previous program, and a decision on the old "delete this function" note (N058, N073, N074).

- [ ] T37: Replace the hotfixes in tools and devices (from T19) [phase: B]
      Goal: Focus, layer, plane, DHM and serialization code have no open hotfixes.
      Priority: medium | Depends on: T43
      Done when:
        - The focus-detection noise threshold `minDiffMax` is replaced by a justified criterion, and its value is checked for 63x (N084, N010).
        - Layer: sample dictionary, missing `self.device` and the result object are fixed (N085, N086, N088); the orientation part is done in T43.
        - The plane angle edge case (-180 vs 180) is handled (N090).
        - DHM: capture time analysed; motor scan loop with limit checks and an own exception (N075, N076).
        - `DrawableObject._init_args` stores "data" instead of the hotfix (N046).

- [ ] T28: Overview images and time estimate (from T19) [phase: B]
      Goal: An experiment documents the whole scene and its expected duration.
      Priority: low | Depends on: T47
      Done when:
        - An overview image of the whole scene is taken before and after printing and stored in the experiment file (N009).
        - The expected and the actual duration of an experiment are logged and stored (N023).

- [ ] T35: Clarify line and rectangle details (from T19) [phase: B]
      Goal: Line-based structures have checked parameters and no unexplained hotfixes.
      Priority: low | Depends on: –
      Done when:
        - `IFOV_Lines`: velocity unit (mm/s), validation, default maximum speed (100 × IFOV size) and the speed values from parameters (N065–N067).
        - Vector printing functionality is designed (N068).
        - The `Z == 0` hotfix in `Rectangle3D` is understood and replaced or documented (N069).
      Notes: The QR-code drop direction (N070) moved to T43.

- [ ] T36: Z-line: offset, global variables and focal-point script (from T19) [phase: B]
      Goal: Z-line programs are consistent and the focal-point study script is complete.
      Priority: low | Depends on: –
      Done when:
        - The camera offset is integrated into `System.zline` (N071); the z-line program uses global variables and is not recompiled every time (N072).
        - `z_line_focal_points.py`: dz split, z recalculation, noise on dz, min_distance, boundary, result dictionary and file-exists check are resolved (N014–N020).

- [ ] T38: Visualization: laser power and axis formatting (from T19) [phase: B]
      Goal: Movement plots show the laser power and readable axes.
      Priority: low | Depends on: –
      Done when:
        - The laser power is read from the program and shown as colour (N091, N092).
        - Axis labels are shown without scientific notation (N093).

- [ ] T39: Manual DHM helper: implement reset (from T19) [phase: B]
      Goal: The interactive DHM helper can reset its state.
      Priority: low | Depends on: –
      Done when:
        - `test/manual/dhm/DHMUserBackend.py` implements its reset method (N094).

- [ ] T60: Experiment plots: corners, QR code and structure plots (found during T41) [phase: B]
      Goal: The overview plot shows everything that is printed, and structure plots can be switched on.
      Priority: low | Depends on: –
      Done when:
        - `plot_experiment()` draws the corners (marking the double corner) and the QR code, and shows the experiment UUID.
        - The hard-coded `plotting_structure = False` in `structure_program` is replaced by a parameter (default off) or removed.
        - Test: the plot is written for the dry-run experiment.

## In Progress
<!-- Claude Code moves a todo here when starting work. -->
## Blocked
<!-- Format: todo as above, plus the line "Blocked by: <reason or T<n>>". -->
- [ ] T53: Voxel database (SQLite) [phase: 4]
      Goal: Voxel width and height can be looked up for material, objective, setup, power and velocity, with interpolation between measured points.
      Priority: high | Depends on: –
      Done when:
        - `docs/design/VOXEL_DATABASE.md` defines schema, interpolation and fallback, and is approved by the maintainer.
        - The SQLite database has at least the tables `material` and `voxel_measurement` (material, objective, setup, power_mW, velocity_um_s, width_um, height_um, method, experiment_uuid, date, notes); the schema version is kept in `PRAGMA user_version` and migrations run in order when the database is opened.
        - A class (e.g. `VoxelDatabase`) adds measurements, imports CSV files and returns the voxel size for a parameter set, or `None`.
        - Interpolation per material/objective/setup over a dose-like variable (e.g. P²/v, logarithmic), only inside the convex hull of the measured points and with a configurable minimum number of points; no extrapolation; unknown material or too few points → `None`.
        - The database path is configured in `nanofactory.json`; the `.sqlite` file is not in git, a CSV or SQL seed file is.
        - Tests with synthetic data: exact hit, interpolation, outside the hull, unknown material.
      Blocked by: waiting for maintainer approval of `docs/design/VOXEL_DATABASE.md` (draft written 2026-09-30; decisions V1–V5 in §9).
- [ ] T58: Define the capture position of `measure()` (found during T41) [phase: 1]
      Goal: Camera and DHM captures are taken at a defined Z and galvo position, not wherever the last layer left the axes.
      Priority: medium | Depends on: T46
      Done when:
        - Decision: capture Z (e.g. plane height at the structure center plus an offset, per drop direction) and whether A/B are reset to 0 before a capture; documented in the `measure()` docstring.
        - `measure()` moves to that position before every capture; the commanded position is what T46 stores.
        - Dummy test: after a layer with galvo offsets, the capture is taken at the defined Z and A = B = 0 (or the decided values).
      Notes: Today `measure()` sends only `LINEAR X Y`; in the T41 dry run captures were taken at A = 30 µm, B = 225 µm and the Z of the last layer.
      Blocked by: Decision. Proposal: before every capture move to Z = plane height at the capture position plus an objective-specific offset `captureZOffset` (new key of the objective section, default 0 µm), and set A = B = 0. Asked 2026-09-29.
- [ ] T45: Take camera images only on request [phase: 1]
      Goal: `Experiment.measure()` takes a camera image only when this is explicitly enabled.
      Priority: medium | Depends on: –
      Done when:
        - A parameter `camera_capture: bool = False` exists (Decision: `sys_args["camera"]` or `Experiment` argument; document the choice) and is stored in the experiment dictionary.
        - `measure()` skips `System.getimage()` when it is False and returns `None` for the camera container; `restart_experiment()` uses the stored value.
        - Experiment scripts that need camera images set it to True explicitly (listed in WORKLOG.md).
        - Dummy tests for both values.
      Notes: Video recording in a thread is future_todo.md F3.
      Blocked by: Decision. Proposal: an `Experiment` keyword argument `camera_capture: bool = False` (an experiment choice, not a camera device setting, so not in `sys_args["camera"]`), stored in the experiment metadata. Question: which experiment scripts in `mains/Experiments/` need camera images (they get `camera_capture=True`)? Asked 2026-09-29.
- [ ] T44: Restructure how plane fitting is run [phase: 1]
      Goal: Plane-fit modes are named, documented and selectable per experiment, and a single plane fit can run outside `Experiment`. The fitting algorithms stay unchanged.
      Priority: high | Depends on: T43
      Done when:
        - `plane_fit_mode: int` is replaced by an enum with descriptive names for the current modes 0 and 1; the old integers are still accepted when an `experiment_dictionary.json` is read.
        - A "border only" mode exists (N026).
        - A single plane fit can be run outside `experiment.py` (N079).
        - The `+1` in the sample points for mode 0 is checked (N078); the experiment center is validated against the resin drop edges (N022); for big structures the z deviation between the corners is checked and a warning is logged above a configurable threshold (N082).
        - Mode, sample points and the fitted plane are stored in the experiment dictionary.
        - A dummy test per mode checks number and positions of the sample points.
      Notes: Replaces T29.
      Blocked by: T43.
- [ ] T43: Make the drop direction consistent everywhere [phase: 1]
      Goal: The drop direction is one explicit parameter that flows from the experiment script through `Experiment`, `System`, the tools and the structures; no orientation hotfixes remain.
      Priority: high | Depends on: –
      Done when:
        - Every active experiment script in `mains/` passes `drop_direction` explicitly (N002); no script sets a z sign by hand.
        - `tools/layer.py` and `tools/detector.py` derive their orientation from `DropDirection` instead of the separate `Orientation` value and the "Top" hotfix; the drop direction is part of `sys_args` where the tools need it (N087, N089). Decision: merge `Orientation` into `DropDirection` or map one to the other.
        - `QRCode` takes the drop direction into account (N070).
        - Every place that depends on the sign is listed in the `DropDirection` docstring (coordinate system, layer order in `print_structure`, start z in `plane_fit`, restart, detector) and checked.
        - The `DropDirection` docstring states that dip-in needs a different computation and is planned (future_todo.md F8); no `DIP_IN` member is added yet.
        - Dummy tests: UP and DOWN give mirrored z values in the layer programs; existing golden files are unchanged.
      Notes: Covers N002, N070, N087, N089 (parts of T35 and T37).
      Blocked by: Decision (Orientation vs. DropDirection). Proposal: remove `parameter.Orientation` and let `Scanner`/`Layer` take a `DropDirection` from `sys_args["layer"]["dropDirection"]` (set by `Experiment`). Open physics question for the maintainer: today `Layer` hard-codes `Orientation.UP` for both objectives, and the scanner removes the second layer (immersion oil) above the interface for UP and below for DOWN. Must DOWN (63x) really map to the "below" rule, or should both drop directions keep the current UP behaviour? Asked 2026-09-29.

## Done
<!-- Claude Code adds: - [x] T<n>: title — YYYY-MM-DD — 1–2 sentences on what changed — commits: `<sha>`, … -->
- [x] T1: Record baseline and review the code — 2026-09-28 — Recorded the test baseline (global env: all 40 files fail on a NumPy ABI mismatch; clean venv: 16 passed / 20 failed / 16 errors over `test/`) in WORKLOG.md and wrote `docs/reviews/CODE_REVIEW_2026-09-28.md`; follow-ups T9–T18 added. — commits: `bf98f78`

- [x] T2: Design the dummy hardware backend — 2026-09-28 — Wrote `docs/design/DUMMY_BACKEND.md` (seam/role protocols, explicit `backend=` switch, socket-level fake controller, deterministic simulated world with call log); approved by the maintainer with three decisions (controller merge later as T20, no env var, `plane_fit(plane=...)` instead of simulated detection). — commits: `46ae4b1`, `b6340a4`

- [x] T12: Rename `devices/aerotech_old.py` to `devices/a3200.py` — 2026-09-28 — Pure `git mv` plus the import in `devices/__init__.py`; hardware-free test results unchanged (16 passed / 11 failed / 3 errors, as in baseline B). — commits: `6b43511`

- [x] T3: Implement the dummy hardware backend — 2026-09-28 — Added `nanofactorysystem.backends` (protocols, RealBackend, DummyBackend with socket-level fake A3200, simulated camera/DHM/attenuator, deterministic world and call log), lazy config with built-in default, device injection parameters, `System/Experiment(backend=...)` and `plane_fit(plane=...)`; 40 new tests, real-hardware path verified unchanged. — commits: `df14fd7`, `65cd58c`, `8dc0b46`, `597b8ba`

- [x] T4: pytest configuration and shared fixtures — 2026-09-28 — Added `[tool.pytest.ini_options]` (testpaths, norecursedirs, markers `hardware`/`slow`) and `test/conftest.py` with `--run-hardware` and the fixtures `test_config`, `tmp_program_dir`, `dummy_backend`, `no_sleep`, `dummy_controller`, `dummy_system`; 7 fixture tests. — commits: `97c5612`

- [x] T15: Repair failing hardware-free unit tests — 2026-09-28 — Fixed `create_variable`/`AerotechVariable` (separate fix commit) and updated outdated tests with justification (axis names, Python 3.12 changes, timestamp header, removed `CornerRectangle`, wrong cm value); `test_prevent_mixed_axes` is strict xfail (T23). 31 passed, 1 xfailed. — commits: `69827fd`, `22e8e7e`

- [x] T5: Triage and convert the device tests — 2026-09-28 — Every device/DHM/Femtika/tools/system/slicer test file is converted (dummy + `hardware` tests with assertions) or moved to `test/manual/`, reasons in WORKLOG.md; `python -m pytest` passes without hardware or config (104 passed, 14 skipped, 1 xfailed) and `-m hardware --run-hardware` collects 13 tests. — commits: `96d54a4`, `4cbda21`

- [x] T6: Dry-run an experiment with the dummy backend — 2026-09-28 — `default_exp_file.py` runs end to end on the dummy backend (plane_fit with known plane, build_programs, print_experiment); integration test writes only to `tmp_path`; the dry run found and fixed a tuple bug in the template. — commits: `c6179d0`, `2e911c2`, `43cb532`

- [x] T7: Golden-file tests for AeroBasic generation — 2026-09-28 — 11 representative programs (DefaultSetup and SetupIFOV, incl. corners, stair, QR code, IFOV grating) are compared against `test/golden/*.txt`; `--update-golden` regenerates them deliberately. — commits: `175af6b`

- [x] T8: Write `test/README.md` and update the documentation — 2026-09-28 — `test/README.md` documents the four test categories with per-module tables, run commands, markers, dummy backend usage and artefact locations; CLAUDE.md Commands, Architecture (and the outdated Configuration) sections updated. — commits: `1705ca4`

- [x] T9: Fix packaging and pin a working environment — 2026-09-29 — `pyproject.toml` discovers all subpackages, declares all runtime dependencies (OpenCV pinned for NumPy 2) and a `test` extra; a fresh venv with `pip install ".[test]"` passes the suite. — commits: `7aecd16`

- [x] T10: Fix defects in the experiment flow — 2026-09-29 — `opl_scan` uses `motorscan`, a failed layer is logged (task stopped, printing continues) via the new `TaskFailedError`, substrate information is merged, empty structures work, and the experiment dictionary stores the right objective and log file; 6 new dummy tests. — commits: `b1d19a2`, `b0ed53e`

- [x] T21: Stop `Parameter` from mutating the caller's argument dictionaries — 2026-09-29 — `Parameter` works on a copy of each section, so `sys_args` can be reused; also fixed `Camera` ignoring `product`/`deviceID`. — commits: `4911149`, `5af8e45`

- [x] T13: Add timeouts to hardware communication and wait loops — 2026-09-29 — Configurable connect timeouts (10 s), optional response timeouts, responses read until the terminator, bounded axis/z-line waits and stall/stop bounds for tasks; terminated `~LASTERROR`; 12 dummy tests. — commits: `1ee7ef0`, `8d9d4dc`

- [x] T14: Remove the hardcoded calibration path from `IFOV_Lines` — 2026-09-29 — `IFOV_Lines` takes a `PowerCalibration` (explicit, active context, or configured file); `Experiment.build_programs()` uses its attenuator calibration; golden files unchanged; 8 new tests. — commits: `eb26199`, `69547ba`

- [x] T11: Fix small defects in `System` and the `A3200` controller — 2026-09-29 — Fixed `object_pos`/`camera_pos`, `A3200.home`, `A3200.container`, `self.z` before an absolute z move and the recursive `send_one`; a dummy test per fix. — commits: `6ef8d37`, `b65b604`

- [x] T22: Fix NumPy 2.5 deprecation in `Attenuator` — 2026-09-29 — `reshape` instead of assigning `array.shape` in `Attenuator` and `CameraDevice` (the `IFOV_Lines` case went away in T14); the suite passes with the deprecation as error. — commits: `daa757e`

- [x] T16: Fix always-true `assert (path, Path)` in experiment scripts — 2026-09-29 — The 48 always-true asserts in `mains/` are replaced by `path = Path(path)`, which accepts the str paths the callers pass; no warnings remain. — commits: `d1f1f67`

- [x] T17: Clean up logging — 2026-09-29 — `getLogger()` no longer duplicates handlers (one console handler, one log file that is replaced for a new file); command failures are logged instead of printed. — commits: `2da7be2`, `cdcee08`

- [x] T24: Fix `utils.visualization.plot_movements` — 2026-09-29 — Arcs, ragged segments, empty programs, degenerate axes and RAPID/variables are handled; all program plots work and plotting errors fail the tests again; 5 new tests. — commits: `da404d1`, `e2df115`

- [x] T25: Fix argument passing in experiment scripts — 2026-09-29 — The restart script now rebuilds the experiment from `experiment_dictionary.json` via the new `Experiment.parameters_from_dictionary()` (the original finding about the logger was inaccurate, see WORKLOG), and the template passes substrate information; dummy restart test added. — commits: `56e4d9a`, `412c763`

- [x] T23: Decide and implement axis validation for `SingleAxis` — 2026-09-29 — Maintainer decision: mixing stages allowed; `~`, `^` and an empty `&` raise `AxisError`; the xfail test is replaced by `test_axis_combinations`. — commits: `6d4009a`

- [x] T20: Merge `A3200` and `Aerotech3200` into one controller class — 2026-09-29 — `A3200` builds on the new `AerotechController` and one ASCII interface; `System.controller is System.a3200_new`; golden command logs recorded before the merge are unchanged; maintainer decision: `.api` Z moves beyond zMax are refused. — commits: `f49d935`, `fdb0719`, `dcf80dc`, `5f8e203`

- [x] T19: Identify each and every todo and note in all of the documents — 2026-09-29 — All 535 work markers (94 distinct) and the slicer roadmap are recorded in `todo_notes.md` with meaning, locations and 15 work packages (T26–T40), then removed from the active code; explanatory notes kept (maintainer decision). — commits: `b2d2f05`, `5f8af15`

- [x] T18: Translate German identifiers and comments — 2026-09-29 — German comments/docstrings in the package and test modules translated, `run_testzweck_altesSystem` renamed to `send_with_simple_protocol`, one module per commit; `mains/` and `test/manual/` scripts left (see WORKLOG). — commits: `118a095` … `7d973e9` (15)

- [x] T41: Audit the experiment metadata — 2026-09-29 — `docs/reviews/METADATA_AUDIT.md` lists every file an experiment writes and rates each metadata item, checked against two dummy dry runs of the template; defects outside T42–T50 were added as T55–T60. — commits: `bf5565a`

- [x] T42: Design the experiment storage and substrate model — 2026-09-29 — `docs/design/EXPERIMENT_STORAGE.md` defines one self-contained HDF5 file per experiment below the per-user default root, substrate/experiment labels and UUIDs, write strategy, JSON copies, legacy reading and the store API; approved by the maintainer with all proposals D1–D8. — commits: `ef2ff63`, `3f75e0a`

- [x] T46: Record the stage position of every capture — 2026-09-29 — `measure()` stores a `CaptureRecord` (commanded and actual XYZAB position, structure, phase, layer, image index/count, UTC time) in every camera/DHM container and in `captures.json`, and accepts a list of capture offsets; golden command logs unchanged. — commits: `c16f5ae`

- [x] T47: Implement the HDF5 experiment store — 2026-09-30 — New `nanofactorysystem.storage` (`ExperimentStore`, records, JSON copies, lock file, software info); `Experiment` writes metadata, calibration, plane fit, OPL scan, layout, structures, layer programs, progress and captures (no more `.zdc`/`.npy`) into `experiment.h5`, exports the JSON copies from it, and refuses an existing experiment folder unless `resume=True`. — commits: `bc371eb`, `fe6036a`, `bed280b`

- [x] T55: Store the controller command log with the experiment — 2026-09-30 — `A3200.log` is written into the experiment folder, and the command log and the session's console log are stored per session under `/logs` in `experiment.h5`, also after an exception or abort. — commits: `b624a66`

- [x] T57: Store paths relative to the experiment folder — 2026-09-30 — Layer/structure program files and the log file are stored relative to the experiment folder (file and JSON copies); `parameters_from_dictionary()` uses the given folder, so a moved experiment can be restarted; old absolute entries still work. — commits: `e07db5a`

- [x] T48: Substrate model, default location and experiment index — 2026-09-30 — `SubstrateStore` (substrate.json with record and experiment index, labels `HR-26-001`/`-A`, `find_experiments`, `default_root` with `dataRoot` and refused synced folders); `Experiment(path=None, substrate=...)` creates a new folder per print and keeps the index up to date; `substrate_information.json` merging replaced (old files importable). — commits: `1014892`, `cf5ed05`

- [x] T49: Experiment summary — 2026-09-30 — `storage/summary.py` builds a summary (UUID, one row per user structure with position, slice, hatch, power, velocity, IFOV, DHM, camera, status); written into `/summary` and `experiment_summary.json` after building and after every structure and logged as table. — commits: `92b9bcc`

- [x] T50: Restart and repetitions on the new storage — 2026-09-30 — Restart reads parameters and per-layer progress from `experiment.h5` (resumes correctly after any number of aborts, keeps the UUID); old JSON folders are imported into a new experiment file on restart; `REPEAT` fixed (own grid cell, `<name>_rep<n>`, `repeat_of`). — commits: `7aaee04`

- [x] T59: Correct the print-progress record — 2026-09-30 — `print_progress.json` is exported from the experiment file (schema `nanofactory.print_progress/2`): printed/failed layer counts, start/end time per layer and structure; UP and DOWN tested after a complete and an aborted structure. — commits: `154d85d`

- [x] T56: Make structure serialisation complete and reversible — 2026-09-30 — `to_json()` stores only constructor parameters (with `__module__`, reversible encoding of enums/points/calibrations, lost parameters reported), `structure_from_json()` rebuilds structures; all golden-test structures round-trip to identical programs, golden files unchanged. — commits: `1f379ae`
