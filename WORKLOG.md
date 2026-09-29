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

