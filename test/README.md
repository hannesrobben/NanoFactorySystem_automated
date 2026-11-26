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
| `test_aerobasic/test_line_details.py` | Line structures (T35): non-IFOV velocity in µm/s written as mm/s, `Rectangle3D` without height (nothing) or lower than half a slice (one layer), `step_slice_size`, DOEs with zero-height pixels, `IFOV_Lines` velocity handling and the fixed IFOV speeds | Division by zero for flat steps or sockets; wrong speed units in programs | – |
| `test_aerobasic/test_optimize.py` | T130 program optimiser: number format, modal feed and unchanged axis words dropped, collinear moves merged but not across a laser switch, lines with variables and unknown commands kept (knowledge reset), incremental moves, golden programs (rectangle, IFOV grating, QR code) expose the same path within 10 nm (reference interpreter over X/Y/Z/A/B with gate ON/AUTO, power and feed) | An optimised program that writes a different structure | – |
| `test_aerobasic/test_constants.py` | Parsing and combining axes (`Axis`, `SingleAxis`, `Stages`) | Wrong axis names in `ENABLE`/`HOME`/`LINEAR` commands; invalid axis combinations (`~`, `^`, empty `&`). | – |
| `test_aerobasic/test_coordinate_system.py` | Plane fit and the local → stage coordinate transformation, azimuth of the plane normal in (-180°, 180°] | Structures written at the wrong height or position on a tilted substrate | – |
| `test_aerobasic/test_program.py` | `AeroBasicProgram` text output and writing `.pgm` files | Broken program files that the controller rejects | – |
| `test_aerobasic/test_program_split.py` | T125: splitting layer programs longer than the `PROGRAM LOAD` limit: short programs unchanged; IFOV layers (header and footer in every part, body unchanged, cuts before a `RAPID`); laser-gated layers (cut with the laser off at an absolute X/Y/Z move, feed rate replayed); power replayed; refusal without a cut place, in incremental mode and with a too long header; part files and line count; reuse of existing parts only while complete, not older than the program and within the limit; no stale parts after a new split | Layers that the controller refuses to load; parts that expose with the laser on at a cut, start at a wrong position or lose power / feed rate | – |
| `test_aerobasic/test_power_calibration.py` | Power (mW) → attenuator conversion for IFOV structures: explicit, active and configured calibration; `Experiment` uses its attenuator | Wrong laser power in IFOV programs; programs depending on a lab-only file | – |
| `test_aerobasic/test_structure_json.py` | `DrawableObject.to_json()` / `structure_from_json()`: every structure of the golden tests and a DOE with height profile is rebuilt from its JSON form and writes the same programs; encoding of enums, points, arrays; lost arguments are reported | Experiments whose structures cannot be rebuilt from `structures.json`; silently dropped constructor arguments | – |
| `test_aerobasic/test_variables.py` | `create_variable`, `DVAR` declarations | Invalid variable declarations in generated programs | – |
| `test_aerobasic/test_drawings/test_circles.py`, `test_corners.py` | Circle and corner structures generate programs | Exceptions in drawing code; the program content is checked by the golden tests | – |
| `test_aerobasic/test_golden_programs.py` | Generated text of 11 representative programs (DefaultSetup and SetupIFOV) against `test/golden/*.txt` | **Any unintended change** of the commands sent to the machine, e.g. after refactoring the drawing classes | – |
| `test_parameter.py` | `Parameter`: argument dictionaries are not modified; T111: an incomplete `user:<name>` section raises a `KeyError` naming the user and the missing keys (instead of an `AttributeError` inside `scidatacontainer`) | A `System` that fails with an unreadable error on a new lab user | – |
| `test_layout.py` | T80: `grid_geometry` (rows along y, columns along x), `spec_layout` as plain data (cells with structure names incl. repetitions and empty cells, corners with the double corner, QR code, plane-fit points, JSON), equal to `experiment_layout` of the experiment built from the same spec; `layout_figure` opens no window | A layout plot or GUI view that differs from what is printed | – |
| `test_print_strategies.py` | T81: print strategies registered by name (`static` built in, unknown names refused with the registered ones listed); a registered strategy changes the slicer arguments of a structure without changing the spec, and name and parameters survive the spec JSON; a strategy on a drawing is refused; specs without strategy are written as before | A structure printed with another slicing than its spec names, or a spec that cannot be rebuilt | `trimesh`, `shapely` |
| `test_aerobasic/test_ifov_rectangles.py` | T114: `Rectangle2D_IFOV` / `Rectangle3D_IFOV` take `objective=` (IFOV configuration of the 20x or 63x, default 63x as before, stored in `to_json()`); with `alternate_hatching` the direction comes from the layer index, so two iterations give identical programs and the object is not changed | A 20x print with the 63x IFOV configuration; a restart or time estimate that turns the hatch direction | – |
| `test_utils/test_visualization.py` | Reading programs into movements and plotting them (arcs, variables, empty programs), attenuator value per movement shown as colour (mW with a calibration), mm axes without offset or scientific notation | Broken movement plots used for manual inspection of generated programs | – |
| `test_utils/test_units.py` | Prototype unit conversion (`UnitFloat`, defined in the test) with `Unit` | Wrong mm/µm/cm factors | – |
| `voxel/test_material_registry.py` | Material registry (T75): migration of a version-1 database keeps its data, refractive index per wavelength and state (most recent value, exact state before `any`, no interpolation), new keys and text values without code change, unit/state/kind validation and unit warning, shared material table, CSV round trip, seed and atomic import, snapshots of known and unknown names, `open_existing` never creates a file, name precedence (argument > substrate > `sys_args`) | Refractive indices taken from the wrong wavelength or state; a registry update that breaks the voxel data; experiments without a record of their material | – |
| `voxel/test_voxel_database.py` | Voxel database with synthetic data: schema version and migrations, constraints, exact hit (weighted duplicates), 2-D interpolation, no extrapolation, unknown material, too few points, dose fallback, separate width/height points, CSV round trip and seed, atomic import, configured path | Wrong voxel sizes from extrapolation or mixed conditions; a database that cannot be opened after an update | – |
| `test_config_sources.py` | Config lookup order, built-in default, `use_config`, lazy class defaults | The package failing to import without `~/nanofactory.json`; the config not being switchable in tests | – |
| `test_runtime.py` | `getLogger()` does not duplicate handlers and switches log files; failed controller commands are logged, not printed | Duplicated or misrouted log lines when several experiments run in one process | – |
| `test_conftest.py` | The `--run-hardware` handling and the shared fixtures | Hardware tests running (or silently not running) on the wrong machine | – |
| `storage/test_experiment_store.py` | `ExperimentStore` (HDF5 experiment file): schema version, metadata, structures, layer programs, progress, captures, DHM products, calibration, plane fit, OPL scan, layout, slicer job, sessions and lock file; reads without HDF5 file locking (T66); material snapshots round trip (T75); experiment spec and input files (`/spec`, `/inputs`, T77); T124: whole-structure program gzip-compressed (reads back, smaller), as reference only, and the text scalar of older files | Lost or unreadable experiment data; a file handle left open while printing; two processes writing one experiment | – |
| `storage/test_dhm_storage.py` | DHM service results in `experiment.h5` (T83, `EXPERIMENT_STORAGE.md` §15, schema 1.3): reserved capture, job states, `ProductSet` as `header_json` + one dataset per buffer with flat traceability attributes, frame records round trip, stitched `LayerProduct` under `/dhm_groups` in the MIRA layout, orphans as references, background calibration, second delivery of a job dropped, recovered result marked, legacy capture unchanged, `captures.csv` with job columns; T79: DHM session record, parameter set once per hash (same content only), DHM line in the summary; the vendored example `storage/data/dhm_example/experiment.h5` matches its generator `storage/dhm_example.py` (product headers from the vendored DHMConnect contract examples `storage/data/contracts`) | A DHM result that cannot be matched to its capture or parameter set; a layout the readers in OffAxisHolo / MIRA / DHMConnect do not understand; a duplicate result after a restart | – |
| `storage/test_substrate_layout.py` | `substrate_layout.json` / `.png` next to `substrate.json` (T118): written on creation, rewritten on plan / register / status change, content (drops with ellipse, areas, states, bounds), `write_layout` on request, a failing plot only logs and never breaks the index | Not knowing where on a substrate earlier experiments are; a plotting error stopping a print | – |
| `storage/test_substrate_store.py` | Substrate records and labels (`HR-26-001`, counter per year), experiment letters, the experiment index and `find_experiments`, the default data root (`dataRoot`, refused synchronised folders), import of an old `substrate_information.json`; record version 2 (T76: version-1 file read as version 2 and written only on change, substrate type/dimensions validated, material per drop, planned entries replaced by the experiment, `substrate_overview` with and without refresh) | Experiments that cannot be found again; two substrates with the same label; experiment data written into a Seafile folder | – |
| `storage/test_summary.py` | Experiment summary: slice, hatch, velocity and power from the structure arguments (IFOV power, units), slicer structures with their voxel values (T54), corners and QR code excluded, text table | A misleading summary of what was printed | – |
| `slicer/test_model3d.py` | `Model3D_Slicer`: STL → toolpath → layer programs, JSON and HDF5 export (checks in `slicer/model3d_checks.py`) | Regressions in the 3D-model slicing pipeline | `trimesh`, `shapely`, `h5py` (skipped if missing) |
| `slicer/test_voxel_slicing.py` | Voxel-aware slicing (T54): box and cylinder envelopes (toolpath plus voxel) match the design; `VOXEL_OVERLAP` spacing, `STATIC_HATCHING` with gap warnings, partial data, a part thinner than a voxel; without data the job is unchanged; strategies receive the voxel context; database-backed model; `Model3D_Slicer` records the values; job file round trip | Parts printed larger than designed; silent gaps between lines; a changed no-data path | `trimesh`, `shapely` (`h5py` for the round trip) |
| `slicer/test_segment_power.py` | Laser power per segment in `Model3D_Slicer` (T31): unchanged programs without overrides, `power_map` per role and layer, per-element overrides on the toolpath, missing structure power | Programs that print segments at the wrong power | `trimesh`, `shapely` |
| `test_substrate_plan.py` | Substrate main files (T52): experiment area (grid, margin, corner and QR clearance), the QR code width, overlap between experiments and with experiments already on the substrate, resin drop bounds, objective and duplicate-name checks, layout plot; T120: a hidden plot is built without pyplot (no Tk objects) | Experiments printed over each other or outside the resin drop | – |
| `test_resin_drop.py` | Resin-drop outline (T62): ellipse through the four edge points, circle and degenerate points (fallback), rectangle inside the ellipse, no boundary for dip-in, layout check against the ellipse | Experiments near the rim of a round drop printed into air or the drop edge | – |
| `test_image_functions.py` | `contour_mask` fills a contour found by `get_contours` (T65) | Focus and plane detection crashing in OpenCV on the lab PC (NumPy 2 makes `int` 64 bit on Windows) | – |
| `test_time_estimate.py` | Expected printing time of layer programs (T28): length over speed for `LINEAR`/`RAPID`, default and modal speed, incremental moves, `DWELL`, galvo plus stage, the stored record and duration formatting | Wrong time estimates in the log and the summary | – |
| `test_overview.py` | Overview mosaic (T28): field of view, image grid with overlap, stitched image shows a synthetic scene at the right stage coordinates (mirrored y axis), scaling to the pixel size | An overview that is mirrored, shifted or too large to store | – |
| `testprint/test_testprint_structure.py` | T137: `ParameterFieldStructure` translates a hand-made toolpath job into one IFOV layer program per z level (ascending, z rounded to 1 nm), one block per run of equal power and leaf kind, element order kept, `SET_POWER` values follow the attenuator calibration, `DWELL` only after a power change, per-element powers need a structure power, JSON round trip with identical programs | Test fields printed at the wrong power or in the wrong layer; a restart building another field | `trimesh`, `shapely` |
| `testprint/test_testprint_cells.py` | T138: cell primitives (lines, line sets, polylines, dots, bridges, woodpile) and sliced height maps (pad with ramp, wedge, cap, pillar on base): element counts, bounds, power and cell id on every element, aligned z grid (cells with the same Δz share layers), substrate anchoring by repeating the first slice, `min_z_um`, determinism, invalid input names the cell | Cells whose layers do not line up (many layer programs); unanchored volume cells | `trimesh`, `shapely` |
| `testprint/test_testprint_field.py` | T139: `ParameterField` header (L mark, 3-bit id, REF pad), merge by z, ordering strategies (`row_by_row`, registry, unknown name), validation reporting every problem (outside, header strip, gaps 2 / 4.5 µm and per-cell override, z range, power range, duplicates), cell table and CSV, round trip and determinism through `ParameterFieldStructure`, top-view plot | Overlapping or misplaced cells; a cell table that does not match the print | `trimesh`, `shapely` |
| `testprint/test_testprint_voxel_fit.py` | T150: `VoxelFitModel` kinds `threshold_ln`, `power_law`, `tabulated` reproduce known points, no extrapolation outside the power range or at another velocity, JSON round trip, new kinds without class change, `Model3D_Slicer(voxel_model=…)` accepts the model | Hatch / slice distances from an extrapolated voxel size | `trimesh`, `shapely` for the slicer case |
| `testprint/test_testprint_calibration.py` | T140: `ProcessCalibration` conversions with the voxel size at the cell power, range errors, JSON round trips, missing values (`MissingPropertyError`), schema errors | Stage B printed with wrong absolute values or a silent default | – |
| `testprint/test_power_switch.py` | T148: `PowerSwitchLines` (line pairs 2 µm apart, four segments alternating 0.25/0.75 mW, one IFOV block with `$AO` per segment, `DWELL` only on the second line of a pair, two reference lines), JSON round trip; slow: layout and dry run of `mains/lab_checks/power_switch_check.py` | A lab check that writes another pattern than the work order describes | – (dry run marked `slow`) |
| `testprint/test_testprint_parameter_tests.py` | T158–T161, parameter tests version 2: material start file (defaults, halves a/b, round trip, errors), sub-field bit in the header, every Quick PT / Full PT-01 sub-field valid with the powers of its half, cell counts, geometry rules (walls from −1 to +1 µm, pads 1 µm in the substrate, F2 line 2.5 µm, F4 three layers, F5 caps at the support power, F7 pillars from the base top), Voxel PT-01 gap-cell z levels (gap 0 = double exposure), factories (spec round trip, power check only with a known range), slow: program lines and layer counts | A parameter test that does not fit its 60 µm field or writes other values than its cell table | `trimesh`, `shapely` |

## Dummy integration tests

These run the real classes (`System`, `A3200`, `Aerotech3200`, `Camera`, `Dhm`, `Attenuator`, `Experiment`)
on simulated hardware from `nanofactorysystem.backends.dummy`. The fake controller works at the TCP/ASCII
level, so the exact command strings are checked.

| Module | What it tests | Why it matters (failure it catches) | Requirements |
|---|---|---|---|
| `backends/test_dummy_controller.py` | The fake A3200: protocol frames, motion, laser and exposures, program tasks, fault injection, call log; T127/T128: the program is removed under its loaded name, T152: every load gets a fresh execution name whose copy is deleted after the removal, and a refused LOAD blocks only its own name (the next program loads), a task error before start carries the decoded error code and is cleaned up, an early "complete" is a failure (trailing empty lines are not), a refused LOAD carries the `~LASTERROR` text and is cleaned up, a LOAD without reply times out and the connection is reopened, a failed removal does not raise | The simulation itself being wrong, which would make all other dummy tests meaningless | – |
| `backends/test_dummy_devices.py` | Camera, DHM and attenuator facades on the simulated devices; determinism; protocol conformance | Exposure/OPL optimisation or calibration conversion breaking | – |
| `backends/test_command_logs.py` | Golden command logs (`test/golden/commands_*.txt`) of System use and complete experiments (DefaultSetup and SetupIFOV); the random session token of the execution names (T152) is written as `<session>` | **Any change of the commands sent to the controller**, e.g. by refactoring the controller classes (recorded before the T20 merge) | – (experiment flows marked `slow`) |
| `backends/test_controller_merge.py` | One controller object in `System`, program tasks on `A3200`, zMax guard for `.api` moves, `Aerotech3200` without config, error types | Moving above the safe z range through `.api`; regressions of the controller merge | – |
| `backends/test_timeouts.py` | Connect/response timeouts, reading split responses, bounded waiting for axes, z-line, stalled tasks and `PROGRAM STOP` | A missing or hung device freezing the program instead of failing with an error | – |
| `backends/test_dummy_system.py` | `System` start-up command sequence, z-line, backend switch; the real backend still opens the same devices; T135: a z-line after a program on its task loads the z-line program again | `System` sending different commands to the machine; the default backend changing | – |
| `backends/test_dry_run_helper.py` | `backends.dummy.dry_run` (T110): the context manager that main scripts use for dry runs adds a missing user and objective to the configuration only for the dry run, replaces `time.sleep` by the virtual clock and restores both, also after an error | A dry run that changes the configuration or `time.sleep` of the session after it ends | – |
| `devices/test_aerotech.py` | The old `A3200` controller: commands, µm parsing, `zMax` safety, power, z-line, errors; T154: execution copies above the path limit go to the short folder, or are refused | Moving outside the safe z range; wrong units | – (plus 1 hardware test) |
| `devices/test_program_loader.py` | T129/T132 library loader on the dummy loader: memory budget (peak, largest part, part size, fits, no room), last statement line, every part on task 1 with add-ahead (compile without a task, associate when the previous part has completed; task 2 never used) with every program removed and the execution copies deleted, the order add → associate → start → add next → remove → associate, task error (message with the decoded error code) / early end / compile failure / associate failure stop and clean up (with the layer as key), execution names unique across runners, compile postponed when the budget is exhausted, a first part over budget refused | A loader that leaves programs on the controller, prints on the untuned task 2, compiles beyond the memory budget, or reports a failed part as printed | – |
| `devices/test_health.py` | T133 controller health check on the fake controller: healthy report, axis fault and task error as problems, unreachable interface, R0 stops tasks without moving and removes the given execution names (T152), `tasklist` parsing in any locale, `mains/controller_health.py --dry-run --r0`; R1 restarts the interface and reconnects, gives up after the wait; R2 reset; `controller_health.py --r1/--r2/--r3` (R2/R3 only after the confirmation) | A print started on a controller in error, or a recovery that moves an axis | – |
| `devices/test_attenuator.py` | Power ↔ attenuator conversion | Wrong laser power | – (plus 1 hardware test) |
| `devices/test_camera.py` | Exposure optimisation, image container | Unusable camera images | – (plus 1 hardware test) |
| `devices/test_camera_timeout.py` | T102: the wait for a camera image is twice the exposure (µs → ms) plus a transfer margin; a missed frame raises `TimeoutError` instead of blocking, a failed request `RuntimeError` (fake function interface, no mvIMPACT) | A camera call that blocks for hours on a missed frame | – |
| `dhm/test_dhm.py` | DHM client: objective selection, shutter, motor, hologram | DHM communication errors | – (plus 1 hardware test) |
| `dhm/test_dhmclient_errors.py` | T109 (finding B19): the v6 `DhmClient` raises `AttributeError` for writing a read-only and reading a write-only attribute (before: `raise (AttributeError, ...)`, a `TypeError` in Python 3) | A misleading error from the DHM client | – |
| `dhm/test_motorscan.py` | OPL motor scan: the bracket is widened step by step, stays inside the motor range, and a missing maximum raises `MotorScanError` | An OPL scan that drives the motor out of range or gives up too early | – |
| `dhm/test_manual_helper.py` | `reset()` of the interactive DHM helper `test/manual/dhm/DHMUserBackend.py`, run on the dummy DHM | A helper that keeps an old connection or old state after a reset | – |
| `test_femtika/test_device_no_laser.py` | `Aerotech3200` status, positions, tasks, homing on the simulated controller | Parsing errors in the status answers of the controller | – (the same tests also run as hardware tests) |
| `test_experiment.py` | `Experiment`: printing all layers, a failed layer (logged, printing continues with `stop_on_failure=False`), T128: the first failed layer stops the structure (`PrintStoppedError`, program removed under its loaded name), T152: a refused LOAD of one layer does not block the following layers, an early end counts as failure, the restart prints the failed layer again, failed layers behind printed ones are left to `reprint_layers()`, T129: `program_loader="library"` prints every layer on task 1 with add-ahead (T132; part size from the memory budget) and stops at the first failed layer, T133: an unhealthy controller (axis fault R0 cannot clear) is refused before printing, the health log after a failure, empty structures, OPL scan, substrate information, experiment dictionary, restart (same experiment file and UUID), restart after two aborts, import of an old JSON-only folder on restart, repeated structures (names, own grid cell), restart of a moved experiment folder (relative paths), capture records in the experiment file (commanded and actual position per capture, several positions), an exception during printing, refusing a folder that already holds an experiment, command and console log stored per experiment and session (also after an abort), two experiments on one substrate in the default location (labels, folders, index), the substrate index after a restart, substrate information in the experiment file, the summary after building and printing, the experiment plot (corners, double corner, QR code, UUID) and structure plots on request, camera images only with `camera_capture` (both values, stored, used on restart), captures taken with the galvo at A = B = 0 and Z not moved, `print_progress.json` counts and times for drop direction UP and DOWN after a complete and an aborted structure; power per structure and per layer (T31: list or function of the layer id, repetitions, wrong length, stored powers); experiment center inside the ellipse through the resin-drop edges (T62), edges stored for a restart; expected and actual printing time (T28); overview mosaic before and after printing (T28: stored image, PNG, single images, area with or without corner markers); T120: a hidden plot is built without pyplot (no Tk objects); T125: layer programs above `max_program_lines` split by the build and printed in parts (same exposures as unsplit, parts removed), the build stops if a layer cannot be split (nothing printed), the print reuses the parts of the build, every part of an IFOV layer carries the whole layer setup, reprinting the failed layers with `reprint_layers()` and `mains/reprint_layers.py` (plan, status, no second exposure; DOWN: highest layer first, split by the reprint itself); T124 whole-structure program compressed or as reference; T130 optimised programs print the same path within 10 nm; T133 R1 at most `max_r1_per_structure` per structure, R2 only after consent and before anything was printed | A single failed layer aborting a whole print; wrong metadata for restarts; captures that cannot be traced to a stage position; an unreadable file after a crash; overwriting an earlier experiment; a command log overwritten by the next run | – |
| `test_experiment_spec_json.py` | Project-file form of `ExperimentSpec`/`StructureSpec` (T77): every field round trip, `null` for objective defaults, named factories (`BuildContext`, wrong arguments, duplicate names, import from the source file), unstorable fields named in the error (plain callables, functions in `layer_power`/`slicer`, two geometries, non-JSON `sys_args`), typos and other major schema versions refused, slicer inputs inline / in `inputs/` / as file with SHA-256 check, stand-alone structure files, a center given as plain `(x, y)` pair converted to `Point2D` (T121) | A spec that is saved silently incomplete or cannot be read back; a changed input file printed without notice | – |
| `test_drop_direction.py` | Drop direction (T43): the scanner keeps the focus range with the highest z for both directions (T168, incl. the lab case of the immersion oil found after the resin interface); `Experiment` passes the drop direction to the tools; UP and DOWN write identical layer programs in opposite order; QR pixel lines are drawn upwards for DOWN | Plane fits on the wrong interface; structures written at mirrored heights | – |
| `test_plane_fitting.py` | Plane-fit modes (`GRID`, `CORNERS`, `BORDER`, old integers), number and positions of the sample points, their storage, the experiment center check, the tilt warning, and a plane fit outside `Experiment` with a stand-in for the detection | Plane fits at wrong positions; experiments outside the resin drop; unnoticed tilt under large structures | – |
| `test_system.py` | `System` data container, homing | Missing metadata in stored experiments | – (plus 1 hardware test) |
| `tools/test_focus_dummy.py` | `Focus` runs end to end on `System`; the z-line exposure reaches the controller | The tools breaking on API changes of `System` | – |
| `integration/test_dry_run_spec.py` | Experiments described by `ExperimentSpec` and run with `run_experiment()`: program sources DRAWING and SLICER (height map through `Model3D_Slicer`, also with `voxel_material` and a voxel database: values in the experiment file and the summary), objective defaults, repetitions, validation, and the examples of `mains/Experiments/old_experiment/experiment_template.py`; the stored spec (`/spec`, `experiment_spec.json`, slicer height map in `inputs/`, T77) can be loaded again | A template or spec that fails on the lab PC; slicer programs with statements the controller simulation does not know | – (marked `slow`) |
| `integration/test_ported_scripts.py` | The experiment scripts ported to `ExperimentSpec` (T51), in `mains/Experiments/old_experiment/` since T113: every script builds a valid spec for its objectives (and refuses the others), structure factories and empty cells; every script's spec survives the project-file round trip with identical built structures, also the template's specs (T77); one script (DHM tomography, reduced grid, no corners) as a dry run on the dummy backend | A ported script that fails on the lab PC before the first print (missing parameters, wrong objective values, left-over `sample.orientation`) | – (dry run marked `slow`) |
| `integration/test_focal_points.py` | Focal-point script (T36, `mains/Experiments/old_experiment/focal_points/`): random points with minimal distance, line lengths with noise, dry run with 3 z-lines (one FocusDetect container each, `focal_points.json`, z-line programs on the controller, corners and QR code printed) | The z-line script failing on the lab PC after the plane fit | – (dry run marked `slow`) |
| `analysis/test_experiment_analysis.py` | Analysis tools in `analysis/experiment_analysis` (T66) on a printed dummy experiment with camera, DHM, overview and a DHM product: unpacking into PNG/CSV/TXT/JSON (lossless images, programs, logs, tables, no `.npy`), refused output folders, zip and `.zdc` export, CSV styles, a snapshot while a process holds the lock, scalar text written as stored without NumPy conversion (T123); `ExperimentFile` reading, storing/loading/deleting results under `/analysis`, writes refused while an experiment process holds the file, reading during an experiment session, the command line; T124: the compressed structure program is unpacked as `program.txt` | An unpacked folder that Windows cannot open or that misses data; an analysis that disturbs a running print or overwrites data of the printing process | – (experiment-based tests marked `slow`; `analysis/` is on the pytest `pythonpath`) |
| `analysis/test_ptd_analysis.py` | T147 (on version 2 since T164): import of filled field-1 rows of a cell-table CSV (Full PT-01 F1) into the voxel database (method required, empty rows and other fields skipped); slow: the cell table regenerated from `/spec` of a dry-run Full PT-01 F1 experiment (sub-fields a and b) equals the builder's table, stage positions = structure centre + cell centre, CSV template with empty measurement columns, result stored through `ExperimentFile` | A cell table that does not match the printed cells; model values in measurement columns; voxel data imported without method | `trimesh`, `shapely`; dry run marked `slow` |
| `analysis/test_voxel_fit_analysis.py` | T151: weighted least-squares fit of the voxel model on synthetic data with noise: `threshold_ln` with given scales recovers P_th and n_eff within 3σ of the stated uncertainty, without scales only d_scale²·n_eff is fitted; AIC prefers the generating model (threshold vs. linear power law); point selection (F1 heights clipped by the substrate are not lengths); fits need widths and lengths; calibration file and plot; slow: inputs and results stored through `ExperimentFile` | A wrong threshold or nonlinearity in the calibration of stage B; a model chosen that does not describe the data | – (storage test marked `slow`) |
| `analysis/test_parameter_test_analysis.py` | T163: relative columns (p_rel, h_rel, s_rel, dz_rel) added after the measurement, no extrapolation outside the voxel model; voxel length from the gap test (bracket, l_base from the base-power experiment, open brackets); fit points from wall widths and gap lengths | Relative values computed with a wrong reference; wrong voxel lengths from the gap test | – |
| `integration/test_dry_run_default_experiment.py` | `mains/Experiments/old_experiment/default_exp_file.py` end to end: start-up, `plane_fit` (known plane), `build_programs`, `print_experiment`; the experiment file matches its JSON copies and the summary | An experiment script failing on the lab PC halfway through a print; JSON copies that differ from the experiment file | – (marked `slow`) |
| `integration/test_lab_check.py` | The lab check of the new features (`mains/lab_checks/new_features_check.py`, T68): valid layout; slow dry run of both experiments (overview before/after, camera captures, power per layer, repetition, slicer block in IFOV mode, unpacked files) | A lab check script that fails on the lab PC before it reaches the hardware | – |
| `lab_checks/test_program_loading_lab.py` | Hardware-free helpers of the program loading lab tests (`mains/lab_checks/program_loading_lab.py`, T129): T153: the dry copy of a real layer for P5 (laser gate off, `$AO` 0, no Z word, stage XY shifted to the current position, galvo lines unchanged; unsafe lines refused; split parts stay dry), the INtime prompt reads a pasted block, the session-3 steps are registered; session 3b: motion steps require enabled and homed axes (`axes_not_ready`); the `states` step of T101 (task-mode bits decoded, galvo rotation angle from an A-only move, its programs set modes only: no motion, laser gate off, mode lines as in a generated IFOV layer program); synthetic dry programs (exact length, laser gate off, galvo axes A/B only within ±0.05 mm, number formats), truncated layer programs keep header and footer, memory queries of the PC and the process, the memory budget uses the largest measured memory per line, worker results; for session 2 (T134): the real-header variant, source lines of a compiled `.ogm`, program name candidates, process age and the stale-restart warning, axis state parsing, the `A3200Reset` prototype check | A lab script that fails on the lab PC, or that exposes or exceeds the memory budget | – (Windows only) |
| `integration/test_main_entry.py` | The main entry point `mains/main.py` and the default experiment `mains/Experiments/default_experiment.py` (T110): the template writes out every `ExperimentSpec` field, its specs resolve and survive the project-file round trip, the rectangle factory takes the acceleration of its axes; the substrate layout of `main.py` is valid; tasks `layout` and `materials` as dry runs; slow dry runs of the default experiment and of the tasks `restart` and `analyse` | The entry point or the template failing on the lab PC before the first print | – (dry runs of experiments marked `slow`) |
| `integration/test_experiment_chain.py` | The experiment chain `mains/Experiments/chain_rectangle_doe_lens.py` (T113): three experiments with a 3 x 3 grid power (rows) x hatch (columns); the structures (rectangle 50 x 50 x 6 µm, DOE levels on a 3.5 µm base, aspheric lens R = 30 µm, k = 2.3, sag 6 µm) start 1 µm inside the substrate with slice 0.25 µm; powers outside the attenuator range are refused; the specs survive the project-file round trip; the layout on the resin drop is valid; slow dry run of the lens experiment | The chain failing on the lab PC before the first print; wrong geometry or parameter order in the grid | – (dry run marked `slow`) |
| `integration/test_parameter_tests.py` | T162: the scripts in `mains/parametertest/`: material start file, 18 experiments (Quick PT, F1–F7, ten Voxel PT-01 powers) with margin 90 µm and reduced corners, QR code and corners at least 20 µm away from every grid (`check_marker_clearance`), layout of all experiments on the T113 drop, selection; slow dry run of Quick PT, Full F3 and Voxel 0.5 mW with the cell tables regenerated from `/spec` | The parameter tests failing on the lab PC; a QR code reaching into an experiment | `trimesh`, `shapely`; dry run marked `slow` (~5 min) |
| `integration/test_ifov_laser_test.py` | The T117 lab test `mains/Experiments/ifov_laser_test.py`: four experiments (current IFOV program, explicit laser ON/OFF, IFOV configuration of 2026-03, galvo only without IFOV) of 2 x 2 squares (0.25 / 0.7 mW x lines along x / y, hatch 0.2 µm); all IFOV variants write the same lines as `Rectangle3D_IFOV`, each differs only in its variant; layout on the drop; slow dry run of one variant | A lab test that changes more than one thing per variant, so its result names no cause | – (dry run marked `slow`) |
| `integration/test_main_png.py` | The PNG entry script `mains/main_PNG.py` (T116): a 16-bit PNG with pixel size and µm per gray value gives one `HeightMap_IFOV` (size, height, 1 µm in the substrate, objective of `main.py`); the spec is one IFOV structure in the center of the resin drop (or at `CENTER`); preview without hardware; the script imports `main.py` from any working directory; slow dry runs (T119): with `SUBSTRATE_LABEL` into that substrate below the data root incl. `substrate_layout.json`, without it into `OUTPUT_ROOT` | A PNG print that fails on the lab PC or lands outside the drop | – (dry run marked `slow`) |
| `integration/test_main_3d_model.py` | T166: `mains/main_3D_model.py` on the experiment environment: a model file (box STL) gives one `ExperimentSpec` with `ProgramSource.SLICER`, IFOV, in the center of the resin drop, area from the model extent plus margin, 0.5 µm in the substrate; the spec saves with the model as input and reads back; a missing model is named; slow dry run on the dummy backend | A 3D-model print that fails on the lab PC or lands outside the drop | `trimesh`, `shapely` (dry run marked `slow`) |
| `integration/test_dry_run_materials.py` | Material snapshots of a dry run (T75): a substrate whose resin is given by registry name stores the full snapshot (refractive indices, text properties, registry file) in `/metadata/materials`, the names reach `sys_args["sample"]` (M4), schema 1.1; without a registry only the names are stored | An experiment file that does not say which material (and which refractive index) was printed | `slow` |
| `integration/test_dry_run_substrate.py` | `substrate_plan.run_substrate()`: two experiments on one substrate give two experiment files and one substrate index; the planned areas match the printed rectangles; a second run is refused because the areas are taken; optional folder, confirmation between experiments; an invalid layout creates nothing; the layout of `mains/substrate_main.py` is valid; T76: area and drop index in the index, an experiment that was not started stays `planned`, `substrate_overview`; T118: `substrate_layout.json` lists both experiments with label, name and state `done`, the plot exists | A substrate main file that overwrites or overprints earlier experiments, or stops halfway with a broken index | – |

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
