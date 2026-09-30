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
