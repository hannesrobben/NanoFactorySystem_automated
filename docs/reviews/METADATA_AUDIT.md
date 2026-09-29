# Experiment metadata audit (T41)

Date: 2026-09-29. Code state: branch `docs/t41-metadata-audit`, based on `main_HR` at `d2dbd66`.

This audit lists everything an experiment writes today, where and by which method, and rates each
metadata item. It is the input for the storage design in T42. Analysis only; no code was changed.

## 1. Method

- Read `nanofactorysystem/experiment.py`, `system.py`, `devices/a3200.py`, `devices/aerotech/__init__.py`,
  `devices/camera.py`, `devices/dhm.py`, `tools/plane.py`, `aerobasic/programs/drawings/base.py`,
  `runtime.py` and `mains/Experiments/default_exp_file.py`.
- Two dummy dry runs of `default_exp_file.binary_testprint` (seed 0, known plane
  `world.sample.plane()`, user `Test`), each written to an empty folder:
  - **Run A**: the template as it is (and as `test/integration/` runs it): Zeiss 20x, `IFOV_off`,
    DHM off. The template adds no user structure, so only the 4 corners and the QR code are printed.
  - **Run B**: Zeiss 63x, `IFOV_on`, DHM on, plus one user structure (`Stair`, `StructureType.NORMAL`,
    added after `plane_fit()`), so that DHM files, `oplscan/` and a user structure appear.
- The contents of all JSON files, of `.zdc` containers (`content.json`, `meta.json`, `data/*`, `meas/*`),
  of a layer program and of the command log were inspected.

Not reproducible in a dry run (read from the code instead): the files of a measured plane fit
(`planefit/`), because the dry run passes `plane=`; everything that depends on real hardware answers.

## 2. Files an experiment writes

`<exp>` is the `path` passed to `Experiment` (in the template: `<path>/testprint_dhm`).
`<name>` is a structure name (`corner_tr`, `corner_tl`, `corner_bl`, `corner_br`, `qrcode`, user names),
`<i>` a layer id (3 digits in file names of programs, unpadded in image names).

| File | Written by | When | Content | Location |
|---|---|---|---|---|
| `experiment_dictionary.json` | `Experiment._save_exp_dict` (from `_create_experiment_dictionary`) | once, in `Experiment.__init__` | constructor arguments (see 3.1) | `<exp>/` |
| `calibration_file.npy` | `Experiment._save_calibration` | once, in `__init__` | attenuator calibration `attenuator.data`: N×2 array (attenuator value, power in mW) | `<exp>/` |
| `substrate_information.json` | `Experiment._save_substrate_information` | once, in `__init__`, only if `substrate_information` is given | free dict from the script, merged into an existing file | **parent** of `<exp>` |
| `experiment.png` | `Experiment.plot_experiment` | when the script calls it | resin ellipse, experiment rectangle, structure grid with indices, plane-fit sample points | `<exp>/` |
| `qr_code_image.png` | `Experiment.add_qrcode_structure` | in `__init__` (unless `skip_corner`) | QR code image of the experiment UUID | `<exp>/` |
| `planefit/back.zdc` | `Experiment.plane_fit` (`plane.layer.focus.imgBack`) | measured plane fit only | background camera image of focus detection | `<exp>/planefit/` |
| `planefit/layer/layer-<nn>/…`, `layer.zdc` | `Plane.run` → `Layer.run` | measured plane fit only, per sample point | layer (resin interface) detection per point, incl. its images | `<exp>/planefit/layer/` |
| `planefit/plane.zdc` | `Experiment.plane_fit` (`Plane.container`) | measured plane fit only | `data/plane.json` (parameters), `meas/steps.json` (x, y and result per sample point), `meas/result.json` (low/high interface points) | `<exp>/planefit/` |
| `oplscan/opl.txt` | `Experiment.opl_scan` | DHM only | one number: OPL motor position in µm | `<exp>/oplscan/` |
| `structures.json` | `Experiment._build_programs` | once, in `build_programs()` | list of structure configurations (see 3.2) | `<exp>/` |
| `structures/<name>/programs/program_<name>.<iii>.txt` | `Experiment.structure_program` (`AeroBasicProgram.write`) | `build_programs()`, one per layer | AeroBasic layer program: header comment with creation time, `LINEAR X Y` to the structure center, layer moves | `<exp>/structures/<name>/programs/` |
| `structures/<name>/program_<name>.txt` | `Experiment.structure_program` | `build_programs()` | all layers of the structure in one program (not executed, reference only) | `<exp>/structures/<name>/` |
| `structures/<name>/plot_<name>.png` | `Experiment.structure_program` | **never**: `plotting_structure = False` is hard-coded | movement plot of the structure | – |
| `structures/<name>/camera_<name>_before.zdc`, `…_after.zdc` | `Experiment.measure` (`System.getimage`) | before (not on restart) and after each structure | `CameraImage` container (see 3.4) | `<exp>/structures/<name>/` |
| `structures/<name>/camera/camera_<name>.<i>.zdc` | `Experiment.measure` | after every layer | `CameraImage` container | `<exp>/structures/<name>/camera/` |
| `structures/<name>/dhm_<name>_before.zdc`, `…_after.zdc` | `Experiment.measure` (`Dhm.container`) | DHM only, as the camera images | `HologramImage` container with `image_count` (after: `+10`) holograms | `<exp>/structures/<name>/` |
| `structures/<name>/dhm/dhm_<name>.<i>.zdc` | `Experiment.measure` | DHM only, after every layer | `HologramImage` container | `<exp>/structures/<name>/dhm/` |
| `print_progress.json` | `Experiment.update_print_progress` | after every layer, on a failed layer, after every structure | current structure, finished structures, error log (see 3.3) | `<exp>/` |
| `console.log` (log file) | `runtime.getLogger(logfile=…)`, called by the script | whole run, appended (`FileHandler` mode `a`, also on restart) | all log messages at DEBUG level with timestamps | `<exp>/` in the template (the path is chosen by the script) |
| `A3200.log` | `AerotechController.save_log` from `System.close()` | once, when the system is closed | controller init/connect times and every command with send/receive time and response | `backend.program_dir()`: **real hardware: the current working directory** (usually `mains/`), dummy: backend workdir |
| `python_aerobasic_program.pgm` | `AerotechController.run_program_as_task` | per layer, copy of the layer `.txt` file | the program the controller actually loads | `program_dir`, **real hardware: the home directory**; overwritten per layer |

Notes on the list in T41:
- The per-layer programs are `.txt` files in the experiment folder. The only `.pgm` file is
  `python_aerobasic_program.pgm` outside the experiment folder, which is overwritten for every layer.
  Since the `.txt` files are byte-identical sources, no program information is lost.
- `plot_<name>.png` is never written in the current code.
- Dummy-only files in the backend workdir (`calibration.dat`, `__zline__.pgm`) are not experiment data.

Counts in the dry runs: run A 5 structures, 50 layer programs, 60 camera containers; run B 6 structures,
61 layer programs, 73 camera and 73 DHM containers.

## 3. Content of the metadata files

### 3.1 `experiment_dictionary.json`

Keys: `path`, `user`, `objective`, `logger`, `sys_args`, `default_power`, `low_speed_um`, `high_speed_um`,
`resin_corner_tr`, `resin_corner_bl`, `structure_size`, `margin`, `padding`, `absolute_grid_center`,
`grid_size`, `n_mid_points`, `drop_direction`, `drop_direction_information`, `corner_z`, `corner_width`,
`corner_length`, `corner_height`, `corner_hatch`, `corner_slice`, `fov_dim`, `skip_corner`,
`plane_fit_mode`, `setup`.

Observations:
- Written only once in `__init__`; later state (UUID, plane, programs, print status) is never added.
- The experiment UUID (`qr_text`) is **not** in the file. It exists only in the log and as `text` of the
  QR-code structure in `structures.json` (after `build_programs()`).
- Vectors are stored as `str()` of NumPy arrays or tuples (`"[ 1310. 19500.]"`, `"[2 3]"`, `"(150, 150)"`)
  and parsed back with string handling in `parameters_from_dictionary`.
- `path` and `logger` are absolute paths; a moved or copied folder is restarted into the old location.
- `drop_direction` is stored as the enum value (`UP = -1`, `DOWN = 1`) plus the name.
- `sys_args` contains `sample.orientation: "top"` from the template, also when the drop direction is DOWN.
- `low_speed_um` is stored but not used anywhere in the code.
- Accelerations read from the controller (`accel_x/a/z`) and the IFOV acceleration workaround
  (`accel_a = accel_x / 2`) are not stored.

### 3.2 `structures.json`

One entry per structure (dummy structures are skipped): `name`, `axes`, `power`, `center_x`, `center_y`,
`center_z`, `structure` (`DrawableObject.to_json()`), `program_file`, `layer_files`, `number of dhm images`.

Observations:
- `center_x/y` is the grid reference point plus `structure.center_point` (XY), `center_z` the plane value
  there; units (µm) are not stated. For corners the reference point is the grid corner, and the corner
  geometry lies at `center_point` (e.g. `(-45, 45, -2)`) relative to it.
- The `StructureType` (NORMAL, CORNER, QRCODE, IFOV, …) and the `CornerPosition` are not stored; corners
  and the QR code are recognisable only by name.
- `power` is in mW (per `A3200.power`), but for IFOV structures the power actually written is the one
  inside the structure (`IFOV_Lines.power`, converted with the calibration); the top-level `power` is then
  only the attenuator setting before the structure. Two different "power" values exist per structure.
- `program_file` and `layer_files` are absolute paths.
- `structure` serialisation (`DrawableObject._init_args`):
  - takes `__init__.__code__.co_varnames`, which also contains local variables, and keeps a name only
    if an attribute of the same name exists; parameters stored under another name are silently dropped;
  - skips `data` and `height_profile` (N046), so height-function structures (gratings, lenses, DOEs) lose
    their height data;
  - stores enums and other objects as `str()` (e.g. `"QrErrorCorrection.Q"`);
  - stores only the class name, not the module;
  - there is no `from_json`; a restart uses the layer program files only and cannot rebuild a structure.
- Slicing and hatching parameters are only available as constructor arguments of each class, with
  class-specific names (`slice_size`, `hatch_size`, …; the slicer pipeline is not used by `Experiment`).
- Velocities likewise have class-specific names and units: `Corner.F = 5000` (µm/s), `Stair.velocity`,
  `QRCode.horizontal_velocity`; the layer program contains `F10.000000` (mm/s).

### 3.3 `print_progress.json`

`current_structure` (`name`, `finished layer`, `layer count (n printed layers)`, `order`, `error`,
`drop direction`, `information`), `finished_structures` (list of the same dicts), `error log`.

Observations:
- `layer count (n printed layers)` is the loop **index** of the last printed layer, not a count: with UP
  and 10 layers it ends at 9, with DOWN it ends at 0.
- No timestamps; the duration of a structure is only in the log ("Making … took …").
- A fixed explanatory text is repeated in every entry.
- Layer ids are recovered from the program file names (`split('.')[-2]`) instead of being stored with
  the layer files.

### 3.4 Camera and DHM containers (`.zdc`)

- `CameraImage`: `content.json` (container UUID, `created`/`storageTime` in UTC with 1 s resolution,
  `usedSoftware: []`), `meta.json` (author, email, organization from the user config; `timestamp` empty),
  `data/camera.json` (camera settings incl. exposure), `data/objective.json`, `data/location.json`
  (**actual** X, Y, Z, A, B in µm read after the move), `meas/image.png`.
- `HologramImage`: `content.json`, `meta.json`, `data/hologram.json` (DHM parameters, device, laser
  wavelength, OPL motor position), `data/objective.json`, `meas/image*.png` (`image_count` holograms),
  `meas/image_capture_times.json` (duration of each capture in s, no absolute time).
  **No stage position** is stored in DHM containers (`measure()` does not pass `loc`).
- Neither container stores the structure name, layer id or the commanded position; they are known only
  from the file name and folder.
- `measure()` moves only X and Y (`LINEAR X Y F20`). Z and the galvo axes stay where the last layer left
  them (run B: `A = 30 µm`, `B = 225 µm`, Z at the last layer). The capture height is therefore not
  defined by the experiment, and differs between UP and DOWN.
- A camera image is always taken; there is no switch (T45).

### 3.5 Layer programs and command log

- Layer program header: `' Created on <local time> by (AeroBasicProgram)` — the build time, not the
  print time. The laser power is **not** in the layer program for non-IFOV structures; it is set through
  the attenuator before the structure (`System.controller.power`). A layer program alone does not
  reproduce the exposure.
- `A3200.log` contains every command with timestamps, which is the only record of what was actually sent,
  but it is written to the working directory, overwritten by the next run, and only on a clean
  `System.close()`.

## 4. Rating of the metadata items

Ratings: **complete** (stored, correct, machine-readable), **incomplete** (partly stored, only derivable,
or not machine-readable), **wrong** (stored, but misleading or incorrect), **missing** (not stored).
"Covered by" names the todo that already addresses the gap.

| Item | Rating | Where today | Finding | Covered by |
|---|---|---|---|---|
| Experiment UUID (QR text) | missing | log; `structures.json` QR structure `text` | not in `experiment_dictionary.json`; a restart creates a new UUID | T42, T47, T50 |
| User | incomplete | exp. dict `user` (config key); author/email in `.zdc` `meta.json` | only the key; name/email/ORCID not in the dict | T42 |
| Objective | complete | exp. dict `objective`; `.zdc` `data/objective.json` | – | – |
| Setup (IFOV on/off) per experiment | complete | exp. dict `setup` | – | – |
| Setup per structure | incomplete | `structures.json` `axes` (`ABZ`/`XYZ`) | IFOV on/off is global only; `axes` is the printing axes, not the setup | T42, T49 |
| DHM usage | complete | exp. dict `sys_args.dhm.usage` | – | – |
| Camera usage | missing | – | images are always taken; not a parameter | T45 |
| Plane-fit mode | incomplete | exp. dict `plane_fit_mode` | stored as bare integer 0/1 without meaning | T44 |
| Plane-fit sample points | incomplete | `planefit/plane.zdc` `meas/steps.json` (measured fit only) | not stored in the dict; with `plane=` not stored at all | T44 |
| Fitted plane | incomplete / missing | `planefit/plane.zdc` `meas/result.json` (points), fit only in the log | fit parameters not stored; with `plane=` nothing is stored | T44, T42 |
| Drop direction | incomplete | exp. dict `drop_direction` (+ name); `print_progress.json` text | stored, but contradicted by `sys_args.sample.orientation: "top"`; layer tools use a separate hard-coded orientation | T43 |
| Experiment center | incomplete | exp. dict `absolute_grid_center` | stored as NumPy string, not as numbers | T42 |
| Resin drop edges | incomplete | exp. dict `resin_corner_tr/bl` | only the bounding box of the four edges; the edges themselves are lost; NumPy strings | T42, T48 |
| Positions of all corners | incomplete | `structures.json` `center_x/y` per corner + `structure.center_point` | corner position enum not stored; reference point vs. geometry position ambiguous | T42 |
| Double corner (position and orientation) | incomplete | `structures.json`: corner with `mark: true` and its `rotation_degree` | only derivable from structure arguments; not an explicit field | T42, T50 |
| Structure type | missing | – | `StructureType` not stored | T42, T49 |
| Slicing and hatching parameters | incomplete | constructor arguments in `structures.json` | class-specific names; dropped for attributes stored under other names; height data skipped | T42, T37 (N046), new T56 |
| Power per structure | incomplete | `structures.json` `power` (mW, unit not stated) | IFOV structures carry a second power inside the structure; not in the layer programs | T49, T31 |
| Velocity per structure | incomplete | constructor arguments (`F`, `velocity`, …) | class-specific names and units | T49 |
| Accelerations | missing | – | read from the controller, not stored | T42 |
| Attenuator calibration | incomplete | `calibration_file.npy` | table stored; fit kind only if set in `sys_args`; source file not recorded | T42, T47 |
| OPL motor position | complete | `oplscan/opl.txt`; `data/hologram.json` | – | – |
| Stage position of every capture | incomplete | camera: `data/location.json` (actual XYZAB); DHM: none | commanded position not stored; DHM without position; Z/galvo at capture undefined | T46, new T58 |
| Capture context (structure, layer, index) | incomplete | file and folder names only | not inside the containers | T46 |
| Print progress | wrong | `print_progress.json` | "layer count" is an index; no timestamps | T47, T50, new T59 |
| Layer programs | complete | `structures/<name>/programs/*.txt` | absolute paths in `structures.json`; power not inside the program | T47, new T57 |
| Command log (`A3200.log`) | wrong | working directory | not in the experiment folder; overwritten by the next run | new T55 |
| Git commit of the software | missing | – | – | T42 |
| Software version | missing | – | `pyproject.toml` version 0.7.0 not recorded; `.zdc` `usedSoftware` empty | T42 |
| Timestamps (start, end, per layer, per structure) | incomplete | log file; `.zdc` `created` (UTC, 1 s); program header (build time) | none in the JSON files; the print time of a layer is only in the log | T42, T47, T49 |
| Substrate information | incomplete | `substrate_information.json` in the parent folder | free dict, merged across experiments; no link from the experiment | T48 |
| Experiment overview plot | incomplete | `experiment.png` | corners and QR code not drawn; no UUID; `plot_<name>.png` never written | new T60 |
| Log file | complete | `console.log` in the experiment folder (chosen by the script) | appended on restart; path stored absolutely in the dict | T42 |

## 5. Defects not covered by T42–T50

Added to `TODO.md` as "(found during T41)":

- **T55**: `A3200.log` goes to the working directory and is overwritten by the next run; it should be
  written into the experiment folder (and survive an abort).
- **T56**: `DrawableObject._init_args` records local variables and silently drops parameters, stores enums
  as strings, and there is no `from_json`; structures cannot be rebuilt from `structures.json`. (N046,
  the skipped `data`, stays in T37.)
- **T57**: `structures.json` and `experiment_dictionary.json` store absolute paths; a copied or moved
  experiment folder cannot be restarted from its new location.
- **T58**: `measure()` moves only X/Y; Z and the galvo axes at the moment of a capture are left from the
  last layer. Decide and implement a defined capture position (Z and A/B).
- **T59**: `print_progress.json`: "layer count (n printed layers)" is the loop index (off by one for UP,
  0 for DOWN at the end), and the entries carry no timestamps.
- **T60**: `plot_experiment()` does not draw corners and QR code, and structure plots
  (`plot_<name>.png`) are disabled by a hard-coded `plotting_structure = False`.

Other observations that the planned todos already cover or that are minor:
- `low_speed_um` is unused (to be decided in T51 with the `ExperimentSpec`).
- The layer tools use a hard-coded `Orientation["UP"]` (T43).
- `sys_args.sample.orientation` duplicates the drop direction (T43).

## 6. Input for T42

- The experiment file must hold the UUID from the first write on, and every item rated "missing" above.
- Store numbers as numbers (no `str()` of arrays), units in names or attributes, and paths relative to
  the experiment root.
- Record commanded and actual position with each capture, for camera and DHM alike (T46).
- Store the command log, software version and git commit per experiment.
- Store the structure type, corner position and the double-corner flag explicitly, not only inside the
  structure arguments.
- Decide which "power" is authoritative for IFOV structures and store it once per structure (and later
  per layer, T31).
