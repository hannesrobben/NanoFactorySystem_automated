# Work Log

Append-only log of completed and partial tasks. Newest entry at the bottom.
Format and rules: see "Work log (mandatory)" in CLAUDE.md.

### 2026-09-28 20:55 CEST — [T1] Record baseline and review the code
- **Status:** done
- **Changes:**
  - `docs/reviews/CODE_REVIEW_2026-09-28.md` (new): code review covering hardware coupling, import-time
    side effects, existing dummy code, correctness defects and the state of the tests.
  - `TODO.md`: T1 moved to In Progress, then to Done; new todos T9–T18 added (found during T1).
  - `WORKLOG.md`: this entry.
- **Tests:** Baseline recorded as described below. No code was changed.

  **Environment.** Windows 11, Python 3.12.3, with `~/nanofactory.json` present. That file only has
  user `Reinhard` and objective `Zeiss 20x`. `mvIMPACT`, `OffAxisHolo` and `PlotFont` are not
  installed, and no hardware is reachable. Timestamps come from PowerShell `TimeZoneInfo`, because
  Git Bash has no tzdata, so `TZ=Europe/Berlin date` prints GMT.

  **Baseline A (global interpreter, `python -m pytest` from the repo root).**
  Result: 1 test collected, 40 collection errors, 0 tests run. All 40 errors are the same
  `ImportError: numpy.core.multiarray failed to import`. NumPy 2.4.6 is installed alongside
  `opencv-python 4.10.0.82` and `SciDataContainer 1.2.0`, whose dependency chain was built against
  NumPy 1.x, so `import nanofactorysystem` fails.

  **Baseline B (isolated venv in the session scratchpad).**
  Packages: numpy 2.5.3, opencv-python 5.0.0, scipy 1.18.1, scikit-image 0.26.0, shapely 2.1.2,
  trimesh 5.1.0, qrcode, h5py, SciDataContainer, pytest 9.1.1. The package itself was not installed;
  the repo root is on `sys.path`. The venv is called via its 8.3 short path, because otherwise the
  shapely DLL path exceeds MAX_PATH.
  - Whole run, `python -m pytest` from the root: **aborts during collection with INTERNALERROR**,
    because `test/test_model3d.py:305` calls `sys.exit()` at module level.
  - Per file, `python -m pytest <file>`, one row per file that pytest would collect from the root.
    Columns: collected / passed / failed / errors, then the reason.

  | File | coll. | pass | fail | err | Reason |
  |---|---|---|---|---|---|
  | `test/test_aerobasic/test_constants.py` | 10 | 7 | 3 | 0 | `SingleAxis` rejects the value 124; `AxisError` not raised for mixed axes; `'XY' != 'X Y'` (axis string format changed) |
  | `test/test_aerobasic/test_coordinate_system.py` | 1 | 1 | 0 | 0 | – |
  | `test/test_aerobasic/test_drawings/test_circles.py` | 6 | 6 | 0 | 0 | passes, but has no assertions (only writes programs) |
  | `test/test_aerobasic/test_drawings/test_corners.py` | 0 | 0 | 0 | 1 | collection: `cannot import name 'CornerRectangle'` |
  | `test/test_aerobasic/test_program.py` | 6 | 1 | 5 | 2 | expected text lacks the timestamp header that `to_text()` now adds; `AerotechVariable` is abstract (`__call__`); `mkdir()` `FileExistsError` on `test/_programs` (depends on state) |
  | `test/test_utils/test_units.py` | 4 | 1 | 3 | 0 | `assertAlmostEquals` was removed in Python 3.12 |
  | `test/test_femtika/test_device_no_laser.py` | 9 | 0 | 8 | 0 (1 skipped) | `ConnectionRefusedError` 127.0.0.1:8000; the skip guard in `__init__.py` is inverted |
  | `test/test_femtika/test_device_WITH_laser.py` | 0 | 0 | 0 | 1 | collection: `No module named 'aerobasic'` (outdated import) |
  | `test/dhm/test_dhm.py` | 1 | 0 | 1 | 0 | `TimeoutError` WinError 10060 connecting to 192.168.22.2:27182 (about 21 s) |
  | `test/devices/test_aerotech.py` | 0 | 0 | 0 | 1 | script; collection: `RuntimeError: Not connected!` |
  | `test/devices/test_attenuator.py` | 0 | 0 | 0 | 1 | script; collection: calibration file `C:/Software/3DPoli Fabrication/...` not found |
  | `test/devices/test_camera.py` | 0 | 0 | 0 | 1 | script; collection: `ImportError: mvIMPACT not imported` |
  | `test/devices/test_dhm_objective.py` | 0 | 0 | 0 | 1 | script; collection: `No module named 'offaxisholo'` |
  | `test/test_system.py` | 0 | 0 | 0 | 1 | script; collection: `mvIMPACT not imported` |
  | `test/test_config.py` | 0 | 0 | 0 | 0 | script; prints the config, no tests |
  | `test/test_model3d.py` | 0 | 0 | 0 | 1 | script; all internal checks pass, but `sys.exit(0)` at module level gives an INTERNALERROR |
  | `test/tools/test_focus.py`, `test_grid.py`, `test_layer.py`, `test_plane.py` | 0 | 0 | 0 | 1 each | scripts; collection: `mvIMPACT not imported` |
  | `test/tools/test_63x_focus.py` | 0 | 0 | 0 | 1 | script; `Unknown user 'Hannes'!` |
  | `test/tools/test_stitch.py` | 0 | 0 | 0 | 1 | script; data file `focus-2/shear-1.json` is not in the repo |
  | `mains/Experiments/**/*_test.py`, `test_*.py` (11 files) | 0 | 0 | 0 | 0 | experiment scripts, no tests collected |
  | `mains/Experiments/Kailas/voxel_dose_test.py`, `zoffset_voxel__dose_test.py` | 1 each | 0 | 0 | 1 each | `testprint()` collected as a test; `fixture 'absolute_center' not found` |
  | `mains/debugging/task_test.py` | 0 | 0 | 0 | 0 | – |
  | `mains/debugging/test_plot.py` | 0 | 0 | 0 | 1 | `SyntaxError` (parameter without default after default) |
  | `nanofactorysystem/aerobasic/programs/drawings/new/test_stitching.py` (legacy) | 0 | 0 | 0 | 1 | missing module `drawings.basic_structures` |
  | `nanofactorysystem/aerobasic/programs/drawings/new/test_workflow.py` (legacy) | 1 | 0 | 1 | 0 | writes to `/home/claude/workflow_test.png`; takes 84 s |
  | `nanofactorysystem/aerobasic/programs/drawings/test/*.py` (3 files) | 0 | 0 | 0 | 0 | scripts; `test_heightstructure.py` runs 135 s of module-level code during collection |

  Totals over `test/`, run file by file: 37 collected, 16 passed, 20 failed, 16 errors, 1 skipped.
  The only hardware-free files that pass completely are `test_coordinate_system.py` and
  `test_circles.py`.
  The script tests created `.test/*` and `test/_programs/` in the working tree. Both are
  gitignored, and I removed them after the run.
- **Commits:** `bf98f78` docs(review): add baseline code review and follow-up todos [T1]
- **Follow-ups:** T9–T18 added to TODO.md. T15 (repair failing hardware-free unit tests) blocks T5.
  T12 needs a maintainer decision (status of `devices/aerotech_old.py`) and affects the T2 design.
  Reproducing baseline B needs a NumPy-2-compatible environment; T9 will make that reproducible.

### 2026-09-28 20:59 CEST — [T2] Design the dummy hardware backend
- **Status:** blocked (waiting for maintainer approval)
- **Changes:**
  - `docs/design/DUMMY_BACKEND.md` (new): the design. It covers the role and seam protocols per device
    (motion controller for both `A3200` and `Aerotech3200`, attenuator, camera, DHM), the single
    `backend=` switch with real hardware as default, the socket-level `FakeA3200Transport`, the
    deterministic `SimulatedWorld` with a call log and virtual clock, synthetic images, operation
    without `~/nanofactory.json`, lazy `mvIMPACT` import, the file layout, the API impact and a
    commit plan for T3.
  - `TODO.md`: T2 moved to In Progress, then to Blocked.
  - `WORKLOG.md`: this entry.
- **Tests:** none; this is a design document only.
- **Commits:** `46ae4b1` docs(design): propose dummy hardware backend [T2]
- **Follow-ups:** The maintainer needs to approve the design and decide on §10:
  (1) rename `devices/aerotech_old.py` → `devices/a3200.py` (T12) before modifying it;
  (2) keep the `NANOFACTORY_BACKEND` environment variable, yes or no;
  (3) simple sample/spot model first, with seeding `plane.zdc` as the fallback for T6.
  T3–T8 are waiting on this approval. **Resume at:** T2 approval, then T3 step 1 in §11 of the design.

### 2026-09-28 22:46 CEST — [T2] Design the dummy hardware backend (approval)
- **Status:** done
- **Changes:**
  - `docs/design/DUMMY_BACKEND.md`: status set to approved. §10 now records the maintainer decisions:
    (1) `A3200` and `Aerotech3200` are merged later as T20, and T12 is only a rename;
    (2) there is no `NANOFACTORY_BACKEND` variable, only the explicit `backend=` argument, and usage
    must be documented; (3) `plane_fit()` is not simulated and gets `plane=...` instead, so spot
    rendering was removed from the dummy camera and DHM. §4, §5, §9 and §11 were adjusted to match.
  - `TODO.md`: T12 reworded to a pure rename; T20 (controller merge) added; T2 moved to Done. The
    maintainer's own uncommitted T19 ("Identify each and every todo and note") is committed unchanged.
  - `WORKLOG.md`: this entry.
- **Tests:** none; this is a documentation change.
- **Commits:** `b6340a4` docs(design): record maintainer decisions for dummy backend [T2]; the next
  commit contains this entry. Note: the message of `b6340a4` still says "T19" for the controller
  merge. The todo was renumbered to T20, because T19 was already taken.
- **Follow-ups:** T12 (rename) comes next, then T3 following §11 of the design.

### 2026-09-28 22:47 CEST — [T12] Rename `devices/aerotech_old.py` to `devices/a3200.py`
- **Status:** done
- **Changes:**
  - `nanofactorysystem/devices/aerotech_old.py` (renamed → `nanofactorysystem/devices/a3200.py`): no content change.
  - `nanofactorysystem/devices/__init__.py`: imports `A3200` from `.a3200`.
  - `TODO.md`: T12 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `pytest --continue-on-collection-errors test/test_aerobasic test/test_utils` (baseline B venv):
  16 passed, 11 failed, 3 errors. This is identical to the baseline for these files; all failures are the
  known ones (T15). `from nanofactorysystem import A3200` resolves to `nanofactorysystem.devices.a3200`.
- **Commits:** `6b43511` refactor(devices): rename aerotech_old.py to a3200.py [T12]
- **Follow-ups:** `NanoFactorySystem-TREE.txt` still lists the old name. It is a stale snapshot that
  includes `.pyc` files, so I left it alone. CLAUDE.md's architecture section will be updated in T8.

### 2026-09-28 23:03 CEST — [T3] Implement the dummy hardware backend
- **Status:** done
- **Changes:**
  - `nanofactorysystem/config.py`: config lookup order `use_config()` → `$NANOFACTORY_CONFIG` →
    `~/nanofactory.json` → built-in `DEFAULT_CONFIG` (with a warning); `Config.load()`/`section()`;
    `use_config()` context manager that swaps the content in place; `ConfigDefaults` descriptor
    (lazy, deep-copied class defaults).
  - `nanofactorysystem/system.py`: `_defaults` via `ConfigDefaults`; `backend=` parameter; injection of
    drivers, transport, calibration file and program directory; `A3200.log` goes to the backend
    workdir for non-real backends.
  - `nanofactorysystem/devices/a3200.py`: `_defaults` via `ConfigDefaults`; keyword-only `transport`,
    `program_dir`.
  - `nanofactorysystem/devices/attenuator.py`: `_defaults` via `ConfigDefaults`; clear error when no
    calibration file is configured.
  - `nanofactorysystem/devices/camera.py`, `nanofactorysystem/devices/dhm.py`: `_defaults` via
    `ConfigDefaults`; keyword-only `driver`.
  - `nanofactorysystem/camera/camera.py`: `mvIMPACT` is imported on first use, with a clear `ImportError`;
    importing the package no longer emits a warning.
  - `nanofactorysystem/aerobasic/ascii.py`: `transport_factory` parameter; `DummyAsciiInterface`
    documented as deprecated.
  - `nanofactorysystem/devices/aerotech/__init__.py`: `transport_factory` and `program_dir`
    parameters; `dummy=True` now uses `FakeA3200Transport`.
  - `nanofactorysystem/experiment.py`: `backend=` parameter; `plane_fit(plane=...)`; the coordinate
    system setup was extracted into `_init_coordinate_system()`.
  - `nanofactorysystem/backends/__init__.py`, `protocols.py`, `real.py` (new): backend protocol,
    `resolve_backend`, role and seam protocols, `RealBackend`.
  - `nanofactorysystem/backends/dummy/__init__.py`, `world.py`, `calllog.py`, `a3200.py`, `camera.py`,
    `dhm.py`, `attenuator.py` (new): `DummyBackend` and the simulated devices.
  - `test/test_config_sources.py` (new, 9 tests), `test/backends/conftest.py` (new),
    `test/backends/test_dummy_controller.py` (new, 16 tests), `test/backends/test_dummy_devices.py`
    (new, 8 tests), `test/backends/test_dummy_system.py` (new, 7 tests).
  - `TODO.md`: T3 moved to In Progress, then to Done; T21 and T22 added.
  - `WORKLOG.md`: this entry.
- **Tests:** baseline B venv, hardware-free files (`test/test_aerobasic`, `test/test_utils`,
  `test/test_config_sources.py`, `test/backends`): 56 passed, 11 failed, 3 errors. The failures and errors
  are identical to baseline B (T15); the 40 new tests all pass, in about 0.6 s. The new tests also pass
  with a home directory that has no `nanofactory.json`, and `mvIMPACT`/`OffAxisHolo` are not installed.
  `test_real_backend_constructs_the_same_objects` checks that the default backend still calls
  `socket.socket(AF_INET, SOCK_STREAM)`, `CameraDevice(None, None)` and `DhmClient("192.168.22.2", 27182)`,
  sends the same start-up commands, and writes `__zline__.pgm` and `A3200.log` to the current working
  directory as before.
- **Commits:** `df14fd7` refactor(config): resolve config lazily and add built-in default [T3];
  `65cd58c` refactor(devices): add optional device injection and lazy mvIMPACT [T3];
  `8dc0b46` feat(backends): add dummy backend with simulated devices [T3];
  `597b8ba` feat(system): select hardware backend in System and Experiment [T3]
- **Deviations from the design:**
  - The built-in default config is a dict in `config.py` rather than `data/default_config.json`,
    because packaging does not ship data files yet (T9).
  - `Backend.dhm_driver(objective)` replaces `(host, port)`, because the DHM needs the objective's `dhmId`.
  - Attribute access on `Config` still raises for missing sections. The new `Config.section()` returns
    `{}`, which is what `ConfigDefaults` uses.
  - The fake can report "running" for a configurable number of `TaskState` polls.
  - Steps 5 and 6 were implemented before step 4.
- **Behaviour notes:** `ConfigDefaults` returns a deep copy, so `A3200._defaults["tasks"]` is no longer shared
  between instances. For the first instance nothing changes; before, a second `A3200` in the same process
  skipped loading the z-line program.
- **Follow-ups:**
  - T21: `Parameter` pops keys from the caller's argument dicts, so reusing `sys_args` fails.
  - T22: NumPy 2.5 deprecation in `attenuator.py:62`.
  - The dummy backend reproduced T11 (`A3200.zline` needs `self.z`, which only exists after an absolute Z
    move) and T10 (a task error raises `ValueError`). Both are covered by tests that document the current
    behaviour.
  - How to use the dummy backend is documented in T8 (`test/README.md`).

### 2026-09-28 23:06 CEST — [T4] pytest configuration and shared fixtures
- **Status:** done
- **Changes:**
  - `pyproject.toml`: `[tool.pytest.ini_options]` with `testpaths = ["test"]`, `norecursedirs` (`_programs`,
    `manual`, `old_to-delete`, `new`, plus pytest's defaults `.*`, `build`, `dist`, `*.egg`, `__pycache__`),
    and the markers `hardware` and `slow`.
  - `test/conftest.py` (new): the `--run-hardware` option; `hardware` tests are skipped without it, with the
    reason "needs the lab hardware; run with --run-hardware on the lab PC". Fixtures: `test_config`,
    `tmp_program_dir`, `dummy_backend`, `no_sleep`, `dummy_controller`, `dummy_system`. There is also the
    helper `dummy_sys_args()`, which returns fresh arguments (see T21).
  - `test/test_conftest.py` (new, 7 tests): marker handling via `pytester`, and every fixture.
  - `test/backends/conftest.py` (deleted): its fixtures moved to `test/conftest.py`; `backend` was renamed
    to `dummy_backend`.
  - `test/backends/test_dummy_system.py`: uses `dummy_backend`.
  - `TODO.md`: T4 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `test/test_conftest.py`: 7 passed. `test/backends` and `test/test_config_sources.py`:
  40 passed. A plain `python -m pytest` now collects only `test/`, but still aborts during collection
  (INTERNALERROR from `test/test_model3d.py`'s module-level `sys.exit()`); that file is triaged in T5.
- **Commits:** `97c5612` test: add pytest configuration and shared fixtures [T4]
- **Follow-ups:** none.

### 2026-09-28 23:11 CEST — [T15] Repair failing hardware-free unit tests
- **Status:** done
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/__init__.py`: **bug fix**. `AerotechVariable.__call__` was missing,
    so `create_variable()` could never instantiate a variable. The variable object was stored instead of its
    name. The declaration comment had no line break. Nothing in the package used this yet, so no generated
    program changes.
  - `test/test_aerobasic/test_variables.py` (new, 3 tests): covers the fix.
  - `test/test_aerobasic/test_constants.py`:
    - `test_values` expects `"X Y"` (space-separated, as the AeroBasic commands and `test_program` require).
    - `test_axis_parsing_invalid_value` asserts that 124 raises `ValueError` (Python ≥ 3.11 `Flag` STRICT
      boundary) and that 28 is valid.
    - `test_prevent_mixed_axes` is `xfail(strict=True)`: the validation was never implemented and
      conflicts with `Aerotech3200.home()` (T23).
  - `test/test_aerobasic/test_program.py`:
    - Content is compared without the non-deterministic timestamp header (the header was added to
      `to_text()` after the tests were written).
    - The write tests use a temporary directory; before, they failed whenever `test/_programs` already
      existed.
    - Plotting is synchronous instead of in non-daemon threads. Plotting errors, which the threads
      hid, are now warnings (T24).
  - `test/test_aerobasic/test_drawings/test_corners.py`: removed `test_all_markers` and
    `test_all_markers_optimized`, which used `CornerRectangle`. That class was deleted in `084f3aa`;
    `Experiment.add_corner_structures` places the corners now, and the T6 dry run covers it.
  - `test/test_utils/test_units.py`: `assertAlmostEquals` → `assertAlmostEqual` (removed in Python 3.12).
    The expected cm value was wrong by a factor of 100 (0.573123 mm = 0.0573123 cm). Note: this file tests
    a prototype `UnitFloat` class defined in the test itself, not package code.
  - `TODO.md`: T15 moved to In Progress, then to Done; T23 and T24 added.
  - `WORKLOG.md`: this entry.
- **Tests:** `test/test_aerobasic` and `test/test_utils`: 31 passed, 1 xfailed (baseline B: 16 passed,
  11 failed, 3 errors). The plotting warnings are expected; see T24.
- **Commits:** `69827fd` fix(aerobasic): make program variables usable [T15];
  `22e8e7e` test(aerobasic): update outdated unit tests to the current API [T15]
- **Follow-ups:** T23 (axis validation decision); T24 (`plot_movements` fails for most programs).

### 2026-09-28 23:17 CEST — [T5] Triage and convert the device tests
- **Status:** done
- **Changes (one decision per file, with the reason):**

  | File | Decision | Reason |
  |---|---|---|
  | `test/devices/test_aerotech.py` | converted: 8 dummy tests + 1 `hardware` | The script only logged the position. Now the commands, µm parsing, decimal comma, `zMax` safety, power, z-line task, fault handling and container are asserted on the fake; the hardware test asserts the real read-out. |
  | `test/devices/test_attenuator.py` | converted: 4 dummy + 1 `hardware` | The script printed and plotted the lab file. Conversion is checked on a synthetic calibration; the hardware test checks that the lab file is monotonic and spans 0..10. Plotting was dropped. |
  | `test/devices/test_camera.py` | converted: 1 dummy + 1 `hardware` | Same flow (`optexpose`, container) with assertions. |
  | `test/devices/test_dhm_objective.py`, `_test_dhm_objective.py`, `_test_dhm.py`, `live_tilt.py`, `live_tilt_cv.py` | moved to `test/manual/devices/` | Interactive live views and objective checks; they need `offaxisholo` and a person to judge the images. |
  | `test/dhm/test_dhm.py` | converted: 1 dummy + 1 `hardware` | Shared assertions for the simulated and the real client. The address now comes from the config instead of being hardcoded. |
  | `test/dhm/DHMUserBackend.py`, `test/dhm/path/test.tif` | moved to `test/manual/dhm/` | Interactive user helper, not a test. |
  | `test/test_femtika/__init__.py`, `test_device_no_laser.py` | converted: 8 dummy + 8 `hardware` (+ `test_linear`, skipped as before) | The inverted `EXECUTE_FEMTIKA_TESTS` guard is replaced by the marker. The same tests run on the real and the simulated controller and assert instead of printing. `test_move_home`/`test_homing` still move the real stage, as before. |
  | `test/test_femtika/test_device_WITH_laser.py` | moved to `test/manual/femtika/` | Laser visibility has to be judged by a person. Imports fixed (the old top-level `aerobasic` package no longer exists) and the file made self-contained. |
  | `test/tools/test_focus.py`, `test_layer.py`, `test_plane.py`, `test_grid.py`, `test_63x_focus.py` | moved to `test/manual/tools/` | Measurement procedures that expose the laser into a real sample; the outcome depends on the sample. Plane detection is not simulated (maintainer decision). |
  | `test/tools/test_stitch.py`, `eval_grid.py`, `grid.png` | moved to `test/manual/tools/` | Need data files (`focus-2/…`) that are not in the repository. |
  | `test/tools/test_focus_dummy.py` | new: 1 dummy test | Keeps the tools layer under test: `Focus` runs end to end on the dummy system (result "no focus"), and the exposure reaches the controller. |
  | `test/test_system.py` | converted: 2 dummy + 1 `hardware` | Container content and homing are asserted on the dummy; the hardware test checks that the system opens and closes. |
  | `test/test_config.py` | moved to `test/manual/print_config.py` | It only prints the config; `test/test_config_sources.py` tests the config. |
  | `test/example_planefit.py` | moved to `test/manual/` | Example script, not a test (it was never collected). |
  | `test/test_model3d.py` (slicer) | converted: `test/slicer/model3d_checks.py` + `test/slicer/test_model3d.py` | Hardware-free checks that used to abort the whole pytest run with `sys.exit`. The checks run via `runpy`, the test asserts that none failed, and temp files go to `tmp_path`. |
  | `test/__ZLINE__.OGM`, `test/__zline__.pgm`, the same two in `test/dhm/` and `test/tools/` | deleted | Artefacts that `A3200.init_zline` wrote into the current working directory during earlier runs. |
  | `nanofactorysystem/aerobasic/programs/drawings/test/*.py` | unchanged | Not in the directories listed in T5, and not collected (`testpaths = ["test"]`). These are height-structure scripts; left for T19 (inventory of notes) or a later triage. |

  - `test/conftest.py`: new fixture `lab_user` for hardware tests.
  - `TODO.md`: T5 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests (baseline B venv):**
  - `python -m pytest`: **104 passed, 14 skipped, 1 xfailed**. The 14 skipped are the 13 hardware tests plus
    `test_linear` (skipped as before). Baseline: the collection aborted with an INTERNALERROR.
  - The same result with a home directory without `nanofactory.json`. `mvIMPACT` and `offaxisholo` are not
    installed.
  - `python -m pytest -m hardware --run-hardware --co` collects 13 hardware tests.
  - The global interpreter on this PC still fails to import the package because of the NumPy ABI mismatch;
    that is T9.
- **Commits:** `96d54a4` test: move manual scripts to test/manual and remove artefacts [T5];
  `4cbda21` test: convert device and system scripts into test cases [T5]
- **Follow-ups:**
  - Safety question for the maintainer: `TestFemtikaNoLaser.test_move_home` moves the real stage to
    X=Y=Z=0 when run with `--run-hardware`. That is unchanged from before, but it is worth checking whether
    Z=0 is safe with the objective mounted.
  - The hardware tests were not run (no lab access in this session).

### 2026-09-28 23:20 CEST — [T6] Dry-run an experiment with the dummy backend
- **Status:** done
- **Changes:**
  - `mains/Experiments/default_exp_file.py`:
    - **Bug fix**: `structure_size = fov,` was a tuple, so the template failed before touching any
      hardware.
    - New optional arguments `backend` and `plane`, forwarded to `Experiment`/`plane_fit`; without them the
      behaviour is unchanged.
  - `test/integration/test_dry_run_default_experiment.py` (new): runs `binary_testprint()` end to end on
    the dummy backend. The flow is System start-up, `plane_fit(plane=<known sample plane>)`,
    `build_programs()`, then `print_experiment()`. It checks:
    - the output files exist, and every layer file is inside `tmp_path`;
    - all 50 layer programs ran to completion as controller tasks, with 0 statements the simulation could
      not execute;
    - there were no controller faults or unknown commands;
    - all 540 exposures lie within 20 µm of the plane, and camera images were stored;
    - only `tmp_path` was written.

    It is marked `slow` (about 10 s) but runs by default.
  - `TODO.md`: T6 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest test/integration`: 1 passed (9.5 s). The whole suite: see T8.
- **Commits:** `c6179d0` fix(mains): pass structure size as number in experiment template [T6];
  `2e911c2` feat(mains): allow a dry run of the experiment template [T6];
  `43cb532` test(integration): dry-run the experiment template on the dummy backend [T6]
- **Notes:**
  - `plane_fit()` is not simulated (maintainer decision); the dry run passes the known plane.
  - The dry run uses `dhm_usage=False`. With the DHM, `opl_scan()` would hit the known defect
    `dhm.opl_scan` → `motorscan` (T10).
  - Other experiment scripts can be dry-run the same way once they accept `backend`/`plane`.
- **Follow-ups:** none new.

### 2026-09-28 23:23 CEST — [T7] Golden-file tests for AeroBasic generation
- **Status:** done
- **Changes:**
  - `test/test_aerobasic/test_golden_programs.py` (new): 11 golden cases, each checked against its reference
    and for determinism (two runs give the same text).
    - `DefaultSetup` with `SetupIFOV` for 20x and 63x.
    - With `DefaultSetup`: `Corner` (plain and rotated by 45°), `Rectangle3D`, `Stair` (drop direction down),
      `FilledCircle2D` and `QRCode`.
    - With `SetupIFOV`: `Rectangle2D_IFOV` (20x) and `BinaryGrating_IFOV` (63x).
    - Each case renders the setup plus every layer program, as `Experiment.build_programs()` writes them,
      without the timestamp header.
  - `test/golden/*.txt` (new, 11 files, 179 kB): the reference programs. They are `.txt` because `*.pgm` is
    gitignored; line endings are normalised on comparison, so Git's CRLF conversion on Windows does no
    harm.
  - `test/conftest.py`: `--update-golden` option and `golden` fixture. On a mismatch the test shows a unified
    diff (truncated to 60 lines) and the command to update the references.
  - `TODO.md`: T7 moved to In Progress, then to Done; T22 and T14 extended.
  - `WORKLOG.md`: this entry.
- **Tests:** `test/test_aerobasic/test_golden_programs.py`: 23 passed. Also checked by hand: a tampered
  reference file makes the test fail with a readable diff, and `--update-golden` restores it.
- **Regenerating references:** `python -m pytest test/test_aerobasic/test_golden_programs.py --update-golden`,
  then review `git diff test/golden` before committing.
- **Commits:** `175af6b` test(aerobasic): add golden-file tests for generated programs [T7]
- **Notes / follow-ups:**
  - The IFOV structures read the lab calibration file from a hardcoded path (T14). The test points
    `IFOV_Lines.calibrationFile` to a synthetic file; T14 was extended to replace this patch.
  - T22 was extended: the same NumPy 2.5 deprecation occurs in `drawings/lines.py:82`.
  - Numbers are formatted with 10 decimals. A different NumPy or platform could change the last digits of
    computed coordinates. If that happens, review and regenerate the references rather than loosening the
    comparison.

### 2026-09-28 23:26 CEST — [T8] Write `test/README.md` and update the documentation
- **Status:** done
- **Changes:**
  - `test/README.md` (new):
    - the four categories (unit, dummy integration, hardware, manual), with a table per category: module,
      what it tests, which failure it catches, requirements;
    - run commands per category, the markers `hardware`/`slow`, `--run-hardware` and `--update-golden`;
    - dummy backend usage with an example test and the fixture list;
    - where generated artefacts go: `tmp_path`, `test/_programs/`, `test/golden/`.

    The code examples were executed once as a temporary test (2 passed), and the temporary file was removed.
  - `CLAUDE.md`:
    - `## Commands`: test commands, pointer to `test/README.md`, pytest configuration, markers, fixtures,
      environment requirement.
    - `## Architecture`: new "Hardware backends" part, `devices/a3200.py`, the controller merge (T20), and
      `plane_fit(plane=)` and the dry run in the experiment flow.
    - `## Configuration`: the lookup order and lazy defaults, because the old text ("System fails without
      the file") was wrong after T3; plus the T21 caveat.
    - `## Current Status` and `## Status Update Anchor` do not exist in the file and were not added.
  - `TODO.md`: T8 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests (final, baseline B venv):**
  - `python -m pytest`: 128 passed, 14 skipped (13 hardware + `test_linear`), 1 xfailed.
  - The same result without `~/nanofactory.json`.
  - `-m hardware --run-hardware --co`: 13 tests collected.
  - Global interpreter: still `ImportError: numpy.core.multiarray failed to import` (T9).
- **Commits:** `1705ca4` docs: describe the test suite and the dummy backend [T8]
- **Follow-ups:** none new. The `testing-infrastructure` group (T1–T8, plus T12 and T15, which were done as
  prerequisites) is complete.

### 2026-09-29 09:40 CEST — [T9] Fix packaging and pin a working environment
- **Status:** done
- **Changes:**
  - `pyproject.toml`:
    - `[tool.setuptools.packages.find] include = ["nanofactorysystem*"]` replaces the explicit list, which
      installed only the top-level package.
    - Dependencies now cover all imports of active modules (`scipy`, `qrcode`, `shapely`, `trimesh`, `h5py`
      added) and pin `opencv-python>=4.10.0.84` for NumPy 2.
    - The `test` extra adds `pytest`; `requires-python = ">=3.11"`; the build requirements are reduced to
      `setuptools>=64`.
    - The hardware-only packages that are not on PyPI are documented in a comment.
  - `test/README.md`: environment setup via `pip install ".[test]"`, the OpenCV/NumPy note, and the Windows
    path-length note for `shapely`.
  - `CLAUDE.md`: install command and environment note in `## Commands`.
  - `TODO.md`: T9 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:**
  - A fresh venv (`python -m venv`, then `pip install ".[test]"`) installed numpy 2.5.3 and opencv-python
    5.0.0.93.
  - From outside the repository, `nanofactorysystem.backends.dummy`, `aerobasic.programs.drawings`,
    `aerobasic.slicer` and `devices.aerotech` import from `site-packages`.
  - `pytest` (the venv's executable, so the installed package is used) in the repo:
    128 passed, 14 skipped, 1 xfailed.
  - Build artefacts (`build/`, `*.egg-info`) and the stale ignored `.test/` directory from the T4 run were
    removed.
- **Commits:** `7aecd16` build: install all subpackages and declare the real dependencies [T9]
- **Follow-ups:** The global interpreter on this PC still has `opencv-python 4.10.0.82` with NumPy 2.4.6.
  I did not change it. Running `pip install --upgrade "opencv-python>=4.10.0.84"`, or reinstalling the
  package with `pip install .`, fixes it; that is the maintainer's decision.

### 2026-09-29 09:44 CEST — [T10] Fix defects in the experiment flow
- **Status:** done
- **Changes:**
  - `nanofactorysystem/experiment.py`:
    - `opl_scan()` calls `Dhm.motorscan()` (the old `dhm.opl_scan()` does not exist).
    - `print_structure()` stops a failed task (`_stop_failed_task`) and continues; `layer_id`/`layer_count`
      are initialised, so an empty layer list does not raise.
    - `update_print_progress()` records the name of a structure without layers.
    - `_save_substrate_information()` merges into an existing file.
    - Found during T10: the experiment dictionary stored the hard-coded objective "Zeiss 20x" and took the
      log file from `handlers[1]`. It now stores `self.objective` and the path of the latest `FileHandler`
      (`_log_file()`).
  - `nanofactorysystem/aerobasic/ascii.py`: new `TaskFailedError(AerotechError, ValueError)`.
  - `nanofactorysystem/devices/aerotech/task.py`: `wait_to_finish()` raises `TaskFailedError` and closes its
    progress bar.
  - `test/test_experiment.py` (new, 6 tests): the whole flow, a failed layer, an empty structure, the OPL
    scan, the substrate merge and the experiment dictionary.
  - `test/backends/test_dummy_controller.py`: expects `TaskFailedError`.
  - `test/README.md`: row for `test_experiment.py`.
  - `TODO.md`: T10 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 134 passed, 14 skipped, 1 xfailed.
- **Commits:** `b1d19a2` fix(experiment): repair OPL scan, failed layers and experiment metadata [T10];
  `b0ed53e` test(experiment): cover the experiment flow on the dummy backend [T10]
- **Behaviour change on hardware (intended):**
  - After a failed layer, `PROGRAM 1 STOP` is sent before the next layer is loaded. Before, the exception
    ended the whole print.
  - `TaskFailedError` is still a `ValueError`, so existing handlers keep working.
- **Follow-ups:**
  - T25 (new): `mains/restart_experiment.py` passes the stored log *path* as `logger` to `Experiment`, which expects a
    logger object. The script is outside T10; noted here.
  - `default_exp_file.binary_testprint` accepts `substrate` but does not pass it to `Experiment`.

### 2026-09-29 09:46 CEST — [T21] Stop `Parameter` from mutating the caller's argument dictionaries
- **Status:** done
- **Changes:**
  - `nanofactorysystem/parameter.py`: `__init__` pops from a copy of the section.
  - `nanofactorysystem/devices/camera.py` (found during T21): `product`/`deviceID` were popped from the
    wrong dictionary and never reached `CameraDevice`. They are now read from a copy of the camera section.
  - `test/test_parameter.py` (new): two `System` objects from one `sys_args` dict. The test fails without
    the fix ("Maximum z position is missing!").
  - `test/devices/test_camera.py`: new test that `product`/`deviceID` reach `CameraDevice`.
  - `CLAUDE.md`, `test/README.md`, `test/conftest.py`, `test/backends/test_dummy_system.py`: the "build a
    fresh dict" caveat is removed.
  - `TODO.md`: T21 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 136 passed, 14 skipped, 1 xfailed.
- **Commits:** `4911149` fix(parameter): do not modify the caller's argument dictionaries [T21];
  `5af8e45` fix(devices): use the configured camera product and device ID [T21]
- **Behaviour change on hardware (intended):** a `camera={"product": ..., "deviceID": ...}` argument now
  selects that camera. No script in `mains/` passes these keys, so current lab runs are unaffected.
- **Follow-ups:** none.

### 2026-09-29 09:50 CEST — [T13] Add timeouts to hardware communication and wait loops
- **Status:** done
- **Changes:**
  - `nanofactorysystem/aerobasic/ascii.py`:
    - New `recv_line()` reads until the terminating character and raises `ConnectionError` on a closed
      connection.
    - `AerotechAsciiInterface(connect_timeout=10.0, response_timeout=None)`; a connect timeout is handled
      like a refused connection.
  - `nanofactorysystem/devices/a3200.py`:
    - New defaults `connectTimeout` (10 s), `responseTimeout` (None), `waitTimeout` (600 s) and
      `zlineTimeout` (600 s).
    - `run()` uses `recv_line` and sends `~LASTERROR` with its terminator.
    - `drivestatus(wait=True)` and `zline()` raise `TimeoutError` when the bound is exceeded.
  - `nanofactorysystem/devices/aerotech/task.py`: `wait_to_finish(stall_timeout=600)` fails only if the line
    number stops advancing; `finish(timeout=30)`. Both count the sleep intervals (virtual clock).
  - `nanofactorysystem/dhm/dhmclient.py`: `DhmClient(host, port, timeout=10.0)` applies the timeout to
    connect only; the image transfer detects a closed connection.
  - `nanofactorysystem/devices/dhm.py`: new default `connectTimeout`, passed to `DhmClient`.
  - `nanofactorysystem/backends/dummy/a3200.py`: records `settimeout()` calls in `timeouts`; new
    `chunk_size` option.
  - `test/backends/test_timeouts.py` (new, 12 tests); `test/backends/test_dummy_system.py` expects the DHM
    timeout; `test/README.md` gets a row.
  - `TODO.md`: T13 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 147 passed, 14 skipped, 1 xfailed.
- **Commits:** `1ee7ef0` fix(devices): bound connects and waits to avoid hangs [T13];
  `8d9d4dc` test(backends): cover timeouts and bounded waiting [T13]
- **Design decision:** responses keep **no** default limit. A motion command may legitimately block for
  minutes, so a default response timeout could abort a real print. The limit can be configured in the
  `controller` section (`responseTimeout`). The polling bounds (600 s) are generous for the same reason;
  `Task.wait_to_finish` measures stalling, not total duration.
- **Behaviour change on hardware (intended):**
  - Connects fail after 10 s.
  - `~LASTERROR` now ends with `\n`. Before, a failing command could block forever while the controller
    waited for the terminator.
  - Waiting for axes and the z-line program stop after 600 s.
  - A task that makes no progress for 600 s is reported as failed.
- **Follow-ups:** none. The values should be checked on the lab PC during the first hardware test run.

### 2026-09-29 09:54 CEST — [T14] Remove the hardcoded calibration path from `IFOV_Lines`
- **Status:** done
- **Changes:**
  - `nanofactorysystem/devices/power_calibration.py` (new):
    - `PowerCalibration` implements the fits previously in `IFOV_Lines` (2nd order polynomial or quadratic
      spline) and uses `reshape` instead of assigning `array.shape`.
    - `from_file`, `from_config`, `to_json`.
    - Context manager `power_calibration()`, plus the helpers `active_power_calibration()` and
      `resolve_power_calibration()`.
  - `nanofactorysystem/aerobasic/programs/drawings/lines.py`: `IFOV_Lines(calibration=None)`; the hardcoded
    `calibrationFile` class attribute and `_load_calibration_file()` are removed.
  - `nanofactorysystem/experiment.py`: `build_programs()` activates the calibration of
    `self.system.controller.attenuator` (the actual work moved to `_build_programs()`).
  - `test/test_aerobasic/test_power_calibration.py` (new, 8 tests).
  - `test/test_aerobasic/test_golden_programs.py`: activates a synthetic calibration instead of patching the
    class attribute.
  - `CLAUDE.md` (architecture) and `test/README.md` (new row).
  - `TODO.md`: T14 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 155 passed, 14 skipped, 1 xfailed. The golden files are unchanged: the IFOV
  programs are identical when the same calibration data is used. The NumPy deprecation warnings from
  `lines.py` are gone.
- **Commits:** `eb26199` refactor(drawings): take laser power calibration from outside [T14];
  `69547ba` test(aerobasic): cover the power calibration of IFOV structures [T14]
- **Behaviour on hardware:**
  - Inside an `Experiment`, IFOV powers are converted with the calibration data the attenuator loaded,
    that is `attenuator.calibrationFile` from `~/nanofactory.json`. On the lab PC this is the same file that
    was hardcoded before.
  - Outside an experiment, the configured file is used.
- **Follow-ups:**
  - `IFOV_Lines.to_json()` cannot serialise the `Point2D` objects in `lines`. This is pre-existing and not
    reached by the experiment flow (IFOV_Lines is only used inside other structures).
  - The `lines.py` half of T22 is done by this change.

### 2026-09-29 09:55 CEST — [T11] Fix small defects in `System` and the `A3200` controller
- **Status:** done
- **Changes:**
  - `nanofactorysystem/system.py`: `object_pos`/`camera_pos` use `self.controller`.
  - `nanofactorysystem/devices/a3200.py`: `home()` (`is None`); `container()` (`.items()`); `self.z` starts at
    `zInit`.
  - `nanofactorysystem/aerobasic/ascii.py`: `send_one()` calls `send()`.
  - `test/devices/test_aerotech.py`, `test/test_system.py`, `test/backends/test_dummy_controller.py`: 6 new
    dummy tests, one per fix (plus homing of a single axis).
  - `TODO.md`: T11 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 161 passed, 14 skipped, 1 xfailed.
- **Commits:** `6ef8d37` fix(devices): repair small defects in System and A3200 [T11];
  `b65b604` test: cover the System and A3200 fixes on the dummy backend [T11]
- **Behaviour change on hardware (intended):** `moveinc()` and `zline()` now check `zMax` against the initial
  z position if no absolute z move happened yet. Before, they raised `AttributeError` in that case.
- **Follow-ups / note for the maintainer:** `send_one()` is used nowhere. Its fallback re-sends a command
  that just failed, via the older `run_testzweck_altesSystem`, which could execute a motion command twice.
  I only removed the infinite recursion. Consider deleting both methods when T20 merges the controllers;
  the German method name is part of T18.

### 2026-09-29 09:56 CEST — [T22] Fix NumPy 2.5 deprecation in `Attenuator`
- **Status:** done
- **Changes:**
  - `nanofactorysystem/devices/attenuator.py`: `reshape` instead of assigning `array.shape`.
  - `nanofactorysystem/camera/camera.py` (found during T22): the same pattern in `CameraDevice.getimage()`.
  - The `lines.py:82` occurrence was already removed in T14 (`PowerCalibration` uses `reshape`).
  - `TODO.md`: T22 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest -W "error:Setting the shape:DeprecationWarning"`: 161 passed, 14 skipped,
  1 xfailed. The warnings dropped from 63 to 16. The real camera path (`camera.py`) is not covered by the
  dummy tests; the change is a mechanical `reshape` of a fresh copy.
- **Commits:** `daa757e` fix(devices): replace deprecated array shape assignment [T22]
- **Follow-ups:** none.

### 2026-09-29 09:57 CEST — [T16] Fix always-true `assert (path, Path)` in experiment scripts
- **Status:** done
- **Changes:**
  - `mains/**/*.py` (48 files, one line each): `assert (path, Path)` became `path = Path(path)  # accept str or
    Path`. A strict `isinstance` check would reject the strings that `mains/main.py` passes; the conversion
    keeps the following `os.path.join` working.
  - `TODO.md`: T16 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:**
  - Compiling every file in `mains/` reports no "assertion is always true" warning anymore.
  - `python -m pytest`: 161 passed, 14 skipped, 1 xfailed. This includes the dry run of `default_exp_file.py`,
    which passes a `Path`.
- **Commits:** `d1f1f67` fix(mains): convert path arguments instead of always-true asserts [T16]
- **Follow-ups:** `mains/debugging/test_plot.py` has a pre-existing `SyntaxError` (a parameter without default
  after a parameter with default). It is a debugging script, not collected by pytest; it is left for T19.

### 2026-09-29 09:59 CEST — [T17] Clean up logging
- **Status:** done
- **Changes:**
  - `nanofactorysystem/runtime.py`: `getLogger()` is idempotent. It keeps one console handler and at most one
    log file (a new file replaces the old one, the same file is not added twice). Its handlers are marked,
    so handlers added by others are left alone. The logger name `'dummy'` is kept for compatibility.
  - `nanofactorysystem/aerobasic/ascii.py`: `print()` replaced by `self.logger.error(...)`. The old fallback
    `run_testzweck_altesSystem` also sends `~LASTERROR` with its terminator and uses `recv_line` (same hang
    as fixed in T13).
  - `nanofactorysystem/devices/aerotech/task.py`: an incomplete program is logged as a warning instead of
    printed.
  - `test/test_runtime.py` (new, 4 tests); `test/README.md` gets a row.
  - `TODO.md`: T17 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 165 passed, 14 skipped, 1 xfailed.
- **Commits:** `2da7be2` fix(runtime): stop duplicating log handlers and printing errors [T17];
  `cdcee08` test(runtime): cover logger handlers and logged command errors [T17]
- **Behaviour change (intended):** when a second experiment in the same process calls
  `getLogger(logfile=...)`, the first experiment's log file no longer receives the second experiment's
  messages.
- **Follow-ups:** The logger is still called `'dummy'`, which can now be confused with the dummy backend.
  Renaming it (e.g. to `'nanofactorysystem'`) would change which loggers external scripts configure, so I
  left it for the maintainer.

### 2026-09-29 10:02 CEST — [T24] Fix `utils.visualization.plot_movements`
- **Status:** done
- **Changes:**
  - `nanofactorysystem/utils/visualization.py`:
    - Arcs return (n, 3) arrays.
    - The clockwise arc uses the correct center (start + I/J) and decreasing angles.
    - `plot_movements_fast` handles segments of different lengths, empty programs and zero-width axes, and
      adds only non-empty collections.
    - The reader parses `RAPID` and skips variables.
  - `test/test_utils/test_visualization.py` (new, 5 tests): arc geometry, reader, empty program, filled
    circle.
  - `test/test_aerobasic/test_program.py`: plotting errors fail the test again (the warning fallback from T15
    is removed).
  - `test/README.md`: new row; warning note removed.
  - `TODO.md`: T24 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:**
  - `python -m pytest`: 170 passed, 14 skipped, 1 xfailed, and only 1 warning in the whole suite.
  - No "Could not plot" warnings remain.
  - The rendered filled ring (`test/_programs/TestCircles/test_filled_ring.png`) was checked by eye: a correct
    ring.
- **Commits:** `da404d1` fix(utils): make movement plots work for all generated programs [T24];
  `e2df115` test(utils): assert that program movements can be plotted [T24]
- **Follow-ups:** `read_text` still skips linear moves that start at a zero coordinate (`(x + a) != 0 and ...`),
  which looks like a heuristic for the move from the origin. I left it unchanged.

### 2026-09-29 10:05 CEST — [T25] Fix argument passing in experiment scripts
- **Status:** done
- **Correction of the finding (T10):** `mains/restart_experiment.py` did **not** pass a path string as logger;
  its `load_experiment_parameter()` created a logger. The real problem was that the function is a
  placeholder: it returns hardcoded values and ignores the stored `experiment_dictionary.json`. The fix
  therefore addresses that.
- **Changes:**
  - `nanofactorysystem/experiment.py`: new `Experiment.parameters_from_dictionary(path)`. It rebuilds all
    constructor arguments from `experiment_dictionary.json`, parsing the `str()`-encoded vectors, and creates
    a logger for the stored log file.
  - `mains/restart_experiment.py`: `restart(path, backend=None)` uses the stored parameters and runs only as
    a script. The hardcoded placeholder values were removed; the maintainer's German notes are kept verbatim
    (T18/T19).
  - `mains/Experiments/default_exp_file.py`: `substrate` is passed to `Experiment` as
    `substrate_information`.
  - `test/test_experiment.py`: new restart test. An aborted print (after layer 2) is resumed through the
    script with the dummy backend; exactly the remaining layers are printed.
  - `test/integration/test_dry_run_default_experiment.py`: checks `substrate_information.json`.
  - `TODO.md`: T25 moved to In Progress, then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 171 passed, 14 skipped, 1 xfailed.
- **Commits:** `56e4d9a` feat(experiment): restart experiments from their stored parameters [T25];
  `412c763` test(experiment): cover restart and substrate information [T25]
- **Follow-ups (from the kept notes):** a restarted experiment gets a new UUID/QR text, and the maintainer
  suspects a wrong resume position after a second abort. The test covers one abort; both notes are listed for
  T19.

### 2026-09-29 13:24 CEST — [T23] Decide and implement axis validation for `SingleAxis`
- **Status:** done
- **Decision (maintainer, 2026-09-29):** mixing stages stays allowed; `~`, `^` and an empty `&` raise `AxisError`.
- **Changes:**
  - `nanofactorysystem/aerobasic/constants/axes.py`: `SingleAxis.__invert__`, `__xor__`/`__rxor__` raise
    `AxisError`; `__and__`/`__rand__` raise it when there is no common axis. No code in the package uses these
    operators on axes; `|` and membership tests are unchanged.
  - `test/test_aerobasic/test_constants.py`: the strict-xfail `test_prevent_mixed_axes` is replaced by
    `test_axis_combinations`, which asserts the decided behaviour.
  - `test/README.md`: description updated.
  - `TODO.md`: T23 moved to In Progress (with the decision), then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 172 passed, 14 skipped, no xfail left.
- **Commits:** `6d4009a` feat(aerobasic): reject invalid axis combinations [T23]
- **Follow-ups:** none.

### 2026-09-29 13:34 CEST — [T20] Merge `A3200` and `Aerotech3200` into one controller class
- **Status:** done
- **Decision (maintainer, 2026-09-29):** the zMax limit also guards Z moves sent through `.api`.
- **Changes:**
  - `test/backends/test_command_logs.py`, `test/golden/commands_*.txt` (new, committed **before** the
    refactor): golden command logs of System use and two complete experiments (DefaultSetup and SetupIFOV).
    They are unchanged after the merge.
  - `nanofactorysystem/aerobasic/ascii.py`:
    - `AerotechError` derives from `RuntimeError`.
    - New `z_limit` guard for immediate absolute Z moves; the mode is tracked from ABSOLUTE/INCREMENTAL.
    - A refused connect leaves no socket behind (`is_opened` was wrongly True).
  - `nanofactorysystem/devices/aerotech/__init__.py`: new base `AerotechController` (tasks, status, command
    log). `Aerotech3200` builds on it, keeps `version`/`home()` and gets an optional `z_max`.
  - `nanofactorysystem/devices/a3200.py`: `A3200(Parameter, AerotechController)`.
    - It connects via `AerotechAsciiInterface` and `run()` = `api.send()`.
    - `socket` is a read-only property; `z_limit` is set from `zMax`.
    - The helpers are unchanged.
  - `nanofactorysystem/system.py`: `a3200_new = controller`.
  - `test/backends/test_controller_merge.py` (new, 9 tests); `test/backends/test_dummy_system.py` patches
    `socket.socket` directly; `test/test_experiment.py` gets a `setup` parameter.
  - `CLAUDE.md` (architecture) and `test/README.md` (2 rows).
  - `TODO.md`: T20 moved to In Progress (with the decision), then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest`: 184 passed, 14 skipped. The 3 golden command logs match the pre-merge
  recording.
- **Commits:** `f49d935` test(backends): record golden controller command logs before the merge [T20];
  `fdb0719` refactor(aerobasic): derive AerotechError from RuntimeError [T20];
  `dcf80dc` refactor(devices): merge A3200 and Aerotech3200 into one controller [T20];
  `5f8e203` test(backends): cover the merged controller and document it [T20]
- **Behaviour changes on hardware:**
  - Immediate absolute Z moves above `zMax` through `.api` are refused before sending (decision).
  - `A3200.log` now contains all controller commands.
  - A command rejected as INVALID no longer triggers a `~LASTERROR` query. Failures are `AerotechError`,
    still a `RuntimeError`.
  - Successful flows send exactly the same commands (golden logs).
- **Follow-ups:**
  - `send_one`/`run_testzweck_altesSystem` (T11 note) are still in `AerotechAsciiInterface` and unused; they
    could be removed.
  - The deprecated `DummyAsciiInterface` could be removed as well.

### 2026-09-29 13:41 CEST — [T19] Identify each and every todo and note in all of the documents
- **Status:** done
- **Scope (maintainer, 2026-09-29):** remove work markers only (TODO/ToDo/FIXME/hotfix, including
  multi-line todo blocks and docstring lines). Explanatory notes stay; legacy code (`old_to-delete/`,
  `drawings/new/`, `*_old*.py`, `OLD_*.py`) is untouched.
- **Changes:**
  - `todo_notes.md` (new):
    - 95 inventory entries: 94 distinct marker texts from 535 occurrences in 78 files, plus the slicer
      roadmap. Each has the original text, its English meaning, all `file:line` locations and a work package.
    - 15 work packages T26–T40 in `TODO.md` format.
  - 78 code files in `nanofactorysystem/`, `mains/`, `test/`: markers removed with a tokenizer-based script.
    Whole comment lines are removed with their continuation lines. After code or inside commented-out code
    only the marker comment is cut. Docstring lines are removed, keeping any text before the marker.
  - `nanofactorysystem/aerobasic/slicer/TODO.txt` (deleted): its roadmap is entry N095 / T40.
  - `nanofactorysystem/aerobasic/programs/zline.py`: the class docstring, which was only a marker, now
    describes the class.
  - `TODO.md`: T19 moved to In Progress (with the scope decision), then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:**
  - A rescan finds 0 markers.
  - Every changed file still parses; the only syntax error in `mains/` is the pre-existing one in
    `mains/debugging/test_plot.py`.
  - `python -m pytest`: 184 passed, 14 skipped.
- **Commits:** `b2d2f05` docs(todo): inventory all work markers in todo_notes.md [T19];
  `5f8af15` chore: remove work markers from the code [T19]
- **Notes:**
  - The phrase "to do" in ordinary English ("Nothing to do for empty set") is not a marker and was kept.
  - Commented-out asserts that belonged to "ToDo: Make sure center is within the edges" were removed with it
    and are recorded in N022.
  - `nanofactorysystem/aerobasic/slicer/tree_overview_slicer.txt` still lists `TODO.txt`. It describes the
    layout of the original tpp_slicer project, so I left it unchanged.
- **Follow-ups:** the work packages T26–T40 are in `todo_notes.md`; move them to `TODO.md` to schedule them.

### 2026-09-29 13:46 CEST — [T18] Translate German identifiers and comments
- **Status:** done
- **Scope:** package modules in `nanofactorysystem/` and `test/`. Excluded: legacy code; the experiment scripts
  in `mains/` (scripts, not modules); the manual scripts in `test/manual/`. Work markers had already been
  removed in T19.
- **Changes (one module per commit):**
  - `nanofactorysystem/aerobasic/ascii.py`: identifier `run_testzweck_altesSystem` renamed to
    `send_with_simple_protocol` (only used in `send_one()`).
  - Comments and docstrings translated in:
    - `nanofactorysystem/aerobasic/programs/drawings/`: `__init__.py`, `base.py`, `calc_polygons.py`,
      `height_function_structures/structures.py`, `height_function_structures_fixed.py` (this also fixes
      mis-encoded umlauts), `hollow_structure.py` (also the plot title and a stale docstring argument
      `liste`), `ifov_gratings.py`, `lens.py`, `lines.py`, `test/test_factor_matrix.py`;
    - `nanofactorysystem/aerobasic/programs/setups.py`;
    - `nanofactorysystem/devices/aerotech/task.py`;
    - `nanofactorysystem/experiment.py`;
    - `test/slicer/model3d_checks.py`.
  - `TODO.md`: T18 moved to In Progress (with the scope), then to Done.
  - `WORKLOG.md`: this entry.
- **Tests:**
  - Three detection passes over all comments, docstrings and identifiers (German function words, suffixes,
    umlauts), reviewed by hand. The last pass finds only false positives such as the unit "um" and the
    license header.
  - `python -m pytest`: 184 passed, 14 skipped.
- **Commits:** `118a095` refactor(aerobasic): rename German method run_testzweck_altesSystem [T18];
  `1d39956`, `239ed54`, `fdfea3a`, `a705542`, `121d2f6`, `e0714bd`, `317f5a9`, `9a56aac`, `5b93e4e`, `179e504`,
  `50e6a64`, `1c0e1ca`, `882011d`, `7d973e9` docs(...): translate German comments in <module> [T18]
- **Follow-ups:** German comments remain in the experiment scripts (`mains/`) and in `test/manual/`. Those are
  lab scripts; translating them can be scheduled together with T26 (parameterise the experiment scripts).


### 2026-09-29 20:28 CEST — [T41] Audit the experiment metadata
- **Status:** done
- **Branch:** `docs/t41-metadata-audit` (new, from `main_HR` at `d2dbd66`)
- **Changes:**
  - `docs/reviews/METADATA_AUDIT.md` (new): every file an experiment writes (method, time, content,
    location), the content of the JSON files and `.zdc` containers, a rating of each metadata item
    (complete / incomplete / wrong / missing, with the todo that covers it), and the input for T42.
  - `TODO.md`:
    - T41 moved to Done.
    - New todos "(found during T41)": T55 (command log into the experiment), T56 (reversible structure
      serialisation), T57 (relative paths), T58 (defined capture position, phase 1), T59 (print-progress
      counts and timestamps), T60 (experiment plots, phase B). The phase table lists them.
  - `WORKLOG.md`: this entry.
- **Tests:** no code changed, so the suite was not run. Two dummy dry runs of
  `default_exp_file.binary_testprint` were run with a scratch script outside the repository:
  - A: the template as it is (20x, IFOV off, no DHM);
  - B: 63x, IFOV on, DHM on, plus one `Stair` structure.
  Both finished. Their files are the basis of the ratings.
- **Commits:** `bf5565a` docs(reviews): audit the experiment metadata [T41];
  `3754290` docs(todo): close T41 and add its follow-up todos [T41]
- **Notes:**
  - The global Python still fails on the OpenCV/NumPy mismatch (T9 note). I used the venv from an earlier
    session with `PYTHONPATH` set to the repository.
  - `TZ=Europe/Berlin date` in Git Bash prints GMT here (no time-zone data). The timestamp of this entry
    comes from Windows (`W. Europe Standard Time`).
  - `.claude/settings.local.json` (gitignored, not committed): `Bash` added to the allowed tools, as the
    maintainer requested.
- **Follow-ups:** T42 (design of the experiment storage) is next. It ends at a maintainer approval gate.

### 2026-09-29 20:31 CEST — [T42] Design the experiment storage and substrate model
- **Status:** blocked (draft written; waiting for maintainer approval)
- **Changes:**
  - `docs/design/EXPERIMENT_STORAGE.md` (new): the design draft. It covers:
    - hierarchy, folder layout below `~/Documents/Femtika_Experiment/<user>/`, explicit `path` override
      and the check against synchronised folders;
    - IDs: substrate label `<initials>-<yy>-<nnn>`, substrate UUID, experiment label `<substrate>-A`,
      experiment UUID = QR text;
    - the HDF5 schema (metadata, calibration, plane fit, OPL scan, layout with corners and the double
      corner, structures with layer programs, progress and captures, DHM products, slicer outputs,
      summary, logs), with `schema_version`;
    - write strategy (open/write/close per event, state after a crash, recovery, lock file, one writing
      process);
    - the JSON copies, the substrate record and experiment search, the legacy reader and restart of old
      folders, the summary content, and an API sketch (`ExperimentStore`, `SubstrateStore`) mapped to
      every `Experiment` method named in T42.
  - `TODO.md`: T42 moved to In Progress, then to Blocked ("waiting for maintainer approval").
  - `WORKLOG.md`: this entry.
- **Tests:** none; this is a design document only.
- **Commits:** `ef2ff63` docs(design): draft the experiment storage and substrate model [T42];
  the TODO/WORKLOG commit docs(todo): block T42 on maintainer approval [T42]
- **Open decisions (§12 of the document):**
  - D1: default root, and a hard error for synced folders;
  - D2: label scheme and counter reset;
  - D3: folder name;
  - D4: copy or link slicer outputs;
  - D5: which power counts as authoritative;
  - D6: stop writing `.zdc` files;
  - D7: importing old folders on restart;
  - D8: console log inside the file.
- **Follow-ups:** T47–T50 start after the approval. Phase 1 (T43–T46, T58) can proceed meanwhile.

### 2026-09-29 23:04 CEST — [T42] Design the experiment storage and substrate model (approval)
- **Status:** done
- **Decision (maintainer, 2026-09-29):** "approve your suggestions at t42". The design is approved, and all
  proposals D1–D8 in §12 are accepted as written:
  - D1: a synced root is a hard error;
  - D2: the substrate counter restarts each year;
  - D3: the folder name is the label plus the start time;
  - D4: slicer jobs are copied into the file;
  - D5: the written power is authoritative;
  - D6: no more `.zdc` files;
  - D7: old folders are imported on restart;
  - D8: the console log is copied into the file.
- **Changes:**
  - `docs/design/EXPERIMENT_STORAGE.md`:
    - status line `Status: approved 2026-09-29`; §12 and §14 record the accepted decisions;
    - the approval was given in the session, and I wrote it into the document on the maintainer's
      instruction.
  - `TODO.md`: T42 moved from Blocked to Done.
  - `WORKLOG.md`: this entry and the phase 0 summary below.
- **Tests:** see the phase summary.
- **Commits:** `3f75e0a` docs(design): record the approval of the experiment storage design [T42];
  the TODO/WORKLOG commit docs(todo): close T42 and summarise phase 0 [Phase 0]
- **Follow-ups:** T47–T50 may start; they depend on T42 (done) and the phase order.

### 2026-09-29 23:04 CEST — [Phase 0] Phase summary
- **Finished todos:**
  - T41: metadata audit, `docs/reviews/METADATA_AUDIT.md`;
  - T42: storage design, `docs/design/EXPERIMENT_STORAGE.md`, approved 2026-09-29.
- **New todos from phase 0 (found during T41):**
  - T55: command log into the experiment;
  - T56: reversible structure serialisation;
  - T57: relative paths;
  - T58: defined capture position (phase 1);
  - T59: print-progress counts and timestamps;
  - T60: experiment plots (phase B).
- **Tests:** `python -m pytest` in a fresh venv (`pip install ".[test]"`), including the dry run in
  `test/integration/`: 184 passed, 14 skipped.
  - The one warning is `plt.show()` under the Agg backend in the dry run of the template. It is harmless.
  - Environment note: a venv inside the Claude scratchpad folder fails `test_model3d_checks`. The error is
    "DLL load failed … Der Dateiname oder die Erweiterung ist zu lang": the shapely DLL path exceeds the
    Windows 260-character limit. A venv at a short path (`%LOCALAPPDATA%\Temp\nfsv`) passes, so this is not
    a code defect.
- **Open follow-ups:** T58 is added to phase 1. T55–T57 and T59 are added to phase 2 and follow the approved
  design.
- **To check on the lab PC:** nothing yet; phase 0 changed documentation only.
  - Before T48 is implemented, confirm that `~/Documents` on the lab PC is not inside a Seafile library.
    If it is, set a `dataRoot` for each user.
- **Next:** phase 1, starting with T43 (drop direction). T43 contains the decision "merge `Orientation`
  into `DropDirection` or map one to the other".

### 2026-09-29 23:19 CEST — [T46] Record the stage position of every capture
- **Status:** done
- **Branch:** `feat/phase1-capture-positions`, based on `docs/t41-metadata-audit`
- **Changes:**
  - `nanofactorysystem/storage/__init__.py` (new): the storage package of the approved design. T47 adds the
    store to it.
  - `nanofactorysystem/storage/records.py` (new):
    - `CaptureRecord` (kind, structure, phase, layer id, image index, image count, offset, commanded
      X/Y/Z, actual X/Y/Z/A/B, UTC time, relative file);
    - `utc_timestamp()`.
  - `nanofactorysystem/experiment.py`:
    - `measure()` has new keyword arguments `structure`, `phase`, `layer_id` and `offsets_um`.
    - The actual position is read after every move. It is passed to the camera container, as
      `System.getimage()` did before, and now also to the DHM container (`data/location.json`).
    - Each capture record is written to the container (`data/capture.json`) and appended to
      `captures.json` in the experiment folder.
    - `print_structure()` passes structure, phase and layer id.
    - Return value: one `(dhm, camera)` tuple per position; the old version returned one tuple. The only
      callers are in `print_structure()`, which ignores the return value; the calls in `mains/` are
      commented out.
  - `test/test_experiment.py`: two tests. One takes two capture positions with DHM on and checks commanded
    and actual positions, the records inside the containers and the file names. The other checks the
    before/layer/after records of a printed structure.
  - `test/README.md`: `test_experiment.py` row.
  - `TODO.md`: T46 moved to In Progress, then to Done.
- **Tests:** `python -m pytest` (short-path venv): 186 passed, 14 skipped. The golden command logs
  (`test_command_logs.py`) are unchanged: without DHM the controller receives exactly the same commands.
- **Commits:** `c16f5ae` feat(experiment): record the stage position of every capture [T46];
  docs(todo): close T46 [T46]
- **Behaviour change on hardware:** with DHM on, the stage position is read before the DHM capture instead of
  just before the camera capture. It is the same number of queries, in a different order.
- **Follow-ups:**
  - The commanded Z is None because `measure()` does not move Z; T58 defines it.
  - `captures.json` is the interim storage until T47 moves the records into `experiment.h5`.

### 2026-09-30 08:34 CEST — [T47] Implement the HDF5 experiment store
- **Status:** done
- **Branch:** `feat/phase2-experiment-store`, based on `feat/phase1-capture-positions`
- **Changes:**
  - `nanofactorysystem/aerobasic/slicer/storage.py`: new `write_job()`, which writes the unchanged `job.h5`
    schema into an open group. `save_job()` uses it.
  - `nanofactorysystem/storage/` (package from T46, extended):
    - `experiment_store.py` (new): `ExperimentStore` with `create`/`open`/`exists`, sessions with a lock,
      and the write methods of design §11. Read methods: `read`, `read_uuid`, `has_structure`,
      `read_capture`, `read_dhm_product`, `read_program`, `plane_fit_container`. Export: `export_capture`
      writes a `.zdc` file on request. Every write opens and closes the file.
    - `records.py`: `StructureRecord`, `PlaneFitRecord`, `CornerRecord`, `LayoutRecord`, `ExperimentRecord`,
      `z_function_to_json`/`z_function_from_json`; `CaptureRecord` gets a `capture_id`.
    - `schema.py` (new): file type, `SCHEMA_VERSION = "1.0"`, status values, and the mapping of constructor
      argument → JSON key → HDF5 attribute.
    - `json_copies.py` (new): `experiment_dictionary.json` and `structures.json` built from the record. The
      old keys stay; vectors are numbers now.
    - `locking.py` (new): lock file with host, PID and start time. On Windows the PID check uses
      `OpenProcess`, because `os.kill(pid, 0)` would terminate the process there.
    - `software.py` (new): package version, git commit/branch/dirty state, library versions.
  - `nanofactorysystem/experiment.py`:
    - The constructor creates or opens `experiment.h5`. Each `Experiment` is one session;
      `__exit__` records how it ended and sets the status to `failed` or `aborted` after an exception.
    - New keyword `resume`. Without it, an existing experiment file is refused. With it, the stored
      experiment continues with its UUID; `parameters_from_dictionary()` sets it, and reads vectors as
      numbers or old strings.
    - `plot_experiment`, `plane_fit` (given, loaded, measured, incl. the `.zdc` containers),
      `opl_scan`, `_build_programs`, `print_structure` (status, per-layer progress with start/end time)
      and `print_experiment`/`restart_experiment` (final status) write through the store.
    - `measure()` stores the images and holograms in the file and no longer writes `.zdc` files.
      Its signature is `measure(coordinate, *, structure, phase, layer_id, dhm_image_count, offsets_um)`.
      Structures printed or measured without `build_programs()` are registered as type `DIRECT`.
    - `calibration_file.npy`, `_create_experiment_dictionary` and `captures.json` (from T46) were removed.
  - `test/storage/test_experiment_store.py` (new): 11 unit tests.
  - `test/test_experiment.py`: the capture tests read from the store. New tests: an exception during
    printing leaves a readable file with status `failed`; an existing folder is refused; a restart keeps
    the file and the UUID.
  - `test/integration/test_dry_run_default_experiment.py`:
    - it checks `experiment.h5`, and that the JSON copies equal what is exported from the file;
    - it checks the camera captures inside the file instead of `calibration_file.npy` and `.zdc` files.
    Justification: design D6, approved 2026-09-29. No assertion was weakened; the file checks were
    replaced by stronger content checks.
  - `test/README.md`, `CLAUDE.md`: the storage package and the changed tests.
  - `TODO.md`: T47 moved to Done.
- **Tests:** `python -m pytest` (short-path venv): 199 passed, 14 skipped. Golden programs and golden command
  logs are unchanged.
  - The suite takes about 80 s instead of about 40 s. The two DHM-on command-log experiments and the dry run
    are already marked `slow`.
  - Profiling shows file opens of about 6 ms (plain) and 14 ms (HDF5) on this PC, probably on-access virus
    scanning of the temp folder, plus about 45 ms of gzip per camera image.
  - On the lab PC this adds roughly 0.1 s per layer.
- **Commits:** `bc371eb` refactor(slicer): write a job into an open HDF5 group [T47];
  `fe6036a` feat(storage): add the HDF5 experiment store [T47];
  `bed280b` feat(experiment): write all experiment data through the store [T47];
  docs(todo): close T47 [T47]
- **Deviations from the design:**
  - A stale lock (same host, process no longer running) is replaced with a warning, instead of requiring
    `force=True`. A restart after a crash must not need a manual step, and a dead process cannot be
    writing.
  - The layer program files stay in `structures/<name>/programs/`; the design's `programs/` layout comes
    with the folder layout in T48.
  - `print_progress.json` is still written, because the restart logic reads it (T50, T59).
- **Behaviour changes on hardware:**
  - No `.zdc` files for captures and no `calibration_file.npy`; everything is in `experiment.h5`.
  - Running a script twice into the same folder now fails with `FileExistsError`. Before, it overwrote the
    earlier data.
  - The restart script continues the stored experiment and keeps its UUID (part of N027/T50).
- **Follow-ups:**
  - T55 (`/logs/a3200`), T57 (relative paths), T49 (`/summary`) and T48 (folder layout, substrates) build
    on this.
  - Suggestion: faster tests with a lower gzip level for dummy images. Not done; the design fixes level 4.

### 2026-09-30 08:38 CEST — [T55] Store the controller command log with the experiment
- **Status:** done
- **Changes:**
  - `nanofactorysystem/devices/aerotech/__init__.py`: `command_log()` returns the log text; `save_log()` uses it.
  - `nanofactorysystem/system.py`: new attribute `log_dir`, the folder for `A3200.log` on `close()`.
    The default is unchanged: the backend's program folder, else the working directory.
  - `nanofactorysystem/storage/experiment_store.py`: `write_log(kind, text)` and `read_logs(kind)` for
    `/logs/<kind>/<session>`.
  - `nanofactorysystem/experiment.py`:
    - `System.log_dir` is set to the experiment folder.
    - `__exit__` closes the system first and then calls `_end_session()`. That method stores the command
      log and the console-log text written since the experiment started (offset remembered in
      `__init__`, design D8), sets `failed`/`aborted` after an exception, ends the session and exports the
      JSON copies. It runs in a `finally`, so an aborted run keeps its logs.
  - `test/test_experiment.py`: two tests (two experiments in a row with separate logs; a
    KeyboardInterrupt keeps the log and sets `aborted`).
  - `test/README.md`, `CLAUDE.md`: logs in the experiment.
  - `TODO.md`: T55 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 201 passed, 14 skipped.
- **Commits:** `b624a66` feat(experiment): store command and console logs with the experiment [T55];
  docs(todo): close T55 [T55]
- **Behaviour change on hardware:**
  - `A3200.log` of an experiment is now in the experiment folder, not in `mains/`.
  - `/logs/console` also covers D8 of the approved design.
- **Follow-ups:** none.

### 2026-09-30 08:42 CEST — [T57] Store paths relative to the experiment folder
- **Status:** done
- **Changes:**
  - `nanofactorysystem/experiment.py`:
    - `_relative()` and `_absolute()` convert paths to and from the experiment folder.
    - The log file, layer files, structure program and layer-program `file` attributes are stored
      relative to the folder.
    - `structure_configs` in memory stays absolute (`_with_absolute_paths()`, also used by
      `retrieve_programs()`), so callers see no change. Print and restart resolve the stored paths.
    - `parameters_from_dictionary()` uses the given folder and finds the log file there by name.
  - `nanofactorysystem/storage/json_copies.py`: `"path"` is `"."` in `experiment_dictionary.json`.
  - `test/test_experiment.py`: a new test builds an experiment, moves its folder and restarts it from the
    new place. `test_experiment_dictionary` and the restart test now expect relative paths; these asserts
    changed because T57 requires relative paths.
  - `test/integration/test_dry_run_default_experiment.py`: the paths in `structures.json` are relative
    and resolve to existing files.
  - `test/README.md`, `CLAUDE.md`.
  - `TODO.md`: T57 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 202 passed, 14 skipped.
- **Commits:** `e07db5a` feat(experiment): store paths relative to the experiment folder [T57];
  docs(todo): close T57 [T57]
- **Follow-ups:** A folder written before T57 still holds absolute paths. They are used as they are, so
  a legacy folder can only be restarted in its original place. T50 imports legacy folders and can
  relocate those paths.

### 2026-09-30 08:55 CEST — [T48] Substrate model, default location and experiment index
- **Status:** done
- **Changes:**
  - `nanofactorysystem/storage/substrate_store.py` (new):
    - `SubstrateRecord` (label, UUID, created, user, material, resin drops, notes, experiments, extra);
    - `SubstrateStore`: `create` (label proposed per user and year, D2), `get` by label or UUID,
      `add_resin_drop`, `next_experiment_label`, `experiment_folder` (D3), `register_experiment` and
      `update_experiment` (lock file plus atomic write), `import_legacy` for old
      `substrate_information.json` files;
    - `find_experiments` (by substrate, objective, date range, status);
    - `default_root` (`dataRoot` of the user, else `~/Documents/Femtika_Experiment/<user>`) and
      `check_not_synced` (D1: hard error for Seafile/OneDrive/Dropbox; names configurable as
      `system.syncFolderNames`).
  - `nanofactorysystem/experiment.py`:
    - new keyword arguments `substrate`, `data_root`, `allow_synced_root`.
    - `path=None` creates the next experiment folder of the substrate and adds `console.log` there.
    - The experiment is registered in the substrate index once; the status is copied into the index at
      the end of every session.
    - The experiment file holds the experiment label, the substrate UUID/label and a copy of the substrate
      record.
    - `_save_substrate_information` (merge into the parent folder) is removed; the free dictionary is stored
      as `/metadata/substrate/information`.
    - `parameters_from_dictionary()` passes substrate and data root for experiments in a substrate folder.
  - `nanofactorysystem/storage/experiment_store.py`: `/metadata/substrate`, `read_identification()`,
    `read_status()`. `records.py`: `ExperimentRecord.substrate`. `json_copies.py`: `substrate` key.
  - Tests:
    - `test/storage/test_substrate_store.py` (new): 9 tests.
    - `test/test_experiment.py`: two experiments on one substrate (the same experiment printed twice);
      the index after an abort and a restart; path or substrate needed.
    - `test_substrate_information_is_merged` is replaced by
      `test_substrate_information_is_stored_in_the_experiment`, because T48 replaces the merge logic.
    - The dry run checks the substrate information in the file instead of `substrate_information.json`.
  - `test/README.md`, `CLAUDE.md`.
  - `TODO.md`: T48 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 214 passed, 14 skipped.
- **Commits:** `1014892` feat(storage): add substrate records and the experiment index [T48];
  `cf5ed05` feat(experiment): place experiments on substrates in the default location [T48];
  docs(todo): close T48 [T48]
- **Deviations from the design:**
  - `substrate.json` has an additional `extra` field for keys without a fixed field (old dictionaries).
  - Material fields are free-form.
  - The experiment template (`default_exp_file.py`) still uses an explicit `path`; T51/T52 move the scripts to
    substrates.
- **Behaviour change on hardware:** `substrate_information.json` is no longer written into the parent folder.
- **To check on the lab PC:** `~/Documents` must not be inside a Seafile library, otherwise set `dataRoot` per
  user.

### 2026-09-30 13:17 CEST — [T49] Experiment summary
- **Status:** done
- **Changes:**
  - `nanofactorysystem/storage/summary.py` (new):
    - `summary(record)`: experiment fields plus one row per user structure; corners and the QR code are
      excluded.
    - `print_parameters(structure)`: slice, hatch, velocity and power are taken from the stored constructor
      arguments, using the first of the known names. D5 applies: IFOV structures report their own power.
    - `format_table()` formats the summary for the log.
  - `nanofactorysystem/storage/experiment_store.py`: `write_summary`, `read_summary` (`/summary`).
  - `nanofactorysystem/experiment.py`: `_write_summary()` after `build_programs()` and after every structure,
    also written as `experiment_summary.json`; the table is logged after building and at the end of printing
    or a restart; `log_summary()`.
  - Tests:
    - `test/storage/test_summary.py` (new, 2 tests);
    - `test/test_experiment.py`: summary of two printed structures; `make_experiment` gets a `grid`
      parameter;
    - dry run: the summary exists, equals the file, and has no user rows, because the template adds no
      user structure.
  - `test/README.md`, `CLAUDE.md`.
  - `TODO.md`: T49 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 217 passed, 14 skipped; the dry run passes with the summary check.
- **Commits:** `92b9bcc` feat(experiment): write an experiment summary [T49]; docs(todo): close T49 [T49]
- **Notes:**
  - The template experiment of the todo text has no user structures (the stair is commented out), so the
    rows are checked with a small experiment of two structures instead.
  - The velocity unit is `um/s`, or `mm/s` for IFOV classes (T35, N065). A velocity above 500 passed to
    `IFOV_Lines` is divided by 1000 internally; the summary shows the value as passed.
  - Camera usage is always "yes" until T45 adds the switch.
- **Follow-ups:** none new.

### 2026-09-30 13:29 CEST — [T50] Restart and repetitions on the new storage
- **Status:** done
- **Changes:**
  - `nanofactorysystem/experiment.py`:
    - `restart_experiment()` reads the progress events from the experiment file. It skips finished
      structures and every layer with an event from an earlier session; never-started structures get their
      "before" capture. The final status and summary are written.
    - `parameters_from_dictionary()` reads `experiment.h5` (`_parameters_from_file`), else the JSON.
    - A `resume` of a folder without `experiment.h5` imports it (`_import_legacy`, session kind `imported`).
    - `add_structure()` has a NumPy docstring, a fixed `REPEAT` (names `<name>_rep<n>`, grid check,
      `repeat_of`), and the duplicate-name check now runs after the type branch, so repeats are covered.
  - `nanofactorysystem/storage/legacy.py` (new): `read_legacy`, `is_legacy_folder`. The UUID comes from the
    QR-code structure or the log. Paths are relocated into the folder. Structure types are guessed from the
    names. Progress comes from `print_progress.json`.
  - `nanofactorysystem/storage/records.py` and `experiment_store.py`: `StructureRecord.repeat_of`.
  - `mains/restart_experiment.py`: docstring.
  - `test/test_experiment.py`:
    - new helper `abort_after()` makes the controller fail after n layers;
    - the restart tests and the moved-folder test abort for real instead of writing a fake
      `print_progress.json`, because the restart no longer reads that file;
    - new tests: restart after two aborts (every layer printed exactly once), import of an old JSON-only
      folder with absolute lab paths, repeated structures at their own grid cells.
  - `test/README.md`, `CLAUDE.md`.
  - `TODO.md`: T50 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 220 passed, 14 skipped.
- **Commits:** `7aaee04` feat(experiment): restart and repetitions on the experiment file [T50];
  docs(todo): close T50 [T50]
- **Notes:**
  - A layer interrupted by an abort has no progress event and is printed again on restart. A layer that
    failed with an `AerotechError` has a `failed` event and is not printed again; this is the behaviour of
    the old restart logic.
  - In imported old folders, the layers listed in `print_progress.json` count as printed.
  - The double-corner position and orientation are stored in `/layout` since T47 (for F1).
- **Behaviour change on hardware:** `REPEAT` works now; it failed before with a TypeError. The restart script
  continues the stored experiment, and a second abort no longer shifts the resume point.

### 2026-09-30 13:44 CEST — [T59] Correct the print-progress record
- **Status:** done
- **Changes:**
  - `nanofactorysystem/storage/json_copies.py`: `print_progress()` and `export_progress()`. The schema
    `nanofactory.print_progress/2` is documented in the docstring; `export_json()` writes the file as well.
  - `nanofactorysystem/storage/experiment_store.py`:
    - `set_structure_status()` records `started` (first time only) and `ended`;
    - `read(include_captures=False)` skips capture metadata for the exports, so they don't grow with every
      layer.
  - `nanofactorysystem/storage/records.py`: `StructureRecord.started` and `ended`.
  - `nanofactorysystem/storage/legacy.py`: also reads the new schema.
  - `nanofactorysystem/experiment.py`:
    - `update_print_progress()` is removed;
    - `print_progress.json` is exported after every layer and structure;
    - the loop variable `layer_count` (an index) is renamed `index`.
  - Tests:
    - the old progress keys are replaced by the new schema in the existing asserts. Each check still
      tests the same behaviour: layers printed, a failed layer with its error, an empty structure, a
      restart;
    - new parametrised test for UP and DOWN after a complete and an aborted structure;
    - the legacy-import test writes an old-format `print_progress.json` itself;
    - one store unit test expects the new end time.
  - `test/README.md` (and a follow-up commit that fixes escaped backticks), `CLAUDE.md`.
  - `TODO.md`: T59 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: all pass (221 passed plus the fixed store test; storage tests 22 passed).
- **Commits:** `154d85d` feat(experiment): export print_progress.json from the experiment file [T59];
  `0356fc2` docs(test): fix escaped backticks in the README [T59]; docs(todo): close T59 [T59]
- **Behaviour change:** `print_progress.json` has a new format. It is a readable copy; restart uses the
  experiment file.

### 2026-09-30 13:51 CEST — [T56] Make structure serialisation complete and reversible
- **Status:** done
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/drawings/base.py`:
    - `_init_args()`/`to_json()` use `inspect.signature` and the new class attributes `_json_attributes`
      (parameter → attribute) and `_json_skip` (`data`, `height_profile`, N046).
    - A lost parameter gives a warning and a `__missing__` entry.
    - New functions: `encode_json_value`, `decode_json_value`, `structure_from_json`.
    - `to_json()` adds `__module__`.
    - Two commented-out former versions of `_init_args` were removed (dead code inside the rewritten
      function).
  - `ifov_gratings.py`: `Rectangle2D_IFOV._json_attributes = {"angle": "phi"}`.
  - `devices/power_calibration.py`: `PowerCalibration.from_json()`.
  - `test/test_aerobasic/test_structure_json.py` (new, 10 tests): the 8 golden-test structure classes
    round-trip and render identical programs; value encoding; reporting of lost arguments.
  - `test/test_aerobasic/test_power_calibration.py`: the calibration inside `IFOV_Lines.to_json()` is now
    encoded with its class. The old assert (raw `calibration.to_json()`) is replaced by the new encoding
    plus a check that the rebuilt structure sets the same power. This assert changed because T56 requires
    a reversible encoding.
  - `test/README.md`, `CLAUDE.md`.
  - `TODO.md`: T56 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 232 passed, 14 skipped. The golden files are unchanged.
- **Commits:** `1f379ae` feat(drawings): make structure serialisation complete and reversible [T56];
  docs(todo): close T56 [T56]
- **Notes:**
  - `structures.json` and `/structures/<name>` configs now contain `__module__` and the new enum/object
    encoding.
  - Structure classes outside the golden tests are not checked one by one; if they lose a parameter, they
    warn at `build_programs()`. No such warning appears in the test suite or the dry run.

### 2026-09-30 13:51 CEST — [Phase 2] Phase summary
- **Finished todos:**
  - T47: HDF5 experiment store;
  - T48: substrates, default location, experiment index;
  - T49: summary;
  - T50: restart and repetitions;
  - T55: command log in the experiment;
  - T56: reversible structure serialisation;
  - T57: relative paths;
  - T59: print progress.
  - Also T46 (phase 1), which the store builds on.
- **Branches:**
  - `feat/phase1-capture-positions` (T46, based on `docs/t41-metadata-audit`);
  - `feat/phase2-experiment-store` (T47–T59, based on the phase 1 branch).
  - Nothing is pushed.
- **Tests:** `python -m pytest` (fresh short-path venv): 232 passed, 14 skipped, including the dry run in
  `test/integration/`. Golden programs and golden command logs are unchanged.
  - The suite takes about 105 s now (about 40 s before phase 2): about 15–50 ms per HDF5 write on this PC.
- **Open follow-ups:**
  - T45 (camera switch): the summary shows `camera = yes` until then.
  - T58 (capture Z): the commanded Z is None until then.
  - T51/T52: move the experiment scripts to substrates and the default location. `default_exp_file.py`
    still uses an explicit `path`.
- **To check on the lab PC:**
  1. `~/Documents` must not be inside a Seafile library; otherwise set `dataRoot` for each user in
     `nanofactory.json`.
  2. A dry run of a real script with `backend=None`: `experiment.h5` is written next to the JSON copies,
     `A3200.log` is in the experiment folder, and there are no `.zdc`/`.npy` files.
  3. Restart an interrupted print with `mains/restart_experiment.py`, also a second time.
  4. An old experiment folder (JSON only) can be restarted; it is imported into `experiment.h5`.
  5. `StructureType.REPEAT` works. It failed before with a TypeError.
  6. Disk usage: roughly 0.3–0.6 MB per camera image and about 10× more per hologram series. Check the free
     space on the lab PC for large experiments.

### 2026-09-30 13:52 CEST — [T53] Voxel database (design part)
- **Status:** blocked (design draft written; waiting for maintainer approval)
- **Branch:** `docs/phase4-voxel-database`, based on `feat/phase2-experiment-store`
- **Changes:**
  - `docs/design/VOXEL_DATABASE.md` (new). It covers:
    - terms and units;
    - SQLite schema v1 with `PRAGMA user_version` and migrations;
    - lookup: exact hit, 2-D interpolation in (ln P, ln v) inside the convex hull, 1-D dose fallback for
      collinear data, no extrapolation;
    - the CSV seed, import and export;
    - the location of the database;
    - the `VoxelDatabase` API, the tests and the link to T54.
  - `TODO.md`: T53 moved to In Progress, then to Blocked ("waiting for maintainer approval").
  - `WORKLOG.md`: this entry.
- **Tests:** none (design document).
- **Commits:** `b45a7d2` docs(design): draft the voxel database [T53]; docs(todo): block T53 on approval [T53]
- **Open decisions (§9):**
  - V1: interpolation variable;
  - V2: power reference, and whether to record the calibration file;
  - V3: existing measurements for the seed file;
  - V4: location of the database;
  - V5: minimum numbers of points.

### 2026-09-30 13:57 CEST — [T60] Experiment plots: corners, QR code and structure plots
- **Status:** done
- **Branch:** `feat/phaseB-plots`, based on `docs/phase4-voxel-database`
- **Changes:**
  - `nanofactorysystem/experiment.py`:
    - `plot_experiment()` has a NumPy docstring and draws corners, the double corner, the QR code and the
      UUID/label, using the stored layout. It returns the figure and closes it when not shown.
    - `build_programs(plot_structures=False)` passes `plot` to `structure_program()`. This replaces the
      hard-coded `plotting_structure = False` and its commented-out switch.
  - `test/test_experiment.py`: two tests (plot content; structure plot only on request).
  - `test/README.md`.
  - `TODO.md`: T60 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 234 passed, 14 skipped.
- **Commits:** `f729324` feat(experiment): show corners and QR code in the experiment plot [T60]; docs(todo): close T60 [T60]
- **Notes:**
  - The plot uses a y axis pointing up, and the corner names follow the experiment's `rectangle_*`
    properties, where "top" is the smaller Y. Whether that matches the camera view on the lab PC is not
    verified.

### 2026-09-30 14:06 CEST — [T38] Visualization: laser power and axis formatting
- **Status:** done
- **Changes:**
  - `nanofactorysystem/utils/visualization.py`:
    - `ATTENUATOR_PATTERN`; `Movement.attenuator`;
    - `read_text()` tracks `$AO[0].A=` (N091);
    - `plot_movements_fast(calibration=...)` colours laser-on lines by power with a colour bar on the
      second axes (N092);
    - `_axis_formatter()` uses `ScalarFormatter(useOffset=False)` with scientific notation off for mm
      (N093); the commented-out calls are removed;
    - docstrings.
  - `nanofactorysystem/experiment.py`: structure plots use the attenuator calibration.
  - `test/test_utils/test_visualization.py`: two tests (power colours with and without calibration; mm axes
    without offset and scientific notation).
  - `test/README.md`.
  - `TODO.md`: T38 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 236 passed, 14 skipped. A first version put the colour bar on both axes,
  which made `tight_layout()` in the drawing tests warn; it is on the second axes now.
- **Commits:** `f688a61` feat(visualization): colour movements by laser power, plain axis labels [T38];
  docs(todo): close T38 [T38]
- **Open question (not changed):** IFOV programs switch the laser without `GALVO LASEROVERRIDE`; presumably
  `LINEAR` moves in IFOV mode are exposures and `RAPID` moves are not. The reader still treats all
  movements of IFOV programs as laser off, as before. Whether IFOV `LINEAR` should count as laser on needs
  confirmation from the maintainer.

### 2026-09-30 14:09 CEST — [T39] Manual DHM helper: implement reset
- **Status:** done
- **Changes:**
  - `test/manual/dhm/DHMUserBackend.py`:
    - `reset(reconnect=True)` closes the client, restores the start state and reconnects (N094);
    - the default motor positions moved into `default_motor_pos()`, which the constructor uses too;
    - earlier values are kept as a comment;
    - the German module note is translated.
  - `test/dhm/test_manual_helper.py` (new, 2 tests on the dummy DHM).
  - `test/README.md`.
  - `TODO.md`: T39 moved to In Progress, then to Done.
- **Tests:** `python -m pytest`: 238 passed, 14 skipped.
- **Commits:** `b875fe0` feat(dhm): implement reset of the manual DHM helper [T39]; docs(todo): close T39 [T39]
- **Note:** the old Zeiss 20x default had two assignments (3100.0, then 100.0); the effective value 100.0 is kept.

### 2026-09-30 14:10 CEST — [T28] Overview images and time estimate (evaluated, blocked)
- **Status:** blocked (decision needed)
- **Changes:**
  - `TODO.md`: T28 moved to Blocked, with proposals for the overview image (mosaic or center capture) and the
    time estimate (path length / F per layer program plus overhead).
  - `WORKLOG.md`: this entry.
- **Tests:** none (no code change).
- **Commits:** docs(todo): block T28 on decisions [T28]
- **Notes:**
  - The actual durations are already stored since T47/T59: session, structure and layer start/end times.
  - Only the estimate and the overview image are missing.

### 2026-09-30 18:38 CEST — [T43] Make the drop direction consistent everywhere
- **Status:** done
- **Branch:** `feat/phase1-execution-parameters`, based on `feat/phaseB-plots`
- **Decisions (maintainer, 2026-09-30):**
  - Physics: for a drop facing down, the substrate/polymer interface is the lower one, and an
    oil/substrate interface can appear above it (objective raised too high) and must not be used. For a
    drop facing up, the interface with the higher z is decisive; below it is polymer/air. Dip-in behaves
    like UP without an upper end.
  - "The z coordinate should NOT be changed. Only the order changes in regards to how the droplet is
    oriented." So the criterion "mirrored z values" of the todo reads as: identical layer programs, printed
    in opposite order.
- **Changes:**
  - `nanofactorysystem/parameter.py`: `Orientation` removed; its only users were the scanner and the
    layer.
  - `nanofactorysystem/tools/detector.py`: `Scanner(drop_direction=...)`. DOWN keeps the lowest focus
    range, UP the highest; the result reports `dropDirection`.
  - `nanofactorysystem/tools/layer.py`: new parameter `dropDirection` (default `"DOWN"`, which is the former
    hard-coded behaviour); the hotfix and the commented `sampleOrientation` are removed (N087, N089).
  - `nanofactorysystem/experiment.py`: `_with_drop_direction()` makes a copy of `sys_args` with
    `layer.dropDirection`, rejects a contradicting value, and is used for `System` and the tools; the value
    is stored with the experiment.
  - `nanofactorysystem/aerobasic/programs/drawings/qr_code.py`: the pixel lines are drawn upwards for DOWN
    (N070).
  - `nanofactorysystem/devices/coordinate_system.py`: the `DropDirection` docstring lists every place that
    depends on it and the dip-in plan (F8).
  - `test/test_drop_direction.py` (new, 6 tests); `test/README.md`; `CLAUDE.md` (separate commit, because
    the first edit did not apply).
  - `TODO.md`: T43 moved from Blocked to In Progress (with the decision), then to Done.
- **Tests:** `python -m pytest`: 244 passed, 14 skipped; golden programs and command logs are unchanged.
  - A script check finds all 58 `Experiment` calls in `mains/` passing `drop_direction`, and no hand-made
    z sign.
- **Commits:** `97e2345` feat(tools): derive the resin-layer choice from the drop direction [T43];
  `5a8402d` docs(claude): describe what the drop direction changes [T43]; docs(todo): close T43 [T43]
- **Behaviour changes on hardware (to check on the lab PC):**
  1. 20x (UP) plane fits: when two focus ranges are found, the highest one is now kept (before: always the
     lowest). With one focus range nothing changes.
  2. 63x (DOWN): unchanged, because the old hard-coded rule is the DOWN rule.
  3. QR codes printed with 63x (DOWN): the vertical pixel lines are now drawn from the anchor upwards
     instead of downwards.
- **Follow-ups:** `sys_args["sample"]["orientation"] = "top"` in the scripts is no longer read by any code;
  T51 can drop it when the scripts are migrated.

### 2026-09-30 18:47 CEST — [T44] Restructure how plane fitting is run
- **Status:** done
- **Changes:**
  - `nanofactorysystem/plane_fitting.py` (new):
    - `PlaneFitMode`: `GRID` = 0, `CORNERS` = 1, new `BORDER` = 2 (N026); `parse()` takes a member, a name or an
      integer.
    - `sample_points()`; `measure_plane()` (the former body of `Experiment.plane_fit`, now usable from scripts,
      N079); `interface_for()`; `structure_tilt()`.
  - `nanofactorysystem/experiment.py`:
    - `plane_fit_mode` accepts a member, a name or an integer, and is stored by name;
    - new `tilt_warning_um` (default 1 µm) and `_check_tilt()` after every plane fit (N082);
    - the centre is checked against the resin edges (N022, `ValueError`);
    - `plane_fit()` uses `measure_plane()`; the commented-out old sample-point function is removed;
    - the unused imports `Plane` and `PlaneFit` are removed;
    - reading from the file and from old dictionaries: `PlaneFitMode.parse`, and parameters missing from older
      files keep the constructor default.
  - `nanofactorysystem/storage/schema.py`: `plane_fit_mode` has kind "enum"; new parameter `tilt_warning_um`.
  - `test/test_plane_fitting.py` (new, 11 tests); `test/test_experiment.py`: `make_experiment(center=...)`;
    `test/README.md`; `CLAUDE.md`.
  - `TODO.md`: T44 moved to Done.
- **Tests:** `python -m pytest`: 255 passed, 14 skipped.
- **Commits:** `c619b7e` feat(experiment): named plane-fit modes and a stand-alone plane fit [T44]; docs(todo): close T44 [T44]
- **Notes:**
  - N078: the `+1` is correct. There are rows + 1 and cols + 1 grid lines (before, between and after the
    cells).
  - The tilt check only warns. N082 also suggested placing a structure at the lowest or highest corner height
    instead of its centre; that is not implemented, because it would change the printed z (open for the
    maintainer).
  - `measure_plane()` cannot run on the dummy backend, which does not simulate plane detection. It is tested
    with a stand-in for `tools.plane.Plane`.
- **Behaviour change on hardware:** an experiment centre outside the resin-drop box now fails at construction.
  The dictionaries store the mode name instead of the integer.

### 2026-09-30 18:51 CEST — [T45] Take camera images only on request
- **Status:** done
- **Decision (maintainer, 2026-09-30):**
  - The switch is `Experiment(camera_capture=False)`, an argument of the experiment, not `sys_args["camera"]`.
  - The existing experiment scripts get `camera_capture=True`, so that they keep their behaviour.
- **Changes:**
  - `nanofactorysystem/experiment.py`: argument `camera_capture` with a docstring. `measure()` takes camera
    images only with it and otherwise returns None as camera container. It is stored in the parameters, and
    `parameters_from_dictionary()` restores it for the restart.
  - `nanofactorysystem/storage/schema.py`: parameter `camera_capture`. `summary.py`: comment (files written
    before T45 always had camera images).
  - `test/test_experiment.py`: tests for both values (captures, camera calls, stored value, summary, restart)
    and for the default. `make_experiment` keeps camera images on by default for the tests written before
    T45.
  - `test/README.md`, `CLAUDE.md`.
  - Scripts with `camera_capture=True` added, one line each before `drop_direction=` (57 calls in 57 files):
    - `mains/Experiments/Big_substrate_20x/grating_ifov_test.py`
    - `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py`
    - `mains/Experiments/Grating_20x/grating_big_stitching.py`
    - `mains/Experiments/Grating_20x/plane_fitting_20x.py`
    - `mains/Experiments/Grating_20x/zumLaufBringen_20x.py`
    - `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py`
    - `mains/Experiments/Grating_63/Angle_test_NO_hatching.py`
    - `mains/Experiments/Grating_63/Angle_test_with_hatching.py`
    - `mains/Experiments/Grating_63/FOV_Stitch_test.py`
    - `mains/Experiments/Grating_63/binary_grating_test1.py`
    - `mains/Experiments/Grating_63/coordinate_test.py`
    - `mains/Experiments/Grating_63/grating_test_claude.py`
    - `mains/Experiments/Grating_63/grid_point_test.py`
    - `mains/Experiments/Grating_63/parameter_test.py`
    - `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py`
    - `mains/Experiments/Grating_63/realignment_grating.py`
    - `mains/Experiments/Grating_63/test_program_cycle.py`
    - `mains/Experiments/Grating_63/test_stitching.py`
    - `mains/Experiments/IFOV_63/ifov_test.py`
    - `mains/Experiments/Kailas/Quadrants_line_power_gap.py`
    - `mains/Experiments/Kailas/Rectangle_plane_fitting.py`
    - `mains/Experiments/Kailas/Voxel_row_on_pad.py`
    - `mains/Experiments/Kailas/grating_ifov_big.py`
    - `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py`
    - `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py`
    - `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py`
    - `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py`
    - `mains/Experiments/Kailas/lens_surface_test.py`
    - `mains/Experiments/Kailas/lenses.py`
    - `mains/Experiments/Kailas/padding_test_0_5mm.py`
    - `mains/Experiments/Kailas/parametric_4q.py`
    - `mains/Experiments/Kailas/power_z_pitch_lines.py`
    - `mains/Experiments/Kailas/voxel_dose_test.py`
    - `mains/Experiments/Kailas/zoffset_voxel__dose_test.py`
    - `mains/Experiments/Model_3D_experiment.py`
    - `mains/Experiments/default_exp_file.py`
    - `mains/Experiments/dhm/dhm_img_4_SEM.py`
    - `mains/Experiments/dhm/dhm_paper.py`
    - `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py`
    - `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py`
    - `mains/Experiments/dhm/dhm_paper_voxel_axial.py`
    - `mains/Experiments/other/dhm_paper_print.py`
    - `mains/Experiments/other/parameter_testprint.py`
    - `mains/Experiments/other/parameter_testprint_slicing_hatching.py`
    - `mains/Experiments/other/qr_code_investigation.py`
    - `mains/Experiments/other/testprint_dhm.py`
    - `mains/Experiments/other/testprint_dhm2.py`
    - `mains/Experiments/other/testprint_dhm3.py`
    - `mains/Experiments/other/z_line_focal_points.py`
    - `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py`
    - `mains/Experiments/parameter_study/parameter_testprint_power_speed.py`
    - `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py`
    - `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py`
    - `mains/Experiments/refractive_index/refractive_index_vel_power.py`
    - `mains/Experiments/stacked/stacked_lenses_test.py`
    - `mains/dhm_paper.py`
    - `mains/dhm_paper_pillowProblem_63.py`
    `mains/restart_experiment.py` passes the stored value (`**parameters`) and needs no change.
  - `TODO.md`: T45 moved from Blocked (with the decision) to In Progress, then to Done.
- **Tests:** `python -m pytest`: 258 passed, 14 skipped.
- **Commits:** `0315df1` feat(experiment): take camera images only on request [T45];
  `314a30b` chore(mains): keep camera images in the existing experiment scripts [T45]; docs(todo): close T45 [T45]
- **Behaviour change:** new scripts take no camera images unless they pass `camera_capture=True`. The
  existing scripts are unchanged.

### 2026-09-30 18:57 CEST — [T58] Define the capture position of `measure()`
- **Status:** done
- **Decision (maintainer, 2026-09-30):** before every capture only the galvo axes are set to A = B = 0; Z stays
  where it is.
- **Changes:**
  - `nanofactorysystem/experiment.py`: `measure()` sends `LINEAR A0 B0 F20` before the X/Y move; docstring.
  - `nanofactorysystem/storage/records.py`: `commanded_um` is (X, Y, Z, A, B) with Z = None and A = B = 0.
    Records written before T58 have three values.
  - `test/golden/commands_experiment_ifov_off.txt`, `commands_experiment_ifov_on.txt`: re-recorded with
    `--update-golden`. The diff consists only of 65 added lines `LINEAR A0.0000000000 B0.0000000000 F20.000000`
    per file, one before each capture move. T58 requires this change of the commands sent.
  - `test/test_experiment.py`: new test. After galvo layers every capture has A = B = 0 and Z is not
    commanded. Without the reset the test fails (A = 30 µm, B = 2030 µm), which was checked.
  - `test/README.md`.
  - `TODO.md`: T58 moved from Blocked (with the decision) to In Progress, then to Done.
- **Tests:** `python -m pytest`: 259 passed, 14 skipped.
- **Commits:** `fc9c425` feat(experiment): set the galvo to zero before every capture [T58]; docs(todo): close T58 [T58]
- **Behaviour change on hardware:** one extra galvo move to A = B = 0 before every camera/DHM capture.

### 2026-09-30 18:57 CEST — [Phase 1] Phase summary
- **Finished todos:**
  - T46: capture positions (before phase 2);
  - T43: drop direction;
  - T44: plane-fit modes and stand-alone plane fit;
  - T45: camera images only on request;
  - T58: galvo at zero before captures.
- **Maintainer decisions used:** the drop-direction physics and "z never changes, only the order" (T43);
  `camera_capture` as an `Experiment` argument, with True in the existing scripts (T45); only A = B = 0 before
  captures (T58).
- **Tests:** `python -m pytest` (short-path venv): 259 passed, 14 skipped, including the dry run.
  - Golden programs are unchanged.
  - The golden command logs of the experiment flows changed only by the galvo reset of T58 (justified in the
    T58 entry).
- **Branch:** `feat/phase1-execution-parameters`, stacked on the earlier branches. Nothing is pushed.
- **Open follow-ups:**
  - T37 (phase B) is no longer blocked by T43.
  - N082 (writing a structure at the lowest or highest corner height instead of its centre) is open; T44
    only warns.
- **To check on the lab PC:**
  1. 20x (UP) plane fits when two focus ranges are found: the highest range is kept now.
  2. QR codes with 63x (DOWN): the pixel lines are drawn upwards now.
  3. The galvo reset before captures (T58) and the tilt warning after the plane fit (T44).
  4. `sys_args["sample"]["orientation"]` is no longer read.
  5. An experiment centre outside the resin-drop box now raises an error.

### 2026-09-30 19:02 CEST — [T53] Voxel database (SQLite)
- **Status:** done
- **Branch:** `feat/phase4-voxel-database`, based on `feat/phase1-execution-parameters`
- **Decision (maintainer, 2026-09-30):** the design is approved with all proposals V1–V5. For V2 this means
  the power as set in the software, without recording the calibration file. V3: the seed file has the header
  only.
- **Changes:**
  - `docs/design/VOXEL_DATABASE.md`: approval recorded.
  - `nanofactorysystem/voxel/` (new):
    - `database.py`: `VoxelDatabase` with `create`, `default`, `add_material`, `add_measurement`,
      `import_csv` (atomic), `export_csv`, `measurements`, `voxel_size`; also `VoxelSize` and
      `default_path`;
    - `interpolation.py`: the lookup rules of design §4;
    - `migrations.py`: schema version 1 with `PRAGMA user_version`. The statements run one by one, because
      `executescript()` would commit the migration transaction halfway.
  - `config/voxel_seed.csv` (new, header only); `.gitignore`: `*.sqlite`.
  - `test/voxel/test_voxel_database.py` (new, 10 tests); `test/README.md`; `CLAUDE.md` (voxel section; data
    locations in the configuration section).
  - `TODO.md`: T53 moved from Blocked to In Progress, then to Done.
- **Tests:** `python -m pytest`: 269 passed, 14 skipped.
- **Commits:** `b45a7d2` docs(design): draft the voxel database [T53];
  `2de4367` docs(design): record the approval of the voxel database design [T53];
  `9c52f15` feat(voxel): add the voxel database [T53]; docs(todo): close T53 [T53]
- **Follow-ups:** T54 (voxel-aware slicing) needs T51 as well.

### 2026-09-30 19:14 CEST — [T51] New template for experiment scripts (core)
- **Status:** partial (the script migration waits for the maintainer's list)
- **Branch:** `feat/phase3-experiment-spec`, based on `feat/phase4-voxel-database`
- **Changes:**
  - `nanofactorysystem/experiment_spec.py` (new):
    - `ExperimentSpec`, `StructureSpec`, `CornerSpec`, and `OBJECTIVE_DEFAULTS` (the per-objective values of
      `default_exp_file.py`);
    - `default_sys_args()` (N001);
    - `resolved()` fills in the defaults and validates;
    - `experiment_arguments()`; `run_experiment(confirm=...)`.
    - The OPL start (the former `m0=350`, N021), the structure size separate from the FOV (N006), the grid and
      `n_mid_points` (N007, N008, N013) are parameters.
  - `nanofactorysystem/experiment.py`: `ProgramSource` (DRAWING, SLICER) and the argument `program_source`,
    stored in the file and the dictionary. `storage/schema.py`: parameter. `storage/summary.py`: the program
    source is an experiment field.
  - `nanofactorysystem/backends/dummy/a3200.py`: axis speed statements `BF…`, `ZF…` are accepted. Every IFOV
    setup program contains them; the slicer dry run showed they were missing (separate fix commit).
  - `mains/Experiments/experiment_template.py` (new): template with a DRAWING and a SLICER example; `main()`
    uses message boxes on the lab PC.
  - `test/integration/test_dry_run_spec.py` (new, 5 tests, marked `slow` where they print): dry runs for DRAWING
    and SLICER, spec validation, and the template examples (reduced to one coarse structure).
  - `test/README.md`, `CLAUDE.md`.
  - `TODO.md`: T51 moved to In Progress, with a status note and the open decision.
- **Tests:** `python -m pytest`: 274 passed, 14 skipped.
- **Commits:** `6462705` fix(backends): accept axis speed statements for all axes in the fake controller [T51];
  `acb2fe2` feat(experiment): describe experiments with ExperimentSpec [T51]; docs(todo): T51 status [T51]
- **Remaining gap:**
  - Migrate the scripts the maintainer still uses; move the others to `mains/Experiments/historical/` (or
    list them in a README); translate German text in the migrated scripts.
  - Confirm the program-source reading: DRAWING = the drawing classes.
- **Notes:**
  - The dummy does not simulate exposures in IFOV mode, so the slicer dry run checks the programs instead of
    exposures.
  - `default_exp_file.py` stays, because the older dry run and the lab use it.

### 2026-09-30 19:20 CEST — [T37] Replace the hotfixes in tools and devices
- **Status:** partial (the focus threshold needs lab data; N088 needs the maintainer)
- **Branch:** `fix/phaseB-tools-hotfixes`, based on `feat/phase3-experiment-spec`
- **Changes:**
  - N090: `(phi % 360) - 180` from commit f91fe30 rotated the reported azimuth by 180° instead of
    normalising it.
    - Fix: new `coordinate_system.normalize_angle()`, used by `PlaneFit.phi_degree` and `tools/plane.py`; tests
      added. Separate `fix:` commit.
    - Only the reported azimuth changes; no coordinate depends on it.
  - N076: `dhm/motorscan.py` has a new `bisectAroundMax()`: a loop over the widening factors 1, 2, 4 and 8, with
    a motor-range check (`MotorMinPos`/`MotorMaxPos`) and the dedicated `MotorScanError`.
    `test/dhm/test_motorscan.py` (new, 3 tests).
  - N075: analysis, no code bug. The capture time in `Dhm.container()` covers only `getimage()`: with
    `opt=False` this is one `CameraImage` request, i.e. mainly the network transfer. The pause between series
    images is not included. A comment documents it.
  - N046: `DrawableObject` no longer skips `data`/`height_profile`. `DOEstep` keeps `feature_size` and stores
    its height profile; a round-trip test was added.
  - N085/N086: resolved in T43; the hotfix line with `self.device` and the sample dictionary was removed there.
  - `test/README.md`; `TODO.md`: T37 moved to In Progress; new follow-up T61 (`minDiffMax` with lab data, N088).
- **Tests:** `python -m pytest`: all pass (282 passed plus the new tests; test_aerobasic 75 passed).
- **Commits:** `8444d70` fix(tools): report the plane azimuth without a 180 degree shift [T37];
  `b396a38` feat(dhm): widen the OPL scan bracket in a loop within the motor range [T37];
  `040e831` feat(drawings): store height profiles with the structure [T37]; docs(todo): T37 status and T61 [T37]
- **Remaining gap (T61):**
  1. A justified focus-detection threshold for 20x and 63x (N084, N010).
  2. N088 (Dominik's result object): what is meant?
- **Observation:** `DOEstep` fails with a height-profile pixel of 0: a zero-height `Rectangle3D` gives NaN
  layers. This belongs to T35 (the "`Z == 0` hotfix" in `Rectangle3D`).
- **Behaviour change on hardware:**
  - The reported plane azimuth is rotated by 180° compared with before; it is now correct.
  - The OPL motor scan tries up to 8× the bracket (before: 2×) and stops at the motor limits.

### 2026-09-30 21:59 CEST — [T51] Port the experiment scripts in use, move the others to historical/
- **Status:** done
- **Branch:** `feat/phase3-ported-scripts`, based on `fix/phaseB-tools-hotfixes`
- **Changes:**
  - `nanofactorysystem/experiment_spec.py`: `StructureSpec.factory(experiment)` for structures that need the
    running experiment (controller acceleration); `StructureSpec.empty()` for a skipped grid cell
    (`run_experiment` calls `skip_structure`); `run_experiment(substrate_information=)`; `script_output()`
    (output folder convention of the older scripts) and `messagebox_confirm()`.
  - Ported to `experiment_spec()` + `run_experiment()` (maintainer's list). The former entry function keeps its
    signature and gains `backend=`/`plane=`. Objective values unchanged; `sample.orientation` dropped (T43);
    an objective without a parameter set raises `ValueError`; German text translated:
    - `mains/Experiments/Kailas/parametric_4q.py`, `Quadrants_line_power_gap.py`, `lens_surface_test.py`,
      `zoffset_voxel__dose_test.py`, `Voxel_row_on_pad.py`
    - `mains/Experiments/parameter_study/parameter_testprint_power_speed.py`,
      `parameter_testprint_power_speed_test4orientation.py`, `parameter_testprint_slicing_hatching.py`,
      `line_test/Power_speed_line_test.py`
    - `mains/Experiments/refractive_index/refractive_index_vel_power.py`
    - `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py`
  - Renamed → `mains/Experiments/historical/…` (unchanged content): `Big_substrate_20x/`, `Grating_20x/`,
    `Grating_63/`, `IFOV_63/`, `dhm/`, `other/`, `stacked/`, `Model_3D_experiment.py`, and
    `Kailas/{Rectangle_plane_fitting, grating_ifov_big, ifovGrating_diffPower_500um, ifovGrating_diffPower_75um,
    ifovGrating_noPower_differentSize, ifovLens_diffSlice_75um, lenses, padding_test_0_5mm, power_z_pitch_lines,
    voxel_dose_test}.py`.
  - `mains/Experiments/historical/README.md` (new): status, content, how to port a script.
  - `mains/main.py`, `mains/main_IFOV.py`, `mains/main_3D_model.py`, `mains/grating_try.py`: imports from
    `Experiments.historical`; two already stale commented imports corrected.
  - `test/integration/test_ported_scripts.py` (new): every ported script builds a valid spec for its objectives
    and refuses the others; dry run of the DHM tomography script (grid 1 × 2, coarse hatch, no corners; 6 s).
  - `test/README.md`, `CLAUDE.md`: scripts in use vs. historical.
  - `TODO.md`: T51 moved to Done.
- **Tests:** `python -m pytest`: 295 passed, 14 skipped. The five active imports of the entry scripts import
  from `mains/`.
- **Commits:** `854bc8c` feat(experiment): structure factories and empty cells in specs [T51];
  `6d9afc1` refactor(mains): port the current experiment scripts to ExperimentSpec [T51];
  `905d1c2` chore(mains): move the unported experiment scripts to historical/ [T51];
  docs(todo): close T51 [T51]
- **Follow-ups:**
  - The active import of `mains/main.py` (`power_z_pitch_lines`) and of `main_IFOV.py` now point to historical
    scripts, which still set `sample.orientation`; the maintainer should port them if they are used again.
  - `todo_notes.md` still lists the old paths of the moved scripts (notes file, left unchanged).
- **Behaviour change on hardware:** none for the ported scripts' parameters; 20x runs of scripts without a 20x
  parameter set now stop before the hardware starts.

### 2026-09-30 23:27 CEST — [T52] Substrate-specific main file
- **Status:** done
- **Branch:** `feat/phase3-substrate-main`, based on `feat/phase3-ported-scripts`
- **Changes:**
  - `nanofactorysystem/experiment.py`: a new experiment with `substrate=` and an explicit `path=` gets the
    next free experiment label. Before, it was entered into the index with an empty label, and a second one on
    the same substrate failed. Separate `fix:` commit with a regression test in `test/test_experiment.py`.
  - `nanofactorysystem/substrate_plan.py` (new):
    - `SubstrateSpec` (label, user, objective, resin edges, material, notes, data root) and
      `SubstrateExperiment` (`ExperimentSpec` + optional folder);
    - `experiment_area`: the same geometry as `Experiment` (grid + margin), widened by the QR code (140 µm,
      centred on the upper edge) and the corners when markers are printed;
    - `existing_areas`: rectangles of the experiments already in the substrate index, read from their files;
    - `check_layout`: resin-drop bounding box, overlaps, existing experiments, objective, unique names; every
      problem in one `LayoutError`;
    - `plot_substrate`, `open_substrate` (creates the substrate and records the resin drop once);
    - `run_substrate`: checks first, then runs the experiments one after another via `run_experiment` into
      the substrate index, with optional `confirm_between`.
  - `nanofactorysystem/experiment_spec.py`: `run_experiment(allow_synced_root=)`.
  - `mains/substrate_main.py` (new): template with two ported Kailas experiments (63x); `mains/main.py` is
    unchanged.
  - `test/test_substrate_plan.py` (new, 7 tests); `test/integration/test_dry_run_substrate.py` (new, 4 tests:
    two experiments on one substrate give two experiment files and one index, planned areas equal the printed
    rectangles, a repeated run is refused, optional folder, confirmation between experiments, an invalid layout
    creates nothing, the template's layout is valid).
  - `test/README.md`, `CLAUDE.md`; `TODO.md`: T52 moved to Done, new T62.
- **Tests:** `python -m pytest`: 307 passed, 14 skipped. A full dry run of the template took 7 minutes (real 63x
  structures with DHM). It was run once, passed, and is not part of the suite; the suite checks the
  template's layout only.
- **Commits:** `b46bed8` fix(experiment): label experiments in explicit folders on their substrate [T52];
  `1796164` feat(experiment): run several experiments on one substrate [T52];
  `ff6d3a0` feat(mains): add a substrate main template [T52]; docs(todo): close T52, phase 3 summary [T52]
- **Follow-ups:** T62 (phase B, low): the resin check uses the bounding box of the four edge points, like the
  centre check of `Experiment`. An area near the rim of a round drop passes the check.

### 2026-09-30 23:27 CEST — [Phase 3] Phase summary
- **Finished todos:**
  - T51: `ExperimentSpec`/`run_experiment`, program sources DRAWING and SLICER, 11 scripts ported, the others
    moved to `mains/Experiments/historical/`;
  - T52: substrate main files with layout checks.
- **Maintainer decisions used:** DRAWING = the drawing classes; the list of scripts still in use; all other
  scripts go to `historical/`.
- **Tests:** `python -m pytest` (short-path venv): 307 passed, 14 skipped, including the dry runs.
  Golden files are unchanged.
- **Branches:** `feat/phase3-experiment-spec` → `fix/phaseB-tools-hotfixes` (T37) → `feat/phase3-ported-scripts`
  → `feat/phase3-substrate-main`, stacked on the earlier branches. Nothing is pushed.
- **Open follow-ups:** T62 (resin-drop outline). The active imports of `mains/main.py`
  (`power_z_pitch_lines`) and `mains/main_IFOV.py` point to historical scripts that still set
  `sample.orientation`.
- **To check on the lab PC:**
  1. One ported script per objective, e.g. `DHM_tomography/hollow_rect_first_print_63xobj.print_file`: the same
     values as before (zMax, margin, corners, plane-fit mode).
  2. `mains/substrate_main.py` with a real substrate label: the layout plot, the message boxes between the
     experiments, and `substrate.json` afterwards.
  3. Scripts without a 20x parameter set now stop with `ValueError` before the hardware starts.

### 2026-09-30 23:46 CEST — [T54] Voxel-aware slicing and hatching
- **Status:** done
- **Branch:** `feat/phase4-voxel-slicing`, based on `feat/phase3-substrate-main`
- **Decision (maintainer, 2026-09-30):** option (b) is the default: with voxel data the hatch spacing and layer
  height are derived from the voxel size and an overlap ratio. Option (a) stays available as `static_hatching`
  (given spacing, gaps only warned about), e.g. for very dense spacing later.
- **Changes:**
  - `nanofactorysystem/aerobasic/slicer/voxel.py` (new):
    - `SpacingMode` (`voxel_overlap`, `static_hatching`);
    - the `VoxelModel` protocol, so the slicer stays self-contained;
    - `VoxelContext`;
    - `compensate()`: contour offset = width / 2 (an explicit offset is kept), `voxel_height_um` = height, and
      the spacing per mode; the report goes into `job.meta["voxel"]`.
  - `slicer/parameters.py`: `voxel_height_um` (0 = the old planes), `spacing_mode`, `voxel_overlap` (0.3).
  - `slicer/slicing.py`: with a voxel height, the first and last plane lie half a voxel height inside the
    part, with even spacing (at most `layer_height_um`) in between. A part thinner than one voxel gets one plane
    at mid-height and a warning.
  - `slicer/hatching.py`: the strategies get `voxel=` (a `VoxelContext` or None).
  - `slicer/pipeline.py`: `slice_geometry(voxel_model=)`.
  - `slicer/storage.py`: string parameters are read back as `str`. `slicer/__init__.py`: exports.
  - `aerobasic/programs/drawings/model3d.py`: `voxel_model`, `spacing_mode`, `voxel_overlap`. A voxel model
    needs `power`. The power is recorded in `LaserParameters`. `to_json()["voxel"]`.
  - `nanofactorysystem/voxel/model.py` (new): `NoVoxelData`, `FixedVoxelModel`, `DatabaseVoxelModel`.
    `voxel/__init__.py`: exports.
  - `nanofactorysystem/experiment_spec.py`: `ExperimentSpec.voxel_material`, `voxel_database`, `voxel_model()`.
    SLICER structures then get the model and their power.
  - `nanofactorysystem/storage/summary.py`:
    - new columns `voxel_width_um`, `voxel_height_um`;
    - slice and hatch size of `Model3D_Slicer` structures come from their stored job parameters (before, the
      summary showed none);
    - the velocity unit follows their IFOV convention.
  - Tests:
    - `test/slicer/test_voxel_slicing.py` (new, 10 tests);
    - `test/integration/test_dry_run_spec.py`: SLICER dry run with a voxel database;
    - `test/storage/test_summary.py`: the expected `print_parameters` result gains the two new keys (new
      output, no assertion weakened), plus a slicer case.
  - `test/README.md`, `CLAUDE.md`; `TODO.md`: T54 moved to Done, new T63.
- **Tests:** `python -m pytest`: 319 passed, 14 skipped. The golden files are unchanged, so the no-data path is
  identical.
- **Commits:** `e5a2173` feat(slicer): slice with the voxel size of the laser parameters [T54];
  `e7ec542` feat(experiment): voxel material in experiment specs and summary [T54]; docs(todo): close T54 [T54]
- **Follow-ups:**
  - T63: `IFOV_Lines` writes with `F=5` (63x) or `F=10` (20x) mm/s regardless of `velocity`, so the voxel lookup
    uses the nominal velocity, not the real writing speed.
  - The default overlap of 0.3 is a proposal; the maintainer should check it with the first lab prints.
- **Behaviour change on hardware:** none without `voxel_material` or `voxel_model`. With them, SLICER programs
  set the structure power themselves (`SET_POWER`), and hatch and slice size come from the voxel data.

### 2026-10-01 00:18 CEST — [T31] Laser power per structure, layer and line
- **Status:** done
- **Branch:** `feat/phase4-voxel-slicing` (after T54)
- **Changes:**
  - N012 (power per structure): this worked already with `add_structure(power=)`; a dummy test now shows the
    exposures at two powers.
  - `nanofactorysystem/experiment.py`: `add_structure(layer_power=)` takes a list or a function of the layer id.
    - `structure_program` writes `POWER(ptoa(p))` with a comment at the start of every layer program, so a
      restart replays the powers from the stored programs.
    - A wrong list length raises `ValueError`. Repetitions inherit the layer powers.
  - `storage/records.py`, `storage/experiment_store.py`: `StructureRecord.layer_powers_mw` (optional attribute
    `layer_powers_json`; older files read back as empty, so the schema version is unchanged).
  - `storage/json_copies.py`: `layer_powers` in `structures.json`.
  - `storage/summary.py`: column `layer_power_mw` (range).
  - `experiment_spec.py`: `StructureSpec.layer_power`.
  - `aerobasic/programs/drawings/model3d.py` (N083, per segment):
    - elements with `PathElement.power_mw` go into their own IFOV blocks; consecutive equal powers share one,
      so the programs are unchanged without overrides;
    - `power_map(z_um, role)` sets overrides; existing overrides are kept;
    - overrides need the structure power;
    - `element_powers_mw` in `to_json()`.
  - Tests:
    - `test/test_experiment.py`: 3 tests (per structure, per layer with a repetition, function and wrong
      length);
    - `test/slicer/test_segment_power.py` (new, 4 tests);
    - `test/integration/test_dry_run_spec.py`: layer powers of a repetition.
  - `test/README.md`, `CLAUDE.md`; `TODO.md`: T31 moved to Done.
- **Tests:** `python -m pytest`: 326 passed, 14 skipped. Golden files are unchanged.
- **Commits:** `a01c64b` feat(experiment): laser power per layer [T31];
  `1e6cf41` feat(drawings): laser power per segment in slicer structures [T31]; docs(todo): close T31, phase 4
  summary [T31]
- **Follow-ups:** The hand-written drawing classes (`Rectangle3D`, …) have no power per line; so far only the
  slicer IR carries it. This is not required by T31; adaptive strategies (F7) will build on the IR.
- **Behaviour change on hardware:** none without `layer_power` or power overrides.

### 2026-10-01 00:18 CEST — [Phase 4] Phase summary
- **Finished todos:**
  - T53: voxel database;
  - T54: voxel-aware slicing;
  - T31: power per structure, layer and segment.
- **Maintainer decisions used:**
  - T53: V1–V5 approved;
  - T54: `voxel_overlap` is the default spacing mode, and `static_hatching` stays available.
- **Tests:** `python -m pytest` (short-path venv): 326 passed, 14 skipped, including the dry runs. Golden files
  are unchanged.
- **Branch:** `feat/phase4-voxel-slicing`, stacked on `feat/phase3-substrate-main` and the earlier branches.
  Nothing is pushed.
- **Open follow-ups:**
  - T63: the real IFOV writing speed for the voxel lookup;
  - the default overlap of 0.3 is to be checked in the lab;
  - the voxel database is still empty: the seed CSV has the header only.
- **To check on the lab PC:**
  1. Fill the voxel database with the first measurements (CSV import).
  2. Print a SLICER structure with `voxel_material`, then compare its size with the design (SEM/DHM).
  3. Print a structure with `layer_power` and check that the attenuator value changes between the layers.
  4. Print a slicer structure with `power_map` (contours at another power).

### 2026-10-01 13:03 CEST — [T37, T61, T32] Maintainer answers on the open todos
- **Status:** done (bookkeeping, no code change)
- **Branch:** `feat/phaseB-followups`, based on `feat/phase4-voxel-slicing` (the branch of the open PR stays
  unchanged)
- **Decisions (maintainer, 2026-10-01):**
  - T28: 5 s overhead per layer; the mosaic shows the corners (only the structure grid with `skip_corner`);
    by default only the stitched image is stored, optionally every single image.
  - T62: an ellipse through the edge points; no check for dip-in; automatic detection later (F9).
  - T63/T35: the IFOV writing speed stays fixed per objective; non-IFOV velocities are independent; programs
    get mm/s.
  - N069: probably related to the base height of another structure that uses `Rectangle3D`.
  - N068: shell ("vector") printing, detailed in F12.
  - T61: the focus detection is reworked later with example data (F10); N088 is dropped and kept in
    `todo_notes.md`.
  - T32: moved to F11, to be done with the A3200 manual.
  - T36: finish the focal-point script without changing the system behaviour or the plane fitting.
  - Voxel overlap: no value known yet. Without voxel data the slicer behaves as before, so the default (0.3)
    has no effect for now.
  - Port the scripts imported by `main.py` and `main_IFOV.py` (new T64). Close T37.
- **Changes:**
  - `TODO.md`:
    - T37, T61 and T32 moved to Done (T61 and T32 without code change);
    - T28 unblocked with the decisions;
    - T62, T63, T35 and T36 updated with the decisions;
    - new T64.
  - `future_todo.md`: new F9 (drop outline detection), F10 (focus detection with data), F11 (AeroBasic API
    with the manual, formerly T32, with all notes and locations), F12 (shell printing), F13 (free IFOV speed);
    F7 and F8 cross-references.
  - `todo_notes.md`: N088 status (dropped, where it was).
- **Tests:** none (documentation only).
- **Commits:** docs(todo): record the maintainer answers on the open todos [T61]
- **Follow-ups:** T28, T62, T63, T35, T36 and T64 are worked on next.

### 2026-10-01 13:15 CEST — [T63] Look up voxels at the IFOV writing speed
- **Status:** done
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/drawings/lines.py`: the fixed IFOV speeds (`IFOV_WRITING_SPEED_MM_S`
    = 5/10 mm/s, z 1 mm/s) are defined once, with `ifov_writing_speed_mm_s()` and `set_ifov_speeds()`.
    `IFOV_Lines` uses them; its output is unchanged (golden files).
  - `nanofactorysystem/aerobasic/programs/drawings/model3d.py`:
    - `IFOV_PolyLines` uses `set_ifov_speeds()`;
    - `Model3D_Slicer` writes the effective IFOV speed into `params.laser.scan_speed_um_s`, so the voxel
      lookup and the time estimate use it; `velocity` is stored as given;
    - an unsupported objective now fails at construction.
  - `test/slicer/test_voxel_slicing.py`: for both objectives, the lookup speed equals the speed in the
    program.
  - `TODO.md`: T63 moved to Done.
- **Tests:** `test/slicer`, `test/test_aerobasic` (golden files), `test/integration/test_dry_run_spec.py`: pass.
- **Commits:** `b2b07cd` fix(slicer): look up voxels at the IFOV writing speed [T63]; docs(todo): close T63 [T63]
- **Follow-ups:** none. A free IFOV speed is F13.
- **Behaviour change on hardware:** no program changes. The time estimate of slicer structures now uses the
  real IFOV speed.

### 2026-10-01 13:23 CEST — [T62] Check experiment areas against the drop ellipse
- **Status:** done
- **Changes:**
  - `nanofactorysystem/resin_drop.py` (new):
    - `Ellipse` and `ellipse_through()`: an axis-parallel conic through the four points; the inscribed
      box ellipse with a warning if the points define none;
    - `rectangle_inside()` (all four corners);
    - `drop_outline()`;
    - `has_drop_boundary()`: False for a drop direction named `DIP_IN`, ready for F8.
  - `nanofactorysystem/substrate_plan.py`: experiment areas are checked against the ellipse, not for dip-in;
    the plot draws the ellipse.
  - `nanofactorysystem/experiment.py`: `resin_edges=`; `_check_center()` uses the ellipse, else the old box;
    the edges are stored (`resin_edges_um`) and restored by `parameters_from_dictionary()`.
  - `nanofactorysystem/storage/schema.py`: parameter `resin_edges_um` (kind `points`; older files have none,
    so the box check applies on their restart).
  - `nanofactorysystem/experiment_spec.py`: passes four edge points as `resin_edges`.
  - Tests:
    - `test/test_resin_drop.py` (new, 5 tests);
    - `test/test_experiment.py`: center check and restart;
    - `test/test_substrate_plan.py`: the plot test expects 4 patches instead of 3, because of the added
      ellipse (no assertion weakened).
  - `test/README.md`, `CLAUDE.md`; `TODO.md`: T62 moved to Done.
- **Tests:** `python -m pytest`: 328 passed before the new tests, plus 6 new tests passing.
- **Commits:** `b9d8cfd` feat(experiment): check experiment areas against the drop ellipse [T62]; docs(todo):
  close T62 [T62]
- **Follow-ups:** automatic outline detection is F9.
- **Behaviour change on hardware:** an experiment whose center (or, in a substrate plan, whose area) lies in
  the box of the edge points but outside the ellipse is now refused before printing.

### 2026-10-01 13:38 CEST — [T35] Clarify line and rectangle details
- **Status:** done
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/drawings/lines.py`:
    - new `step_slice_size()`;
    - `Rectangle3D`: height 0 prints nothing (before: an empty program, then division by zero); a height
      below half a slice gives one layer;
    - `IFOV_Lines`: velocities 50–500 log a warning instead of raising `Warning`; the docstring states the
      fixed IFOV writing speed;
    - `Stair` uses `step_slice_size`.
  - `DOE.py`, `gratings.py`, `Stacked_lens.py`, `z_line_matrix.py`: `step_slice_size()` instead of
    `h / round(h / slice)` (a flat step or socket divided by zero; this is the base-height problem the
    maintainer remembered).
  - `test/test_aerobasic/test_line_details.py` (new, 6 tests); `test/README.md`; `TODO.md`: T35 moved to Done.
- **Tests:** `python -m pytest`: 340 passed, 14 skipped. Golden programs are unchanged: the new code gives
  the same values wherever the old formula worked.
- **Commits:** `3edbae7` fix(drawings): handle flat steps and validate IFOV velocities [T35]; docs(todo):
  close T35 [T35]
- **Follow-ups:** N068 (shell printing) is F12; a free IFOV speed is F13.
- **Behaviour change on hardware:** none for working structures. Structures with a flat step, pixel or socket
  can now be built.

### 2026-10-01 13:40 CEST — [T64] Port the scripts the entry files import
- **Status:** done
- **Changes:**
  - `mains/Experiments/historical/Kailas/power_z_pitch_lines.py` (renamed →
    `mains/Experiments/Kailas/power_z_pitch_lines.py`):
    - ported to `experiment_spec()`; drop direction DOWN for both objectives, plane fit CORNERS, objective
      values as before;
    - checks kept; the attenuator range is checked in the structure factory;
    - plane-fit duration logged;
    - `__main__` called a missing function and now calls `testprint`.
  - `mains/Experiments/historical/Big_substrate_20x/grating_ifov_test.py` (renamed →
    `mains/Experiments/Big_substrate_20x/grating_ifov_test.py`): ported.
    - Entry functions `binary_testprint` and `print_file`: `main_IFOV.py` imported `binary_testprint`, which did
      not exist, so it failed on import.
    - The output folder `grating_nach_debuggen` is now `grating_after_debugging`, and the substrate text is
      translated.
  - `mains/main.py`, `mains/main_IFOV.py`: imports. `mains/Experiments/historical/README.md`: table.
  - `test/integration/test_ported_scripts.py`: both scripts; the stand-in experiment gets an attenuator.
  - `TODO.md`: T64 moved to Done.
- **Tests:** `test/integration/test_ported_scripts.py`: 14 passed. Both modules import from `mains/`.
- **Commits:** `b90d42f` refactor(mains): port the scripts the entry files import [T64]; docs(todo): close T64 [T64]
- **Follow-ups:** none.
- **Behaviour change on hardware:** `grating_ifov_test` writes into `<path>/grating_after_debugging` instead
  of `grating_nach_debuggen`.

### 2026-10-01 14:33 CEST — [T28] Overview images and time estimate
- **Status:** done
- **Changes:**
  - `nanofactorysystem/time_estimate.py` (new): `estimate_program_s()` (LINEAR/RAPID, modal and default speed,
    INCREMENTAL, DWELL, galvo plus stage; acceleration ignored), `TimeEstimate`, `format_duration()`.
  - `nanofactorysystem/overview.py` (new): `field_of_view_um()`, `grid_positions()` (overlap 20 %),
    `stitch()` (`tools.stitch.Canvas`, placement with `Transform.P2D`, scaled to `overview_pixel_um`), `Mosaic`.
  - `nanofactorysystem/experiment.py`:
    - new arguments `layer_overhead_s` (5 s), `overview_capture`, `overview_single_images`,
      `overview_pixel_um`, all stored as parameters;
    - estimate after `build_programs()`, `log_duration()` after printing;
    - `overview_area()` and `capture_overview()`, called before and after printing (restart: "before" only if
      missing);
    - `QR_CODE_WIDTH_UM` and `OVERVIEW_BORDER_UM`.
  - `storage/experiment_store.py`: `write_time_estimate`, `write_overview`, `read_overview`;
    `storage/records.py`: `ExperimentRecord.time_estimate`; `storage/schema.py`: new parameters;
    `storage/summary.py`: `estimated_s`/`duration_s` per structure and in total, header line.
  - `experiment_spec.py`: `layer_overhead_s`, `overview_capture`, `overview_single_images`.
    `substrate_plan.py`: imports `QR_CODE_WIDTH_UM`.
  - Tests:
    - `test/test_time_estimate.py` (new, 4 tests) and `test/test_overview.py` (new, 3 tests, with stitching
      of a synthetic scene and a mirrored y axis);
    - `test/test_experiment.py`: 3 tests (estimate and log, overview before and after, area with corners).
  - `test/README.md`, `CLAUDE.md`; `TODO.md`: T28 moved to Done.
- **Tests:** `python -m pytest`: 352 passed, 14 skipped. Golden files are unchanged.
- **Commits:** `6dca352` feat(experiment): estimate and log the printing time [T28]; `909d2e7`
  feat(experiment): stitched camera overview before and after printing [T28]; docs(todo): close T28 [T28]
- **Decision taken without asking:** the overview is off by default (`overview_capture=False`), like
  `camera_capture` (T45). The maintainer can switch the default.
- **Follow-ups:** none.
- **To check on the lab PC:**
  - Does the mosaic line up? The camera offset of `Transform` is not applied, because all images share it.
  - Is the camera calibration (`cameraPitch`) right for both objectives?
- **Behaviour change on hardware:** without `overview_capture`, only the time estimate is logged and stored.

### 2026-10-01 14:39 CEST — [T36] Z-line focal-point script
- **Status:** done (N071 moved to F14 by the maintainer decision)
- **Changes:**
  - `mains/Experiments/historical/other/z_line_focal_points.py` (renamed →
    `mains/Experiments/focal_points/z_line_focal_points.py`): finished.
    - Flow: plane fit, z-lines at random points inside the structure grid via `tools.focus.Focus.run`, then
      corners and QR code.
    - Output: one `FocusDetect` container per point, plus `focal_points.json` (parameters, seed, points).
    - N014/N018: all variables at the top.
    - N015: more result information.
    - N016/N017: the z-line program writes z − dz/2 to z + dz/2, so no recalculation is needed (documented).
    - N019: a new folder per run.
    - N020: noise on the line lengths.
    - `min_distance`: rejection in x and y.
    - Removed: the draft's stair (power 700) and the scidatacontainer test block.
  - `future_todo.md`: F14 (camera offset in `System.zline`, N071). The change would affect every plane fit;
    N072 was already done (global variables, loaded once).
  - `test/integration/test_focal_points.py` (new): sampling and lengths; slow dry run with 3 z-lines.
  - `test/README.md`, `CLAUDE.md`, `mains/Experiments/historical/README.md`; `TODO.md`: T36 moved to Done.
- **Tests:** `python -m pytest`: 354 passed, 14 skipped.
- **Commits:** `9498bee` feat(mains): finish the focal-point z-line script [T36]; docs(todo): close T36 [T36]
- **Follow-ups:** F14.
- **Behaviour change on hardware:** none outside the script.

### 2026-10-01 14:40 CEST — [Phase B] Phase summary
- **Finished todos:**
  - earlier: T60, T38, T39, T37;
  - today: T63, T62, T35, T64, T28, T36;
  - closed without code change by maintainer decision: T61 (→ F10) and T32 (→ F11).
- **Open todos:** none. Future todos added: F9 (drop outline detection), F10 (focus detection with data),
  F11 (AeroBasic API with the manual), F12 (shell printing), F13 (free IFOV speed), F14 (camera offset in
  `System.zline`).
- **Tests:** `python -m pytest`: 354 passed, 14 skipped, including the dry runs. Golden files are unchanged.
- **Branch:** `feat/phaseB-followups`, on top of `feat/phase4-voxel-slicing`. Nothing is pushed.
- **To check on the lab PC:**
  1. An experiment near the rim of the drop is refused (ellipse, T62).
  2. Expected vs. actual printing time in the log (T28).
  3. The overview mosaic with `overview_capture=True`: alignment and the camera calibration.
  4. The focal-point script with a few points (T36).
  5. `main.py` (`power_z_pitch_lines`) and `main_IFOV.py` (`grating_ifov_test`, output folder now
     `grating_after_debugging`).

### 2026-10-18 14:30 CEST — [T65] Contour mask as uint8 for OpenCV
- **Status:** done
- **Context:** First lab-PC run of `main.py` (`parametric_4q`) after the update. Two setup problems were solved
  on the lab PC without code change: mvIMPACT was not on the path of the old venv (added via a `.pth` file
  pointing to `C:\Program Files\Balluff\ImpactAcquire\LanguageBindings\Python\Output\lib.win-amd64-cpython-312`),
  and `pip install -e .` upgraded the venv to NumPy 2.2.6 / OpenCV 4.12. The plane fit then stopped in
  `cv.drawContours` ("Layout of the output array image is incompatible with cv::Mat").
- **Cause:** `image.functions.contour_mask` used `dtype=int`, which NumPy 2 makes int64 on Windows (int32 with
  NumPy 1); OpenCV does not accept int64 images. The dummy dry runs pass a known plane and never call the
  focus detection, so no test covered it. The other `dtype=int` places in the package are NumPy-only.
- **Changes:**
  - `nanofactorysystem/image/functions.py`: `contour_mask` allocates the mask as uint8.
  - `test/test_image_functions.py` (new): `contour_mask` on a square found by `get_contours`; fails without
    the fix (same cv2 error), passes with it.
  - `test/README.md`: new test module listed.
  - `TODO.md`: T65 added to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest` in a fresh venv (NumPy 2.5.4, OpenCV 5.0.0): 355 passed, 14 skipped.
- **Commits:** `31b77fd` fix(image): build the contour mask as uint8 for OpenCV [T65]; docs(todo): log T65 [T65]
- **Follow-ups:** the plane fit / focus detection on the lab PC still has to be confirmed after this fix.
  Branch `fix/contour-mask-uint8` (from `main_HR`), not pushed.

### 2026-10-18 18:22 CEST — [T66] Unpacker and live access for experiment files
- **Status:** done
- **Context:** Maintainer request: the data of `experiment.h5` must be usable before the planned automated
  access exists. (1) Quick fix: an unpacker that takes the path of the file and an output path and writes
  everything in formats a Windows PC opens without extra software. (2) An interface for live access that
  reads the file, lets analyses compute, and stores their results back in the file, as basis of a later
  evaluation (T67). New folder `analysis/` next to `mains/`, `docs/`, `config/`; not part of the installed
  package.
- **Design decisions:**
  - The unpacker mirrors the HDF5 tree generically (one folder per group), so new groups of later schema
    versions are unpacked without code change; only a dataset type without a common format would become
    `.npy` (none in the current schema, checked by a test).
  - CSV default `de` (`;`, decimal comma, UTF-8 with BOM) so that German Excel opens it by double click;
    `en` optional. To be confirmed by the maintainer.
  - Analysis results only under `/analysis/{experiment,structures,captures}/<name>`; groups of the printing
    process are never changed (a rebuild replaces structure groups, which would delete results stored
    there). DHM products use the existing `add_dhm_product()` (design §5.6, F4).
  - Writes hold `experiment.lock` for one write and are refused while an experiment process holds it
    (design §6.3: one writer). Readers use no HDF5 file lock and retry, so they never block a write of the
    printing process; the unpacker copies the file first while it is locked.
  - The output folder must not contain the experiment file, because `overwrite` deletes the output folder.
- **Changes:**
  - `nanofactorysystem/storage/experiment_store.py`: `read_locking` argument (constructor, `open()`),
    `_read()` used by every read; default behaviour unchanged.
  - `test/storage/test_experiment_store.py`: test of reading without file locking.
  - `analysis/README.md` (new): usage, output layout, rules for live access.
  - `analysis/unpack_experiment.py` (new): unpack script (settings at the top, or command line).
  - `analysis/analysis_template.py` (new): template for an analysis that stores results.
  - `analysis/experiment_analysis/__init__.py` (new): public API.
  - `analysis/experiment_analysis/__main__.py` (new): `python -m experiment_analysis unpack|info|tree`.
  - `analysis/experiment_analysis/convert.py` (new): dataset → PNG/CSV/TXT/JSON/blob rules, CSV styles,
    Windows-safe names.
  - `analysis/experiment_analysis/unpack.py` (new): `unpack_experiment()` with README, summary, JSON copies,
    `tables/*.csv`, optional zip and `.zdc` export, snapshot while locked.
  - `analysis/experiment_analysis/access.py` (new): `ExperimentFile`, `lock_holder`, `ExperimentBusyError`.
  - `test/analysis/test_experiment_analysis.py` (new): 12 tests (10 marked `slow`, they print a dummy
    experiment with camera, DHM and overview).
  - `pyproject.toml`: `analysis` on the pytest `pythonpath`.
  - `test/README.md`: new test module, store test mentioned.
  - `docs/design/EXPERIMENT_STORAGE.md`: §5.9 analysis results (minor schema addition, version stays 1.0).
  - `CLAUDE.md`: analysis tools in the architecture section.
  - `TODO.md`: T66 added to Done, T67 (evaluation pipeline) added to Open.
  - `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest` in a fresh short-path venv (`%LOCALAPPDATA%\Temp\nfsv`, NumPy 2.5.4, h5py
  3.16.0 / HDF5 2.0.0): 368 passed, 14 skipped (the old venv there was empty and was recreated). An unpacked
  dummy experiment was inspected by hand: 98 PNG, 17 CSV, 44 JSON, 9 TXT files, 20 MB.
- **Commits:** `6b26274` refactor(storage): optional read without HDF5 file locking [T66]; `4687c0a`
  feat(analysis): unpack experiment files and live access for analyses [T66]; docs(todo): log T66 [T66]
- **Follow-ups:** T67 (evaluation pipeline). On the lab PC: unpack a real experiment and open it in Excel
  (CSV style), check the size for experiments with many DHM captures. Branch `feat/analysis-unpack`, created
  from `fix/contour-mask-uint8` (contains T65, not yet merged into `main_HR`), not pushed.


### 2026-11-15 23:15 CET — [Reorganisation] Project files for the four-repository system plan
- **Status:** done
- **Context:** Maintainer request: create `CLAUDE.md` and `TODO.md` for OffAxisHolo, DHMConnect and MIRA in
  the style of this repository and sort the todos of all four. The maintainer had moved this repository's
  project files into `todo_claude/` together with the plans `00_SOFTWARE_PLAN_OVERVIEW.md` and
  `03_NANOFACTORYSYSTEM_PLAN.md`; they are back at the root (content unchanged except where listed).
  Decisions taken with the maintainer: G1 — the communication repository is DHMConnect, package
  `dhmconnect` (the plan said `dhmlink`); the system plan is copied into every repository, master copy here;
  all four repositories use the format of this `TODO.md`.
- **Changes:**
  - `docs/system/SOFTWARE_PLAN_OVERVIEW.md` (new): system plan v0.2 (G1 decided, `dhmlink` → `dhmconnect`,
    unified todo rules, rule for contract changes); master copy.
  - `CLAUDE.md`: project files listed (incl. `future_todo.md`, `todo_notes.md`, `docs/system/`), new section
    "System context", legacy DHM path described, language rule extended, session start step 4, commit rules
    (feature branch from `main_HR`, topic split, messages for human readers), `dhmconnect`/`mira` in the
    testing rule, empty sections `## Current Status` / `## Status Update Anchor` added for the status
    review routine (they were referenced but missing).
  - `TODO.md`: phase plan extended by phases 5–10 (T70–T97 from the plan), working rules 7–9, table of open
    global decisions, recipe field reference under phase 7, T98 and T99 added (found during the
    reorganisation), field "Size" added to the format, T68 added to Done (it had been committed in `ed4e769`
    but not logged).
  - `future_todo.md`: F3, F4, F5, F6, F7, F12 marked as scheduled (→ T…, or moved to MIRA / DHMConnect);
    F15 (system GUI), F16 (controller and mode `correct`), F17 (dynamic slicing) added.
  - `WORKLOG.md`: this entry. Note: T68 has no entry of its own in this log; its commit message documents it.
  - `todo_notes.md`, `TODO_default_origin.md`, `Information_Mehrere_Experimente.txt`: restored unchanged at
    the root (T98 turns the last one into an English guide).
- **Tests:** none (documentation only).
- **Commits:** uncommitted — proposed messages (one per topic, on a branch `docs/system-plan` from the
  current branch `feat/lab-check`):
  1. `docs(system): add the plan for the four cooperating repositories`
     Files: `docs/system/SOFTWARE_PLAN_OVERVIEW.md` (new)
  2. `docs(claude): describe the system context and tighten the commit rules`
     Files: `CLAUDE.md`
  3. `docs(todo): schedule phases 5–10 for DHM service, operating modes and GUI`
     Files: `TODO.md`, `future_todo.md`, `WORKLOG.md`
- **Follow-ups:** T70–T74 (designs) are next; T69 (lab check) on the lab PC; the untracked folder
  `todo_claude/` can be removed once the maintainer has reviewed the files.

### 2026-11-16 17:14 CET — [Handover] OffAxisHolo handover of 2026-11-16 and commit of the reorganisation
- **Status:** done
- **Context:** The maintainer handed over `to_nanofactorysystem_2026-11-16.md` from OffAxisHolo (K2–K7 done,
  G2 decided, SA1–SA7 for the planning session K18). First, the reorganisation of 2026-11-15 (logged above
  as uncommitted) was committed on the new branch `docs/system-plan` from `main_HR` (which already contains
  `feat/lab-check`), in the three proposed topic commits.
- **Changes:**
  - `docs/system/handover/from_offaxisholo_2026-11-16.md` (new): the handover, filed with a header that says
    where its content went.
  - `docs/system/SOFTWARE_PLAN_OVERVIEW.md`: v0.3 — G2 decided, G9 partly decided, new G10 (reference mask,
    averaging, stitching; K18), milestone P1 (planning session K18) before S3/S4, S1 progress, new §8 facts
    about the DHM-PC (CUDA 13, no Python yet).
  - `TODO.md`: open decisions (G2 moved to decided, G4 and G10 added, G7 and G9 updated); recipe reference
    with the selection policies, frame metrics, `products`, `keep_raw` recommendation and a `background`
    field; T71 (background policy, z hint, product fields for the storage amendment), T72 (footprint for
    the reference mask), T75 (`n_medium` in the snapshot), T83 (product traceability fields, frame records,
    keep `EXPERIMENT_STORAGE.md` current for K12), T86 (together with K14), T89 (G10); new T100 (input for
    K18), phase table updated.
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `89ab8bb` docs(system): add the plan for the four cooperating repositories; `3f5bdd5`
  docs(claude): describe the system context and tighten the commit rules; `c8524ca` docs(todo): schedule
  phases 5-10 for DHM service, operating modes and GUI; `50661ab` docs(system): system plan v0.3 with the
  OffAxisHolo handover of 2026-11-16; docs(todo): take the OffAxisHolo handover into the todos
- **Follow-ups:** copy the plan v0.3 unchanged into OffAxisHolo, DHMConnect and MIRA (those repositories
  are not reachable from this working copy; one `docs(system): …` commit each). T100 before K18.
  `todo_claude/` (old copies of the project files) is still untracked and can be removed by the maintainer.

### 2026-11-16 17:19 CET — [T70] Design the information model v2
- **Status:** blocked (design written; waiting for maintainer approval, working rule 2)
- **Context:** First open todo of phase 5. Investigated `experiment_spec.py`, `substrate_plan.py`,
  `storage/substrate_store.py`, `storage/records.py`, `storage/schema.py`, `voxel/migrations.py`,
  `aerobasic/programs/setups.py`, `drawings/base.py`, `experiment.py` (setup and accelerations), the eight
  scripts in `mains/Experiments/` that use `factory=`, and the golden files `commands_experiment_ifov_on.txt`,
  `commands_experiment_ifov_off.txt`, `corner_default.txt`, `rectangle2d_ifov_20x.txt`,
  `binary_grating_ifov_63x.txt`.
- **Findings (IFOV decision):** the setup is sent once by immediate commands; layer programs have no setup
  header; IFOV layer programs configure IFOV completely themselves (their values even override those of
  `SetupIFOV`: 63x size 0.15 vs 0.075, tracking 16.5 vs 7.5); `IFOV_on` experiments already print corners and
  QR code as non-IFOV programs; `accel_a` is `accel_x / 2` for the whole `IFOV_on` experiment; voxel lookup,
  `StructureRecord.setup` and the summary report the experiment setup for every structure; `DefaultSetup`
  never resets `GALVO ROTATION A -0.6`, `RAMP RATE 0`, `LOOKAHEAD FAST`, `METRIC`, `GALVO LASEROVERRIDE A AUTO`
  (persistence unknown → T101).
- **Changes:**
  - `docs/design/INFORMATION_MODEL.md` (new): four levels with fields and storage, `StructureSettings` and
    resolution order, storage table, project file and structure JSON, named factories with `BuildContext`,
    reading old data, IFOV investigation with options, material store options, amendments to
    `EXPERIMENT_STORAGE.md` (schema 1.1), decisions M1–M6 with proposals, todo mapping.
  - `TODO.md`: T70 moved to Blocked (waiting for approval); T101 added (found during T70); T78 notes its
    dependency on T101 for the setup switch; phase table lists T101.
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only; no code changed).
- **Commits:** `2709356` docs(design): information model v2 for material, substrate, experiment [T70];
  docs(todo): log the T70 design and add T101 [T70]
- **Follow-ups:** maintainer answers M1–M6 and approves (line `Status: approved <date>`); T101 on the lab PC.
  Next todo without approval dependency: T71 (design of the DHM service integration).
  Branch `docs/t70-information-model` on top of `docs/system-plan` (from `main_HR`); nothing pushed.

### 2026-11-16 18:00 CET — [T70] Maintainer decisions M1–M6 worked into the information model
- **Status:** blocked (decisions recorded; the approval line `Status: approved <date>` is still missing)
- **Context:** The maintainer answered M1–M6: M1, M3 (several materials per substrate unlikely), M4, M5 as
  proposed; M2: setup sent for every structure, unchanged within a structure, changeable between
  structures, default `IFOV_on` (non-IFOV is outdated but stays selectable); M6: camera per structure only
  before and after, no layer captures. Future camera wishes: video of the structure while printing (→ T94)
  and a stitched overview of the experiment before and after printing by stage xy positions (exists since
  T28, `overview_capture=True`).
- **Changes:**
  - `docs/design/INFORMATION_MODEL.md`: status line, §3.2 (M3 note), §4 (`setup` default `IFOV_on`,
    `camera_capture` before/after only), §7 (decision M2 replaces the options; new §7.1 with the default
    change, five scripts that need an explicit `setup="IFOV_off"`, re-recorded golden command logs, camera
    behaviour change), §11 (decisions), §13.
  - `TODO.md`: T78 acceptance criteria follow M2/M6; T101 asks for the resets of both setup programs; T94
    note on the structure video; T70 blocked reason updated.
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `c68d2a3` docs(design): record the maintainer's decisions M1-M6 in the info model [T70];
  docs(todo): log the T70 decisions [T70]
- **Follow-ups:** maintainer writes the approval line; then phase 6 (T75 first). T101 on the lab PC.

### 2026-11-16 18:29 CET — [T70] Information model approved
- **Status:** done
- **Changes:**
  - `docs/design/INFORMATION_MODEL.md`: status line `approved 2026-11-16`, entered at the maintainer's request.
  - `TODO.md`: T70 moved from Blocked to Done.
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `42313ef` docs(design): approve the information model v2 [T70]; docs(todo): close T70 [T70]
- **Follow-ups:** phase 6 is open (T75 first, T101 on the lab PC). Next by working rule 1: T71.

### 2026-11-16 18:33 CET — [T71] Design the DHM service integration and measurement recipes
- **Status:** blocked (design written; waiting for maintainer approval, working rule 2)
- **Context:** Investigated `devices/dhm.py`, `backends/protocols.py` (`DhmRole`, `DhmDriver`),
  `Experiment.measure()`, `opl_scan()`, the print loop and the hologram counts in `build_programs()`
  (grid structures 10 / 10 / 20, corners and QR code 1 / 1 / 11 for before / layer / after),
  `ExperimentStore.add_capture()` / `add_dhm_product()` (the latter has no caller) and
  `EXPERIMENT_STORAGE.md` §5.3/§5.6. DHMConnect DL-A2/DL-A3 are not reachable from this working copy; field
  names follow the system plan and the OffAxisHolo draft 0.3.
- **Changes:**
  - `docs/design/DHM_SERVICE_INTEGRATION.md` (new): role protocol `DhmMeasurement` (configure, calibrate,
    acquire_background, measure, result, acknowledge, sync, close), adapters legacy / service / fake, adapter
    selection by recipe mode, `DhmRecipe` fields with defaults, `CaptureContext` incl. z hint, capture
    sequence with `reserve_capture()`, job states, single-writer queue, back pressure (`maxPending`, default 1
    until measured), store-then-acknowledge, restart with `sync`, calibration and background policy,
    decisions D1–D4, tests, todo mapping.
  - `docs/design/EXPERIMENT_STORAGE.md`: proposed §15 (capture job fields, raw reference, `frames` table,
    product traceability attributes, `/dhm_groups`, `/calibration/dhm`, `/metadata/dhm`, `/dhm_orphans`,
    unpack tool).
  - `TODO.md`: T71 via In Progress to Blocked (waiting for approval).
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `8118e4c` docs(design): DHM service integration and measurement recipes [T71]; `9f09c68`
  docs(design): propose storage of DHM service results [T71]; docs(todo): log the T71 design [T71]
- **Follow-ups:** maintainer answers D1–D4 and approves. Next: T72.

### 2026-11-16 18:35 CET — [T72] Design the operating modes and feedback hooks
- **Status:** blocked (design written; waiting for maintainer approval, working rule 2)
- **Context:** Investigated the slicer job model (`ElementGroup.contours` and `z_um` per layer group, kept for
  in-situ DHM comparison; shell groups without contours), `Model3D_Slicer.iterate_layers`, the program parser
  `utils/visualization.read_text` (laser state and power per movement, T38) and `EXPERIMENT_STORAGE.md` §5.9
  (`/analysis` was reserved for the analysis tools, which conflicts with T90 → amendment §16).
- **Changes:**
  - `docs/design/OPERATING_MODES.md` (new): modes off / monitor / shadow / correct with validation,
    evaluation hook at the result drain with an evaluation worker, `Evaluator` / `Controller` protocols,
    `DeviationReport` and `CorrectionPlan` fields, `LayerTarget` (thickness, top/bottom, mask, footprint
    polygons; sliced from contours, drawn from the voxel-rasterised toolpath or footprint only), reference
    mask input for K18, storage, monitor rules, hard limits without defaults, decisions O1–O5, tests.
  - `docs/design/EXPERIMENT_STORAGE.md`: proposed §16 (`/analysis/captures/<id>/deviation` written by the
    printing process, `/feedback/<structure>`, structure status `stopped`).
  - `TODO.md`: T72 to Blocked (waiting for approval).
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `e6df488` docs(design): operating modes, feedback hooks and layer targets [T72]; `8e0934d`
  docs(design): propose storage of feedback results [T72]; docs(todo): log the T72 design [T72]
- **Follow-ups:** maintainer answers O1–O5 and approves. Next: T73.

### 2026-11-16 18:38 CET — [T73] Design the camera live feed and recording
- **Status:** blocked (design written; waiting for maintainer approval, working rule 2)
- **Context:** Investigated `devices/camera.py`, `camera/camera.py` (single image requests),
  `camera/optexpose.py`, `System.getimage()` / `optexpose()` and their consumers (`measure()`, `overview.py`,
  `tools/focus.py`, `tools/layer.py`, `tools/grid.py`), the dummy camera driver, F3. Found that the image
  wait timeout is `2000 × ExposureTime` with the exposure in µs, i.e. about 11 h at 20 ms (→ T102).
- **Changes:**
  - `docs/design/CAMERA_LIVE.md` (new): `CameraService` with direct mode (feed off, unchanged device calls)
    and threaded mode (one owner, snapshots preempt the feed, separate measurement and feed settings,
    bounded subscriber queues, stop on abort), frame-to-layer mapping by times, recording per structure or
    experiment next to the experiment file with `/recordings` table and limits, live feed interface, dummy
    support, decisions C1–C5, tests.
  - `TODO.md`: T73 to Blocked (waiting for approval); T102 added (found during T73); phase table lists T102.
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `d690f28` docs(design): camera live feed, recording and single camera owner [T73];
  docs(todo): log the T73 design and add T102 [T73]
- **Follow-ups:** maintainer answers C1–C5 and approves; T102 (lab PC confirms the exposure unit). Next: T74.

### 2026-11-16 18:40 CET — [T74] Design the headless core for a GUI
- **Status:** blocked (design written; waiting for maintainer approval, working rule 2)
- **Context:** Searched the package for calls that wait for a person (`messagebox`, `plt.show()`, `input()`,
  `imshow`) and for pyplot use; read `plot_experiment()`, the substrate plot, `print_experiment()`,
  `Experiment.__exit__` / `_end_session`, `_stop_failed_task` and `AerotechTask.wait_to_finish`.
  `confirm` is already injectable in `run_experiment()` / `run_substrate()` (16 scripts import
  `messagebox_confirm`); `plt.show()` in the run path only runs with `show=True`.
- **Changes:**
  - `docs/design/GUI_READINESS.md` (new): inventory of blocking calls and pyplot use, thread and ownership
    rules (one worker thread owns all devices and is the only writer), `RunEvent` kinds and `EventBus`,
    `RunControl` with pause / resume / abort / `stop_now` at checkpoints, runner API, decisions P1–P3, tests.
  - `TODO.md`: T74 to Blocked (waiting for approval).
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `2a2b0a6` docs(design): headless core with run control and progress events [T74];
  docs(todo): log the T74 design [T74]
- **Follow-ups:** maintainer answers P1–P3 and approves. Next: T100 (K18 input), then phase 6 (T75).

### 2026-11-16 18:41 CET — [T100] Input for the planning session K18
- **Status:** blocked (note written; the todo asks for the maintainer's review before the session)
- **Changes:**
  - `docs/system/handover/to_offaxisholo_k18_2026-11-16.md` (new): when and where footprints are known,
    coordinate frame, proposals for SA1 (a priori with a posteriori check), SA2 (`reference_mask.occupied_um`
    polygons in `CaptureContext`, union of everything printed in the field of view), margin split
    (`pose_tolerance_um` here, `optical_margin_um` from OffAxisHolo), SA5, SA6; needs from MIRA and
    OffAxisHolo; questions for the session.
  - `TODO.md`: T100 to Blocked (review).
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** `2345a36` docs(system): nanofactorysystem input for the planning session K18 [T100];
  docs(todo): log T100 [T100]
- **Follow-ups:** maintainer reviews the note and takes it to K18. Phase 5 has no open todo left (T71–T74,
  T100 wait for the maintainer); phase 6 can start with T75 (T70 approved).

### 2026-11-16 19:04 CET — [T75] Material registry for photopolymers
- **Status:** done
- **Context:** First implementation todo of phase 6 (design T70 approved, decision M1: registry in the voxel
  SQLite; M3: batch belongs to the use; M4: names into `sys_args["sample"]`). The old test venv was gone; a fresh
  one was created at `%LOCALAPPDATA%\Temp\nfsv` (`pip install -e ".[test]"`: NumPy 2.5.5, h5py 3.16.0, OpenCV 5.0.0).
  The global Python still has the NumPy/OpenCV mismatch of T1.
- **Changes:**
  - `nanofactorysystem/voxel/migrations.py`: `migrate_1_to_2` (`material.kind`, `material.created`,
    table `material_property` with constraints and index).
  - `nanofactorysystem/voxel/materials.py` (new): `MaterialProperty`, `Material` (lookup by key, wavelength,
    state), `MaterialSnapshot`, `MaterialRegistry` (add, query, CSV import/export, `open_existing`, `snapshot`),
    `material_names` (argument > substrate > sys_args), `as_material_dict`, `UnitWarning`.
  - `nanofactorysystem/voxel/__init__.py`: exports.
  - `config/material_seed.csv` (new): seed, header only (no invented values).
  - `nanofactorysystem/storage/records.py`: `ExperimentRecord.materials`.
  - `nanofactorysystem/storage/experiment_store.py`: `write_materials` / `read_materials`, property table;
    `read()` fills `materials`.
  - `nanofactorysystem/storage/schema.py`: schema version 1.1.
  - `nanofactorysystem/experiment.py`: `materials=`, `material_registry=`, snapshots written into a new file,
    M4 for `sys_args["sample"]`.
  - `nanofactorysystem/experiment_spec.py`: `ExperimentSpec.materials`, `run_experiment(material_registry=)`.
  - `nanofactorysystem/substrate_plan.py`: `SubstrateSpec.material` as registry name or dict,
    `run_substrate(material_registry=)`.
  - `test/conftest.py`: autouse fixture `no_default_material_registry` (opening the default database would
    migrate the PC's file).
  - `test/voxel/test_material_registry.py` (new, 10 tests); `test/voxel/test_voxel_database.py`: expected schema
    version 2 instead of 1 (the migration raises it; the assertion is as strict as before) and the new table;
    `test/storage/test_experiment_store.py`: snapshot round trip; `test/integration/test_dry_run_materials.py`
    (new, 2 slow dry runs).
  - `docs/design/VOXEL_DATABASE.md`, `docs/design/EXPERIMENT_STORAGE.md`, `test/README.md`, `CLAUDE.md`: documented.
  - `TODO.md`: T75 to Done. `WORKLOG.md`: this entry.
- **Tests:** `python -m pytest` in the new venv: 383 passed, 14 skipped (11 min 29 s; warnings unchanged).
- **Commits:** `1a78f06` feat(voxel): material registry with extensible properties [T75]; `5953d36`
  feat(experiment): store a material snapshot with every experiment [T75]; docs(todo): close T75 [T75]
- **Follow-ups:** which refractive index is `n_medium` stays G4 / O1 / O11; the registry has no data yet (the
  maintainer enters values or a seed). Next: T77 (depends only on T70), then T76.
  Branch `feat/t75-material-registry` on top of the design branches; nothing pushed.

### 2026-11-17 08:57 CET — [T77] Serialisable experiments and structures
- **Status:** done
- **Changes:**
  - `nanofactorysystem/structure_factories.py` (new): `@structure_factory(name)` registry, `BuildContext`
    (objective, setup, accelerations, drop direction, attenuator power range and calibration, `check_power`),
    `FactoryCall` (name + JSON arguments; stored with module and source file, loading imports either).
  - `nanofactorysystem/experiment_spec.py`: `to_json`/`from_json`/`save`/`load` for `ExperimentSpec` and
    `StructureSpec` (geometry kinds drawing/factory/slicer/empty, slicer inputs inline or in `inputs/` with
    SHA-256, typos and other major versions refused), `SpecSerialisationError` naming structure and field,
    `store_spec()` called by `run_experiment()`, `drawable()` builds `FactoryCall`s with a `BuildContext`;
    new fields `description`, `tags`.
  - `nanofactorysystem/storage/experiment_store.py`, `records.py`, `json_copies.py`: `/spec`, `/inputs`,
    `ExperimentRecord.spec`, export of `experiment_spec.json`.
  - `nanofactorysystem/aerobasic/programs/drawings/hollow_structure.py`, `dots/dot_rows_on_base.py`: keep all
    constructor arguments, so that `to_json()` is complete (separate `fix` commit).
  - `mains/Experiments/` (8 scripts: DHM_tomography/hollow_rect_first_print_63xobj.py,
    Kailas/lens_surface_test.py, Kailas/power_z_pitch_lines.py,
    parameter_study/line_test/Power_speed_line_test.py, parameter_study/parameter_testprint_power_speed.py,
    parameter_study/parameter_testprint_power_speed_test4orientation.py,
    parameter_study/parameter_testprint_slicing_hatching.py, refractive_index/refractive_index_vel_power.py):
    closures replaced by named factories, same structures.
  - `test/test_experiment_spec_json.py` (new); `test/integration/test_ported_scripts.py` (round trip of every
    ported script and of the template); `test/integration/test_dry_run_spec.py` (stored spec and height map);
    `test/storage/test_experiment_store.py` (spec/inputs round trip); `test/README.md`.
  - `docs/design/EXPERIMENT_STORAGE.md` (`/spec`, `/inputs` in schema 1.1), `docs/design/INFORMATION_MODEL.md`
    (§6.5 implementation notes), `CLAUDE.md` (project files and named factories), `TODO.md` (T77 done, new T103).
- **Tests:** `python -m pytest` in the venv: 413 passed, 14 skipped (14:42 min); the earlier HollowRectangle
  warning is gone.
- **Commits:** `2c9bd1b` fix(drawings): keep all constructor arguments of two structures [T77]; `d431bbd`
  feat(storage): store the experiment spec and its input files [T77]; `4f83dd7` feat(spec): save experiments
  as project files with named factories [T77]; `e749109` refactor(mains): use named structure factories in
  the ported scripts [T77]; docs(todo): close T77 [T77]
- **Follow-ups:** T103 (`ExperimentSpec.from_record()` for files without `/spec`). Until T78 the `defaults`
  group uses the existing field names (INFORMATION_MODEL §6.5). Next: T76 (substrate record v2), then T79/T80,
  T78 after T101. Branch `feat/t77-serialisable-specs` on top of `feat/t75-material-registry`; nothing pushed.

### 2026-11-17 09:55 CET — [T76] Substrate record v2 and experiment overview
- **Status:** done
- **Changes:**
  - `nanofactorysystem/storage/substrate_store.py`: record version 2 (`schema_version` "2.0"): `substrate_material`,
    `substrate_type`, `dimensions`, per drop `material`/`batch`/`thickness_um`/`application`, validation
    (`check_substrate_fields`); version 1 read as 2, written as 2 only on change; `drop_index()`,
    `material_names(drop)`, `update_substrate()`, `plan_experiment()`, `register_experiment(replaces=)`,
    `layout_area_um()`, `ExperimentOverview`, `substrate_overview()`; `find_experiments()` returns planned
    entries only with `status="planned"`.
  - `nanofactorysystem/substrate_plan.py`: `SubstrateSpec` v2 fields, `open_substrate()` writes them,
    `run_substrate()` plans every experiment before the first print, `existing_areas()` via the overview
    (planned entries skipped).
  - `nanofactorysystem/experiment.py`: drop of the experiment by its edges, material names from that drop,
    `area_um`/`resin_drop` in the index entry, `plan_id` replaces the planned entry.
  - `nanofactorysystem/experiment_spec.py`: `run_experiment(plan_id=)`.
  - `mains/substrate_main.py`: optional v2 fields in the template.
  - `test/storage/test_substrate_store.py`: expected version "2.0" (justified: record version 2), new tests for
    the v1 upgrade, v2 fields, planned entries and the overview.
  - `test/integration/test_dry_run_substrate.py`: an experiment stopped before its start now stays `planned`
    in the index (justified: new planned entries, design §3.2); area, drop and overview after the dry run.
  - `test/README.md`, `CLAUDE.md`, `docs/design/EXPERIMENT_STORAGE.md` (§8), `docs/design/INFORMATION_MODEL.md`
    (§6.6 implementation notes), `TODO.md` (T76 done).
- **Tests:** `python -m pytest` in the venv: 416 passed, 14 skipped (8:38 min).
- **Commits:** `31ae2b2` feat(storage): substrate record version 2 and substrate overview [T76]; `dd1bc9a`
  feat(substrate): plan experiments in the index, resin per drop [T76]; docs(todo): close T76 [T76]
- **Follow-ups:** none new. Next in phase 6: T79 (configuration record), T80 (layout as data, uses
  `substrate_overview`), T103; T78 waits for T101 (lab PC). Branch `feat/t76-substrate-record-v2` on top of
  `feat/t77-serialisable-specs`; nothing pushed.

### 2026-11-17 16:09 CET — [T99] Translate the remaining German in active code
- **Status:** done
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/drawings/calc_polygons.py`: `__main__` demo comments, printed text
    and plot titles in English.
  - `nanofactorysystem/aerobasic/programs/drawings/height_function_structures/structures.py`: three exception
    messages in English (no test matches their text).
  - `TODO.md`: T99 moved to Done.
- **Tests:** `python -m pytest` in the short-path venv (`%LOCALAPPDATA%\Temp\nfsv`): 416 passed, 14 skipped
  (6:23 min), unchanged.
- **Commits:** `49b1fc6` docs(drawings): translate German demo output and error messages [T99]; bookkeeping in
  the following `docs(todo)` commit.
- **Follow-ups:** the folders named in T99 (`mains/Experiments/` outside `historical/`, `mains/lab_checks/`,
  `test/manual/`) were already English, so `CLAUDE.md:17` ("comments are often in German") is outdated (the
  maintainer's file, not changed). German that stays on purpose: legacy folders, the commented-out `"Mitte"`
  in `mains/main.py`, `drawings/Plan.md`, `TODO_default_origin.md`, quotes in `todo_notes.md`.

### 2026-11-17 16:09 CET — [T98] English guide to substrate and experiment specs
- **Status:** partial — the guide is done; moving the German source file to `attic/` waits for approval.
- **Changes:**
  - `docs/guides/SUBSTRATE_AND_EXPERIMENT_SPECS.md` (new): English version of
    `Information_Mehrere_Experimente.txt`, checked against `experiment_spec.py` and `substrate_plan.py`
    (fields `materials`, `description`, `tags` and the further `SubstrateSpec` fields added; a table of
    `OBJECTIVE_DEFAULTS`; line numbers and personal paths removed; example file name with underscores so the
    dry-run import works; the closing question of the chat note dropped).
  - `README.md`: link to the guide.
  - `nanofactorysystem/aerobasic/programs/drawings/height_function_structures/README.md`: translated to
    English; a note at the top says it describes the original installation and that the tree differs today.
  - `TODO.md`: T98 moved to In Progress with the remaining step.
- **Tests:** documentation only; the full suite above ran with these files present (416 passed, 14 skipped).
- **Commits:** `3101a96` docs(guides): add English guide to substrate and experiment specs [T98]; bookkeeping in
  the following `docs(todo)` commit.
- **Follow-ups:** approval to move `Information_Mehrere_Experimente.txt` to `attic/`; `attic/` is gitignored in
  this repository, so decide first whether moved files stay versioned. The cross-repository overview of this
  session (errors, duplicates, decisions, lab checks) lives outside the repository in
  `Seafile/phoenixd-robben/Code/_system/`.

### 2026-11-18 17:42 CET — [T98, X-C, X-J] Merge and attic move
- **Status:** done
- **Changes:**
  - `docs/ATTIC_INDEX.md` (new): attic index (X-B)
  - `docs/guides/SUBSTRATE_AND_EXPERIMENT_SPECS.md`: source note points to the attic index
  - `Information_Mehrere_Experimente.txt`, `todo_claude/00_SOFTWARE_PLAN_OVERVIEW.md`, `todo_claude/03_NANOFACTORYSYSTEM_PLAN.md`, `todo_claude/CLAUDE.md`, `todo_claude/Information_Mehrere_Experimente.txt`, `todo_claude/TODO.md`, `todo_claude/TODO_default_origin.md`, `todo_claude/WORKLOG.md`, `todo_claude/future_todo.md`, `todo_claude/todo_notes.md` (removed from Git, moved to the local `attic/`)
- **Tests:** `python -m pytest -m "not slow"` in the short-path venv before the changes: exit code 0.
- **Commits:** `9c62592` Merge branch 'docs/translate-german' into main_HR [T98, T99], `32d04e2` chore(attic): move approved files to the local attic [T98, X-C], merged with `9e9976b`.
- **Follow-ups:** none.

### 2026-11-18 17:42 CET — [X-D, T71–T74, T100] Master plan v0.4, design approvals and todo revision
- **Status:** done
- **Changes:**
  - `docs/system/SOFTWARE_PLAN_OVERVIEW.md`: master v0.4 from the decision session of 2026-11-17/18 (all global decisions, G5-new with N1–N7, group protocol, contracts, deferred points, milestones, attic rule, machine facts)
  - `docs/design/DHM_SERVICE_INTEGRATION.md`: approved; D1–D4 renamed SI1–SI4; recipe defaults; §8 background per structure; §10.1 decided
  - `docs/design/OPERATING_MODES.md`: approved; O1–O5 renamed OM1–OM5; §4.2, §4.4; §8.1 decided
  - `docs/design/CAMERA_LIVE.md`: approved; §8.1 decided
  - `docs/design/GUI_READINESS.md`: approved; §7.1 decided
  - `TODO.md`: phase plan, "Open decisions" (deferred points), new "Decided" table; rewritten T79, T83, T85, T86, T89, T90, T91, T93, T94, T97, T102 (now phase 9, high); new T104–T109; T71–T74, T98, T100 done
  - `CLAUDE.md`: system context after G5-new, rules of 2026-11-18, attic procedure
  - `future_todo.md`: F15 takes over the DHM operation panel (O9)
  - `WORKLOG.md`: these entries
- **Tests:** none (documentation only).
- **Commits:** `dbd4e67` docs(system): master plan v0.4 from the decision session 2026-11-18, `3048e1f` docs(design): record approval of the designs T71-T74 of 2026-11-18, `e22fdda` docs(todo): derive the todos from the decisions of 2026-11-18, `e3da359` docs(todo): move the DHM operation panel into F15 [O9], plus the `docs(todo)` commit of these entries.
- **Follow-ups:** T108 (material states + SZ2080 seed) is the first implementation task; the seed rows need the new states, so `config/material_seed.csv` was not filled in this revision.

### 2026-11-18 21:35 CET — [T108] Material states and the SZ2080 seed
- **Status:** done
- **Changes:**
  - `nanofactorysystem/voxel/materials.py`: `STATES` with `cured_in_resin` / `cured_developed`, `LEGACY_STATES`, `PHYSICAL_STATES`, `normalize_state`, `MissingPropertyError`, `Material.require_refractive_index`, `Material.contract_snapshot` (DHMConnect `material_snapshot` form), `MaterialRegistry.export_json` (schema `nanofactory.material_registry/1`); legacy `cured` mapped on input and in lookups
  - `nanofactorysystem/voxel/migrations.py`: `migrate_2_to_3` rebuilds `material_property` with the new CHECK constraint and rewrites `cured` rows
  - `nanofactorysystem/voxel/__init__.py`: new public names
  - `config/material_seed.csv`: SZ2080 at 674.994 nm in three states (maintainer's measurement, recorded 2026-11-18)
  - `test/voxel/test_material_states.py` (new): 9 tests (migration of a version-2 file, old CSV, old snapshot dict, seed values and Δn, missing index, contract snapshot incl. DHMConnect schema check when installed, JSON export)
  - `test/voxel/test_material_registry.py`, `test/voxel/test_voxel_database.py`: schema version 3 instead of 2; seed import in its own registry
  - `docs/design/INFORMATION_MODEL.md`, `CLAUDE.md`: states of schema version 3
- **Tests:** short-path venv `%LOCALAPPDATA%\Temp\nfsv` (Python 3.12.3): `python -m pytest -m "not slow"` 401 passed, 15 skipped; full `python -m pytest` exit code 0.
- **Commits:** `e79a531` feat(materials): split cured into cured_in_resin / cured_developed [T108], `0108f7f` feat(materials): seed SZ2080 refractive indices at 674.994 nm [T108], `698cc5c` docs(materials): describe the material states of schema version 3 [T108]
- **Follow-ups:** lab PC: the default voxel database is migrated to version 3 on first open (back it up first; `_system/LAB_PC_CHECKS.md` A7); the seed is not imported automatically into an existing database (`MaterialRegistry.import_csv(config/material_seed.csv)` once); OffAxisHolo K9 can generate its material presets from `export_json`.

### 2026-11-18 22:48 CET — [T83, T90] Notes from MIRA MI-10 and MI-53
- **Status:** done
- **Changes:**
  - `TODO.md`: T83 notes MIRA's HDF5 layout of a `LayerProduct` (`header_json` + one dataset per buffer) as a proposal; T90 notes that `mira.api.evaluate_layer` exists (MIRA `f513ef0`) and its context / settings keys
  - `WORKLOG.md`: this entry
- **Tests:** none (documentation only).
- **Commits:** see the `docs(todo)` commit of this entry.
- **Follow-ups:** none.

### 2026-11-19 22:39 CET — [T110] Main entry point and fully documented default experiment
- **Status:** done
- **Changes:**
  - `nanofactorysystem/backends/dummy/dry_run.py` (new): `dry_run(user)` context manager (dummy backend, known
    plane, `time.sleep` on the virtual clock, missing user/objective added to the config only for the dry run,
    restored on exit); a user section with only `name` crashed `System` in `scidatacontainer` (→ T111), so the
    added user carries placeholder email/organization/orcid.
  - `test/backends/test_dry_run_helper.py` (new): 4 tests.
  - `mains/main.py` (new; the former file → `mains/main_legacy.py`): entry point with SETTINGS block and the tasks
    experiment, slicer, layout, substrate, spec_file, restart, overview, analyse, materials; `--dry-run`,
    `--task demo`; dry runs use their own material registry (seed + invented voxel data).
  - `mains/main_legacy.py` (renamed from `mains/main.py`): header docstring; contains the maintainer's uncommitted
    formatting/path edit of the working tree. The pure rename landed in `9bd6c74` by mistake (staged by `git mv`;
    not amended per the commit rules).
  - `mains/Experiments/default_experiment.py` (new): every `ExperimentSpec`/`StructureSpec` field and slicer option
    with comment; named factory `default_experiment.rectangle` takes the controller acceleration of its axes.
  - `test/integration/test_main_entry.py` (new): 8 tests (2 slow dry runs).
  - `test/README.md`, `README.md`, `CLAUDE.md`: new entry point, default experiment, dry-run helper.
  - `TODO.md`: T110 done; new T111, T112 in the backlog.
- **Tests:** short-path venv: `python -m pytest` 436 passed, 15 skipped (11:41 min). Manual:
  `cd mains && python main.py --task demo --dry-run` exit 0, all nine tasks, 7 experiments finished (9:39 min);
  `python -m Experiments.default_experiment --dry-run` exit 0. Errors found and fixed during the runs (all in the
  new files): voxel method `"sem"` → `"SEM"`; `ExperimentFile.is_busy` is a property; `Session.run` passed
  `confirm` twice; the first template version used `acceleration=500` (estimate 2 h 58 min → 57 min, mostly the
  78-layer stair).
- **Commits:** `9bd6c74` feat(backends): add a dry-run context manager for main scripts [T110], `76138ba`
  chore(mains): keep the former main script as main_legacy.py [T110], `e374b12` feat(mains): add a main entry
  point for every task and a default experiment [T110], `268f1c4` docs: point new users to mains/main.py and the
  default experiment [T110], plus the `docs(todo)` commit of this entry.
- **Follow-ups:** T111 (clear error for incomplete user sections), T112 (acceleration=500 in
  `experiment_template.py` and the lab check → 2 mm run-up per line on the stages; decision needed before T69).
  The local `~/nanofactory.json` of this PC has neither user `Hannes` nor `Zeiss 63x` (the dry-run helper bridges
  it). The slicer logs "mesh is not watertight" for height maps (harmless).

### 2026-11-20 11:33 CET — [T113] Older experiment scripts to old_experiment/ and an experiment chain
- **Status:** done
- **Changes:**
  - `mains/Experiments/{Big_substrate_20x,DHM_tomography,Kailas,focal_points,historical,parameter_study,refractive_index}/**`,
    `mains/Experiments/default_exp_file.py`, `mains/Experiments/experiment_template.py` (renamed →
    `mains/Experiments/old_experiment/...`, unchanged except the run command in `experiment_template.py`)
  - `mains/Experiments/old_experiment/README.md` (new): content, import path, note on old `experiment_spec.json` files
  - `mains/Experiments/old_experiment/historical/README.md`: new paths, template is `default_experiment.py`
  - `mains/main.py`, `mains/substrate_main.py`, `mains/main_legacy.py`, `mains/main_IFOV.py`, `mains/main_3D_model.py`,
    `mains/grating_try.py`: imports from `Experiments.old_experiment`
  - `test/integration/test_ported_scripts.py`, `test_dry_run_spec.py`, `test_focal_points.py`,
    `test_dry_run_default_experiment.py`: paths of the moved scripts (tests unchanged otherwise)
  - `mains/Experiments/chain_rectangle_doe_lens.py` (new): substrate chain of three IFOV experiments (rectangle,
    DOE on base, aspheric lens), 3×3 power × hatch grid each, named factories, `--layout`, `--dry-run`
  - `test/integration/test_experiment_chain.py` (new): 9 tests (1 slow dry run)
  - `CLAUDE.md`, `test/README.md`, `docs/guides/SUBSTRATE_AND_EXPERIMENT_SPECS.md`: new locations, chain
  - `TODO.md`: T113 done, new T114, T112 path updated
- **Tests:** short-path venv: `python -m pytest` 445 passed, 15 skipped (11:14 min). Manual:
  `cd mains && python -m Experiments.chain_rectangle_doe_lens --dry-run` exit 0 (8 min), all three experiments
  finished; expected printing time 33:41 / 33:13 / 31:17 min (rectangle / DOE / lens), mostly the 5 s layer overhead.
- **Commits:** `6c82ef8` chore(mains): move all older experiment scripts to old_experiment/ [T113], `1e4c3f9`
  feat(mains): add a chain of rectangle, DOE and aspheric lens experiments [T113], `75c3d19` docs: describe
  old_experiment/ and the experiment chain [T113], plus the `docs(todo)` commit of this entry.
- **Follow-ups:** T114 (`Rectangle3D_IFOV` always uses the 63x IFOV configuration; alternating hatch mutates the
  object). Interpretations to confirm by the maintainer: total heights include the 1 µm in the substrate; DOE base
  hatch = DOE hatch; lens in IFOV; alternating hatch on. Branch based on `feat/t110-main-access-point` (T110 not yet
  in `main_HR`).

### 2026-11-20 12:14 CET — [T115] Chain decisions and the remaining old entry scripts
- **Status:** done
- **Changes:**
  - `mains/dhm_paper.py`, `mains/dhm_paper_pillowProblem_63.py`, `mains/grating_try.py` (renamed →
    `mains/Experiments/old_experiment/`, unchanged)
  - `mains/Experiments/old_experiment/README.md`: lists them
  - `mains/Experiments/chain_rectangle_doe_lens.py`: `overview_capture=True`; DOE base with explicit
    `socket_hatch_size`/`socket_slice_size` (same hatch and slice as the fields); docstring states the written height
    above the substrate (5 µm) and the cross hatching
  - `test/integration/test_experiment_chain.py`: checks overview, cross hatching, base hatch/slice
  - `TODO.md`: T115 done
- **Tests:** `python -m pytest test/integration/test_experiment_chain.py` 9 passed (incl. slow dry run). Manual:
  chain `--dry-run` exit 0, three experiments finished, `overview_before.png` / `overview_after.png` in every folder.
  The full suite was not rerun: the change touches only the chain script, its test and file moves without
  references (`todo_notes.md` is a historical inventory and keeps the old paths).
- **Commits:** `21806e8` chore(mains): move dhm_paper and grating_try scripts to old_experiment/ [T115], `1ee08c1`
  feat(mains): cross hatching and overview mosaic in the experiment chain [T115], plus the `docs(todo)` commit of
  this entry.
- **Follow-ups:** T114 unchanged (the cross hatching of `Rectangle3D_IFOV` flips its own state; with 25 layers a
  second iteration starts in the other direction).

### 2026-11-20 16:49 CET — [T116] Entry script for printing a PNG height map
- **Status:** done
- **Changes:**
  - `mains/main_PNG.py` (new): prints a 16-bit PNG as `HeightMap_IFOV` in IFOV mode; only `PNG`, `PIXEL_SIZE_UM`,
    `HEIGHT_PER_GRAY_UM` (and optional `GRAY_OFFSET`) must be set; user, objective, resin edges, output root and
    substrate label from `main.py`; center of the resin drop unless `CENTER` is set; `--preview`, `--dry-run`.
    Based on the maintainer's draft `height_map_ifov.py`.
  - `test/integration/test_main_png.py` (new): 5 tests (1 slow dry run)
  - `test/README.md`: new test module
  - `TODO.md`: T116 done
- **Tests:** short-path venv: `python -m pytest test/integration/test_main_png.py` 5 passed (incl. dry run);
  `python -m pytest -m "not slow"` 423 passed, 15 skipped.
- **Commits:** `f6efbac` feat(mains): add main_PNG.py to print a 16-bit PNG height map [T116], plus the
  `docs(todo)` commit of this entry.
- **Follow-ups:** none. 8-bit PNGs are refused by `HeightMap_IFOV` (deliberate `require_16bit`).

### 2026-11-20 17:03 CET — [T117] Analysis of the failed chain print (IFOV structures print as "+")
- **Status:** partial (analysis done, cause in the controller behaviour still open)
- **Changes:**
  - `TODO.md`: new T117 with the finding, the suspects and a lab test plan; phase table
- **Tests:** none (analysis only). Checked on the data of substrate HR-26-002 (copy on the office PC): layer
  programs of all 27 structures (correct square geometry, grid placement, z range 6 µm), `print_progress.json`
  (all layers ok, 2.7–4.4 s per layer), `A3200.log` (no error), camera captures after every layer (the "+" builds
  up layer by layer, identical for all powers and hatches), git history of `IFOV_Lines` /
  `initialise_IFOV_configuration` (no functional change since 2026-06-05; T35/T63 kept the programs, golden
  files). Dry run of one chain rectangle gives the same programs as the lab run.
- **Commits:** the `docs(todo)` commit of this entry.
- **Follow-ups:** T117 (lab test). `main_PNG.py` uses the same IFOV path and should not be used for a long
  print before T117 is solved.

### 2026-11-20 17:46 CET — [T117] Lab test script for the IFOV laser band failure
- **Status:** partial (script ready and dry-run; the lab print and the fix are open)
- **Changes:**
  - `mains/Experiments/ifov_laser_test.py` (new): four experiments a–d (current `Rectangle3D_IFOV`, explicit
    laser ON/OFF, IFOV configuration of 2026-03, galvo only without IFOV), each 2 x 2 squares 50 x 50 x 3 µm
    (0.25 / 0.7 mW x lines along x / y, hatch 0.2 µm, slice 0.25 µm, no cross hatching); `--layout`, `--dry-run`
  - `test/integration/test_ifov_laser_test.py` (new): 10 tests (1 slow dry run)
  - `test/README.md`: new test module
  - `TODO.md`: T117 to In Progress with the state
- **Tests:** short-path venv: `python -m pytest test/integration/test_ifov_laser_test.py` 10 passed (incl. dry
  run). Manual: `python -m Experiments.ifov_laser_test --dry-run` exit 0, all four experiments finished with
  4 x 13 layers. Interpretation choices (to confirm): lines in one direction per square instead of cross hatching,
  height 3 µm incl. 1 µm in the substrate, slice 0.25 µm, centers y = 20800 µm next to the chain experiments.
- **Commits:** `7cf1403` feat(mains): add a lab test for the IFOV laser band failure [T117], plus the
  `docs(todo)` commit of this entry.
- **Follow-ups:** variant c may inherit RAMP/LOOKAHEAD/SYNCAXES settings from earlier IFOV programs (no setup
  resets them). Branch based on `feat/t116-main-png`.

### 2026-11-20 18:13 CET — [T117] Switches for the confirmation boxes of the lab scripts
- **Status:** done (maintainer request; part of the T117 lab work)
- **Changes:**
  - `mains/Experiments/ifov_laser_test.py`: `ASK_EACH_STEP`, `ASK_BETWEEN`
  - `mains/main.py`: `ASK_EACH_STEP`, `ASK_BETWEEN` in SETTINGS; `Session.confirm_between` (task `substrate`
    used `confirm` for both questions before)
  - `mains/main_PNG.py`: `ASK_EACH_STEP`
  - `mains/Experiments/chain_rectangle_doe_lens.py`: `ASK_EACH_STEP`, `ASK_BETWEEN`
  - The switches turn off only the message boxes; plots still depend on the backend (lab = shown).
- **Tests:** short-path venv: `test_main_entry.py` 8 passed (incl. slow demo dry run); `test_main_png.py`,
  `test_experiment_chain.py`, `test_ifov_laser_test.py` with `-m "not slow"`: 27 passed.
- **Commits:** `4719134` feat(mains): switch the confirmation boxes of the IFOV lab test [T117], `c936384`
  feat(mains): switch the confirmation boxes in main, main_PNG and the chain [T117], plus the `docs(todo)`
  commit of this entry.
- **Follow-ups:** none.

### 2026-11-20 20:33 CET — [T117] Switch to suppress the plot windows (unattended run)
- **Status:** done (T117 itself stays in progress until the lab test is evaluated)
- **Changes:**
  - `mains/main.py`: `SHOW_PLOTS` in the SETTINGS block next to `ASK_EACH_STEP`/`ASK_BETWEEN`, passed as `Session(show_plot=)` in a real run.
  - `mains/main_PNG.py`: `SHOW_PLOTS` switches off the preview window and the layout plot.
  - `mains/Experiments/chain_rectangle_doe_lens.py`: `SHOW_PLOTS` (default True), `show_plot=interactive and SHOW_PLOTS`.
  - `mains/Experiments/ifov_laser_test.py`: `SHOW_PLOTS = False` (matching the maintainer's False confirmation switches there).
- **Tests:** `test_main_png.py`, `test_ifov_laser_test.py`, `test_main_entry.py` (incl. slow demo dry run): 21 passed; `test_experiment_chain.py -m "not slow"`: 8 passed.
- **Commits:** see `git log` on `feat/t117-show-plots-switch` (feat(mains): add SHOW_PLOTS to run the lab scripts unattended [T117])
- **Follow-ups:** none; `experiment.png` is still written with the windows off.

### 2026-11-21 09:45 CET — [T118] Substrate layout as JSON and image in the substrate folder
- **Status:** done
- **Changes:**
  - `nanofactorysystem/storage/substrate_layout.py` (new): `layout_dict`, `plot_layout` (plain matplotlib Figure, no window), `write_substrate_layout` → `substrate_layout.json` (schema `nanofactory.substrate_layout/1`) and `substrate_layout.png`.
  - `nanofactorysystem/storage/substrate_store.py`: `create` and `_update` rewrite the layout after every index write (failure only logged); `write_layout(label)`; a planned entry keeps its `name` on registration.
  - `mains/main.py`: task `overview` writes the layout of every substrate (also for substrates from before T118).
  - `test/storage/test_substrate_layout.py` (new): 5 tests.
  - `test/integration/test_dry_run_substrate.py`: checks the layout after the two-experiment dry run.
  - `test/README.md`: new row, extended row.
  - `docs/design/EXPERIMENT_STORAGE.md`, `CLAUDE.md`: layout files documented.
  - `TODO.md`: T118 in Done (maintainer request, added directly as done).
- **Tests:** full `python -m pytest`: 465 passed, 15 skipped.
- **Commits:** `1b110d0` feat(storage): write the substrate layout as JSON and image [T118], `b191ac0` docs(storage): describe substrate_layout.json and .png [T118]
- **Follow-ups:** none.

### 2026-11-21 13:14 CET — [T119] PNG experiment into a substrate, import fix
- **Status:** done
- **Changes:**
  - `mains/main_PNG.py`: `SUBSTRATE_LABEL` (set by the maintainer, previously unused) now runs the experiment via `run_substrate` with `main.substrate_spec()` under that label; `None` runs it into `OUTPUT_ROOT`; `sys.path` gets the script folder before `import main` (fixes `ModuleNotFoundError: No module named 'main'` when started from another working directory); dry run uses its own data root.
  - `test/integration/test_main_png.py`: import from another working directory (subprocess `--help`), slow dry runs with and without substrate.
  - `test/README.md`: row updated.
  - `TODO.md`: T119 added as done (maintainer report).
- **Tests:** `test/integration/test_main_png.py`: 7 passed (incl. slow).
- **Commits:** `b2cff99` feat(mains): enter the PNG experiment into a substrate [T119]
- **Follow-ups:** none.

### 2026-11-21 14:43 CET — [T120] Tcl_AsyncDelete crash of hidden plots
- **Status:** done (fix not yet verified on the lab PC)
- **Changes:**
  - `nanofactorysystem/utils/figures.py` (new): `new_figure(show)` (plain Figure without pyplot when hidden), `finish_figure` (show, close, `gc.collect()` in the main thread).
  - `nanofactorysystem/experiment.py`: `plot_experiment` uses them; structure plots (`plot_structures`) close their figure and collect at once.
  - `nanofactorysystem/substrate_plan.py`: `plot_substrate` uses them.
  - `nanofactorysystem/experiment_spec.py`: `messagebox_confirm` with its own hidden, topmost root, destroyed and collected in the main thread.
  - `test/test_experiment.py`, `test/test_substrate_plan.py`: hidden plots have no pyplot manager.
  - `test/README.md`: rows updated. `TODO.md`: T120 added as done.
- **Cause:** TkAgg creates Tk objects for every pyplot figure; after `plt.close` they were freed by the garbage collector in a non-main thread (camera driver) during the layer detection, which aborts the process.
- **Tests:** full `python -m pytest`: 468 passed, 15 skipped.
- **Commits:** `7360a3c` fix(experiment): stop hidden plots from crashing the run with Tcl_AsyncDelete [T120]
- **Follow-ups:** verify on the lab PC (start main_PNG with SHOW_PLOTS = False up to the print start).

### 2026-11-21 15:03 CET — [T117] IFOV "+" prints closed: controller configuration
- **Status:** done
- **Changes:**
  - `TODO.md`: T117 moved from In Progress to Done. The maintainer found the cause in the lab: a wrong configuration on the A3200 controller, not the generated programs. No code change to the IFOV generation, golden files unchanged.
- **Tests:** none (bookkeeping only).
- **Commits:** see `git log` on `docs/t117-close` (docs(todo): close T117, the cause was the controller configuration)
- **Follow-ups:** none; `mains/Experiments/ifov_laser_test.py` stays as a lab check for the IFOV laser gating.

### 2026-11-21 15:30 CET — [T121] Experiment center given as tuple aborts the layout check
- **Status:** done
- **Changes:**
  - `nanofactorysystem/experiment_spec.py`: `ExperimentSpec.__post_init__` converts a two-element center to `Point2D`, TypeError naming the field otherwise.
  - `mains/main_PNG.py`: `CENTER = Point2D(500, -25000)` instead of a plain tuple (cause of the lab traceback in `substrate_plan.experiment_area`).
  - `test/test_experiment_spec_json.py`: new test (tuple center converted, `experiment_area` works, invalid center refused).
  - `test/README.md`: row of `test_experiment_spec_json.py` updated.
  - `TODO.md`: T121 added as done, T122 added to Open.
- **Tests:** short-path venv `python -m pytest -m "not slow"`: 437 passed, 15 skipped, 3 failed. The 3 failures (`test_main_entry.py::test_main_substrate_layout_is_valid`, `::test_main_layout_and_materials_dry_run`, `test_main_png.py::test_spec_is_one_ifov_structure_in_the_drop_center`) fail identically without this change: they depend on the lab values committed in `bdba4c6` / `973c166` → T122.
- **Commits:** `e460cf5` fix(spec): accept an (x, y) pair as experiment center [T121]
- **Follow-ups:** T122 (entry-script tests independent of the SETTINGS values).

### 2026-11-22 11:49 CET — [T123] Unpack text datasets larger than 2 GB
- **Status:** done (not yet re-run on the lab file)
- **Changes:**
  - `analysis/experiment_analysis/convert.py`: `write_dataset` decides scalar vs. array from `dataset.shape` and writes scalar byte text unchanged; `np.ndim(data)` converted the text to a NumPy string, which fails above 2 GB.
  - `test/analysis/test_experiment_analysis.py`: new test for scalar text and text arrays.
  - `test/README.md`: row of `test_experiment_analysis.py` updated.
  - `TODO.md`: T123 added as done, T124 added to Open.
- **Cause:** the main_PNG experiment (2048 x 2048 µm height map, 47 993 944 lines) stores its whole-structure program `structures/<name>/program` as one uncompressed text of more than 2 GB.
- **Tests:** short-path venv `python -m pytest test/analysis`: 13 passed.
- **Commits:** `314d634` fix(analysis): unpack text datasets larger than 2 GB [T123]
- **Follow-ups:** T124 (do not store the whole-structure program as a second uncompressed copy).


### 2026-11-22 17:52 CET — [T125] Layer programs over 80 000 lines: split into parts, reprint missing layers
- **Status:** done (lab check of the split programs open)
- **Cause (from the logs of the DOE print 2026-11-21, `surface_16bit`):** `PROGRAM 1 LOAD` failed for 57 of 73 layers ("An out of memory error occurred." for 12–30 MB, `!` for 44–78 MB and for 96 737 lines); 81 751 lines still loaded. The experiment logged each failure and went on, so only the socket (layers 0–13) and layers 71/72 were printed. The maintainer's research (A3200 help) confirms the 60 000–80 000-line limit of the LOAD path and names queue mode (`BUFFEREDRUN`) as the fix (T126).
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/split.py` (new): `count_lines`, `plan_split`, `split_lines`, `split_program_file`, `ProgramSplitError`, `MAX_PROGRAM_LINES = 80_000` (maintainer decision). Body = trailing motion/laser-gate/power/feed lines; cuts only before a RAPID/LINEAR with the laser off that names every body axis; header and footer in every part; power and feed rates replayed.
  - `nanofactorysystem/experiment.py`: `max_program_lines` (None disables), `_layer_parts`, `_run_layer` (parts in order, part named in the error, parts deleted after the layer), `_check_program_lengths` after the time estimate (warning, trial split of the longest layer), `ProgramSplitError` recorded as failed layer; `reprint_layers(name, layer_ids=None)`.
  - `nanofactorysystem/reprint.py` (new): `missing_layers`, `select_layers` (refuses unknown and already printed layers), `reprint_plan`, `format_plan`.
  - `mains/reprint_layers.py` (new): lab script (SETTINGS, `--plan` without hardware, asks before printing).
  - `test/test_aerobasic/test_program_split.py` (new), `test/test_experiment.py`: split print gives the same exposures as unsplit, unsplittable layer recorded as failed, reprint of a failed layer through the script.
  - `test/README.md`, `CLAUDE.md`: new tests and the program length / reprint behaviour.
  - `TODO.md`: T125 added as done; T126, T127, T128 added to Open.
- **Tests:** short-path venv `python -m pytest`: 478 passed, 15 skipped, 4 failed. The failures (`test_main_entry.py::test_main_substrate_layout_is_valid`, `::test_main_layout_and_materials_dry_run`, `::test_main_restart_and_analyse_dry_run`, `test_main_png.py::test_spec_is_one_ifov_structure_in_the_drop_center`) come from the lab SETTINGS in `main.py` / `main_PNG.py` (T122); `test_main_restart_and_analyse_dry_run` fails identically with the changes stashed (experiment center outside the resin edges in `main.py`). Manual: the real DOE layer programs split correctly (layer 71: 2 parts, 70: 5, 23 with 2 193 987 lines: 28 parts, ≤ 79 992 lines each; parts reassemble to the original body; every cut before a RAPID); about 15–35 s for the largest layer.
- **Commits:** `76b8839` fix(experiment): print layer programs over 80 000 lines in parts [T125], `d46ad4a` feat(experiment): reprint the layers a structure is missing [T125], `a6db390` docs: describe program splitting and the layer reprint [T125]
- **Follow-ups:** T126 (queue mode, the real fix), T127 (REMOVEPROGRAM name), T128 (`~LASTERROR` for `!`, stop on load failure). Lab: run `mains/reprint_layers.py --plan`, then a split layer with the laser off/shutter closed before reprinting the DOE.

### 2026-11-22 18:35 CET — [T125] Maintainer review: split while building, setup per part, reprint order
- **Status:** done (lab check of the split programs open)
- **Review points and answers:**
  - The build must not skip a layer that cannot be loaded: `build_programs()` now splits every too long layer program and raises `ProgramSplitError` if one cannot be split (experiment not built, `structure_configs` stays None, nothing printed). Before, the build only warned and split at print time; an unsplittable layer was recorded as failed during printing.
  - Setup per part: the experiment setup (`DefaultSetup` / `SetupIFOV`) is sent once per experiment as immediate commands (also on restart / reprint); every IFOV layer program carries its whole setup (`initialise_IFOV_configuration`), which every part repeats as header; nothing else is sent between layers except camera captures. Checked by a new test on every part of a built IFOV structure.
  - The interim solution splits too: `reprint_layers()` → `print_structure()` prepares (splits) all missing layers before the first one is printed; old experiments built without parts are split then.
  - Order: the reprint follows the drop direction, DOWN prints the highest missing layer first (layers 70 → 14 for the DOE); new test.
- **Changes:**
  - `nanofactorysystem/aerobasic/programs/split.py`: `existing_parts` (reuse only if complete, not older than the program, within the limit), `remove_parts`; `split_program_file` removes stale parts first.
  - `nanofactorysystem/experiment.py`: `_split_long_programs` in the build, `_prepare_layers` before printing, `_run_layer(parts)`, parts removed after a printed layer, `ProgramSplitError` no longer a failed layer; docstrings; German comments in `print_structure` removed.
  - `mains/reprint_layers.py`: docstring.
  - `test/test_aerobasic/test_program_split.py`, `test/test_experiment.py`: new tests (see commit).
  - `CLAUDE.md`, `test/README.md`: updated. `TODO.md`: T125 entry updated.
- **Tests:** short-path venv `python -m pytest`: 482 passed, 15 skipped, 4 failed (the same four T122 failures as in the previous entry, lab SETTINGS in `main.py` / `main_PNG.py`).
- **Commits:** `9974a31` fix(experiment): split too long layer programs while building, stop if one cannot be split [T125], `2e7ad3a` docs: describe the split while building and the reprint order [T125]
- **Follow-ups:** unchanged (T126, T127, T128); lab: `reprint_layers.py --plan`, one split layer with the laser off before the DOE reprint. Splitting the 57 missing DOE layers before the reprint takes roughly 15–30 min and about 3.7 GB of disk space next to the layer programs.

### 2026-11-23 14:34 CET — [T129] Lab check: load a layer program through the A3200 C library
- **Status:** partial
- **Changes:**
  - `mains/lab_checks/library_load_check.py` (new): standalone lab check (standard library only). `inspect` lists the A3200 libraries, the header prototypes of the program functions, and name, bitness and memory of the process serving port 8000; `load` loads a layer program through `A3200C64.dll` on an idle task (prototypes checked against the installed headers first, memory of Python and of the port-8000 process sampled), then stops the task and removes the program; `ascii-load` does the same with `PROGRAM <task> LOAD` for comparison. It never starts a program.
  - `TODO.md`: T129 added to Open.
- **Tests:** smoke test on the development PC (`inspect` without an Aerotech installation; netstat, tasklist and header-prototype parsers, memory sampler checked with sample input). No pytest module: the script lives in `mains/` and needs the lab PC; unit tests follow with the loader in T129.
- **Commits:** `9e7365a` feat(lab): add a lab check that loads a layer program via the A3200 C library [T129]
- **Follow-ups:** lab run of `inspect`, `load` (layer 68 or 69, full length) and optionally `ascii-load`; then the loader in T129. The uncommitted phase-1 safety edits on `fix/load-failures` (`ascii.py`, `devices/aerotech/__init__.py`) are still incomplete (missing `TaskFailedError` import, `Task(program_name=)`); layer 70 of `surface_16bit` was skipped on purpose by the maintainer; layers printed by hand in Motion Composer are not in `experiment.h5`.

### 2026-11-23 15:13 CET — [T129] Lab check: compiled .ogm over ASCII; program optimiser noted as T130
- **Status:** partial
- **Changes:**
  - `mains/lab_checks/library_load_check.py`: `inspect` lists every program and compiler function declared in the installed A3200 headers; the procedure gains a step that loads the `.ogm` object file Motion Composer wrote over ASCII (separates "the ASCII interface cannot hold large programs" from "its own compilation of the source fails").
  - `TODO.md`: T130 (program optimiser) added to Open.
- **Tests:** compiler-function discovery checked with a sample header; no pytest module (lab script, see the previous entry).
- **Commits:** `b9fc573` feat(lab): list compiler functions and test loading a compiled .ogm over ASCII [T129]
- **Follow-ups:** lab steps `inspect`, `load`, `ascii-load` with the `.ogm`; the 10 s `program_ready_timeout` of `run_program_as_task` is not a cause (LOAD over ASCII blocks until the compile is done, the 10 s start afterwards) but must be revisited for an asynchronous library loader (T129). `nanofactorysystem/aerobasic/ascii.py` shows formatting changes in the working tree (probably the IDE formatter) besides the unfinished T128 edit; keep them out of functional commits.

### 2026-11-23 15:38 CET — [T128] Repair run_program_as_task after the unfinished T128 edits landed on main_HR
- **Status:** partial (T128 and T127 remain open)
- **Changes:**
  - `fe2dba9` merge of `main_HR` into `fix/load-failures`: brings `596a451`, `0593145` (maintainer updates of `mains/reprint_layers.py`, `nanofactorysystem/reprint.py`) and `67fd927` "clean up docs", which contains the unfinished T128 edits of `nanofactorysystem/aerobasic/ascii.py` (`~LASTERROR` after `!`, `LAST_ERROR` with try/finally, plus formatting) and `nanofactorysystem/devices/aerotech/__init__.py` (`Task(program_name=)`, `TaskFailedError` raises).
  - `nanofactorysystem/devices/aerotech/task.py`: `Task` accepts and stores `program_name`; without it every `run_program_as_task` raised a `TypeError` on `main_HR`. `finish()` still removes `file_path` (T127 open, golden command logs unchanged).
  - `nanofactorysystem/devices/aerotech/__init__.py`: missing `TaskFailedError` import added.
  - `test/backends/test_dummy_controller.py`: `test_program_error_before_start` expects `TaskFailedError` with the task state.
- **Tests:** short-path venv: `test/backends test/devices test/test_aerobasic test/test_system.py` 171 passed, 4 skipped; `test/test_experiment.py test/storage` 77 passed. Full suite run after the push (see the next entry or the session report).
- **Commits:** `236b85c` fix(devices): make run_program_as_task work again after the T128 edits [T128]
- **Follow-ups:** the rest of phase 1 (early end as failure, state 8 with error code, stop the structure on the first failure, T127 removal name) stays open; `fix/load-failures` merged into `main_HR` and pushed at the maintainer's request.

### 2026-11-24 10:52 CET — [T129] Evaluation of the library load lab check
- **Status:** partial (loader not implemented yet)
- **Changes:**
  - `TODO.md`: T129 gets the lab result and the design consequences (32-bit `A3200AsciiInterface.exe` serves port 8000; library load of the full layer 68 works in 129 s with a 19.3 GB peak in the 64-bit client; `.ogm` cannot be loaded over ASCII; a failed build leaves every later ASCII LOAD refused within 0.1 s; task 3 inactive).
- **Tests:** none (evaluation of lab output; the result folders `mains/lab_checks/library_load_check_2026112*` and `mains/lab_checks/console_logs.txt` stay untracked).
- **Commits:** see the docs(todo) commit of this entry.
- **Follow-ups:** T129 implementation (library loader in a worker process, task alternation 1/2); lab check whether a failed build blocks only the same program name or every load (small program of another name over ASCII after a refusal).

### 2026-11-24 11:34 CET — [T129] Work order and lab tests for library loading within a memory budget
- **Status:** partial (lab results and implementation open)
- **Changes:**
  - `mains/lab_checks/program_loading_lab.py` (new): lab steps `system`, `ladder`, `precision`, `ogm`, `cycle`, `sticky`, `watch`; one session folder per day; loads run in worker processes and are refused above the memory budget (default 22 GB for the whole PC); the cycle runs synthetic galvo-only programs with the laser gate forced off on tasks 1/2 with prefetch.
  - `test/lab_checks/test_program_loading_lab.py` (new): hardware-free helpers (synthetic and truncated programs, memory queries, budget estimate, worker result parsing).
  - `test/README.md`: row for the new test module.
  - `docs/design/PROGRAM_LOADING.md` (new): work order for T129 (findings, requirements R1-R10 of the maintainer: 32 GB RAM, at most 20-25 GB used, bounded compilation, tasks 1/2 alternating, work packages, open points, acceptance).
  - `docs/guides/PROGRAM_LOADING_LAB_TESTS.md` (new): lab procedure, safety, manual checklist, decision table.
  - `TODO.md`: T129 links the work order and the lab guide.
- **Tests:** `test/lab_checks` 6 passed; `program_loading_lab.py system` run on the development PC (no A3200 installation: library and ASCII reported as unavailable). The library and controller steps run for the first time on the lab PC.
- **Commits:** `6912824` feat(lab): add the lab tests for library loading within a memory budget [T129], `b3ece21` docs(design): work order and lab guide for program loading through the A3200 library [T129]
- **Follow-ups:** lab session per `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`; results into section 6 of the work order; then P1-P5 of the work order.

### 2026-11-24 13:05 CET — [T129] Evaluation of program loading lab session 1, plan and new todos
- **Status:** partial (implementation of T129 and the new todos open)
- **Changes:**
  - `docs/design/PROGRAM_LOADING.md`: section 6 holds the results of lab session 1 (linear compile cost 19.6 kB and 96 µs per line; memory freed at `A3200Disconnect`; programs survive the worker; removal verified for `.pgm`; `.ogm` load of a full layer in 5.9 s / 1.87 GB; cycle gaps 0.15 s; task 2 1.8× slower than task 1; Motion Composer compiles with a third of the memory; the A3200 software had not been restarted, so `sticky` is unanswered; an ASCII LOAD got no reply within 600 s); new section 7 (plan after the lab, default part size 400 000 lines from the budget) and section 8 (health check and recovery levels R0-R3, maintainer idea); section 5 marked superseded; acceptance renumbered to 9.
  - `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`: step 8 says in words why `sticky` runs last (the maintainer read "last" as an option `--last`).
  - `TODO.md`: T128 gets the ASCII LOAD response timeout; T129 gets the lab result; new T131 (precompiled `.ogm`), T132 (task 2 slower), T133 (health check and recovery), T134 (lab session 2).
- **Tests:** none (documentation and evaluation of lab output; `mains/lab_checks/program_loading_lab_20261124` and `console_log_loading_lab.txt` stay untracked).
- **Commits:** see the commits of this branch (`docs/load-lab-results`).
- **Follow-ups:** T134 (extend the lab script, lab session 2), then P1 (T127/T128), T129 P2-P5, T131-T133.

### 2026-11-24 14:15 CET — [T134, T127, T128, T129, T133, T130] Lab session 2 tools, load safety, library loader, health check, optimiser
- **Status:** T127, T128 done; T129, T130, T133 partial (see In Progress); T134 blocked (lab session 2 on the lab PC)
- **Changes:**
  - `mains/lab_checks/program_loading_lab.py`: session 2 steps `api`, `ogm-clean`, `add-associate`, `hold`, `taskspeed`, `runner`, `recover-ascii`, `reset` (`~RESETCONTROLLER` or `A3200Reset`), `restart-service`; restart check (process start times) and ASCII LOAD probe in `system`; ASCII replies wait 60 s; removal by candidate names verified with the added-program count; kB per line of an `.ogm` from its source `.pgm`.
  - `test/lab_checks/test_program_loading_lab.py`: tests of the new hardware-free helpers.
  - `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`: section "Session 2" (procedure, checklist, decisions).
  - `docs/design/PROGRAM_LOADING.md`: R2 via `~RESETCONTROLLER`; implementation status of section 8.
  - `nanofactorysystem/aerobasic/ascii.py`: `send_timed`, `PROGRAM_LOAD` with `load_timeout` (connection reopened after a timeout).
  - `nanofactorysystem/devices/a3200.py`: config `loadTimeout`, `libraryDll`, `memoryBudgetGb`, `memoryReserveGb`, `compileKbPerLine`.
  - `nanofactorysystem/devices/aerotech/task.py`: `error_info`, early end raises `TaskFailedError`, `remove_program`/`abort` remove the loaded name (T127).
  - `nanofactorysystem/devices/aerotech/__init__.py`: `run_program_as_task` decodes task errors, cleans up after every failure, logs the load time.
  - `nanofactorysystem/backends/dummy/a3200.py`: loaded programs and unknown removals, `program_incomplete_next`, `hang_next`.
  - `nanofactorysystem/experiment.py`: `stop_on_failure` + `PrintStoppedError`, restart prints a failed layer again (not behind printed ones), `program_loader="library"` with `max_program_lines="auto"`, health check before every structure and after a failure (`/logs/health`).
  - `nanofactorysystem/devices/aerotech/library.py` (new): ctypes wrapper of `A3200C64.dll`, memory queries.
  - `nanofactorysystem/devices/aerotech/loader.py` (new): `LibraryLoader` (worker process), `MemoryBudget`, `ProgramRunner` (tasks 1/2 with prefetch).
  - `nanofactorysystem/backends/dummy/loader.py` (new), `backends/dummy/__init__.py`, `backends/real.py`: `program_loader()`.
  - `nanofactorysystem/devices/aerotech/health.py` (new), `mains/controller_health.py` (new): health check and R0.
  - `nanofactorysystem/aerobasic/programs/optimize.py` (new): program optimiser (T130).
  - `mains/reprint_layers.py`: docstring on what the restart prints now.
  - Tests: `test/backends/test_dummy_controller.py`, `test/test_experiment.py` (old continue-after-failure tests opt out with `stop_on_failure=False`, justified: the default changed by T128), `test/devices/test_program_loader.py` (new), `test/devices/test_health.py` (new), `test/test_aerobasic/test_optimize.py` (new); golden command logs `test/golden/commands_experiment_ifov_off.txt` / `_on.txt` re-recorded deliberately (REMOVEPROGRAM name, health check queries).
  - `CLAUDE.md`, `test/README.md`: documentation of all of the above.
  - `TODO.md`: T127, T128 done; T129, T130, T133 in progress with status; T134 blocked by the lab session; new T135 (z-line program shares task 1 with layer programs).
- **Tests:** short-path venv: targeted runs passed (`test/backends test/devices test/test_experiment.py test/lab_checks test/test_aerobasic/test_optimize.py`); full suite 4 failed, 522 passed, 15 skipped (the 4 failures are the known T122 entry-script tests); `test/test_aerobasic/test_optimize.py` 8 passed (added after the full run started).
- **Commits:** `b052ff3` feat(lab): add lab session 2 steps for .ogm loading, task speed and recovery [T134]; `2a6e48f` feat(lab): reset the controller with ~RESETCONTROLLER in the R2 lab step [T134]; `79a789d` fix(devices): remove programs under their loaded name and report load and task failures [T127, T128]; `3f773a3` feat(experiment): stop printing at the first failed layer and print it again on restart [T128]; `0a4e261` feat(devices): load programs through the A3200 library on alternating tasks [T129]; `e77f48b` feat(lab): add a dry lab run of the package library loader [T134, T129]; `1d969e6` feat(devices): check the controller before printing and run recovery level R0 [T133]; `b063502` feat(aerobasic): add an optimiser that shortens generated programs [T130]; this docs(todo) commit.
- **Follow-ups:** lab session 2 (T134); then T129 P5 and the default switch, T131, T132, T133 R1-R3, T130 build-step option, T135.

### 2026-11-25 12:08 CET — [T136] Import the PTD-01 test print planning (design, todos, decisions, future todos)
- **Status:** partial (design written as draft; T136 blocked until the maintainer approves it and answers D1–D16)
- **Background:** Between 2026-11-20 and 2026-11-25 the maintainer and Claude (outside this repository) planned the standard parameter test print PTD-01 "voxel and line interaction". It is the first of a series of calibration prints modelled on FDM and resin printing, and its data go into the material table. Eight 50 × 50 µm fields F0–F7: interface and threshold ladder, line test, bridges, line pairs, squares (hatch), layer test (wedge, cap), crossings and woodpile, pillars on bases. It runs in two stages: A = F0 gives P_th, P_dam, z0 and a first voxel fit; B = F1–F7 on axes normalised with P/P_th, h/w(P) and Δz/l(P). Decisions of 2026-11-25: one experiment per field plus a chain over `run_substrate` (T113 pattern); existing code is not changed by the PTD-01 implementation; the voxel fit model w(P), l(P) is a required research result (T150/T151); the Benchy is a separate project. The German concept (with drawing and sources) stays in Claude Docs; the research report and the conversation summary were not imported.
- **Changes:**
  - `docs/design/TEST_PRINT_PTD01.md` (new): design as delivered, status draft, with these changes: background section from the concept; substrate anchoring, where the first slice is repeated down to `anchor_depth_um` (maintainer note, D15, F36); aligned z grid reached without a slicer change (height maps start at z = 0, `voxel_height_um = 0`); in-layer order as a named, exchangeable strategy (`ordering.py`, maintainer note: the order will change, e.g. following outlines or cross hatch, D16); F0 layer count corrected (8 layers + header, 80 IFOV blocks; §9.3 said 10 layers); space check (F7 needs 53 µm, F2 52.5 µm / 46.5 µm, so neither fits the planned gaps: D10, D11); line ends §9.5 (D12); polarisation D13; recalibration rule D14; `dwell_after_power_s` for D9; note on the concept drawing (4 × 2 block) vs. one experiment per field; improvement notes N1–N13 renamed F18–F30.
  - `docs/reviews/PTD01_PLAN_REVIEW_2026-11-25.md` (new): English translation of the plan review (verdict 8/10), with a list of the corrections made on import.
  - `TODO.md`: phase-plan row 11 (proposed, D7); open decision row "PTD-01 D1–D16"; new section "Phase 11 — Standard test prints" with T137–T151 in dependency order (T137, T138, T150, T140, T139, T141–T147, T151, T148, T149); T136 in "Blocked" (waiting for approval). Changes against the delivered todo list: T136 names all decisions of §12; T137 gets `dwell_after_power_s`; T138 gets the aligned grid and the anchoring; T139 holds no `ParameterFieldStructure(ToolpathStructure)` (that class does not exist; the field uses T137's class) and gets the ordering registry; each todo names the decisions it depends on; the D9 check is now its own todo T148 (before T149, maintainer answer); T149 depends on T148 and T151.
  - `future_todo.md`: F18–F30 (former improvement notes N1–N13) and F31–F36 (follow-up prints PTD-02…08, in-situ threshold from DHM time series, material-table output, line ends / PSO, automatic recalibration, anchoring as a general slicer option). Each is marked "to be discussed with the maintainer before scheduling".
- **Verified against the code:** `experiment.py:1469` calls `iterate_layers(coordinate_system)` without an objective; `BuildContext.check_power` raises if the range is unknown (`structure_factories.py:100`); `_check_power` in `mains/Experiments/chain_rectangle_doe_lens.py:211`; `IFOV_WRITING_SPEED_MM_S` (`lines.py:32`); `slice_geometry(run_preprocess=, ground_truth_path=)`; `SlicingParameters.z_epsilon_um` / `voxel_height_um`; `VoxelModel` protocol (`slicer/voxel.py:58`); `ExperimentSpec.tags` / `layer_overhead_s`; `CornerSpec`, `SpecSerialisationError`, `MissingPropertyError`, `ExperimentFile` exist; no `ToolpathStructure` class.
- **Tests:** none (documentation and planning only, no code changed).
- **Commits:** `5881afa` docs(design): add the PTD-01 test print design and plan review [T136]; docs(todo): schedule phase 11 PTD-01 and record improvement ideas [T136] (this commit).
- **Follow-ups:** decision session D1–D16 with the maintainer, then `Status: approved` and T136 done; T148 on the lab PC before stage A.

### 2026-11-25 12:38 CET — [T136] PTD-01 decision session and design approval
- **Status:** done
- **Decisions (maintainer, 2026-11-25):**
  - D1: DOWN order kept; note: with other materials the order may change for the 63x too.
  - D2: reduced corners with QR code; future: one corner frame around all experiments.
  - D3: `p_ref_factor` 1.5.
  - D4: 1 replicate, later 3.
  - D5: gaps 2 µm for line cells and 4.5 µm for volume cells.
  - D6: golden program for F3.
  - D7: phase 11 with priority.
  - D8: stage-A start values in one JSON per material (after an explanation of what the values are).
  - D10: F7 bases 6 × 6 µm; pillar heights changed by the maintainer from 4/8/12/16/24 to 2/4/6/8/10 µm, all below the 10.5 µm pitch.
  - D11: F2 pedestals 2 × 3 × 3 µm with a 2 µm gap.
  - D12: measure the line middle only.
  - D13: polarisation measured before stage B.
  - D14: recalibration rule documented only.
  - D15: anchoring 1.5 µm for volume cells (after the clarification that this is the depth written additionally below the interface).
  - D16: `row_by_row`.
  - D9 stays open until the lab check T148.
  - The design was approved.
- **Changes:**
  - `docs/design/TEST_PRINT_PTD01.md`: `Status: approved 2026-11-25`; §12 split into open (D9) and decided; F2/F7 geometry, space check, layer estimate (F7 about 40 instead of 85 layers; F1–F7 about 110–120 layers incl. anchors, about 10 min overhead), `StageAAxes` per material, anchoring scope, print-order note.
  - `TODO.md`: phase 11 has priority (phase-plan row, text, working rule 1); open decision row only D9; "Decided" row for PTD-01; T136 → Done; T138, T140, T141, T143 carry the decided values.
  - `future_todo.md`: F27 gets the material-dependent print order note; new F37 (one corner frame around all experiments of a substrate); intro range F18–F37.
  - `WORKLOG.md`: this entry.
- **Tests:** none (documentation only).
- **Commits:** docs(design): record the PTD-01 decisions and approve the design [T136] (this commit).
- **Follow-ups:** start phase 11 with T137, T138 and T150 (parallel), then T140 and T139. T148 (attenuator settling) on the lab PC before stage A.

### 2026-11-25 12:11 CET — [T134] Evaluation of program loading lab session 2
- **Status:** partial (lab session 2 evaluated; the gaps .NET compile, INtime memory and R3 moved to T153)
- **Changes:**
  - `docs/design/PROGRAM_LOADING.md`: section 6.2 with the results of lab session 2 (`.ogm` load 2.6× faster with 1/13 of the memory, added as `<stem>.pgm`; Add + Associate; task 2 untuned in every parameter file; runner check with 0.3 s gaps; `sticky` blocks only the failed name; R1 works, R2 unhomes, R3 refused; .NET `Builder.Build` found); section 7.2 with the plan; lab note in section 8; correction: automated prints ran on task 1.
  - `TODO.md`: T134 from Blocked to In Progress with status; T129, T133 status 2026-11-25; T131 clean `.ogm` numbers and removal name; T132 cause found and decision (a) align task 2 / (b) task 1 only with add-ahead; new T152 (fresh ASCII program name per load) and T153 (lab session 3).
- **Tests:** none (documentation and evaluation of lab output; the session folder `mains/lab_checks/program_loading_lab_20261125` stays unversioned). The task-parameter comparison was done with a short script over the 30 `.prma` files in the session folder.
- **Commits:** `d4093ae` docs(loading): record lab session 2 results and the plan after it [T134]; this docs(todo) commit.
- **Follow-ups:** T152 (first), T132 decision (maintainer), T129 P5 with one real layer, T131, T133 R1/R2, T153. Note: work done in a separate worktree on `docs/load-lab-session2` because a parallel session (PTD-01, `docs/ptd01-planning`, new IDs up to T151) edits `TODO.md` in the main working tree.

### 2026-11-25 12:40 CET — [T152] Load every ASCII program under a fresh name
- **Status:** done
- **Changes:**
  - `nanofactorysystem/devices/aerotech/__init__.py`: `exec_program_name()` and `EXEC_PROGRAM_PREFIX`; `run_program_as_task` copies every program to `nfs_<session>_<counter>_<stem>.pgm` (`_exec_copy`), `program_removed()` deletes the copy after a removal, `exec_programs` lists names not removed yet. Reason: a refused LOAD blocks its name on the controller (lab session 2), so the fixed name `python_aerobasic_program.pgm` blocked every later layer (2026-11-21).
  - `nanofactorysystem/devices/aerotech/task.py`: `Task(on_removed=)` callback after a successful `REMOVEPROGRAM`.
  - `nanofactorysystem/devices/aerotech/health.py`: `recover_r0(on_removed=)`, docstring on the names to pass.
  - `nanofactorysystem/experiment.py`: R0 removes the controller's `exec_programs` plus the pre-T152 name.
  - `nanofactorysystem/backends/dummy/a3200.py`: `blocked_programs`: a failed LOAD blocks its name, later loads of it get `!`.
  - `test/backends/test_dummy_controller.py`: `test_exec_program_name`, `test_every_load_gets_a_fresh_name`, `test_refused_load_blocks_only_its_name`; existing T127 tests use the new names (same assertions on removal and cleanup, plus the deleted copy).
  - `test/backends/test_controller_merge.py`, `test/test_experiment.py`, `test/devices/test_health.py`: new names; `test_refused_load_does_not_block_the_following_layers`; `test_recovery_level_r0_removes_the_given_names`.
  - `test/backends/test_command_logs.py`: the session token is normalised to `<session>`.
  - `test/golden/commands_experiment_ifov_off.txt`, `commands_experiment_ifov_on.txt`: re-recorded deliberately; only the 106 LOAD and REMOVEPROGRAM lines per file change.
  - `CLAUDE.md`, `test/README.md`: documentation.
  - `TODO.md`: T152 done; T132 decided as option (b) (task 1 only, add-ahead), Done-when rewritten; T129 status.
- **Tests:** system Python 3.12 (the venv `%LOCALAPPDATA%\Temp\nfsv` is broken: editable finder missing). Targeted: `test/backends/test_dummy_controller.py test/backends/test_controller_merge.py test/devices/test_health.py test/test_experiment.py` 92 passed; golden logs re-recorded, then passed; full suite 4 failed, 535 passed, 15 skipped (the 4 failures are the known T122 entry-script tests).
- **Commits:** `5b856bb` fix(devices): load every ASCII program under a fresh name [T152]; this docs(todo) commit.
- **Follow-ups:** T132 add-ahead mode on task 1; T129 P5; T153 (also: list the added-program names after REMOVEPROGRAM on the real controller).

### 2026-11-25 13:18 CET — [T132] Library loader on task 1 with add-ahead
- **Status:** partial (implemented and tested on the dummy backend; the lab check of the gap is part of T153)
- **Changes:**
  - `nanofactorysystem/devices/aerotech/loader.py`: `ProgramRunner(task=1)` runs every part on one task; the next part is compiled without a task (`add_async`, worker with `A3200ProgramAdd`) while the current one runs, then stop, remove, `associate`, start; execution names via `exec_program_name` with a session token; `LibraryLoader.load_async` replaced by `add_async`/`associate`. Reason: maintainer decision (b) of T132 (task 2 untuned).
  - `nanofactorysystem/devices/aerotech/library.py`: `A3200Library.add`, `associate`.
  - `nanofactorysystem/backends/dummy/loader.py`: `add_async`, `associate` (call log `("loader", "add" / "associate")`).
  - `nanofactorysystem/experiment.py`: docstrings of `program_loader` and `_print_layers_with_library`.
  - `test/devices/test_program_loader.py`: alternation tests replaced by task-1 add-ahead tests (same checks on removal, cleanup and failure stops; the alternation itself is no longer wanted), new `test_associate_failure_stops_and_cleans_up`, `test_execution_names_are_unique_across_runners`.
  - `test/test_experiment.py`: `test_library_loader_prints_every_layer_on_task_1` (renamed from `..._on_alternating_tasks`, same checks plus task 1 only).
  - `mains/lab_checks/program_loading_lab.py`: docstrings (the `runner` step now runs add-ahead on task 1).
  - `docs/design/PROGRAM_LOADING.md`: status in §7.2.
  - `CLAUDE.md`, `test/README.md`: documentation.
  - `TODO.md`: T132 to In Progress with status; T153 extended (T152 and add-ahead check, P5 on the same lab date, maintainer option 2); T129 status.
- **Tests:** system Python 3.12: `test/devices/test_program_loader.py` 11 passed; full suite 4 failed, 537 passed, 15 skipped (the 4 failures are the known T122 entry-script tests).
- **Commits:** `4c5cf7c` feat(devices): run library-loaded parts on task 1 with add-ahead [T132]; this docs(todo) commit.
- **Follow-ups:** lab session 3 (T153): runner gap with add-ahead, T152 on the real controller, P5.

### 2026-11-25 13:24 CET — [T153] Lab session 3 tooling and guide
- **Status:** partial (tools and guide done; blocked by the lab session on the lab PC)
- **Changes:**
  - `mains/lab_checks/program_loading_lab.py`: new steps `ascii-names` (T152 through the package on task 1), `recover-blocked` (R1 on a blocked name), `dotnet-build` (`Aerotech.AeroBasic.Builder.Build` in 64-bit PowerShell with a memory guard, then library load of the `.ogm`), `layer-dry` (P5: `dry_layer_lines` makes a real layer dry - gate OFF, `$AO` 0, no Z word, stage XY shifted to the current position; `dry_problems` checks it; split at the budget part size, add-ahead runner on task 1); `Library.added_program_list` (`A3200ProgramGetAddedPrograms`) in `system` and the controller snapshot; `read_block` for the INtime prompts of `hold`; `terminate_ascii_interface` shared by R1 steps; Build methods in the `api` log.
  - `test/lab_checks/test_program_loading_lab.py`: tests of the dry copy (golden IFOV program), refused lines, split parts stay dry, `read_block`, registered steps.
  - `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`: section "Session 3" (goal, safety, preparation, 10 steps, checklist, decisions).
  - `test/README.md`: test description.
  - `TODO.md`: T153 to Blocked with status; note on T135 (the library loader also uses task 1).
- **Tests:** `test/lab_checks` 21 passed (system Python 3.12); the new steps themselves need the controller (lab session 3).
- **Commits:** `461f4f2` feat(lab): add the lab session 3 steps for names, add-ahead and P5 [T153]; `6cc29c1` docs(guide): describe lab session 3 for program loading [T153]; this docs(todo) commit.
- **Follow-ups:** lab session 3 (maintainer); evaluation into `docs/design/PROGRAM_LOADING.md`; T135 before the library loader becomes the default.

### 2026-11-25 15:25 CET — [T153] Evaluation of lab session 3 and preparation of session 3b
- **Status:** partial (session 3 evaluated; the motion checks repeat in session 3b)
- **Changes:**
  - `nanofactorysystem/devices/aerotech/loader.py`: a failed part names the decoded task error code (session 3 showed only "ended in state error at line 6").
  - `test/devices/test_program_loader.py`: the failure message carries the code.
  - `mains/lab_checks/program_loading_lab.py`: `axes_not_ready` / `require_axes_ready` stop `cycle`, `taskspeed`, `runner`, `layer-dry` unless every axis is enabled and homed; `ascii-names` copies to `~/nfs_lab` and passes only with at least three loads.
  - `test/lab_checks/test_program_loading_lab.py`: `axes_not_ready`.
  - `test/README.md`: test descriptions.
  - `docs/design/PROGRAM_LOADING.md`: section 6.3 with the results of lab session 3 (three attempts; axes never enabled/homed during motion steps; .NET compile 19.9 kB/line; `ImmediateProgram0`; R1 does not clear a blocked name; R3 works as administrator; no library compile or load failed).
  - `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`: section "Session 3b" (ascii-names, runner, layer-dry with homed axes, about 35 minutes).
  - `TODO.md`: T153 status, blocked by session 3b; new T154 (ASCII LOAD at long paths).
- **Tests:** system Python 3.12: `test/devices test/backends test/test_experiment.py test/lab_checks` 177 passed, 3 skipped.
- **Commits:** `2b0fdec` fix(devices): name the task error code when a library part fails [T153]; `ad6f1f8` feat(lab): refuse motion steps without homed axes, short ascii-names path [T153]; `47f3147` docs(loading): record lab session 3 and describe session 3b [T153]; this docs(todo) commit.
- **Follow-ups:** lab session 3b (maintainer); then one real layer with the laser through the library loader; T154; T135 before the default switch.

### 2026-11-25 15:35 CET — [T131] Keep the .ogm cache in view (maintainer note)
- **Status:** partial (note only; T131 stays open)
- **Changes:**
  - `TODO.md`: T131 gets the lab session 3 data (.NET compile 19.9 kB/line, so the cache is per part; `.OGM` load 30 µs/line) and the maintainer's note that the `.ogm` cache is a likely important future step after the library loader runs robustly, with the expected gains.
- **Tests:** none (todo text only).
- **Commits:** this docs(todo) commit.
- **Follow-ups:** T131 after session 3b and the first laser print through the library loader.
