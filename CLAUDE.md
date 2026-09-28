# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`nanofactorysystem` is a Python 3 (3.12) package that drives the Femtika Laser Nanofactory, a two-photon-polymerization (2PP) laser direct-writing system, as a 3D printer. The hardware is an Aerotech A3200 motion controller (stages X/Y/Z and galvo scanner A/B) with a laser attenuator, a MatrixVision camera and a LyncéeTec DHM (digital holographic microscope). Most code only produces real results on the lab PC connected to that hardware.

Comments, docs and TODOs are often in German. `TODO.md` is the task list with the sections Open / In Progress / Blocked / Done; its format rules are in the comment at the top of the file. `ARCHIVE.md` holds archived completed tasks.


## Commands

```bash
python -m pip install .        # build/install package (pyproject.toml, setuptools)
python clean.py                # remove build/, dist/, *.egg-info, __pycache__
python -m pytest test/test_aerobasic            # hardware-free tests (AeroBasic program generation)
python -m pytest test/test_aerobasic/test_drawings/test_circles.py::TestCircles::test_single_circle
```

- Tests are `unittest.TestCase` classes, run with pytest. Only `test/test_aerobasic` and `test/test_utils` run without hardware. Tests under `test/devices`, `test/dhm`, `test/test_femtika`, `test/tools` and `test/test_system.py` talk to real devices, and many of them are plain scripts rather than test cases.
- Generated test programs are written to `test/_programs/` (gitignored).
- Experiment entry scripts in `mains/` import siblings as `from Experiments.… import …`, so run them with `mains/` as the working directory (e.g. `cd mains && python main.py`).
- Optional hardware and local dependencies (`mvImpact`, `OffAxisHolo`, `PlotFont`) are not installable from PyPI. The slicer also uses `trimesh`.

## Configuration

- `nanofactorysystem/config.py` loads `sysConfig` from `~/nanofactory.json`, which has `user:<name>` and `objective:<name>` sections (e.g. `"Zeiss 20x"`, `"Zeiss 63x"`). If the file is missing, only a warning is issued, so `System(...)` then fails on unknown user or objective.
- The YAML files in `config/` (Hydra layout) describe the same data but are not currently read by any Python code.
- Runtime parameters are passed as nested dicts (`sys_args` with sections `attenuator`, `controller`, `sample`, `focus`, `layer`, `plane`, `dhm`, `camera`). Each component takes its own section via `popargs`, and `Parameter` subclasses merge these into their `_defaults`.

## Architecture

**Hardware layer**
- `system.py` `System` aggregates `Camera`, `Dhm` (skipped when `sys_args["dhm"]["usage"]` is False) and `A3200` controller + attenuator (`devices/`). It also holds `a3200_new`, an `Aerotech3200` instance from `devices/aerotech/`.
- There are two controller interfaces:
  - `devices/A3200` is the older interface from Reinhard Caspary. It handles power/attenuator, z-line and the functions used by `tools/`.
  - `devices/aerotech.Aerotech3200` is the newer ASCII-protocol interface (`aerobasic/ascii.py`, TCP 127.0.0.1:8000). It sends AeroBasic commands through `.api` and runs `.pgm` files as controller tasks (`run_program_as_task`).
- `tools/` holds measurement algorithms built on the camera and DHM: `Focus`, `Layer` (resin interface detection), `Plane`, `Grid`, `Stitch`, and `Transform` (camera↔stage pixel/µm transforms).

**AeroBasic program generation** (`aerobasic/`)
- `AeroBasicAPI` (in `aerobasic/__init__.py`) exposes AeroBasic commands as Python methods. `AeroBasicProgram` (in `aerobasic/programs/__init__.py`) collects these commands as text lines and writes a `.pgm` file.
- `programs/setups.py` provides `DefaultSetup` (stages plus galvo, IFOV off) and `SetupIFOV` (Aerotech IFOV mode, objective-specific). The chosen setup changes which axes (`"XYZ"` vs `"ABZ"`) and accelerations are valid.
- `programs/drawings/` defines `DrawableObject`, the abstract base of every printable structure. A structure implements `iterate_layers(coordinate_system)`, which yields one `DrawableAeroBasicProgram` per layer. Each layer's coordinates pass through `devices/coordinate_system.CoordinateSystem`, which maps local µm coordinates to stage coordinates using an offset, a `ZFunction` (`StaticOffset`/`Plane`/`PlaneFit` from plane fitting) and `DropDirection` (the z sign, which differs per objective).
- `DrawableObject.to_json()` serializes the constructor arguments, which lets experiments be saved and restarted.
- Structure families:
  - `lines.py` (`Rectangle3D`, `Stair`, `Corner`, …)
  - `height_function_structures/` (gratings, lenses, DOEs built from `HeightFunctions` + slicer)
  - `hatch_generator.py`, `laser_segments.py`, `apertures.py` (reusable components)
  - `tile_manager.py` (stitching of structures larger than the FOV)
- The directories `old_to-delete/` and `new/` and the files `*_old.py` are legacy or experimental code, not the active path.
- `aerobasic/slicer/` is a separate mesh/heightmap → toolpath pipeline (`pipeline.slice_geometry`). It is a self-contained port of `tpp_slicer`, and its layout is described in `tree_overview_slicer.txt`.

**Experiment orchestration** (`experiment.py`)
- `Experiment` is a context manager that owns a `System`. It lays out a grid of structures inside the resin-drop bounds, adding corner markers plus a QR code (the experiment UUID) unless `skip_corner=True`.
- Typical flow:
  1. `plot_experiment()`
  2. `plane_fit()`, which measures the substrate surface at sample points
  3. `opl_scan()`, only when the DHM is used
  4. `add_structure(StructureType, name, axes, power, structure=DrawableObject)`
  5. `build_programs()`, which writes per-layer `.pgm` files and `structures.json`
  6. `print_experiment()`, which runs each layer as an A3200 task and tracks progress
- `restart_experiment()` and `mains/restart_experiment.py` resume from the saved `experiment_dictionary.json` and `structures.json`.
- Experiment outputs (the JSON files, `calibration_file.npy`, logs and programs) go into the `path` passed in, which is usually a lab-PC path.

**Experiment scripts** (`mains/`)
- `mains/Experiments/**` holds one script per experiment. Each defines a function like `print_file(absolute_center, resin_dimension, path, objective, user, dhm_usage, setup, ...)`, which builds `sys_args` and objective-specific parameters (FOV, zMax, drop direction, corner sizes) and runs the `Experiment` flow.
- `mains/Experiments/default_exp_file.py` is the template for these scripts.
- `mains/main.py` selects one of these functions by import and supplies the resin edge coordinates and center for the current substrate.

## Maintainer Instructions (Hannes)

### Language
Everything is written in English: variable, function and class names, docstrings, comments,
commit messages, documentation, and log entries. If you encounter German identifiers or
comments within the scope of your current task, translate them. Outside that scope,
add a todo instead of renaming them unasked.

### Session start
1. Read `## Current Status` and `## Status Update Anchor` in this file.
2. Read `TODO.md` and pick a task. Prefer the one named as the next task in `## Current Status`.
3. Read the most recent entries in `WORKLOG.md`.

### Work log (mandatory)
After every completed task, and before ending a session even if the task is unfinished,
append an entry to `WORKLOG.md`.

- Get the timestamp from the system: `TZ=Europe/Berlin date "+%Y-%m-%d %H:%M %Z"`. Never guess it.
- The log is append-only. Put the newest entry at the bottom. Never edit past entries.
- Write one entry per task. List **every** file that was created, modified, deleted or renamed.

Format:
```
### <YYYY-MM-DD HH:MM TZ> — [<Todo ID>] <Short task title>
- **Status:** done | partial | blocked
- **Changes:**
  - `path/to/file.py`: what changed and why
  - `path/to/new_file.py` (new): purpose
  - `path/to/old_file.py` (deleted | renamed → `new/path.py`)
- **Tests:** what was run and the result, or "none" with the reason
- **Commits:** `<short SHA>` <commit subject line>, … (or "uncommitted — proposed message:" followed by the full message)
- **Follow-ups:** open points or new todos created
```

### Definition of Done
A task counts as done only if all of the following hold:
- All acceptance criteria stated in the todo are met.
- The code runs, and existing tests pass. New logic has tests where that is feasible.
- Public functions and classes have English docstrings (NumPy style).
- No new `TODO`/`FIXME` related to the task remains in the code.
- The change is committed and logged in `WORKLOG.md`.

If a task does not meet this, mark it `partial` in the log and describe the remaining gap.

### Todos
- Follow the format rules at the top of `TODO.md`.
- When you start a todo, move it to "In Progress". If it cannot proceed, move it to "Blocked"
  and state the reason.
- When a todo meets the Definition of Done, move it to "Done" with the date, 1–2 sentences
  and the commit SHAs. Never move entries to `ARCHIVE.md`; the status review routine does that.
- If a todo is only partially done, keep it in "In Progress" and add a follow-up todo that
  describes the remaining gap.
- If you discover new problems, add them to "Open" and tag them with `(found during T<n>)`.

### Commits (mandatory)
- Commit after every completed task and after every coherent sub-step of larger tasks.
- One logical change per commit. Do not mix refactoring, formatting and feature work.
- Always write a complete commit message in this format (Conventional Commits):
```
  <type>(<scope>): <imperative summary, max. 72 chars> [<Todo ID>]

  <Body: what changed and why, wrapped at 72 chars. Mention design
  decisions and side effects. No restatement of the diff.>

  Files:
  - path/to/file.py: short description of the change
  - path/to/new_file.py (new): purpose

  Refs: <Todo ID>
```
  - `type` is one of: `feat`, `fix`, `refactor`, `test`, `docs`, `perf`, `build`, `chore`.
  - `scope` is the affected module or package, e.g. `slicer`, `tiling`, `aerobasic`.
  - Add `BREAKING CHANGE: <description>` as a footer if a public API changes.
- If you cannot or should not commit, do not commit. This applies to failing tests, unrelated
  uncommitted changes in the working tree, and cases where the maintainer said not to commit.
  Still generate the full commit message: print it at the end of your response and record it
  in WORKLOG.md.
- When working on a feature branch, also generate a pull request title and description:
  Summary, Changes (with files), How it was tested, Linked todos, Open points.
- Do not push, amend, rebase or force-push unless explicitly instructed.
- Do not edit `## Status Update Anchor` or `## Current Status`. These sections are maintained
  exclusively by the status review routine.

### Testing conventions
- `python -m pytest` must pass without hardware, without `~/nanofactory.json`, and without
  `mvImpact` or `OffAxisHolo`. Tests that need the lab are marked `hardware` and only run
  with `--run-hardware`.
- Never make a test pass by weakening or deleting assertions without justification.
  If a test reveals a real bug, fix it in a separate `fix:` commit if the fix is small and clear.
  Otherwise, mark the test `xfail(reason=..., strict=True)` and add a todo.
- Every moved, converted or removed test is justified in WORKLOG.md and reflected in
  `test/README.md`.
- Tests write only to `tmp_path` or `test/_programs/`.
- Keep existing `unittest.TestCase` classes. New tests may use plain pytest style with fixtures.
- Never modify legacy code (`old_to-delete/`, `new/`, `*_old.py`). Exclude it from collection.
- Real hardware is always the default backend. The dummy backend is opt-in.