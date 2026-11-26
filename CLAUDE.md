# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`nanofactorysystem` is a Python 3 (3.12) package that drives the Femtika Laser Nanofactory, a two-photon-polymerization (2PP) laser direct-writing system, as a 3D printer. The hardware is an Aerotech A3200 motion controller (stages X/Y/Z and galvo scanner A/B) with a laser attenuator, a MatrixVision camera and a LyncéeTec DHM (digital holographic microscope). Most code only produces real results on the lab PC connected to that hardware.

Project files:
- `TODO.md`: the task list with the sections Open / In Progress / Blocked / Done; its format rules and the phase plan are at the top of the file. `ARCHIVE.md` holds archived completed tasks (created by the status review routine when it first archives).
- `future_todo.md`: planned but unscheduled ideas (F<number>). Never implement them unless they are moved into `TODO.md`.
- `todo_notes.md`: inventory of the code markers N001–N095 removed in T19, with their meaning and original locations. Reference only.
- `WORKLOG.md`: append-only work log (see "Work log").
- `docs/system/SOFTWARE_PLAN_OVERVIEW.md`: the plan for the four cooperating repositories (this one, OffAxisHolo, DHMConnect, MIRA). This repository holds the **master copy**.
- `docs/design/`: approved design documents. `docs/reviews/`: code review and metadata audit.

Some experiment scripts in `mains/` and the scripts in `test/manual/` still contain German comments (T99).

## System context

This repository is one of four that together build a 2PP system with real-time feedback from the DHM. Ownership (details in `docs/system/SOFTWARE_PLAN_OVERVIEW.md`):

| Package | Repository | Owns |
|---|---|---|
| `nanofactorysystem` (this one) | NanoFactorySystem_automated | Runs on the **Work-PC (control node)**. Orchestration, information model (material registry = master of refractive indices, substrate, experiment, structure), measurement recipes, capture-position plan generator (`GroupSpec`), target rasteriser (`LayerTarget`), calibration writing field ↔ camera ↔ DHM, focus from the corner markers, operating modes, later the controller, `experiment.h5` (single writer), camera live feed, system GUI incl. DHM + stage operation. |
| `offaxisholo` | OffAxisHolo (branch `Holo_HR`) | Reconstruction of one hologram stack on the DHM-PC (golden reference offline, GPU kernel in the service), frame metrics, parameter sets, analysis GUI (observer only). |
| `dhmconnect` | DHMConnect | Protocol v1 between Work-PC and DHM-PC (groups `open_group` / `measure` / `close_group`), the DHM service on the DHM-PC (compute node), the client used here. Replaces protocol v6 / `DhmServ` / `nanofactorysystem.dhm` once the maintainer switches. |
| `mira` | MIRA | On the DHM-PC: registration, speckle fusion, stitching, levelling → stitched `LayerProduct`. Here: `evaluate_layer` (comparison with the target, `DeviationReport`, G6). |

Rules that follow from this:
- No reconstruction, registration, fusion or stitching code in this repository. Call `dhmconnect` and `mira` through adapters.
- `dhmconnect` and `mira` are optional dependencies: `python -m pytest` passes without them (fakes in the dummy backend).
- The legacy DHM path (`Dhm`, `DhmClient`, protocol v6) and the hologram counts 10 / 20 / 1 stay the default until the maintainer switches. Golden command logs must not change in the legacy mode.
- Only the experiment process on this PC writes `experiment.h5`. The DHM-PC delivers, this side stores (design decision T42).
- Shared contracts (`CaptureContext`, `MeasurementRecipe`, `ProductSet`, `LayerTarget`, `DeviationReport`, …) are defined in DHMConnect (`dhmconnect/schemas/`); this repository vendors their example messages as test fixtures. Conventions: units in names (`_um`, `_rad`, `_s`, `_mw`), `schema_version` in every message, never `pickle` across a process or network boundary.
- Decisions of 2026-11-18 (master plan v0.4, "Decided" table in `TODO.md`): the default DHM result per structure and layer is the stitched `LayerProduct`; member products and raw data stay on the DHM-PC and are referenced; the full parameter set is stored once per `config_hash`; no silent defaults for physical parameters. Design decision IDs are `SI1–SI4` (T71) and `OM1–OM5` (T72).
- Files that leave the active code go to the local, Git-ignored `attic/` after approval and are listed in `docs/ATTIC_INDEX.md` (procedure X-B, master plan §9 rule 8).
- Todo IDs of the other repositories may be referenced as dependencies: `K…`/`L…` (OffAxisHolo), `DL-…` (DHMConnect), `MI-…` (MIRA).


## Commands

```bash
python -m pip install ".[test]"   # install package with all subpackages and test dependencies (pyproject.toml)
python clean.py                # remove build/, dist/, *.egg-info, __pycache__
python -m pytest               # all tests without hardware (unit + dummy backend); hardware tests are skipped
python -m pytest test/devices/test_aerotech.py::test_zmax_safety   # a single test
python -m pytest -m "not slow"                  # skip the ~10 s experiment dry run
python -m pytest -m hardware --run-hardware     # hardware tests, only on the lab PC
python -m pytest test/test_aerobasic/test_golden_programs.py --update-golden   # re-record golden programs
```

- `test/README.md` describes every test module, the categories (unit, dummy integration, hardware, manual), the fixtures and how to use the dummy backend. Keep it up to date when adding, moving or removing tests.
- pytest configuration is in `pyproject.toml` (`testpaths = ["test"]`; `test/manual/`, `_programs` and legacy directories are excluded). Markers: `hardware` (skipped without `--run-hardware`), `slow`. Shared fixtures are in `test/conftest.py`: `test_config`, `dummy_backend`, `dummy_controller`, `dummy_system`, `no_sleep`, `tmp_program_dir`, `golden`, `lab_user`.
- `python -m pytest` must pass without hardware, without `~/nanofactory.json` and without `mvIMPACT`/`OffAxisHolo`. The environment needs NumPy-2-compatible builds (`opencv-python>=4.10.0.84`, pinned in `pyproject.toml`); an older OpenCV fails with `numpy.core.multiarray failed to import`.
- Generated program references for golden tests are `test/golden/*.txt`; other test output goes to `tmp_path`, or `test/_programs/` (gitignored) for manual inspection.
- Experiment entry scripts in `mains/` import siblings as `from Experiments.… import …`, so run them with `mains/` as the working directory (e.g. `cd mains && python main.py`).
- Optional hardware and local dependencies (`mvIMPACT`, `OffAxisHolo`, `PlotFont`) are not installable from PyPI; `mvIMPACT` is imported on first use of the real camera. The slicer also uses `trimesh`, `shapely` and `h5py`.

## Configuration

- `nanofactorysystem/config.py` loads `sysConfig`, which has `user:<name>` and `objective:<name>` sections (e.g. `"Zeiss 20x"`, `"Zeiss 63x"`). Lookup order: `use_config(path_or_dict)` (context manager, swaps the content in place), `$NANOFACTORY_CONFIG`, `~/nanofactory.json`, then the built-in `DEFAULT_CONFIG` (devices and both objectives, no users, no calibration file) with a warning.
- Class defaults of `System`, `A3200`, `Attenuator`, `Camera`, `Dhm` are `ConfigDefaults(section, {...})` descriptors, resolved on access (deep copy), so importing the package never reads config sections.
- The YAML files in `config/` (Hydra layout) describe the same data but are not currently read by any Python code. `config/voxel_seed.csv` is the seed of the voxel database.
- Data locations: `user:<name>.dataRoot` (experiment data root, default `~/Documents/Femtika_Experiment/<user>`), `system.voxelDatabase` (default `~/Documents/Femtika_Experiment/voxels.sqlite`), `system.syncFolderNames` (folder names refused as data location, default Seafile/OneDrive/Dropbox); `user:<name>.initials` for substrate labels.
- Runtime parameters are passed as nested dicts (`sys_args` with sections `attenuator`, `controller`, `sample`, `focus`, `layer`, `plane`, `dhm`, `camera`). Each component takes its own section via `popargs`, and `Parameter` subclasses merge these into their `_defaults`. `Parameter` works on a copy of each section, so a `sys_args` dict can be reused.

## Architecture

**Hardware layer**
- `system.py` `System` aggregates `Camera`, `Dhm` (skipped when `sys_args["dhm"]["usage"]` is False) and the `A3200` controller + attenuator (`devices/`). `System.controller` and `System.a3200_new` are the same object.
- One controller class since T20: `devices/a3200.py` `A3200(Parameter, AerotechController)`.
  - All commands go through one `aerobasic/ascii.py` `AerotechAsciiInterface` (`.api`, TCP 127.0.0.1:8000), which records the command history (`save_log()` → `A3200.log`).
  - Config-based µm helpers used by `System` and `tools/`: `moveabs`, `moveinc`, `position`, `wait`, `power`, `pulse`, `laseron/off`, `zline`, `home(axes)`, `container`; `run()` sends a raw command.
  - Program tasks from `devices/aerotech.AerotechController` used by `Experiment`: `run_program_as_task` (loads `.pgm` files as controller tasks), `xyz`, `axis_status`, `save_log`.
  - Safety: the helpers check `zMax` (and close the connection when exceeded); in addition, `api.z_limit` refuses immediate absolute Z moves beyond `zMax` sent through `.api` (maintainer decision). Programs run as tasks are not checked.
  - Program tasks (T127/T128): `run_program_as_task` loads every program under a fresh name `nfs_<session>_<counter>_<stem>.pgm` (T152: a refused LOAD blocks only its own name on the controller, even for valid content, so a fixed name blocked every later layer); `Task.finish()`/`Task.abort()` remove it under that name and the execution copy is deleted; names not removed yet are in `exec_programs`. A refused LOAD carries the text of `~LASTERROR`; `PROGRAM LOAD` waits at most `controller.loadTimeout` (default 600 s; then the connection is reopened). A task error is reported with the decoded error code, and a program that reports complete before its last non-empty line raises `TaskFailedError` (early end). After any failure the task is stopped and the program removed.
  - `devices/aerotech.Aerotech3200` is the same task handling without user/config (e.g. for scripts and `test_femtika`), with an optional `z_max` and its own `home()` sequence.
  - `AerotechError` is a `RuntimeError`; `TaskFailedError` (a failed or stalled task) is also a `ValueError`.
- DHM, legacy path (default until the switch to `dhmconnect`): `devices/dhm.Dhm` wraps `dhm/dhmclient.DhmClient`, which talks protocol v6 (binary, lockstep, one client, no request ids) to `DhmServ.exe` on the DHM-PC (`192.168.22.2:27182`, config section `dhm`); objective selection via `dhmId` (Zeiss 20x = 178, Nikon 20x = 179, Zeiss 63x = 180). Exposure optimisation (`dhm/optimage.py`) and the OPL scan (`dhm/motorscan.py`) run on this PC and fetch every image over the network. `Experiment.measure()` stores the raw hologram stack per capture; `ExperimentStore.add_dhm_product()` is the prepared receiving side for reconstructed products. The Koala pixel size of configuration 180 is wrong for 63x (finding B17): never take a pixel size for reconstruction from the device parameters.
- `tools/` holds measurement algorithms built on the camera and DHM: `Focus`, `Layer` (resin interface detection), `Plane`, `Grid`, `Stitch`, and `Transform` (camera↔stage pixel/µm transforms).

**Hardware backends** (`backends/`, design in `docs/design/DUMMY_BACKEND.md`)
- `System(..., backend=...)` and `Experiment(..., backend=...)` select the backend explicitly: `None`/`"real"` (default, lab hardware) or `"dummy"`/a `DummyBackend` object. There is no environment variable. The backend only replaces the seams that touch hardware; all facades stay the real classes. The device classes take matching keyword-only injection parameters: `A3200(transport=, program_dir=)`, `AerotechAsciiInterface(transport_factory=)`, `Aerotech3200(transport_factory=, program_dir=)`, `Camera(driver=)`, `Dhm(driver=)`.
- `backends/protocols.py` defines the role protocols (what `System`/`tools`/`Experiment` use) and seam protocols (what a backend provides). Extend them when a consumer starts using a new device method.
- `backends/dummy/`: one deterministic `SimulatedWorld` (stage, laser, exposures, tasks, virtual clock, seeded RNG, `CallLog`) shared by `FakeA3200Transport` (socket-level ASCII controller with a small AeroBasic interpreter for program tasks), `DummyCameraDriver`, `DummyDhmClient` and a synthetic attenuator calibration file. Plane detection is not simulated: dry runs pass a known plane via `Experiment.plane_fit(plane=...)`. New AeroBasic commands used by generated programs must be added to `FakeA3200Transport.execute()` (the dry-run test checks that every statement is simulated).

**AeroBasic program generation** (`aerobasic/`)
- `AeroBasicAPI` (in `aerobasic/__init__.py`) exposes AeroBasic commands as Python methods. `AeroBasicProgram` (in `aerobasic/programs/__init__.py`) collects these commands as text lines and writes a `.pgm` file.
- `programs/setups.py` provides `DefaultSetup` (stages plus galvo, IFOV off) and `SetupIFOV` (Aerotech IFOV mode, objective-specific). The chosen setup changes which axes (`"XYZ"` vs `"ABZ"`) and accelerations are valid.
- `programs/drawings/` defines `DrawableObject`, the abstract base of every printable structure. A structure implements `iterate_layers(coordinate_system)`, which yields one `DrawableAeroBasicProgram` per layer. Each layer's coordinates pass through `devices/coordinate_system.CoordinateSystem`, which maps local µm coordinates to stage coordinates using an offset and a `ZFunction` (`StaticOffset`/`Plane`/`PlaneFit` from plane fitting). `DropDirection` (UP for 20x, DOWN for 63x) never changes z coordinates; it reverses the layer print order and selects the plane interface, the resin layer in the scanner and the QR pixel-line direction (all places are listed in its docstring). The tools get it as `sys_args["layer"]["dropDirection"]`.
- `DrawableObject.to_json()` serializes the constructor arguments (with `__module__`; enums, points and calibrations are encoded reversibly), and `drawings.base.structure_from_json()` rebuilds the structure. A parameter stored under another attribute name is declared in `_json_attributes`; a parameter that cannot be stored is reported (warning, `__missing__`).
- Structures that set the laser power in mW (`IFOV_Lines` and the IFOV structures built on it) convert it with a `devices/power_calibration.PowerCalibration`: an explicit `calibration=` argument, else the one activated with `power_calibration(...)` (`Experiment.build_programs()` activates the running system's attenuator calibration), else `attenuator.calibrationFile` from the config.
- Structure families:
  - `lines.py` (`Rectangle3D`, `Stair`, `Corner`, …)
  - `height_function_structures/` (gratings, lenses, DOEs built from `HeightFunctions` + slicer)
  - `hatch_generator.py`, `laser_segments.py`, `apertures.py` (reusable components)
  - `tile_manager.py` (stitching of structures larger than the FOV)
- The directories `old_to-delete/` and `new/` and the files `*_old.py` are legacy or experimental code, not the active path.
- `aerobasic/programs/optimize.py` (T130): `optimize_lines()` / `optimize_file()` / `python -m nanofactorysystem.aerobasic.programs.optimize <file>` shorten a program without changing the exposed path beyond `decimals` (default 5 = 10 nm): trailing zeros, modal feed rates, unchanged axis words and empty moves are dropped, consecutive collinear LINEAR moves merged; lines with variables and commands that may move an axis reset what is known. Not a build default (maintainer decision); the golden programs shrink by 37-53 % in bytes.
- `aerobasic/slicer/` is a separate mesh/heightmap → toolpath pipeline (`pipeline.slice_geometry`). It is a self-contained port of `tpp_slicer`, and its layout is described in `tree_overview_slicer.txt`.

**Voxel database** (`voxel/`, design in `docs/design/VOXEL_DATABASE.md`)
- `VoxelDatabase` (SQLite, schema version in `PRAGMA user_version`, migrations in `voxel/migrations.py`) stores measured voxel widths/heights per material, objective, setup, power and velocity; `voxel_size()` returns an exact hit, a 2-D linear interpolation in (ln P, ln v) inside the convex hull, or a 1-D dose fallback for collinear data, else None (no extrapolation). CSV import/export; `*.sqlite` is not versioned.
- Material registry (T75, design `docs/design/INFORMATION_MODEL.md`): the same SQLite file (schema version 3) holds materials (`kind` resin / substrate / medium) with extensible properties (`material_property`: key, value, unit, wavelength, state uncured/cured_in_resin/cured_developed/any (T108; legacy `cured` → `cured_in_resin`), source, date); API `voxel/materials.MaterialRegistry`, seed `config/material_seed.csv` (SZ2080 at 674.994 nm), `Material.require_refractive_index` / `contract_snapshot` raise `MissingPropertyError` instead of a default (G7), `MaterialRegistry.export_json` writes the versioned offline export for OffAxisHolo / MIRA. `Experiment(materials=, material_registry=)` / `ExperimentSpec.materials` / `SubstrateSpec.material` (registry name of the resin, or the old dict) name the materials; a new experiment file stores a `MaterialSnapshot` per role in `/metadata/materials` (schema 1.1). Without `material_registry` the default database is used only if the file exists; tests never see it (autouse fixture in `test/conftest.py`).
- Voxel-aware slicing (T54): `voxel/model.py` has the voxel models `NoVoxelData`, `FixedVoxelModel` and `DatabaseVoxelModel` (material, objective, setup); the slicer only knows the protocol `aerobasic/slicer/voxel.VoxelModel`. `slice_geometry(..., voxel_model=)` / `Model3D_Slicer(voxel_model=, power=)` / `ExperimentSpec(voxel_material=)` compensate with the voxel size of the job's power and velocity (`slicer/voxel.compensate`): contour offset by half the width, first/last slice half a height inside the part (`SlicingParameters.voxel_height_um`), and spacing per `SlicingParameters.spacing_mode` — `"voxel_overlap"` (default, maintainer decision: spacing = voxel size × (1 − `voxel_overlap`)) or `"static_hatching"` (given spacing, gaps only warned). Strategies get a `voxel=` `VoxelContext`. The values used are in `job.meta["voxel"]`, `Model3D_Slicer.to_json()["voxel"]` and the summary. Without a model or data nothing changes (golden files).

**Standard test prints** (`testprint/`, phase 11, design `docs/design/TEST_PRINT_PTD01.md`, approved 2026-11-25)
- A test field (50 × 50 µm, cells with their own power / z / hatch / slice distance, header strip with L mark, 3-bit id and REF pad) is one `DrawableObject`. No module imports `experiment`; existing code was not changed for it (maintainer decision; merging the duplicated IR → IFOV translation is F18).
- `structure.ParameterFieldStructure(builder, arguments, objective=, power_mw=, dwell_after_power_s=)`: built from a registered field builder (name + JSON arguments, `register_field_builder`), so `to_json()` / `structure_from_json` and restarts rebuild the same programs; one IFOV layer program per z level (ascending, z rounded to 1 nm), one block per run of equal power and leaf kind, element order kept; optional `DWELL` after a power change (D9, lab check T148).
- `cells`: primitives (`line`, `line_set`, `polyline`, `dot` (short in-plane line), `suspended_line`, `woodpile`, `sliced`) and analytic height maps; `sliced` uses `slice_geometry` with `voxel_height_um=0` so planes lie on `k·Δz` (cells with the same Δz share layers) and anchors volume cells by repeating the first slice down to `anchor_depth_um` (D15: 1.5 µm); identical maps are sliced once (cache).
- `field.ParameterField` (merge by z, validation listing every problem, cell table / CSV, plot), `ordering` (in-layer order as named strategy, default `row_by_row`, D16), `voxel_fit.VoxelFitModel` (w(P), l(P); kinds `threshold_ln`, `power_law`, `tabulated`; no extrapolation; slicer `VoxelModel` protocol), `calibration.ProcessCalibration` (JSON file; a source starting with "example" is refused for real prints).
- Evaluation: `analysis/experiment_analysis/ptd.py` (cell table from `/spec`, voxel import) and `voxel_fit.py` (fit, calibration file).
- **Version 2 (current, design `docs/design/PARAMETER_TESTS.md`):** single-stage parameter tests on absolute axes; nothing about the material (threshold, voxel size) is needed to print and the voxel database is never read. `inputs.ParameterTestInputs` (material start file, schema `nanofactory.parameter_tests/1`) is the only input; `parameter_tests` builds Quick PT (`quick_pt.walls`, `quick_pt.pads`), Full PT-01 (`full_pt01.f1` … `f7`) and Voxel PT-01 (`voxel_pt01.gap`, base / gap / lid) in 60 µm fields split into sub-fields a (0.1–0.5 mW) and b (0.6–1.0 mW); `pt_factories` registers the factories. Scripts: `mains/parametertest/` (`quick_pt.py`, `full_pt01.py`, `voxel_pt01.py`, `chain.py`, README per test; margin 90 µm and `check_marker_clearance` keep QR code and corners 20 µm away from every grid). Evaluation: `ptd.add_relative_columns` (P/P_th, h/w, Δz/l after the measurement), `ptd.voxel_lengths_from_gaps`, `voxel_fit.points_from_parameter_tests`. The two-stage version 1 (`ptd01`, `factories`, `StageAAxes`, `mains/Experiments/ptd01/`, golden `ptd01_f3.txt`) is in the attic (T164, `docs/ATTIC_INDEX.md`).

**Experiment orchestration** (`experiment.py`)
- `Experiment` is a context manager that owns a `System`. It lays out a grid of structures inside the resin-drop bounds, adding corner markers plus a QR code (the experiment UUID) unless `skip_corner=True`.
- Typical flow:
  1. `plot_experiment()`
  2. `plane_fit()`, which measures the substrate surface at sample points (or uses a given `plane=`); the points follow `plane_fit_mode` (`PlaneFitMode.GRID`/`CORNERS`/`BORDER`, old integers accepted), and `plane_fitting.py` (`sample_points`, `measure_plane`) also runs a single plane fit without `Experiment`. A warning is logged if the substrate height under a structure varies by more than `tilt_warning_um`
  3. `opl_scan()`, only when the DHM is used
  4. `add_structure(StructureType, name, axes, power, structure=DrawableObject)`; `layer_power=` (list or function of the layer id) makes every layer program set its own power (T31, stored as `layer_powers_mw`). `Model3D_Slicer` prints toolpath elements with a `power_mw` override (or from `power_map(z_um, role)`) in their own IFOV blocks
  5. `build_programs()`, which writes per-layer `.pgm` files and `structures.json`; it estimates and logs the printing time (`time_estimate.py`: path length / speed of every layer program plus `layer_overhead_s`, default 5 s; stored in `/time_estimate`), and the summary shows it next to the actual time (T28)
  6. `print_experiment()`, which runs each layer as an A3200 task and tracks progress; `measure()` takes DHM holograms (with DHM) and camera images only with `Experiment(camera_capture=True)` (default off); with `overview_capture=True` (default off) it also takes a stitched camera mosaic of the experiment area before and after printing (`overview.py`, `Experiment.capture_overview()`; with corners: rectangle incl. corners and QR code, with `skip_corner`: the structure grid; stored in `/overview/<phase>` and `overview_<phase>.png`, single images only with `overview_single_images`; T28)
- `restart_experiment()` and `mains/restart_experiment.py` resume from the progress in `experiment.h5`: every layer printed in an earlier session is skipped, so any number of aborts works. `parameters_from_dictionary()` reads the file (or the JSON of an old folder) and sets `resume=True`; an old JSON-only folder is imported into a new experiment file (`storage/legacy.py`), keeping its UUID.
- Program length (T125, hotfix until queue mode): `PROGRAM LOAD` fails above about 80 000 lines. A layer program longer than `Experiment(max_program_lines=)` (default `aerobasic/programs/split.MAX_PROGRAM_LINES` = 80 000) is split by `build_programs()` into parts in `split/` next to the layer programs (header with the whole layer setup and footer repeated, cut with the laser off at an absolute move, power/feed replayed); a program that cannot be split stops the build (`ProgramSplitError`). `print_structure()` prepares all layers before the first one (reuses valid parts, splits otherwise) and runs the parts one after another; parts of a printed layer are removed. Layers that failed earlier are printed afterwards with `Experiment.reprint_layers()` / `mains/reprint_layers.py` (`nanofactorysystem/reprint.py`; drop-direction order, DOWN highest layer first; split as above).
- Library loader (T129, opt-in until the lab validation, design `docs/design/PROGRAM_LOADING.md`): `Experiment(program_loader="library")` compiles every part through the A3200 C library (`devices/aerotech/library.py`, `A3200C64.dll`) in a worker process (`python -m nanofactorysystem.devices.aerotech.loader`, `A3200ProgramAdd` without a task; the compile memory, 19.6 kB per line, is freed when the worker disconnects, the program stays added) and runs the parts with `ProgramRunner` on task 1 only: while a part runs the next one is compiled, then the finished part is removed and the next one associated (`A3200ProgramAssociate`) and started (add-ahead, T132 decision (b): task 2 has untuned parameters on this controller, so print parts never run there; `devices/aerotech/loader.py`). `MemoryBudget` (config `controller`: `memoryBudgetGb` 22, `memoryReserveGb` 3, `compileKbPerLine` 19.7, `libraryDll`) refuses compiles beyond the budget and sets the part size (`max_program_lines="auto"`: 80 000 for ASCII, from the budget for the library). Backends provide `program_loader()`; the dummy backend's `DummyLoader` runs on the fake controller. The z-line helper keeps its program loaded on task 1 on purpose.
- Controller health (T133, `devices/aerotech/health.py`): `controller_health(api)` reads ASCII, the task states of the printing tasks, axis faults/enable/home, PC memory and the A3200 processes (warning above 1.5 GB, 32-bit limit); `recover_r0(api)` stops tasks 1/2, removes the given programs (in `Experiment`: the controller's `exec_programs` plus the pre-T152 name `python_aerobasic_program.pgm`) and acknowledges faults (nothing moves). `print_structure()` checks before every structure (R0 and a second check on a problem, else `AerotechError`), and after a failed layer runs R0 and the check; every report is stored in `/logs/health/<session>`. `mains/controller_health.py [--r0] [--dry-run]` runs it by hand. Recovery levels R1-R3 follow after lab session 2.
- Failed layers (T128): with `Experiment(stop_on_failure=True)` (default) the first failed layer stops printing: it is recorded as failed with the error, the structure stays `printing`, and `PrintStoppedError` (an `AerotechError`) is raised. `restart_experiment()` prints the failed layer again (double exposure accepted) and continues; failed layers behind a printed layer (runs with `stop_on_failure=False`, which continues after a failure) are left to `reprint_layers()`.
- `StructureType.REPEAT` prints the most recent grid structure again in the next grid cell as `<name>_rep<n>` (`repeat_of` in the file); a duplicate name gets `_(<i>)`.
- Experiment outputs go into the `path` passed in, which is usually a lab-PC path. Without `resume`, a folder that already holds an experiment is refused.

**Experiment storage** (`storage/`, design in `docs/design/EXPERIMENT_STORAGE.md`)
- `ExperimentStore` writes everything of an experiment into `<path>/experiment.h5` (schema version, metadata, calibration, plane fit, OPL scan, layout, structures with layer programs and progress, camera/DHM captures with commanded and actual positions, DHM products, and per session the controller command log and the console log under `/logs`). Every write opens and closes the file; a lock file `experiment.lock` allows one writing process, and each run is a session.
- `experiment_dictionary.json`, `structures.json` and `print_progress.json` (schema `nanofactory.print_progress/2`, documented in `json_copies.print_progress`) are copies exported from the file (`storage/json_copies.py`); all stored paths are relative to the experiment folder, so a moved folder can be restarted; captures are no longer written as `.zdc` files (`export_capture()` writes one on request).
- Substrates (`storage/substrate_store.py`): `Experiment(path=None, substrate=<label>)` creates `<data root>/<substrate>/<label>-A_<YYYYMMDD-HHMM>/`; the data root is `dataRoot` of the user in the config or `~/Documents/Femtika_Experiment/<user>` and must not lie in a Seafile/OneDrive/Dropbox folder. `substrate.json` holds the substrate record and the index of its experiments; `find_experiments()` searches it. Every index write also rewrites `substrate_layout.json` and `substrate_layout.png` (where every experiment of the substrate is, `storage/substrate_layout.py`, T118). An explicit `path` still works; `substrate_information` (free dict) is stored in the experiment file.
- The summary (`storage/summary.py`) lists every user structure with slice, hatch, power, velocity, IFOV, DHM, camera and status; it is written after `build_programs()` and after every structure into `/summary` and `experiment_summary.json`, and logged as table.
- `storage/records.py` holds the plain data records (`ExperimentRecord`, `StructureRecord`, `CaptureRecord`, …); `ExperimentStore.read()` rebuilds all metadata from the file alone.

**Analysis tools** (`analysis/`, not part of the installed package; README there)
- `analysis/experiment_analysis/` (on the pytest `pythonpath`): `unpack_experiment(h5, target)` mirrors the experiment file into common formats (PNG for images and hologram series, CSV for arrays and tables, TXT for programs and logs, JSON for attributes, stored `.zdc`/`.png` blobs; plus summary, JSON copies and `tables/*.csv`; a snapshot copy while a process holds the lock); `ExperimentFile` reads at any time without HDF5 file locking (retries) and stores results under `/analysis/...` while holding `experiment.lock` for one write (refused while an experiment process holds it; design §5.9).
- `analysis/unpack_experiment.py` and `analysis/analysis_template.py` are the scripts to copy/run (settings at the top); `python -m experiment_analysis unpack|info|tree` from `analysis/`.

**Experiment scripts** (`mains/`)
- `mains/Experiments/` holds only the documented default experiment `default_experiment.py` and the experiments built on it: `chain_rectangle_doe_lens.py` (T113) is a substrate chain of three IFOV experiments (rectangle, DOE on a base, aspheric lens), each a 3 x 3 grid power (rows) x hatch (columns), with named structure factories, `--layout` and `--dry-run`. All older scripts are in `mains/Experiments/old_experiment/` (README there; import as `Experiments.old_experiment.…`).
- `mains/Experiments/old_experiment/**` holds the ported experiment scripts. Each describes its experiment in `experiment_spec(objective, absolute_center, ...)` (objective values: FOV, zMax, drop direction, margins, corners) and keeps its former entry function (`print_file`/`testprint`, with `backend=` and `plane=` for dry runs), which runs it with `run_experiment()`. `test/integration/test_ported_scripts.py` checks all of them.
- `mains/Experiments/old_experiment/focal_points/z_line_focal_points.py` exposes z-lines at random points with camera images before and after (one `FocusDetect` container each, training data for a classifier; T36). It only calls `tools.focus.Focus.run`.
- `mains/Experiments/old_experiment/historical/` holds the scripts of earlier experiments that are not ported (not tested; see its README).
- Several experiments on one substrate: `mains/substrate_main.py` is the template (copy per substrate). It defines a `SubstrateSpec` (label, user, objective, resin edges, material) and a list of `SubstrateExperiment`s (an `ExperimentSpec` plus an optional folder); `nanofactorysystem/substrate_plan.run_substrate()` checks all experiment areas (grid, margin, corner/QR clearance) for overlap with each other, with experiments already in the substrate index and with the resin drop before anything is printed, then runs them one after another into the substrate index. Substrate record version 2 (T76): substrate material, type and dimensions, material/batch/thickness/application per resin drop (`SubstrateSpec` fields; version-1 files are read as version 2); `run_substrate()` enters the experiments as `planned` first, each experiment replaces its entry (`area_um`, `resin_drop`), and `substrate_overview()` lists them with the status of their experiment files. The drop is the ellipse through the four edge points (`resin_drop.py`, T62; also the center check of `Experiment(resin_edges=)`); dip-in has no drop boundary and is not checked.
- `mains/lab_checks/new_features_check.py` is a substrate main that exercises the new features on the lab PC (two small experiments: overview, camera captures, power per layer, repetition, slicer block; files unpacked with `analysis/`) and prints a checklist (T68).
- New experiments are described by an `ExperimentSpec` (`nanofactorysystem/experiment_spec.py`: objective defaults for FOV, drop direction, zMax, margins and corners; structures as `StructureSpec`; `ProgramSource.DRAWING` or `.SLICER`) and run with `run_experiment()`; `mains/Experiments/default_experiment.py` is the template (the short T51 template is `mains/Experiments/old_experiment/experiment_template.py`; dry run: `main(backend="dummy", plane=...)`). A spec is a project file (T77): `to_json()`/`from_json()`, `save()`/`load()` (schema `nanofactory.experiment_spec/1`, slicer inputs in `inputs/` with SHA-256); `run_experiment()` stores it as `experiment_spec.json` and in `/spec` of the experiment file. Structures that need values of the running experiment use named factories (`structure_factories.py`: `@structure_factory(name)`, called with keyword arguments, built with a `BuildContext`); a plain callable `factory=` still runs, but the spec is then not stored.
- `mains/Experiments/old_experiment/default_exp_file.py` is an older template; its `binary_testprint(..., backend=, plane=)` can be dry-run on the dummy backend (see `test/integration/`).
- `mains/main.py` is the entry point for every task (T110): a SETTINGS block (task, user, objective, resin edges, folders) and the tasks `experiment`, `slicer`, `layout`, `substrate`, `spec_file`, `restart`, `overview`, `analyse`, `materials`; `python main.py --task demo --dry-run` runs all of them on the dummy backend. `mains/Experiments/default_experiment.py` is the default experiment that writes out every `ExperimentSpec`/`StructureSpec`/slicer setting with an explanation (start here when new). The former script that called one experiment function by import is `mains/main_legacy.py`. `mains/main_3D_model.py` prints a model file (STL, OBJ, …) with the slicer as one IFOV `ExperimentSpec` (settings from `main.py`, `--dry-run`; T166), like `mains/main_PNG.py` for a 16-bit PNG.
- Dry runs from scripts use `backends/dummy/dry_run.dry_run(user)` (dummy backend, known plane, `time.sleep` on the virtual clock, missing user/objective added to the config only for the dry run) instead of the test fixtures.

## Maintainer Instructions (Hannes)

### Language
Everything is written in English: variable, function, class and module names, docstrings,
comments, README and other documentation, design documents, todo entries, commit messages,
pull request texts and log entries. If you encounter German identifiers or comments within
the scope of your current task, translate them. Outside that scope, add a todo instead of
renaming them unasked. Material the maintainer hands over in German (notes, specifications)
is translated when it is turned into documentation or todos.

### Session start
1. Read `## Current Status` and `## Status Update Anchor` at the end of this file. As long as
   they hold no status yet, go by the phase plan in `TODO.md`.
2. Read `TODO.md` and pick a task. Prefer the one named as the next task in `## Current Status`,
   otherwise follow working rule 1 at the top of `TODO.md`.
3. Read the most recent entries in `WORKLOG.md`.
4. If the task touches the DHM, the experiment file layout for DHM products, or MIRA, read
   `docs/system/SOFTWARE_PLAN_OVERVIEW.md` first.

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
- Work on a feature branch created from `main_HR` (`feat/…`, `fix/…`, `docs/…`), never directly on
  `main_HR`.
- Commit after every completed task and after every coherent sub-step of larger tasks. A task
  that ends without a commit is not done.
- Split commits by topic: one logical change per commit. Do not mix refactoring, formatting,
  feature work, tests of unrelated code and documentation of other tasks. Todo bookkeeping
  (`TODO.md`, `WORKLOG.md`) goes into its own `docs(todo): …` commit at the end of a task.
- Write every message for a human who reads `git log` months later without the session: the
  subject says what the change does for the system (not "update files", "fixes", "WIP"), the
  body says why it was needed and what a reader must know (decisions, side effects, limits).
  Example of a good subject: `fix(image): build the contour mask as uint8 for OpenCV [T65]`.
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
  `mvImpact`, `OffAxisHolo`, `dhmconnect` or `mira`. Tests that need the lab are marked
  `hardware` and only run with `--run-hardware`.
- Never make a test pass by weakening or deleting assertions without justification.
  If a test reveals a real bug, fix it in a separate `fix:` commit if the fix is small and clear.
  Otherwise, mark the test `xfail(reason=..., strict=True)` and add a todo.
- Every moved, converted or removed test is justified in WORKLOG.md and reflected in
  `test/README.md`.
- Tests write only to `tmp_path` or `test/_programs/`.
- Keep existing `unittest.TestCase` classes. New tests may use plain pytest style with fixtures.
- Never modify legacy code (`old_to-delete/`, `new/`, `*_old.py`). Exclude it from collection.
- Real hardware is always the default backend. The dummy backend is opt-in.
## Current Status
<!-- Maintained exclusively by the status review routine. Claude Code reads it, never edits it. -->
No status written yet (section created 2026-11-15 during the reorganisation of the project files).

## Status Update Anchor
<!-- Maintained exclusively by the status review routine. Claude Code reads it, never edits it. -->
No anchor set yet.
