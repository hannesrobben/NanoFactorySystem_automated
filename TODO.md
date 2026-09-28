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
- [ ] T3: Implement the dummy hardware backend [group: testing-infrastructure]
      Goal: The whole package can run against simulated devices on any machine.
      Priority: high | Depends on: T2
      Done when:
        - The approved design is implemented, with type hints and English NumPy-style docstrings.
        - The dummy devices have their own tests covering state handling, call log and determinism.
        - The behaviour on real hardware is unchanged; the default backend is still real hardware.

- [ ] T15: Repair failing hardware-free unit tests (found during T1) [group: testing-infrastructure]
      Goal: The existing unit tests for AeroBasic generation and units pass again, or fail visibly as known bugs.
      Priority: high | Depends on: –
      Done when:
        - Every failure in `test/test_aerobasic/test_constants.py`, `test_program.py`,
          `test_drawings/test_corners.py` and `test/test_utils/test_units.py` (baseline B in
          WORKLOG.md) is resolved: the test is updated to the current API with a justification,
          the code is fixed in a separate `fix:` commit, or the test is `xfail(strict=True)` with a todo.
        - `test_program.py` no longer depends on leftover state in `test/_programs/` and starts no
          non-daemon threads.
      Notes: Blocks T5 (`python -m pytest` must pass). Details: `docs/reviews/CODE_REVIEW_2026-09-28.md` §5.

- [ ] T4: pytest configuration and shared fixtures [group: testing-infrastructure]
      Goal: The test suite has a consistent configuration and separates hardware tests cleanly.
      Priority: high | Depends on: T3
      Done when:
        - `[tool.pytest.ini_options]` in `pyproject.toml` defines `testpaths`, the markers
          `hardware` and `slow`, and `norecursedirs` for `_programs`, `manual` and the legacy
          directories.
        - `test/conftest.py` provides the `--run-hardware` option; `hardware` tests are
          skipped without it, with a clear reason.
        - `test/conftest.py` provides the fixtures `dummy_system`, `dummy_controller`,
          `tmp_program_dir` and `test_config`.

- [ ] T5: Triage and convert the device tests [group: testing-infrastructure]
      Goal: `python -m pytest` passes without hardware, and every test has a clear purpose.
      Priority: high | Depends on: T4
      Done when:
        - Every file in `test/devices`, `test/dhm`, `test/test_femtika`, `test/tools` and
          `test/test_system.py` (and the slicer tests, if any) is handled in one of three ways:
          converted into dummy-based test cases, marked `hardware` with real assertions, or
          moved to `test/manual/` (excluded from collection).
        - The reason for each decision is recorded in WORKLOG.md.
        - `python -m pytest` passes on a machine without hardware, without
          `~/nanofactory.json`, and without `mvImpact` or `OffAxisHolo`.
        - `python -m pytest -m hardware --run-hardware` collects the hardware tests.

- [ ] T6: Dry-run an experiment with the dummy backend [group: testing-infrastructure]
      Goal: Experiment scripts can be tested end to end without the lab.
      Priority: medium | Depends on: T3
      Done when:
        - `mains/Experiments/default_exp_file.py` runs end to end with the dummy backend:
          `plane_fit()`, then `build_programs()`, then `print_experiment()`.
        - An integration test covers this dry run and writes only to `tmp_path`.

- [ ] T7: Golden-file tests for AeroBasic generation [group: testing-infrastructure]
      Goal: Unintended changes in the generated `.pgm` programs are detected automatically.
      Priority: medium | Depends on: T4
      Done when:
        - The generated `.pgm` text of representative structures is compared against stored
          reference files, for both `DefaultSetup` and `SetupIFOV`.
        - There is a documented way to regenerate the references deliberately
          (e.g. `--update-golden`).

- [ ] T8: Write `test/README.md` and update the documentation [group: testing-infrastructure]
      Goal: Anyone new understands why each test exists and how to run the test suite.
      Priority: medium | Depends on: T5, T6, T7
      Done when:
        - `test/README.md` explains the test categories: unit (no hardware), dummy
          integration, hardware, manual.
        - For each category, a table lists module, what it tests, why it matters (which
          failure it catches), and requirements.
        - The README documents how to run each category, the markers and `--run-hardware`,
          how to use the dummy backend (with an example test), and where generated artefacts
          go (`test/_programs/`, `tmp_path`).
        - The `## Commands` and `## Architecture` sections in CLAUDE.md are updated.
          `## Current Status` and `## Status Update Anchor` are left untouched.

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

- [ ] T9: Fix packaging and pin a working environment (found during T1)
      Goal: `pip install .` installs a complete, importable package on a fresh machine.
      Priority: high | Depends on: –
      Done when:
        - `pyproject.toml` uses package discovery, so all subpackages are installed.
        - All dependencies imported by active modules (`scipy`, `shapely`, `trimesh`, `qrcode`, `h5py`, …)
          are declared, hardware-only packages are optional extras, and the versions are compatible with
          NumPy 2 (e.g. `opencv-python>=4.10.0.84`).
        - A fresh virtual environment with `pip install .[test]` can run `python -m pytest`.
      Notes: The global interpreter on the lab PC currently fails to import the package (NumPy ABI). Details: `docs/reviews/CODE_REVIEW_2026-09-28.md` §2.

- [ ] T10: Fix defects in the experiment flow (found during T1)
      Goal: The experiment flow handles the DHM OPL scan and failed layers correctly.
      Priority: high | Depends on: T3
      Done when:
        - `Experiment.opl_scan` calls an existing `Dhm` method (`motorscan`), and a dummy-backend test covers it.
        - A failed controller task during `print_structure` is recorded in the progress log instead of
          aborting via an uncaught `ValueError`, and a test covers it.
        - Existing `substrate_information.json` is merged instead of silently discarding new data.
        - An empty layer list does not raise `UnboundLocalError`.
      Notes: Details: `docs/reviews/CODE_REVIEW_2026-09-28.md` §4.

- [ ] T13: Add timeouts to hardware communication and wait loops (found during T1)
      Goal: A missing or unresponsive device leads to a clear error instead of a hang.
      Priority: medium | Depends on: T3
      Done when:
        - TCP connects (A3200, DHM) and receives use configurable timeouts; `send()` reads until the
          terminating character.
        - The polling loops in `aerotech_old.py` (`drivestatus`, `zline`) and `task.py`
          (`wait_to_finish`, `finish`) have an upper time bound.
        - Dummy-backend tests cover the timeout paths.
      Notes: Details: `docs/reviews/CODE_REVIEW_2026-09-28.md` §1, §4.

- [ ] T14: Remove the hardcoded calibration path from `IFOV_Lines` (found during T1)
      Goal: Drawing classes do not read lab files.
      Priority: medium | Depends on: T3
      Done when:
        - `IFOV_Lines` receives calibration data (or an attenuator) instead of opening
          `C:/Software/3DPoli Fabrication/Calibration/Calibration.dat` itself.
        - A test generates an `IFOV_Lines` program without the lab file.
      Notes: Details: `docs/reviews/CODE_REVIEW_2026-09-28.md` §1.

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

## In Progress
<!-- Claude Code moves a todo here when starting work. -->

## Blocked
<!-- Format: todo as above, plus the line "Blocked by: <reason or T<n>>". -->

## Done
<!-- Claude Code adds: - [x] T<n>: title — YYYY-MM-DD — 1–2 sentences on what changed — commits: `<sha>`, … -->
- [x] T1: Record baseline and review the code — 2026-09-28 — Recorded the test baseline (global env: all 40 files fail on a NumPy ABI mismatch; clean venv: 16 passed / 20 failed / 16 errors over `test/`) in WORKLOG.md and wrote `docs/reviews/CODE_REVIEW_2026-09-28.md`; follow-ups T9–T18 added. — commits: `bf98f78`

- [x] T2: Design the dummy hardware backend — 2026-09-28 — Wrote `docs/design/DUMMY_BACKEND.md` (seam/role protocols, explicit `backend=` switch, socket-level fake controller, deterministic simulated world with call log); approved by the maintainer with three decisions (controller merge later as T20, no env var, `plane_fit(plane=...)` instead of simulated detection). — commits: `46ae4b1`, `b6340a4`

- [x] T12: Rename `devices/aerotech_old.py` to `devices/a3200.py` — 2026-09-28 — Pure `git mv` plus the import in `devices/__init__.py`; hardware-free test results unchanged (16 passed / 11 failed / 3 errors, as in baseline B). — commits: `6b43511`

