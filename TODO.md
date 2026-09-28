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
- [ ] T2: Design the dummy hardware backend [group: testing-infrastructure]
      Goal: An approved design for a simulated hardware backend exists before implementation starts.
      Priority: high | Depends on: T1
      Done when:
        - The design defines one `typing.Protocol` or ABC per device role, derived from the
          methods actually used: motion controller (both `devices/A3200` and
          `devices/aerotech.Aerotech3200`), attenuator, camera, DHM.
        - It defines a single, explicit backend switch, e.g. `System(..., backend="dummy")`.
          Real hardware is the default. An environment variable is at most a convenience override.
        - `Aerotech3200` is simulated at the transport (TCP/ASCII) level, so the generated
          AeroBasic command strings remain testable.
        - The dummy devices are specified as deterministic (seeded where needed), with no
          sleeps and no network access.
        - They keep internal state (positions, laser power, running tasks) and record every
          call in a call log.
        - They return plausible synthetic data (camera images, DHM phase images, stage
          positions), and the responses can be configured.
        - The design explains operation without `~/nanofactory.json`, and lazy imports of
          optional dependencies with a clear error message.
        - It describes the file layout and the impact on the public API.
        - The maintainer has approved the design.
      Notes: Present the design and STOP until approval (move to "Blocked" while waiting).

- [ ] T3: Implement the dummy hardware backend [group: testing-infrastructure]
      Goal: The whole package can run against simulated devices on any machine.
      Priority: high | Depends on: T2
      Done when:
        - The approved design is implemented, with type hints and English NumPy-style docstrings.
        - The dummy devices have their own tests covering state handling, call log and determinism.
        - The behaviour on real hardware is unchanged; the default backend is still real hardware.

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

## In Progress
<!-- Claude Code moves a todo here when starting work. -->
- [ ] T1: Record baseline and review the code [group: testing-infrastructure]
      Goal: The current state of the code and the test suite is documented before any change.
      Priority: high | Depends on: –
      Done when:
        - WORKLOG.md contains the baseline: per test file, collected / passed / failed / errors
          and the reason.
        - `docs/reviews/CODE_REVIEW_<YYYY-MM-DD>.md` exists, as a table with the columns
          severity (high/medium/low), `file:line`, issue, recommendation.
        - The review covers hardware coupling: devices opened in constructors or at import
          time, hardcoded IPs, ports and lab paths.
        - The review covers import-time side effects: `config.py` loading `~/nanofactory.json`,
          and hard imports of `mvImpact`, `OffAxisHolo`, `PlotFont`.
        - The review evaluates existing dummy, mock or simulation code
          (search: `rg -i "dummy|mock|fake|simulat|offline|virtual"`).
        - The review covers the state of the tests: scripts vs. test cases, outdated APIs,
          missing assertions, tests that depend on each other.
        - Every finding not covered by T2–T8 has its own todo.
      Notes: Report only, no fixes. Legacy code (`old_to-delete/`, `new/`, `*_old.py`) is excluded.

## Blocked
<!-- Format: todo as above, plus the line "Blocked by: <reason or T<n>>". -->

## Done
<!-- Claude Code adds: - [x] T<n>: title — YYYY-MM-DD — 1–2 sentences on what changed — commits: `<sha>`, … -->