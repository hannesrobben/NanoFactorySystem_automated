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
| B | Backlog from T19 (`todo_notes.md`) | T32, T37, T28, T35, T36, T38, T39, T60, T61, T62, T63, T64 | – |

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

### Phase 4 — Voxel database and voxel-aware slicing

### Phase B — Backlog from T19 (details in `todo_notes.md`)

- [ ] T28: Overview images and time estimate (from T19) [phase: B]
      Goal: An experiment documents the whole scene and its expected duration.
      Priority: low | Depends on: T47
      Done when:
        - An overview image of the whole scene is taken before and after printing and stored in the experiment file (N009).
        - The expected and the actual duration of an experiment are logged and stored (N023).
      Decisions (maintainer, 2026-09-30/2026-10-01): (1) a camera mosaic stitched with `tools.stitch.Canvas`, stored in the experiment file before and after printing; it covers the experiment rectangle including the corners (the defined boundaries), or only the structure grid with `skip_corner`; by default only the stitched image is stored, optionally also every single image (to check the stitching). (2) Expected duration from the path lengths and F values of every layer program plus an overhead of 5 s per layer (configurable; covers capturing and future reconstruction), logged after `build_programs()` and compared with the stored start/end times.

- [ ] T64: Port the experiment scripts imported by `main.py` and `main_IFOV.py` (found during T51) [phase: B]
      Goal: The two scripts the entry files still import run with the current code.
      Priority: medium | Depends on: –
      Done when:
        - `Kailas/power_z_pitch_lines.py` and `Big_substrate_20x/grating_ifov_test.py` are moved back from `historical/` and ported to `experiment_spec()` like the other scripts (maintainer decision 2026-10-01), without `sample.orientation`.
        - `mains/main.py` and `mains/main_IFOV.py` import them from their new place; `test/integration/test_ported_scripts.py` checks them.

- [ ] T35: Clarify line and rectangle details (from T19) [phase: B]
      Goal: Line-based structures have checked parameters and no unexplained hotfixes.
      Priority: low | Depends on: –
      Done when:
        - `IFOV_Lines`: the writing speed stays fixed per objective (maintainer decision 2026-10-01; free speed is F13); the `velocity` argument is documented as not changing the IFOV writing speed (N065–N067).
        - Non-IFOV structures take their velocity independently; the velocity unit is consistent: programs get mm/s (a value in µm/s is too large and the controller raises an error), and every conversion between µm/s and mm/s is explicit and tested.
        - The `Z == 0` hotfix in `Rectangle3D` is understood and replaced or documented (N069; maintainer: probably related to the base height of another structure that uses `Rectangle3D`).
      Notes: The QR-code drop direction (N070) moved to T43. Vector (shell) printing (N068) moved to F12.

- [ ] T36: Z-line: offset, global variables and focal-point script (from T19) [phase: B]
      Decision (maintainer, 2026-10-01): finish the focal-point script; nothing may change the normal behaviour of the system or the plane fitting.
      Goal: Z-line programs are consistent and the focal-point study script is complete.
      Priority: low | Depends on: –
      Done when:
        - The camera offset is integrated into `System.zline` (N071); the z-line program uses global variables and is not recompiled every time (N072).
        - `z_line_focal_points.py`: dz split, z recalculation, noise on dz, min_distance, boundary, result dictionary and file-exists check are resolved (N014–N020).

## In Progress
<!-- Claude Code moves a todo here when starting work. -->
## Blocked
<!-- Format: todo as above, plus the line "Blocked by: <reason or T<n>>". -->
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

- [x] T60: Experiment plots: corners, QR code and structure plots — 2026-09-30 — `plot_experiment()` draws corners (double corner highlighted, positions labelled), QR code and the UUID and returns the figure; `build_programs(plot_structures=True)` replaces the hard-coded switch. — commits: `f729324`

- [x] T38: Visualization: laser power and axis formatting — 2026-09-30 — Movements carry the attenuator value read from `$AO[0].A=`, laser-on lines are coloured by power (mW with a calibration) with a colour bar, and mm axes have no offset or scientific notation. — commits: `f688a61`

- [x] T39: Manual DHM helper: implement reset — 2026-09-30 — `DHMBackend.reset()` closes the client, restores the start state (motor position, flags, counter) and reconnects; tested on the dummy DHM. — commits: `b875fe0`

- [x] T43: Make the drop direction consistent everywhere — 2026-09-30 — `Orientation` merged into `DropDirection`: the scanner keeps the lowest focus range for DOWN and the highest for UP (maintainer's description), `Experiment` passes it via `sys_args['layer']['dropDirection']`, QR pixel lines follow it; z coordinates never depend on it (decision), only the order; docstring lists all places. — commits: `97e2345`

- [x] T44: Restructure how plane fitting is run — 2026-09-30 — `PlaneFitMode` (GRID/CORNERS/new BORDER, old integers accepted), `plane_fitting.sample_points/measure_plane` for plane fits outside `Experiment`, center validated against the resin edges, tilt warning with `tilt_warning_um`; the +1 of mode 0 is correct. — commits: `c619b7e`

- [x] T45: Take camera images only on request — 2026-09-30 — `Experiment(camera_capture=False)` (maintainer decision: Experiment argument); `measure()` skips the camera and returns None without it; stored, shown in the summary and used on restart; the 57 existing script calls pass True. — commits: `0315df1`, `314a30b`

- [x] T58: Define the capture position of `measure()` — 2026-09-30 — Before every capture the galvo is set to A = B = 0, Z is not moved (maintainer decision); the commanded position (X, Y, Z=None, A=0, B=0) is stored; golden command logs re-recorded (one added galvo command per capture). — commits: `fc9c425`

- [x] T53: Voxel database (SQLite) — 2026-09-30 — Design approved; `nanofactorysystem.voxel.VoxelDatabase` (tables material/voxel_measurement, PRAGMA user_version with migrations, CSV import/export, `voxel_size()` with exact hit, 2-D (ln P, ln v) interpolation inside the hull, dose fallback, no extrapolation); path `system.voxelDatabase`, seed CSV versioned. — commits: `b45a7d2`, `2de4367`, `9c52f15`

- [x] T51: New template for experiment scripts — 2026-09-30 — `ExperimentSpec`/`StructureSpec` (structure, slicer height data, or a factory of the running experiment; empty cells), `ProgramSource` (DRAWING/SLICER, stored) and `run_experiment()` with `mains/Experiments/experiment_template.py`; the 11 scripts named by the maintainer are ported (dry-run tested), all others moved to `mains/Experiments/historical/`. — commits: `acb2fe2`, `6462705`, `854bc8c`, `6d9afc1`, `905d1c2`

- [x] T52: Substrate-specific `main.py` — 2026-09-30 — `nanofactorysystem/substrate_plan.py` (`SubstrateSpec`, `SubstrateExperiment`, `run_substrate`): overlap, existing-experiment, resin-drop, objective and name checks before printing, sequential runs into the substrate index with optional confirmation; template `mains/substrate_main.py`; dummy dry run with two experiments on one substrate. — commits: `b46bed8`, `1796164`, `ff6d3a0`

- [x] T54: Voxel-aware slicing and hatching — 2026-09-30 — Voxel models (no data, fixed, database) behind the slicer protocol `VoxelModel`; contour offset, first/last slice at half the voxel height, spacing per `spacing_mode` (maintainer decision: `voxel_overlap` default, `static_hatching` with gap warnings); strategies get a `VoxelContext`; values in job metadata, structure JSON and summary; `ExperimentSpec(voxel_material=)`; no-data path and golden files unchanged. — commits: `e5a2173`, `e7ec542`

- [x] T31: Laser power per structure, layer and line — 2026-10-01 — Power per structure shown in a dummy test; `add_structure(layer_power=)`/`StructureSpec.layer_power` let every layer program set its own power (stored as `layer_powers_mw`, summary column); `Model3D_Slicer` prints toolpath elements with a power override (or `power_map(z_um, role)`) in their own IFOV blocks, unchanged without overrides. — commits: `a01c64b`, `1e6cf41`

- [x] T37: Replace the hotfixes in tools and devices — 2026-10-01 — Azimuth fix, motor-scan loop with limits, capture-time analysis and stored height profiles; the focus threshold and N088 went to T61 (maintainer decision: close T37). — commits: `8444d70`, `b396a38`, `040e831`, `72114eb`

- [x] T61: Justify the focus-detection threshold and clarify the layer result object — 2026-10-01 — Closed without code change (maintainer decision): the focus detection is reworked later with example data (F10); N088 is dropped and kept in `todo_notes.md` for the maintainer.

- [x] T32: Clean up the AeroBasic API and task handling — 2026-10-01 — Closed without code change (maintainer decision): moved to F11, to be done with the A3200 manual.

- [x] T63: Use the real IFOV writing speed for the voxel lookup (found during T54) — 2026-10-01 — The job of `Model3D_Slicer` records the fixed IFOV writing speed (5/10 mm/s), so the voxel lookup and the time estimate use it; the speeds are defined once in `lines.IFOV_WRITING_SPEED_MM_S`. — commits: `b2b07cd`

- [x] T62: Check experiment areas against the shape of the resin drop (found during T52) — 2026-10-01 — Experiment areas (substrate plan) and the experiment center (`Experiment(resin_edges=)`) are checked against the ellipse through the four edge points (`resin_drop.py`); no check for dip-in; the edges are stored with the experiment. — commits: `b9d8cfd`
