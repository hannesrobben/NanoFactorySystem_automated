# Test suite

The tests fall into four categories. The first two run on any machine, with no lab hardware, no
`~/nanofactory.json` and no `mvIMPACT` or `OffAxisHolo`. Only the last two need the Femtika Laser
Nanofactory.

| Category | Needs | Runs by default | How to recognise |
|---|---|---|---|
| **Unit** | nothing | yes | pure functions and program generation, no `System` |
| **Dummy integration** | nothing (simulated hardware) | yes | uses `dummy_backend`, `dummy_controller` or `dummy_system` |
| **Hardware** | lab PC with controller, camera, DHM and `~/nanofactory.json` | no, only with `--run-hardware` | marked `@pytest.mark.hardware` |
| **Manual** | lab PC and a person watching | never collected | lives in `test/manual/` |

## Running the tests

```bash
python -m pytest                                  # unit + dummy integration (hardware tests are skipped)
python -m pytest test/test_aerobasic              # one directory
python -m pytest test/devices/test_aerotech.py::test_zmax_safety   # one test
python -m pytest -m "not slow"                    # skip the ~10 s experiment dry run
python -m pytest -m hardware --run-hardware       # only the hardware tests, on the lab PC
python -m pytest --run-hardware                   # everything, on the lab PC
python -m pytest test/test_aerobasic/test_golden_programs.py --update-golden   # re-record golden files
```

The configuration is in `[tool.pytest.ini_options]` in `pyproject.toml`: `testpaths = ["test"]`, and
`test/manual`, `test/_programs` and the legacy directories are excluded.

**Markers**
- `hardware`: the test talks to the real devices. Without `--run-hardware` it is skipped with the reason
  *"needs the lab hardware; run with --run-hardware on the lab PC"*. Hardware tests take the user from the
  lab configuration (`lab_user` fixture, the first `user:` entry in `~/nanofactory.json`).
- `slow`: the test takes more than a few seconds. It still runs by default; deselect it with `-m "not slow"`.

**Environment.** Set up a virtual environment and install the package with the test extra:

```bash
python -m venv .venv            # outside a synced folder, if possible
.venv/Scripts/python -m pip install ".[test]"      # Windows; use .venv/bin/python elsewhere
```

`pyproject.toml` requires `opencv-python>=4.10.0.84`, the first release built for NumPy 2. With an older
OpenCV next to NumPy 2, `import nanofactorysystem` fails with `numpy.core.multiarray failed to import`.
On Windows, keep the path of the virtual environment short: `shapely` fails to load its DLL when the path
is longer than 260 characters.

## Unit tests

| Module | What it tests | Why it matters (failure it catches) | Requirements |
|---|---|---|---|
| `test_aerobasic/test_constants.py` | Parsing and combining axes (`Axis`, `SingleAxis`, `Stages`) | Wrong axis names in `ENABLE`/`HOME`/`LINEAR` commands; invalid axis combinations (`~`, `^`, empty `&`). | – |
| `test_aerobasic/test_coordinate_system.py` | Plane fit and the local → stage coordinate transformation, azimuth of the plane normal in (-180°, 180°] | Structures written at the wrong height or position on a tilted substrate | – |
| `test_aerobasic/test_program.py` | `AeroBasicProgram` text output and writing `.pgm` files | Broken program files that the controller rejects | – |
| `test_aerobasic/test_power_calibration.py` | Power (mW) → attenuator conversion for IFOV structures: explicit, active and configured calibration; `Experiment` uses its attenuator | Wrong laser power in IFOV programs; programs depending on a lab-only file | – |
| `test_aerobasic/test_structure_json.py` | `DrawableObject.to_json()` / `structure_from_json()`: every structure of the golden tests and a DOE with height profile is rebuilt from its JSON form and writes the same programs; encoding of enums, points, arrays; lost arguments are reported | Experiments whose structures cannot be rebuilt from `structures.json`; silently dropped constructor arguments | – |
| `test_aerobasic/test_variables.py` | `create_variable`, `DVAR` declarations | Invalid variable declarations in generated programs | – |
| `test_aerobasic/test_drawings/test_circles.py`, `test_corners.py` | Circle and corner structures generate programs | Exceptions in drawing code; the program content is checked by the golden tests | – |
| `test_aerobasic/test_golden_programs.py` | Generated text of 11 representative programs (DefaultSetup and SetupIFOV) against `test/golden/*.txt` | **Any unintended change** of the commands sent to the machine, e.g. after refactoring the drawing classes | – |
| `test_utils/test_visualization.py` | Reading programs into movements and plotting them (arcs, variables, empty programs), attenuator value per movement shown as colour (mW with a calibration), mm axes without offset or scientific notation | Broken movement plots used for manual inspection of generated programs | – |
| `test_utils/test_units.py` | Prototype unit conversion (`UnitFloat`, defined in the test) with `Unit` | Wrong mm/µm/cm factors | – |
| `voxel/test_voxel_database.py` | Voxel database with synthetic data: schema version and migrations, constraints, exact hit (weighted duplicates), 2-D interpolation, no extrapolation, unknown material, too few points, dose fallback, separate width/height points, CSV round trip and seed, atomic import, configured path | Wrong voxel sizes from extrapolation or mixed conditions; a database that cannot be opened after an update | – |
| `test_config_sources.py` | Config lookup order, built-in default, `use_config`, lazy class defaults | The package failing to import without `~/nanofactory.json`; the config not being switchable in tests | – |
| `test_runtime.py` | `getLogger()` does not duplicate handlers and switches log files; failed controller commands are logged, not printed | Duplicated or misrouted log lines when several experiments run in one process | – |
| `test_conftest.py` | The `--run-hardware` handling and the shared fixtures | Hardware tests running (or silently not running) on the wrong machine | – |
| `storage/test_experiment_store.py` | `ExperimentStore` (HDF5 experiment file): schema version, metadata, structures, layer programs, progress, captures, DHM products, calibration, plane fit, OPL scan, layout, slicer job, sessions and lock file | Lost or unreadable experiment data; a file handle left open while printing; two processes writing one experiment | – |
| `storage/test_substrate_store.py` | Substrate records and labels (`HR-26-001`, counter per year), experiment letters, the experiment index and `find_experiments`, the default data root (`dataRoot`, refused synchronised folders), import of an old `substrate_information.json` | Experiments that cannot be found again; two substrates with the same label; experiment data written into a Seafile folder | – |
| `storage/test_summary.py` | Experiment summary: slice, hatch, velocity and power from the structure arguments (IFOV power, units), slicer structures with their voxel values (T54), corners and QR code excluded, text table | A misleading summary of what was printed | – |
| `slicer/test_model3d.py` | `Model3D_Slicer`: STL → toolpath → layer programs, JSON and HDF5 export (checks in `slicer/model3d_checks.py`) | Regressions in the 3D-model slicing pipeline | `trimesh`, `shapely`, `h5py` (skipped if missing) |
| `slicer/test_voxel_slicing.py` | Voxel-aware slicing (T54): box and cylinder envelopes (toolpath plus voxel) match the design; `VOXEL_OVERLAP` spacing, `STATIC_HATCHING` with gap warnings, partial data, a part thinner than a voxel; without data the job is unchanged; strategies receive the voxel context; database-backed model; `Model3D_Slicer` records the values; job file round trip | Parts printed larger than designed; silent gaps between lines; a changed no-data path | `trimesh`, `shapely` (`h5py` for the round trip) |
| `slicer/test_segment_power.py` | Laser power per segment in `Model3D_Slicer` (T31): unchanged programs without overrides, `power_map` per role and layer, per-element overrides on the toolpath, missing structure power | Programs that print segments at the wrong power | `trimesh`, `shapely` |
| `test_substrate_plan.py` | Substrate main files (T52): experiment area (grid, margin, corner and QR clearance), the QR code width, overlap between experiments and with experiments already on the substrate, resin drop bounds, objective and duplicate-name checks, layout plot | Experiments printed over each other or outside the resin drop | – |
| `test_resin_drop.py` | Resin-drop outline (T62): ellipse through the four edge points, circle and degenerate points (fallback), rectangle inside the ellipse, no boundary for dip-in, layout check against the ellipse | Experiments near the rim of a round drop printed into air or the drop edge | – |

## Dummy integration tests

These run the real classes (`System`, `A3200`, `Aerotech3200`, `Camera`, `Dhm`, `Attenuator`, `Experiment`)
on simulated hardware from `nanofactorysystem.backends.dummy`. The fake controller works at the TCP/ASCII
level, so the exact command strings are checked.

| Module | What it tests | Why it matters (failure it catches) | Requirements |
|---|---|---|---|
| `backends/test_dummy_controller.py` | The fake A3200: protocol frames, motion, laser and exposures, program tasks, fault injection, call log | The simulation itself being wrong, which would make all other dummy tests meaningless | – |
| `backends/test_dummy_devices.py` | Camera, DHM and attenuator facades on the simulated devices; determinism; protocol conformance | Exposure/OPL optimisation or calibration conversion breaking | – |
| `backends/test_command_logs.py` | Golden command logs (`test/golden/commands_*.txt`) of System use and complete experiments (DefaultSetup and SetupIFOV) | **Any change of the commands sent to the controller**, e.g. by refactoring the controller classes (recorded before the T20 merge) | – (experiment flows marked `slow`) |
| `backends/test_controller_merge.py` | One controller object in `System`, program tasks on `A3200`, zMax guard for `.api` moves, `Aerotech3200` without config, error types | Moving above the safe z range through `.api`; regressions of the controller merge | – |
| `backends/test_timeouts.py` | Connect/response timeouts, reading split responses, bounded waiting for axes, z-line, stalled tasks and `PROGRAM STOP` | A missing or hung device freezing the program instead of failing with an error | – |
| `backends/test_dummy_system.py` | `System` start-up command sequence, z-line, backend switch; the real backend still opens the same devices | `System` sending different commands to the machine; the default backend changing | – |
| `devices/test_aerotech.py` | The old `A3200` controller: commands, µm parsing, `zMax` safety, power, z-line, errors | Moving outside the safe z range; wrong units | – (plus 1 hardware test) |
| `devices/test_attenuator.py` | Power ↔ attenuator conversion | Wrong laser power | – (plus 1 hardware test) |
| `devices/test_camera.py` | Exposure optimisation, image container | Unusable camera images | – (plus 1 hardware test) |
| `dhm/test_dhm.py` | DHM client: objective selection, shutter, motor, hologram | DHM communication errors | – (plus 1 hardware test) |
| `dhm/test_motorscan.py` | OPL motor scan: the bracket is widened step by step, stays inside the motor range, and a missing maximum raises `MotorScanError` | An OPL scan that drives the motor out of range or gives up too early | – |
| `dhm/test_manual_helper.py` | `reset()` of the interactive DHM helper `test/manual/dhm/DHMUserBackend.py`, run on the dummy DHM | A helper that keeps an old connection or old state after a reset | – |
| `test_femtika/test_device_no_laser.py` | `Aerotech3200` status, positions, tasks, homing on the simulated controller | Parsing errors in the status answers of the controller | – (the same tests also run as hardware tests) |
| `test_experiment.py` | `Experiment`: printing all layers, a failed layer (logged, printing continues), empty structures, OPL scan, substrate information, experiment dictionary, restart (same experiment file and UUID), restart after two aborts, import of an old JSON-only folder on restart, repeated structures (names, own grid cell), restart of a moved experiment folder (relative paths), capture records in the experiment file (commanded and actual position per capture, several positions), an exception during printing, refusing a folder that already holds an experiment, command and console log stored per experiment and session (also after an abort), two experiments on one substrate in the default location (labels, folders, index), the substrate index after a restart, substrate information in the experiment file, the summary after building and printing, the experiment plot (corners, double corner, QR code, UUID) and structure plots on request, camera images only with `camera_capture` (both values, stored, used on restart), captures taken with the galvo at A = B = 0 and Z not moved, `print_progress.json` counts and times for drop direction UP and DOWN after a complete and an aborted structure; power per structure and per layer (T31: list or function of the layer id, repetitions, wrong length, stored powers); experiment center inside the ellipse through the resin-drop edges (T62), edges stored for a restart | A single failed layer aborting a whole print; wrong metadata for restarts; captures that cannot be traced to a stage position; an unreadable file after a crash; overwriting an earlier experiment; a command log overwritten by the next run | – |
| `test_drop_direction.py` | Drop direction (T43): the scanner keeps the lowest focus range for DOWN and the highest for UP; `Experiment` passes the drop direction to the tools; UP and DOWN write identical layer programs in opposite order; QR pixel lines are drawn upwards for DOWN | Plane fits on the wrong interface; structures written at mirrored heights | – |
| `test_plane_fitting.py` | Plane-fit modes (`GRID`, `CORNERS`, `BORDER`, old integers), number and positions of the sample points, their storage, the experiment center check, the tilt warning, and a plane fit outside `Experiment` with a stand-in for the detection | Plane fits at wrong positions; experiments outside the resin drop; unnoticed tilt under large structures | – |
| `test_system.py` | `System` data container, homing | Missing metadata in stored experiments | – (plus 1 hardware test) |
| `tools/test_focus_dummy.py` | `Focus` runs end to end on `System`; the z-line exposure reaches the controller | The tools breaking on API changes of `System` | – |
| `integration/test_dry_run_spec.py` | Experiments described by `ExperimentSpec` and run with `run_experiment()`: program sources DRAWING and SLICER (height map through `Model3D_Slicer`, also with `voxel_material` and a voxel database: values in the experiment file and the summary), objective defaults, repetitions, validation, and the examples of `mains/Experiments/experiment_template.py` | A template or spec that fails on the lab PC; slicer programs with statements the controller simulation does not know | – (marked `slow`) |
| `integration/test_ported_scripts.py` | The experiment scripts ported to `ExperimentSpec` (T51): every script builds a valid spec for its objectives (and refuses the others), structure factories and empty cells; one script (DHM tomography, reduced grid, no corners) as a dry run on the dummy backend | A ported script that fails on the lab PC before the first print (missing parameters, wrong objective values, left-over `sample.orientation`) | – (dry run marked `slow`) |
| `integration/test_dry_run_default_experiment.py` | `mains/Experiments/default_exp_file.py` end to end: start-up, `plane_fit` (known plane), `build_programs`, `print_experiment`; the experiment file matches its JSON copies and the summary | An experiment script failing on the lab PC halfway through a print; JSON copies that differ from the experiment file | – (marked `slow`) |
| `integration/test_dry_run_substrate.py` | `substrate_plan.run_substrate()`: two experiments on one substrate give two experiment files and one substrate index; the planned areas match the printed rectangles; a second run is refused because the areas are taken; optional folder, confirmation between experiments; an invalid layout creates nothing; the layout of `mains/substrate_main.py` is valid | A substrate main file that overwrites or overprints earlier experiments, or stops halfway with a broken index | – |

## Hardware tests

Marked `hardware`; run on the lab PC with `--run-hardware`. They need the devices switched on and
`~/nanofactory.json` with at least one user.

| Module | What it tests | Why it matters | Requirements |
|---|---|---|---|
| `devices/test_aerotech.py::test_real_controller_position` | Controller connection and position read-out | Controller unreachable or misconfigured | A3200 (ASCII interface on port 8000) |
| `devices/test_attenuator.py::test_real_calibration_file` | The lab calibration file is complete and monotonic | A corrupt calibration gives wrong laser power | calibration file at the configured path |
| `devices/test_camera.py::test_real_camera` | Camera opens and exposure optimisation converges | Camera driver or setup broken | camera and `mvIMPACT` |
| `dhm/test_dhm.py::test_real_client` | DHM server version, objective, shutter, motor, hologram | DHM server unreachable or misconfigured | DHM server at the configured address |
| `test_femtika/test_device_no_laser.py::TestFemtikaNoLaser` | Status, positions, tasks, **homing and a move to X=Y=Z=0** | The controller answering differently than the simulation assumes | A3200. Note: moves the stage |
| `test_system.py::test_real_system_opens` | The whole system opens and closes | Any device failing at start-up | all devices |

## Manual scripts (`test/manual/`)

These are not collected by pytest. Run them directly on the lab PC when needed.

| Script | Purpose | Requirements |
|---|---|---|
| `devices/_test_dhm.py`, `devices/_test_dhm_objective.py`, `devices/test_dhm_objective.py` | DHM images and objective configuration checks | DHM, `offaxisholo` |
| `devices/live_tilt.py`, `devices/live_tilt_cv.py` | Live view for aligning the sample tilt | DHM, `offaxisholo`, a person |
| `dhm/DHMUserBackend.py` | Interactive DHM helper (its `reset()` is tested in `dhm/test_manual_helper.py`) | DHM |
| `femtika/test_device_WITH_laser.py` | Laser override and IFOV checks; watch whether the laser is visible | A3200 and laser, a person |
| `tools/test_focus.py`, `test_63x_focus.py`, `test_layer.py`, `test_plane.py`, `test_grid.py` | Focus, layer, plane and grid measurements on a real sample (they expose the laser) | all devices, a sample |
| `tools/test_stitch.py`, `tools/eval_grid.py` | Evaluation of stored measurements | data files (`focus-2/…`, not in the repository) |
| `print_config.py`, `example_planefit.py` | Print the active configuration; plane-fit example | – |

## Using the dummy backend

`System` and `Experiment` take an explicit `backend` argument. The default (`None` or `"real"`) is the lab
hardware. There is no environment variable, so a lab PC can never switch to simulation by accident.

```python
from nanofactorysystem import System
from nanofactorysystem.backends import DummyBackend

backend = DummyBackend(seed=0)            # deterministic; its workdir is a new temporary directory
with System("Test", "Zeiss 20x", backend=backend, controller={"zMax": 25000.0}) as system:
    system.moveabs(x=100.0, z=20010.0)
    system.zline(1.0, 100.0, 10.0, 20.0)

backend.calllog.commands()                # every ASCII command sent to the controller, in order
backend.world.exposures                   # laser exposures (stage coordinates in mm, power in mW)
backend.world.stage                       # current axis positions in mm
```

Useful knobs:
- `backend.transport.fail_next(r"^LINEAR", error="Axis fault")` injects a controller fault.
- `backend.transport.respond(r"^~VERSION$", "1.2.3.4")` overrides an answer.
- `backend.transport.program_error_next(...)` makes the next program task end in an error.
- `DummyBackend(strict=True)` rejects unknown commands.
- `DummyBackend(decimal_comma=True)` formats numbers like a controller with German locale settings.

**Example test** with the shared fixtures from `test/conftest.py`:

```python
def test_moving_writes_linear_command(dummy_system, dummy_backend):
    dummy_backend.calllog.clear()

    dummy_system.moveabs(x=dummy_system.x0 + 10.0)

    assert dummy_backend.calllog.commands()[-1].startswith("LINEAR X")
    assert dummy_system.position("X") == dummy_system.x0 + 10.0
```

| Fixture | Provides |
|---|---|
| `test_config` | The built-in default configuration plus the user `Test` (independent of `~/nanofactory.json`) |
| `dummy_backend` | `DummyBackend(seed=0)` with its working directory in `tmp_path` |
| `no_sleep` | `time.sleep` advances the virtual clock instead of waiting |
| `dummy_controller` | A connected `Aerotech3200` on the simulated controller |
| `dummy_system` | `System("Test", "Zeiss 20x")` on `dummy_backend` (closed after the test) |
| `tmp_program_dir` | An empty directory for generated programs |
| `golden` | `golden(name, text)` compares with `test/golden/<name>.txt` |
| `lab_user` | The first lab user (hardware tests only) |

**Dry run of an experiment script.** Pass `backend` and a known substrate plane; plane detection is not
simulated:

```python
backend = DummyBackend()
binary_testprint(..., path=Path("dry_run"), backend=backend, plane=backend.world.sample.plane())
```

## Where generated files go

- `tmp_path` (pytest's per-test temporary directory): everything the unit and dummy tests write. This
  includes experiment output (incl. `A3200.log` of an experiment), the backend workdir (calibration file,
  `__zline__.pgm`, the `A3200.log` of a plain `System`) and programs.
- `test/_programs/` (gitignored): programs and movement plots written by `test_program.py` and the drawing
  tests, kept for manual inspection.
- `test/golden/`: the committed reference programs. Change them only with `--update-golden`, and review the
  diff.
- Hardware and manual scripts may write into the current working directory, as they always did (for example
  `.test/`, `__zline__.pgm`, `A3200.log`).
