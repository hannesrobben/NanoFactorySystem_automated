# TODO

<!--
Format rules (for humans and Claude):
- ID: T<number>, never reused. Follow-ups reference their origin: "(follow-up of T3)" or "(found during T3)".
- Priority: high | medium | low
- Depends on: IDs or "–"
- Done when: one line or sub-bullets; every criterion must be verifiable.
- Sort "Open" by: blockers/dependencies first, then priority.
- "Done" is a staging area: the status review routine moves entries to ARCHIVE.md.
-->

## Open
- [ ] T20: Merge `A3200` and `Aerotech3200` into one controller class (follow-up of T12)
      Goal: One controller class owns the socket, the ASCII protocol, the motion/laser helpers and the program tasks.
      Priority: medium | Depends on: T12, T3, T5, T7
      Done when:
        - A single class, built on `AerotechAsciiInterface`, provides the µm-based methods of the old
          `A3200` (`moveabs`, `position`, `wait`, `power`, `pulse`, `laseron/off`, `zline`, …) and the
          task features of `Aerotech3200` (`run_program_as_task`, `xyz`, `save_log`, `.api`).
        - `System.controller` and `System.a3200_new` refer to the same object; `Aerotech3200` remains
          importable as a compatible alias or thin subclass (also constructible without user/config).
        - For the same flows (System start-up, z-line, `print_structure`), the command log recorded by the
          dummy transport is identical before and after the merge (the recorded logs are committed as
          golden files).
        - `AerotechError` subclasses `RuntimeError`, so existing `except` clauses for both keep working.
        - Whether `zMax` also guards `.api.LINEAR` moves is decided by the maintainer and documented.
      Notes: Maintainer decision 2026-09-28. Refactor only after the dummy backend and tests exist.

- [ ] T11: Fix small defects in `System` and the `A3200` controller (found during T1)
      Goal: Rarely used helpers of `System` and `A3200` work as documented.
      Priority: medium | Depends on: T12, T3
      Done when:
        - `System.object_pos`/`camera_pos` use `self.controller`.
        - `A3200.home` (`in None`), `A3200.container` (dict iteration) and the use of `self.z` before
          assignment are fixed.
        - `AerotechAsciiInterface.send_one` no longer recurses infinitely.
        - Each fix has a dummy-backend test.
      Notes: Details: `docs/reviews/CODE_REVIEW_2026-09-28.md` §4.

- [ ] T16: Fix always-true `assert (path, Path)` in experiment scripts (found during T1)
      Goal: Path arguments of experiment scripts are actually checked.
      Priority: low | Depends on: –
      Done when:
        - The 48 occurrences in `mains/**` are replaced by a working check or conversion, and pytest no longer
          emits `PytestAssertRewriteWarning` for them.

- [ ] T17: Clean up logging (found during T1)
      Goal: Log output is neither duplicated nor mixed with `print`.
      Priority: low | Depends on: –
      Done when:
        - `runtime.getLogger` does not add duplicate handlers on repeated calls.
        - `print()` calls in `aerobasic/ascii.py` and `devices/aerotech/task.py` use the logger.

- [ ] T18: Translate German identifiers and comments (found during T1)
      Goal: The code base follows the English-only language rule.
      Priority: low | Depends on: –
      Done when:
        - German identifiers (e.g. `run_testzweck_altesSystem`) and comments in active, non-legacy modules are
          translated, one module per commit.

- [ ] T19: Identify each and every todo and note in all of the documents
      Goal: Code should be free von notes and todo markers to enhance consistency in code structure. 
      Priority: low | Depends on: –
      Done when:
        - every todo and note section is identified and summerized in a new file 'todo_notes.md' . delete notes and todos in documentation and document the meaning of it in the file. Create workpackages from this in the same style as 'TODO.md' but save them on the bottom of 'todo_notes.md'.  

- [ ] T22: Fix NumPy 2.5 deprecation in `Attenuator` (found during T3)
      Goal: The attenuator keeps working with future NumPy versions.
      Priority: low | Depends on: –
      Done when:
        - `devices/attenuator.py:62` and `aerobasic/programs/drawings/lines.py:82` (`IFOV_Lines`, found during T7) use
          `reshape` instead of assigning `array.shape`, and the tests run without the `DeprecationWarning`.

- [ ] T23: Decide and implement axis validation for `SingleAxis` (found during T15)
      Goal: It is clear whether combining axes of different stages (and `~`, `^`, empty `&`) is an error.
      Priority: low | Depends on: –
      Done when:
        - The maintainer has decided whether mixed-stage combinations must raise `AxisError`. Note that
          `Aerotech3200.home()` uses `Axis.YZ | Axis.AB` on purpose.
        - Either the validation is implemented and the `xfail` on `test_prevent_mixed_axes` is removed, or the
          test is rewritten to the decided behaviour.

- [ ] T24: Fix `utils.visualization.plot_movements` (found during T15)
      Goal: Generated programs can be plotted for manual inspection.
      Priority: low | Depends on: –
      Done when:
        - `read_file`/`plot_movements` handle programs without movement, arcs (`CW`/`CCW`) and filled circles
          without exceptions (today they raise `ValueError`, `LinAlgError` or `AxisError`).
        - The "Could not plot" warnings in `test/test_aerobasic` are gone, and a test asserts that plotting works.

- [ ] T25: Fix argument passing in experiment scripts (found during T10)
      Goal: Restarting an experiment and passing substrate information work as intended.
      Priority: medium | Depends on: –
      Done when:
        - `mains/restart_experiment.py` creates a logger from the stored log file path instead of passing the path
          string as `logger`.
        - `default_exp_file.binary_testprint(substrate=...)` passes the substrate information to `Experiment`.
        - A dummy-backend test restarts an experiment from its stored `experiment_dictionary.json`.

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

