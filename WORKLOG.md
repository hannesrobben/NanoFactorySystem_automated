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

