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
| `test_aerobasic/test_constants.py` | Parsing and combining axes (`Axis`, `SingleAxis`, `Stages`) | Wrong axis names in `ENABLE`/`HOME`/`LINEAR` commands. `test_prevent_mixed_axes` is a strict `xfail` until the decision in T23. | – |
| `test_aerobasic/test_coordinate_system.py` | Plane fit and the local → stage coordinate transformation | Structures written at the wrong height or position on a tilted substrate | – |
| `test_aerobasic/test_program.py` | `AeroBasicProgram` text output and writing `.pgm` files | Broken program files that the controller rejects | – |
| `test_aerobasic/test_variables.py` | `create_variable`, `DVAR` declarations | Invalid variable declarations in generated programs | – |
| `test_aerobasic/test_drawings/test_circles.py`, `test_corners.py` | Circle and corner structures generate programs | Exceptions in drawing code; the program content is checked by the golden tests | – |
| `test_aerobasic/test_golden_programs.py` | Generated text of 11 representative programs (DefaultSetup and SetupIFOV) against `test/golden/*.txt` | **Any unintended change** of the commands sent to the machine, e.g. after refactoring the drawing classes | – |
| `test_utils/test_units.py` | Prototype unit conversion (`UnitFloat`, defined in the test) with `Unit` | Wrong mm/µm/cm factors | – |
| `test_config_sources.py` | Config lookup order, built-in default, `use_config`, lazy class defaults | The package failing to import without `~/nanofactory.json`; the config not being switchable in tests | – |
| `test_conftest.py` | The `--run-hardware` handling and the shared fixtures | Hardware tests running (or silently not running) on the wrong machine | – |
| `slicer/test_model3d.py` | `Model3D_Slicer`: STL → toolpath → layer programs, JSON and HDF5 export (checks in `slicer/model3d_checks.py`) | Regressions in the 3D-model slicing pipeline | `trimesh`, `shapely`, `h5py` (skipped if missing) |

## Dummy integration tests

These run the real classes (`System`, `A3200`, `Aerotech3200`, `Camera`, `Dhm`, `Attenuator`, `Experiment`)
on simulated hardware from `nanofactorysystem.backends.dummy`. The fake controller works at the TCP/ASCII
level, so the exact command strings are checked.

| Module | What it tests | Why it matters (failure it catches) | Requirements |
|---|---|---|---|
| `backends/test_dummy_controller.py` | The fake A3200: protocol frames, motion, laser and exposures, program tasks, fault injection, call log | The simulation itself being wrong, which would make all other dummy tests meaningless | – |
| `backends/test_dummy_devices.py` | Camera, DHM and attenuator facades on the simulated devices; determinism; protocol conformance | Exposure/OPL optimisation or calibration conversion breaking | – |
| `backends/test_dummy_system.py` | `System` start-up command sequence, z-line, backend switch; the real backend still opens the same devices | `System` sending different commands to the machine; the default backend changing | – |
| `devices/test_aerotech.py` | The old `A3200` controller: commands, µm parsing, `zMax` safety, power, z-line, errors | Moving outside the safe z range; wrong units | – (plus 1 hardware test) |
| `devices/test_attenuator.py` | Power ↔ attenuator conversion | Wrong laser power | – (plus 1 hardware test) |
| `devices/test_camera.py` | Exposure optimisation, image container | Unusable camera images | – (plus 1 hardware test) |
| `dhm/test_dhm.py` | DHM client: objective selection, shutter, motor, hologram | DHM communication errors | – (plus 1 hardware test) |
| `test_femtika/test_device_no_laser.py` | `Aerotech3200` status, positions, tasks, homing on the simulated controller | Parsing errors in the status answers of the controller | – (the same tests also run as hardware tests) |
| `test_experiment.py` | `Experiment`: printing all layers, a failed layer (logged, printing continues), empty structures, OPL scan, substrate information, experiment dictionary | A single failed layer aborting a whole print; wrong metadata for restarts | – |
| `test_system.py` | `System` data container, homing | Missing metadata in stored experiments | – (plus 1 hardware test) |
| `tools/test_focus_dummy.py` | `Focus` runs end to end on `System`; the z-line exposure reaches the controller | The tools breaking on API changes of `System` | – |
| `integration/test_dry_run_default_experiment.py` | `mains/Experiments/default_exp_file.py` end to end: start-up, `plane_fit` (known plane), `build_programs`, `print_experiment` | An experiment script failing on the lab PC halfway through a print | – (marked `slow`) |

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
| `dhm/DHMUserBackend.py` | Interactive DHM helper | DHM |
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
  includes experiment output, the backend workdir (calibration file, `__zline__.pgm`, `A3200.log`) and
  programs.
- `test/_programs/` (gitignored): programs and movement plots written by `test_program.py` and the drawing
  tests, kept for manual inspection. Plotting failures appear as warnings (T24).
- `test/golden/`: the committed reference programs. Change them only with `--update-golden`, and review the
  diff.
- Hardware and manual scripts may write into the current working directory, as they always did (for example
  `.test/`, `__zline__.pgm`, `A3200.log`).
