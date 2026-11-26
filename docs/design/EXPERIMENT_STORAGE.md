# Design: Experiment storage and substrate model

Status: approved 2026-09-29; §15 (DHM service results) approved with T71 on 2026-11-18 and fixed by T83 on 2026-11-26

Approved by the maintainer on 2026-09-29 in the Claude Code session, with every proposal in §12
accepted as written.
Date: 2026-09-29. Todo: T42. Basis: `docs/reviews/METADATA_AUDIT.md` (T41).
Implemented by: T47 (experiment store), T48 (substrates, default location, index), T49 (summary),
T50 (restart); related: T46 (capture positions), T55–T59 (defects from the audit).

## 1. Goals and non-goals

**Goals**
- Several experiments on one substrate are stored side by side under a default location and can be
  found again by substrate, date and objective.
- One HDF5 file per experiment holds **all** of its data and metadata, so that a later user interface can
  load and save an experiment from this file alone.
- `structures.json`, `experiment_dictionary.json` and `experiment_summary.json` stay as redundant,
  human-readable copies written from the same data. `structures.json` stays the entry point of an
  experiment for people browsing the folder.
- A crash or abort never destroys data that was written before it, and never overwrites an earlier
  experiment.
- Every item rated missing, incomplete or wrong in the audit has a defined place.
- Old JSON-only experiment folders can still be read, at least for a restart.

**Non-goals**
- The DHM-PC transport and the reconstruction on the DHM PC (F4). This design only defines the
  receiving method `add_dhm_product()` in the printing process.
- Video recording (F3), speckle averaging (F5), DHM stitching (F6). Their data fits the capture model
  (§5.6), but nothing is built for them.
- A database server. The experiment index is plain files (§8).

## 2. Hierarchy

```
User root  ~/Documents/Femtika_Experiment/<user>/
└── Substrate        label HR-26-001, substrate UUID          (substrate.json)
    └── Experiment   label HR-26-001-A, experiment UUID = QR   (experiment.h5 + JSON copies)
        └── Structure    corner_tl, qrcode, grating_0, …
            ├── Layer        layer program, print status and times per layer
            └── Capture      camera image or DHM hologram (+ products), with position and time
```

- A **substrate** is one physical sample. It is described once and referenced by every experiment on it.
- An **experiment** is one run of `Experiment` (one grid with corners and QR code). Printing the same
  script again is a new experiment with a new label and UUID. A **restart** of an aborted run continues
  the same experiment (same folder, file and UUID; T50).
- A **structure** is one entry of `Experiment.structures`, including corners and the QR code.
- A **capture** is one call of the camera or of the DHM at one position (before, per layer, after).

## 3. Folder layout

```
~/Documents/Femtika_Experiment/                 default root (configurable, §3.2)
└── <user>/                                     the user key passed to Experiment (e.g. "Hannes")
    └── HR-26-001/                              substrate folder = substrate label
        ├── substrate.json                      substrate record and its experiment index (§8)
        ├── substrate_layout.json               copy: drops and every experiment area (§8, T118)
        ├── substrate_layout.png                plot of the same (§8, T118)
        ├── HR-26-001-A_20260929-2018/          experiment folder = <experiment label>_<start time>
        │   ├── experiment.h5                   the experiment file (authoritative)
        │   ├── structures.json                 copy, entry point for people
        │   ├── experiment_dictionary.json      copy
        │   ├── experiment_summary.json         copy (T49)
        │   ├── experiment.png, qr_code_image.png
        │   ├── console.log                     log file of all sessions (appended)
        │   ├── programs/<structure>/program_<structure>.<iii>.txt
        │   │                                   layer programs as files; the controller loads these
        │   └── experiment.lock                 only while a process writes (§6.3)
        └── HR-26-001-B_20260930-0912/
            └── …
```

- The experiment folder name contains the start time, so two experiments never share a folder, even if
  a label is reused by mistake. The label alone identifies the experiment for people.
- Layer programs stay files on disk because the controller loads programs from a file. Their text is
  also stored in the HDF5 file, which is authoritative; missing files are regenerated from it on restart.
- Camera and DHM data are **not** written as `.zdc` files any more; they go into `experiment.h5` (§5.6).
  The `.zdc` format stays available as an export (`ExperimentStore.export_capture()`), see §12 D6.
- Plane-fit containers (`planefit/*.zdc`, `layer.zdc`) are stored inside the file as well (§5.3).

### 3.1 Explicit path

`Experiment(..., path=...)` still works. An explicit `path` is the **experiment folder**; no substrate
folder is created around it, and `substrate.json` is not updated unless a substrate is given
explicitly (then the experiment is registered with its path). This keeps existing scripts and the dry
run working.

### 3.2 Default root

- Default: `~/Documents/Femtika_Experiment/<user>/`.
- Configurable per user in `nanofactory.json`: `"user:<name>": {"dataRoot": "D:/Femtika_Experiment/Hannes"}`
  (T48). `<user>` is not appended to a configured root.
- **Not in a synchronised folder:** before the first write the store checks that the resolved root does
  not lie inside a folder that is synchronised (Seafile, OneDrive, Dropbox). The check looks for path
  components named in a configurable list (default `["Seafile", "OneDrive", "Dropbox"]`, key
  `syncFolderNames` in the `system` section) and for a `.seafile-data`/`seafile-ignore.txt` marker in the
  parents. A hit raises an error unless `allowSyncedRoot=True` is passed. Reason: a sync client may lock
  or upload a half-written HDF5 file. Copying finished experiments to Seafile stays a manual step.

## 4. Identification

| ID | Form | Who sets it | Where |
|---|---|---|---|
| Substrate label | `<initials>-<yy>-<nnn>`, e.g. `HR-26-001` | proposed by the software (next free number of that user and year), confirmed by the user, written by hand on the substrate | `substrate.json`, experiment file attributes |
| Substrate UUID | UUID4 | software, once | `substrate.json`, experiment file attributes |
| Experiment label | `<substrate label>-<letter>`, e.g. `HR-26-001-A`, then `-B`, …, `-Z`, `-AA` | next free letter on the substrate | experiment file, folder name, `substrate.json` |
| Experiment UUID | UUID4 = QR-code text | `Experiment.__init__`, kept on restart | experiment file root attribute `experiment_uuid`, QR code, every JSON copy |
| Structure name | unique within the experiment (as today, `name_(1)` for duplicates) | `add_structure` | `/structures/<name>` |
| Capture id | `<nnnn>` running number per experiment | store | `/structures/<name>/captures/<nnnn>` |

- On the substrate only `001-A`, `001-B`, … needs to be written next to each experiment; the full label
  follows from the substrate label.
- `initials` is a new optional key of the user section; fallback: the first letters of the words of
  `name` (e.g. "Hannes Robben" → `HR`). See §12 D2.
- The experiment UUID is the main ID. Labels are for people and may be corrected later; the UUID never
  changes.

## 5. The experiment file (`experiment.h5`)

Conventions:
- Numbers are stored as numbers (scalars or arrays), never as `str()` of arrays.
- Units are part of the name: `_um`, `_mm`, `_mw`, `_um_s`, `_s`. Positions are absolute stage
  coordinates in µm unless the name says otherwise.
- Times are ISO 8601 strings in UTC with milliseconds (`2026-09-29T18:18:49.123Z`).
- Enums are stored by name (`"DOWN"`, `"IFOV_on"`, `"CORNER"`), not by value.
- Free-form nested data that has no fixed schema (e.g. `sys_args`, structure constructor arguments) is
  stored as a JSON string attribute with the suffix `_json`.
- Paths are relative to the experiment folder (T57).
- Large arrays use chunked datasets with `gzip` level 4 and `shuffle`, as the slicer storage does.

### 5.1 Root

Attributes of `/`:

| Attribute | Content |
|---|---|
| `file_type` | `"nanofactory.experiment"` |
| `schema_version` | `"1.0"`; `"1.1"` since T75 (`/metadata/materials`; `/spec` and `/inputs` from T77 belong to the same minor version); `"1.2"` since T124 (compressed or referenced whole-structure program); `"1.3"` since T83 (DHM service results, §15) (§9) |
| `experiment_uuid`, `experiment_label` | §4 |
| `substrate_uuid`, `substrate_label` | §4 (empty strings if no substrate is given) |
| `created` | first write |
| `status` | `created` → `built` → `printing` → `finished` / `aborted` / `failed` |
| `updated` | time of the last write |

### 5.2 `/metadata`

| Group | Content |
|---|---|
| `/metadata/experiment` | all `Experiment` parameters as typed attributes: `center_um` (2), `resin_edges_um` (4×2, the measured edges, not only their bounding box), `resin_corner_bl_um`, `resin_corner_tr_um`, `grid` (2), `structure_size_um`, `margin_um`, `padding_um`, `fov_um` (2), `n_mid_points`, `default_power_mw`, `low_speed_um_s`, `high_speed_um_s`, `corner_*` values, `skip_corner`, `setup`, `drop_direction`, `plane_fit_mode`, `dhm_usage`, `camera_capture` (T45), `program_source` (T51, later) |
| `/metadata/user` | `key`, `name`, `email`, `organization`, `orcid` from the user config |
| `/metadata/objective` | the objective section of the config (as used), `key` |
| `/metadata/system` | `sys_args_json` (as passed); `devices_json`: `System.items()` (controller, camera, DHM, system parameters) at start; `acceleration_x_mm_s2`, `acceleration_a_mm_s2`, `acceleration_z_mm_s2` (read from the controller) and `acceleration_a_rule` (`"controller"` or `"x/2 (IFOV workaround)"`); `backend` (`"real"` or `"dummy"`, so that dry-run files are never mistaken for prints) |
| `/metadata/software` | `package_version` (from `importlib.metadata`), `git_commit`, `git_dirty` (bool), `git_branch` (empty if not a git checkout), `python_version`, `versions_json` (numpy, h5py, SciDataContainer, OpenCV) |
| `/metadata/substrate` | copy of the substrate record at experiment start (§8), so the file stays self-contained |
| `/metadata/materials/<role>` | since 1.1 (T75): material snapshot per role (`resin`, `substrate`, `medium`): attributes `schema`, `name`, `known`, `batch`, `name_source` (`argument`, `substrate`, `sys_args`), `registry_file`, `registry_schema_version`, `taken`, and of a known material `kind`, `supplier`, `notes`, `created`; table `properties` (`key`, `value_real` (NaN for text), `value_text`, `unit`, `wavelength_nm`, `state`, `temperature_c`, `uncertainty`, `source`, `date`, `notes`). Written once when the file is created; a restart keeps it |
| `/spec` | since 1.1 (T77): the experiment spec as written (`ExperimentSpec.to_json()`, schema `nanofactory.experiment_spec/1`, not resolved: `null` = objective default) as text dataset `spec_json`; attributes `schema`, `written`. Written by `run_experiment()` at the start; exported as `experiment_spec.json`. Missing for experiments started without a spec or with a spec that cannot be stored (plain callable factory; a warning is logged) |
| `/inputs/<file name>` | since 1.1 (T77): slicer input files of the spec (height maps as `.npy`, meshes) byte for byte (uint8), attributes `file` (path relative to the experiment folder, `inputs/…`) and `sha256` (decision M5) |
| `/metadata/sessions` | table (compound dataset, one row per run of the process on this file): `started`, `ended`, `kind` (`new`/`restart`), `end_reason` (`finished`/`aborted`/`exception`), `software_git_commit` |

### 5.3 Calibration, plane fit and OPL scan

| Path | Content |
|---|---|
| `/calibration/attenuator` | dataset N×2 (`attenuator_value`, `power_mw`); attributes `fit_kind`, `source_file` (the configured calibration file), `recorded` |
| `/plane_fit` | attributes `mode` (enum name, T44), `source` (`"measured"`, `"loaded"`, `"given"`), `function` (class name: `PlaneFit`, `Plane`, `StaticOffset`), `function_json` (parameters, e.g. plane coefficients), `interface` (`"low"`/`"high"`, the one used for the drop direction) |
| `/plane_fit/sample_points_um` | N×2, the points that were (to be) measured |
| `/plane_fit/interface_points_um` | M×3, the points the fit used |
| `/plane_fit/containers/<name>` | measured fit only: the SciDataContainer files (`back.zdc`, `plane.zdc`, `layer-<nn>.zdc`) stored as opaque byte datasets (`uint8`), attribute `format = "zdc"`; they can be exported unchanged |
| `/opl_scan` | attributes `motor_pos_um`, `source` (`"measured"`/`"loaded"`), `start_pos_um`, `time` |

A plane passed with `plane_fit(plane=...)` is stored with `source = "given"`, so that dry runs and restarts
record the plane that was actually used.

### 5.4 `/layout`

The geometry of the experiment as printed:

| Dataset / attribute | Content |
|---|---|
| `experiment_rectangle_um` | 4×2: TL, TR, BR, BL of the experiment rectangle |
| `corners` | compound table: `name`, `position` (`TL`/`TR`/`BR`/`BL`), `reference_x_um`, `reference_y_um` (grid corner), `x_um`, `y_um` (center of the corner geometry), `rotation_deg`, `double` (bool, the marked corner) |
| `double_corner` | attributes `name`, `x_um`, `y_um`, `rotation_deg`: the orientation mark as its own record (F1, T50) |
| `qrcode` | attributes `x_um`, `y_um`, `text` (= experiment UUID), `pixel_pitch_um`; dataset `image` (the QR bitmap) |
| `grid_positions_um` | (rows·cols)×2, centers of all grid cells in print order |
| `plot` | `experiment.png` as PNG bytes (optional; the file on disk is the copy) |

### 5.5 `/structures/<name>`

One group per structure, in print order (attribute `index`).

Attributes:

| Attribute | Content |
|---|---|
| `index`, `name`, `type` | print order, name, `StructureType` name |
| `grid_index` | cell index for grid structures, −1 for corners and QR code |
| `corner_position` | `TL`/`TR`/`BR`/`BL` or empty |
| `repeat_of` | name of the repeated structure for `REPEAT`, else empty (T50) |
| `axes`, `setup` | printing axes (`ABZ`/`XYZ`) and IFOV setup used |
| `center_um` | 3: absolute center (grid point + `center_point`, z from the plane) |
| `reference_um` | 2: grid point before `center_point` is added |
| `power_mw` | the power that is actually written; for IFOV structures the power of the structure, not the attenuator preset (§12 D5) |
| `attenuator_preset_mw` | the value passed to `controller.power()` before the structure |
| `velocity_um_s`, `slice_um`, `hatch_um` | normalised values, if the structure class provides them (T49/T56 add a small interface `DrawableObject.print_parameters()`); NaN if unknown |
| `class`, `config_json` | module-qualified class name and `to_json()` (reversible after T56) |
| `n_layers`, `layer_order` | number of layers, `+1`/`−1` from the drop direction |
| `dhm_image_count`, `camera_capture` | capture settings used for this structure |
| `status` | `pending`, `printing`, `printed`, `failed`, `skipped` |

Children:

| Path | Content |
|---|---|
| `programs/layer_<iii>` | layer program text (variable-length UTF-8 string); attributes `layer_id`, `file` (relative path of the file copy), `sha256` |
| `program` | whole-structure program (the concatenation of the layer programs). Since 1.2 (T124): gzip-compressed UTF-8 bytes (uint8, chunked) with attributes `storage = "compressed"`, `format = "txt"` (the unpack tool writes `program.txt`), `encoding`, `sha256`, `n_lines`, `n_bytes`, `file`; with `Experiment(structure_program="reference")` an empty dataset with `storage = "reference"` and the same attributes (only hash and file). Before 1.2: a variable-length UTF-8 string. `ExperimentStore.read_structure_program()` reads every form (None for a reference) |
| `progress` | compound table, one row per layer event: `layer_id`, `session`, `started`, `ended`, `status` (`ok`/`failed`), `error` |
| `slicer` | slicer output if the program source is the slicer (§5.7) |
| `captures/<nnnn>` | §5.6 |

### 5.6 Captures (`/structures/<name>/captures/<nnnn>`)

One group per capture; one capture is one device call at one position.

Attributes (all captures):

| Attribute | Content |
|---|---|
| `kind` | `camera` or `dhm` |
| `phase` | `before`, `layer`, `after` |
| `layer_id` | layer after which the capture was taken, −1 for before/after |
| `image_index` | index within a multi-position series (T46), 0 by default |
| `offset_um` | 2: offset from the structure center (T46) |
| `commanded_um` | 3 (X, Y, Z): the target of the move before the capture (T46, T58) |
| `actual_um` | 5 (X, Y, Z, A, B): positions read from the controller after the move |
| `time` | start of the capture |
| `structure`, `session` | redundant back-references for readers that copy a group out |

Camera capture: dataset `image` (H×W `uint8`, chunked per image); attributes `camera_json` (settings as in
`data/camera.json` today).

DHM capture:
- dataset `holograms` (n×H×W `uint8`), dataset `capture_times_s` (n), attributes `dhm_json` (as in
  `data/hologram.json`), `results_json`, `image_count`.
- group `products/<product name>` (`phase`, `amplitude`, `height`, …): dataset plus attributes `source`
  (`"dhm-pc"`, `"offline"`, …), `created`, `parameters_json` (reconstruction parameters), `unit`. This is
  the generic interface for F4: the printing process receives a product and calls
  `add_dhm_product(capture_id, name, data, metadata)`.
- The raw holograms may later be dropped after reconstruction (F5): the design allows a capture with
  products and without `holograms`.

Size estimate: a camera image is 1.3 MB raw (1280×1024, 8 bit), typically 0.3–0.6 MB compressed; a
hologram series of 10 images is about 10× the DHM image size. A 6-structure experiment with 60 layers
and DHM on is on the order of 100–500 MB; large experiments can reach several GB. This is acceptable for
HDF5 but affects §6 (writes stay per capture, never rewrite whole datasets).

### 5.7 Slicer outputs

If a structure comes from the slicer, its `ToolpathJob` is stored in `/structures/<name>/slicer` with the
existing schema of `aerobasic/slicer/storage.py` (`metadata/`, `time_estimate/`, `groups/`). For that,
`save_job()` gets a variant that writes into an open `h5py.Group` instead of creating a file (a small
refactor in T47; the file format of `job.h5` stays identical). The existing `dhm/` and `surface_scan/`
slots of each slicer group stay unused; captures are stored as in §5.6 and refer to the slicer group by
`layer_id`. See §12 D4 for copying vs. linking.

### 5.8 Progress, summary, logs

| Path | Content |
|---|---|
| `/progress` | attributes `current_structure`, `current_layer_id`, `printed_layers` (a count, T59), `updated`; the details are in each structure's `progress` table |
| `/summary` | compound table as in §10, rewritten after `build_programs()` and after every structure |
| `/logs/a3200` | the controller command log (T55), appended per session (variable-length string per session) |
| `/logs/console` | copy of `console.log` for each session, written at the end of the session (the file on disk is the live copy) |

### 5.9 Analysis results (added with T66)

Written only by the analysis tools in `analysis/experiment_analysis` (`ExperimentFile.save_result()`), never
by the printing process; a minor schema addition (§9), so `schema_version` stays `"1.0"`.

| Path | Content |
|---|---|
| `/analysis/experiment/<name>` | result of the experiment |
| `/analysis/structures/<structure>/<name>` | result of one structure |
| `/analysis/captures/<capture id>/<name>` | result of one capture |

Each result is a group: datasets (`data`, or one per key of a dict), attributes for scalar results and
parameters (nested values as `<x>_json`), plus `created`, `updated` and `source` (script name). An
analysis writer holds `experiment.lock` for the duration of one write and refuses to write while an
experiment process holds it (§6.3). Readers in other processes open the file without HDF5 file locking
(`ExperimentStore(read_locking=False)`) and repeat a read that fails, so they never block a write of the
printing process.

## 6. Write strategy

### 6.1 Open, write, close

- `ExperimentStore` keeps only the path. Every public write method opens the file (`h5py.File(path, "a")`),
  writes one event, updates `/updated`, and closes the file. No handle stays open while the stage moves or
  a layer prints.
- Events: creation (metadata, calibration), plane fit, OPL scan, build (per structure: config, programs),
  each layer (progress row), each capture, each DHM product, end of structure (status, summary), end of
  session (logs, session row).
- Writes only append or overwrite small attributes; large datasets are created once and never resized
  (a hologram series is written in one dataset creation).
- After every write that changes the summary or the structure list, the JSON copies are rewritten from the
  file (write to a temporary file, then `os.replace`).

### 6.2 State after a crash

- A crash **between** writes leaves a closed, consistent file; restart continues from `/progress` and the
  structure progress tables.
- A crash or power loss **during** a write can leave the HDF5 file unreadable (HDF5 has no journal). The
  exposure is limited because a write lasts milliseconds and the file is closed otherwise. Recovery path:
  1. the JSON copies and the layer program files are complete up to the last finished event;
  2. `h5clear -s` clears a stale "file open" flag (HDF5 ≥ 1.10), which is the common case;
  3. the store offers `ExperimentStore.recover(folder)`, which rebuilds a new file from the JSON copies and
     program files (captures written before the crash are lost in that case only).
- To keep this path useful, the JSON copies carry all metadata (§7), not only a subset.

### 6.3 Exactly one writing process

- A lock file `experiment.lock` (hostname, PID, start time) is created with exclusive create when a
  session starts and removed when it ends. A second process refuses to write; a stale lock (same host, PID
  not alive) is reported and can be removed with an explicit `force=True`.
- HDF5 file locking stays enabled (h5py default) as a second guard.
- The DHM PC never writes the file. Its data reaches the printing process by a transport defined in F4,
  and the printing process calls `add_dhm_product()`.
- Reading while printing (e.g. a viewer) opens the file read-only between writes; readers must tolerate
  the file being briefly locked.

## 7. JSON copies

Written from the file by `ExperimentStore.export_json()`:

| File | Content |
|---|---|
| `structures.json` | list of structures as today (same keys, so old readers keep working) **plus** `experiment_uuid`, `type`, `corner_position`, `status`, `center_um`; paths relative (T57). Stays the entry point. |
| `experiment_dictionary.json` | today's keys (with numbers instead of strings, old string form still read) plus `experiment_uuid`, `experiment_label`, `substrate_uuid`, `substrate_label`, `schema_version`, `software`, `plane_fit` (mode, source, function), `layout` (corners, double corner, QR code), `calibration` (table, fit kind) |
| `experiment_summary.json` | §10 |

The copies contain no image data. They are never read by the store except by `recover()` and by the
legacy reader (§9).

## 8. Substrates and the experiment index

Every write of the index (also the creation of the substrate) rewrites two copies next to it
(T118, `storage/substrate_layout.py`): `substrate_layout.json` (schema
`nanofactory.substrate_layout/1`: substrate, resin drops with their ellipse, every experiment with
label, planned name, status, state, objective, center and area incl. markers in absolute stage µm,
folder) and `substrate_layout.png` (drops in grey, areas coloured planned / running / done /
aborted). They are written without pyplot (no window) and never read back; a failure is only
logged. `SubstrateStore.write_layout(label)` writes them on request (task `overview` of
`mains/main.py` does this for every substrate). A planned entry keeps its `name` when the
experiment replaces it.

`<root>/<substrate label>/substrate.json`:

```json
{
  "schema_version": "2.0",
  "label": "HR-26-001",
  "uuid": "…",
  "created": "2026-09-29T18:00:00.000Z",
  "user": "Hannes",
  "material": {"substrate": "boro-silicate glass", "thickness_um": 700.0,
               "resin": "SZ2080", "resin_thickness_um": 75.0},
  "substrate_material": "boro-silicate glass",
  "substrate_type": "cover_slip",
  "dimensions": {"shape": "round", "diameter_mm": 30.0, "thickness_um": 700.0},
  "resin_drops": [{"edges_um": [[5720, 22330], [-3333, 22420], [1660, 17212], [1200, 27190]],
                   "added": "…", "material": "SZ2080", "batch": "", "thickness_um": 75.0,
                   "application": "drop"}],
  "notes": "",
  "experiments": [
    {"uuid": "…", "label": "HR-26-001-A", "path": "HR-26-001-A_20260929-2018",
     "started": "…", "objective": "Zeiss 63x", "status": "finished",
     "center_um": [1310, 19500], "double_corner_um": [980, 19295], "double_corner_rotation_deg": 0,
     "area_um": [[700, 19100], [1920, 19900]], "resin_drop": 0, "plan_id": "planned:power_speed"},
    {"uuid": "", "label": "", "name": "lenses", "plan_id": "planned:lenses", "status": "planned",
     "planned": "…", "objective": "Zeiss 63x", "area_um": [[2100, 19100], [3000, 19900]],
     "resin_drop": 0, "center_um": [2550, 19500]}
  ]
}
```

Record version 2 (T76, INFORMATION_MODEL.md §3.2): `substrate_material`, `substrate_type`
(`cover_slip`/`slide`/`wafer`/`other`), `dimensions` (fields of the shape only) and per drop
`material`, `batch`, `thickness_um`, `application` (`drop`/`dip_in`). A `"1.0"` file is read as version 2
(the `material` dict fills the new fields and stays as it is) and written as `"2.0"` only when the record
changes. Index entries carry `area_um` (rectangle incl. corner markers and QR code) and `resin_drop`;
`run_substrate()` enters every experiment as `planned` before the run (`plan_experiment`), and the
experiment replaces its planned entry when it starts. An experiment that was never started stays
`planned`. `substrate_overview(root, label)` lists all entries with the status read from the experiment
files (the index is a cache) and the state `planned` / `running` / `done` / `aborted`.

- The substrate record is small, edited by people (notes) and shared by all experiments, so it stays
  JSON; each experiment file holds a copy (`/metadata/substrate`).
- `SubstrateStore` updates it with a lock file and an atomic replace. Experiments are appended when they
  start and their `status` is updated when they end.
- `resin_drops` is a list: several drops on one substrate are possible; each experiment stores the edges
  it used.
- The fields of today's free `substrate_information` dict are mapped to `material`/`notes`; unknown keys
  go to `notes_json`. Old `substrate_information.json` files are read and converted (T48).
- **Finding experiments** (N025): `find_experiments(root, substrate=None, objective=None, since=None,
  until=None, status=None)` scans `*/substrate.json` below the root. No global index file exists, so
  there is nothing to keep consistent; a user root with a few hundred substrates is scanned in well under
  a second. Experiments with an explicit `path` outside the root are found only if registered with a
  substrate.

## 9. Schema version and old data

- `schema_version` is `"<major>.<minor>"`. A reader accepts files with the same major version; a minor
  version only adds groups or attributes. A major change comes with a migration function
  `migrate_<a>_to_<b>(path)` in `storage/schema.py` that rewrites a copy.
- **Old JSON-only folders** (no `experiment.h5`, but `experiment_dictionary.json`): `LegacyExperimentReader`
  builds the same in-memory `ExperimentRecord`:
  - parameters from `experiment_dictionary.json` (string vectors parsed as `parameters_from_dictionary`
    does today; integer `plane_fit_mode` and `drop_direction` values mapped to enum names);
  - experiment UUID from the QR structure's `text` in `structures.json`, else from the first
    `Experiment <uuid>` line of the log file; if neither exists, a new UUID is generated and flagged
    `uuid_recovered = false`;
  - structures and layer files from `structures.json`, progress from `print_progress.json`, plane from
    `planefit/plane.zdc` if present;
  - captures are not imported (they stay as `.zdc` files in the folder).
- **Restart of an old folder** (T50): the legacy record is written into a new `experiment.h5` in the same
  folder (`/metadata/sessions` gets a row `kind = "imported"`), then the restart proceeds on the new file.
  The old files are left untouched. See §12 D7.

## 10. Experiment summary (T49)

`/summary` and `experiment_summary.json`: experiment-level fields (`experiment_uuid`, `experiment_label`,
`substrate_label`, `objective`, `setup`, `drop_direction`, `plane_fit_mode`, `dhm_usage`,
`camera_capture`, `started`, `status`) and one row per **user** structure (corners and QR code excluded):

| Column | Source |
|---|---|
| `name`, `type`, `grid_index` | structure attributes |
| `x_um`, `y_um` | `center_um` |
| `slice_um`, `hatch_um` | normalised structure parameters |
| `power_mw`, `velocity_um_s` | normalised structure parameters (§12 D5) |
| `ifov` | `setup == "IFOV_on"` |
| `dhm`, `camera` | capture settings of the structure |
| `n_layers`, `printed_layers` | structure, progress |
| `status` | `pending`/`printed`/`failed` |

`ExperimentStore.summary_table()` formats it for the log (fixed-width text table).

## 11. API sketch

New package `nanofactorysystem/storage/`:

| Module | Content |
|---|---|
| `records.py` | dataclasses `ExperimentRecord`, `StructureRecord`, `CaptureRecord`, `PlaneFitRecord`, `SubstrateRecord`, `LayoutRecord` (plain data, no HDF5) |
| `experiment_store.py` | `ExperimentStore` |
| `substrate_store.py` | `SubstrateStore`, `find_experiments()`, `default_root(user)` |
| `schema.py` | `SCHEMA_VERSION`, name constants, compound dtypes, migrations |
| `legacy.py` | `LegacyExperimentReader` |
| `locking.py` | lock file helper |

`ExperimentStore` (all writes open/close the file):

```python
class ExperimentStore:
    @classmethod
    def create(cls, folder: Path, record: ExperimentRecord) -> "ExperimentStore": ...
    @classmethod
    def open(cls, folder: Path) -> "ExperimentStore": ...        # h5 file, or legacy import (§9)
    def session(self, kind: str) -> ContextManager[None]: ...     # lock, session row, logs at the end

    def write_metadata(self, record: ExperimentRecord) -> None: ...
    def write_calibration(self, table: np.ndarray, fit_kind: str, source_file: str | None) -> None: ...
    def write_plane_fit(self, plane: PlaneFitRecord) -> None: ...
    def write_opl_scan(self, motor_pos_um: float, source: str) -> None: ...
    def write_layout(self, layout: LayoutRecord) -> None: ...

    def add_structure(self, structure: StructureRecord) -> None: ...
    def write_layer_program(self, structure: str, layer_id: int, text: str, file: Path) -> None: ...
    def write_structure_program(self, structure: str, text: str, *, mode: str = "compressed", file: str = "") -> None: ...
    def read_structure_program(self, structure: str) -> Optional[str]: ...
    def write_slicer_job(self, structure: str, job: "ToolpathJob") -> None: ...

    def add_capture(self, capture: CaptureRecord, data: np.ndarray) -> str: ...   # returns capture id
    def add_dhm_product(self, capture_id: str, name: str, data: np.ndarray, metadata: dict) -> None: ...

    def update_progress(self, structure: str, layer_id: int, status: str, error: str | None = None) -> None: ...
    def set_structure_status(self, structure: str, status: str) -> None: ...
    def write_summary(self) -> None: ...
    def append_command_log(self, text: str) -> None: ...

    def read(self) -> ExperimentRecord: ...                       # everything except bulk image data
    def read_capture(self, capture_id: str) -> tuple[CaptureRecord, np.ndarray]: ...
    def export_json(self) -> None: ...
    def export_capture(self, capture_id: str, path: Path) -> None: ...   # .zdc export
    @staticmethod
    def recover(folder: Path) -> "ExperimentStore": ...
```

`SubstrateStore`:

```python
class SubstrateStore:
    def __init__(self, root: Path): ...
    def create(self, record: SubstrateRecord) -> SubstrateRecord: ...    # proposes label, assigns UUID
    def get(self, label_or_uuid: str) -> SubstrateRecord: ...
    def next_experiment_label(self, substrate: str) -> str: ...
    def register_experiment(self, substrate: str, entry: dict) -> None: ...
    def update_experiment(self, substrate: str, uuid: str, **fields) -> None: ...
def find_experiments(root: Path, **filters) -> list[dict]: ...
def default_root(user: str) -> Path: ...
```

Use by `Experiment`:

| Today | With the store |
|---|---|
| `__init__` → `_create_experiment_dictionary`, `_save_experimental_data` | resolve folder (explicit `path` or substrate + next label), `ExperimentStore.create()`, `write_metadata()`, `write_calibration()`, `SubstrateStore.register_experiment()`, `export_json()` |
| `_save_exp_dict` | `write_metadata()` + `export_json()` |
| `_save_calibration` | `write_calibration()` |
| `_save_substrate_information` | `SubstrateStore.create()/get()` + `register_experiment()` |
| `plot_experiment` | also `write_layout()` (with the plot bytes) |
| `plane_fit` | `write_plane_fit()` (all three sources); `.zdc` containers into `/plane_fit/containers` |
| `opl_scan` | `write_opl_scan()` |
| `_build_programs` / `structure_program` | `add_structure()`, `write_layer_program()`, `write_structure_program()`, `write_slicer_job()`, `write_summary()`; files in `programs/` as execution copies |
| `measure` | `add_capture()` per camera/DHM capture with commanded and actual position (T46) |
| `update_print_progress` | `update_progress()`, `set_structure_status()`, `write_summary()` |
| `print_experiment` / `restart_experiment` | run inside `store.session("new"/"restart")`; restart reads `store.read()` (or the legacy import) |
| `System.close()` → `save_log()` | `append_command_log()` at the end of the session (T55) |
| `Experiment.parameters_from_dictionary` | `ExperimentStore.open(folder).read()` → constructor arguments; the JSON form stays supported |

## 12. Decisions

All proposals below were accepted by the maintainer on 2026-09-29. The questions after each
proposal are answered by the proposal itself (D1: hard error; D2: `nnn` restarts every year).

- **D1 – Default root and sync check.** Proposal: `~/Documents/Femtika_Experiment/<user>/`, per-user
  `dataRoot` in `nanofactory.json`, and a hard error if the root lies in a Seafile/OneDrive/Dropbox folder
  (override with `allowSyncedRoot=True`). Is a hard error right, or only a warning?
- **D2 – Labels.** Proposal: substrate `<initials>-<yy>-<nnn>` with `nnn` counting per user and year,
  experiments `<substrate>-A`, `-B`, …; initials from a new `initials` key or from the user's name.
  Should `nnn` count per user and year, or per user without the year reset?
- **D3 – Folder name.** Proposal: `<experiment label>_<YYYYMMDD-HHMM>` (label plus start time). Alternative:
  label only (shorter, but relies on labels never repeating).
- **D4 – Slicer outputs.** Proposal: copy the job into the experiment file (self-contained). Alternative:
  an HDF5 external link to the slicer's `job.h5` (smaller, but the experiment breaks if the job file
  moves).
- **D5 – Authoritative power.** Proposal: `power_mw` of a structure is the power that is actually written
  (for IFOV structures the structure's own power), and the attenuator preset is stored separately as
  `attenuator_preset_mw`. Is that the meaning you want in the summary?
- **D6 – `.zdc` files.** Proposal: captures only in the HDF5 file; `.zdc` export on demand. Alternative:
  keep writing `.zdc` files as well during a transition period (doubles the disk usage).
- **D7 – Old folders.** Proposal: a restart of an old JSON folder imports it into a new `experiment.h5` in
  the same folder, leaving the old files untouched; plain reading does not create a file. Acceptable?
- **D8 – Console log in the file.** Proposal: copy `console.log` into `/logs/console` at the end of every
  session. Alternative: keep the log only as a file (the file then is not fully self-contained).

## 13. Mapping to the todos

| Section | Todo |
|---|---|
| §5, §6, §7, §11 `ExperimentStore`, §5.6 `add_dhm_product`, §5.7 | T47 |
| §3, §4, §8, §11 `SubstrateStore` | T48 |
| §10 | T49 |
| §9 restart, §5.2 sessions, §5.4 double corner | T50 |
| §5.6 positions and offsets | T46, T58 |
| §5.8 `/logs/a3200` | T55 |
| §5.5 `config_json`, `class` | T56 |
| relative paths (§5, §7) | T57 |
| `/progress`, `printed_layers` | T59 |

## 14. Approval

Approved by the maintainer on 2026-09-29 (all proposals in §12 accepted); recorded in the status line
at the top.

## 15. DHM service results (T71, approved 2026-11-18; layout fixed by T83, schema 1.3)

Designed with `docs/design/DHM_SERVICE_INTEGRATION.md` (T71, approved 2026-11-18 with §10.1 there) and
fixed when T83 was implemented (2026-11-26). Minor schema addition (1.2 → 1.3): legacy captures and every
existing group stay unchanged, readers of 1.x files keep working. **This section is binding** for the
readers outside this repository: OffAxisHolo K12 (replay), MIRA MI-62 (offline fusion, stitching,
comparison) and the DHMConnect tools. They read with `h5py` only and with HDF5 file locking off
(`HDF5_USE_FILE_LOCKING=FALSE` or `h5py.File(..., locking=False)`), never import nanofactorysystem, and
must not write the file (§6.3). Writing goes through `ExperimentStore` only. An example file built by
`test/storage/dhm_example.py` (`write_dhm_example(path)`) is the fixture the other repositories vendor.

**Product layout (one rule for every contract product).** A contract product (`ProductSet` 1.0 of one
capture, `LayerProduct` 1.0 of a group) is stored as one HDF5 group with the attribute `header_json` (the
contract header exactly as delivered: every field of the message except the buffer bytes, incl. its
`buffers` descriptors) and one dataset per buffer under its contract name (`phase_rad`, `intensity_rel`,
`valid` as uint8, optional `field` as complex64), chunked with `gzip` 4 and `shuffle`. This is the layout of
MIRA `LayerProduct.to_h5` / `from_h5` (MI-10), so a reader rebuilds the product with
`from_message(json.loads(group.attrs["header_json"]), [(name, group[name][()]) ...])`. Products are stored
as delivered: aligned, not levelled (levelling is MIRA's, G10 SA5).

### 15.1 DHM capture (`/structures/<name>/captures/<nnnn>`, `kind = "dhm"`)

`ExperimentStore.reserve_capture(record, ...)` creates the group before the acquisition (DHM service
design §7). Captures written with `add_capture` (legacy mode) and captures of files before 1.3 carry none
of the attributes below; a reader treats a missing `job_state` as `stored` and a missing `adapter` as
`legacy`.

New attributes (all strings unless noted; empty string = not set):

| Attribute | Content |
|---|---|
| `adapter` | `legacy`, `service` or `fake` |
| `job_id` | job id of the DHM service (empty in legacy mode) |
| `job_state` | `reserved`, `sent`, `acquired`, `stored`, `acknowledged`, `failed`, `missing` (legacy: `stored`) |
| `error` | reason of a failed job |
| `group_id` | group the capture belongs to (§15.3), else empty |
| `config_hash`, `parameter_set_id` | parameter set of the reconstruction (DL-A3 a); the set itself is under `/metadata/dhm/parameter_sets` (§15.4) |
| `recipe_json` | effective recipe of this capture (incl. unknown keys passed to the service) |
| `context_json` | `CaptureContext` as sent (incl. material snapshot reference, `z_hint_um`, `occupied_um`, `pose_tolerance_um`) |
| `raw_ref_json` | raw frames that stayed on the DHM-PC: `host`, `path` (DHMConnect raw archive, `<root>/<experiment_uuid>/captures/<capture_id>_<job_id>.h5`, `docs/RAW_ARCHIVE.md` there), `sha256`, `n_frames`, `keep_raw`; `{}` if the frames are stored here or none were kept |
| `recovered` (bool), `recovered_json` | set when the result was fetched after a restart (SI4): `reason`, `original_session`, `time` |

Datasets:
- `holograms`, `capture_times_s`: as in §5.6, only when the raw frames are stored here (legacy mode,
  `products_and_raw`, `publication` transfer T105). A capture may have products and no `holograms`.
- `frames`: compound table, one row per frame of the job (contract `FrameRecord` 1.0): `index` (int32),
  `used` (bool), `reject_reason` (str, empty for `null`), then one float64 column per metric, named
  `metric_<key>` (`metric_saturated_count`, `metric_sideband_fraction`, `metric_piston_rad`, …; the union of
  the keys of all frames, sorted; a missing or `null` metric is NaN). Attribute `acquisition_json`: the list
  of the per-frame `acquisition` objects, unchanged. Readers that need the exact records can rebuild them
  from these two parts.

### 15.2 Products of a capture (`…/captures/<nnnn>/products`)

- Service result (`ProductSet` 1.0): the group `products` follows the product layout above. Its attribute
  `header_json` is the `ProductSet` header (incl. the nested `ReconstructionResult` without buffer bytes);
  the datasets are the buffers. In addition `products` carries the attributes `message_type`
  (`"ProductSet"`), `schema_version`, `product_id`, `job_id`.
- Every product dataset has the attribute `created`; legacy products (`add_dhm_product`) also have
  `metadata_json` (source, unit, reconstruction parameters as given). Service products get these flat
  copies of the header instead, so that a reader without JSON parsing can trace them:

| Attribute | Content |
|---|---|
| `schema_version` | version of the `ReconstructionResult` contract |
| `config_hash`, `parameter_set_id` | parameter set of the reconstruction |
| `background_id`, `background_created`, `background_age_s` | background used (from `quality`) |
| `pixel_um` | float64 (2,), (y, x) after the sideband crop (not the camera pitch) |
| `z_um`, `propagation_index`, `wavelength_um` | propagation distance with its index (G4) and wavelength |
| `quality_json`, `timings_json`, `versions_json`, `warnings_json` | as delivered |

- Legacy products (`phase`, `amplitude`, `height`, … from offline reconstruction, F4) stay as in §5.6 and
  have no `header_json` on `products`. A capture holds either one service `ProductSet` or legacy products.

### 15.3 Groups (`/dhm_groups/<group_id>`)

One group per `open_group(GroupSpec)` of the service (N2): a stitched layer raster, a speckle set, or a
background raster at the object positions (SI3).

| Item | Content |
|---|---|
| attributes | `kind` (`layer`, `speckle`, `background`), `structure`, `phase`, `layer_id` (int), `job_id`, `job_state` (as §15.1), `group_spec_json` (the `GroupSpec` as sent, incl. seed, T85), `recipe_json`, `recovered` (bool), `recovered_json` |
| dataset `members` | capture ids of the member captures (variable-length strings, in position order) |
| group `product` | the `LayerProduct` 1.0 (N1) in the product layout above: `header_json` + `phase_rad`, `intensity_rel`, `valid`, optional `field`. Member `ProductSet`s stay on the DHM-PC and are referenced by `header_json["tiles"][i]["product_id"]` / `member_ids` |

A `LayerProduct` that is recovered after a restart (SI4) is stored the same way with `recovered = true`.

### 15.4 Session metadata and parameter sets (T79)

| Path | Content |
|---|---|
| `/metadata/dhm/sessions/<n>` | once per session that used the DHM (`n` = row of `/metadata/sessions`): attributes `adapter`, `service_version`, `protocol_version`, `software_versions_json`, `parameter_set_id`, `config_hash`, `camera_json`, `pixel_um` (2, (y, x)), `pixel_source` (`parameter_set`, `calibration`, `nominal`; never Koala), `objective` |
| `/metadata/dhm/parameter_sets/<config_hash>` | the full parameter set **once per hash** (DL-A3 a): attributes `parameter_set_id`, `parameter_set_json`, `first_used` |

### 15.5 Calibration and orphans

| Path | Content |
|---|---|
| `/calibration/dhm/<kind>/<id>` | `kind` = `exposure`, `opl_scan`, `background`: attributes `parameters_json`, `result_json`, `time`, `session`, `job_id`; backgrounds as metadata only (frames stay on the DHM-PC unless `keep_raw` asks otherwise). `/opl_scan` (§5.3) keeps the latest OPL result. |
| `/dhm_orphans/<job_id>` | **references only** (SI4): attributes `result_id`, `message_type`, `structure`, `layer_id`, `time`, `host`, `path`, `sha256`, `size_bytes`, `reason`. A `LayerProduct` among the orphans is fetched and stored in full under `/dhm_groups` instead (`recovered = true`). |

### 15.6 JSON copies and unpack tool

The JSON copies (`experiment_dictionary.json`, `structures.json`, `print_progress.json`) list no captures
and stay unchanged. `analysis/experiment_analysis` mirrors the new groups generically (attributes as JSON,
the `frames` table as CSV); `tables/captures.csv` gets the columns `job_id`, `job_state` and `products`.

## 16. Proposed amendment: feedback results (T72, not yet approved)

Proposed with `docs/design/OPERATING_MODES.md` (T72, §5 there); implemented in T88–T91 once approved.
Minor schema addition.

- §5.9 changes: besides the analysis tools, the printing process writes results under
  `/analysis/captures/<capture id>/deviation` with `source = "nanofactorysystem.feedback"` (it holds the
  experiment lock anyway). Analysis tools never overwrite or delete results of that source.
- New group `/feedback/<structure>`: attributes `mode`, `evaluator`, `controller`, `rules_json`,
  `limits_json`, `target_json`; dataset `events` (table: `layer_id`, `capture_id`, `time`, `rmse`, `mae`,
  `validity`, `status`, `action`); subgroups `plans/<layer_id>` with the `CorrectionPlan` (`actions_json`,
  `rationale`, `limits_applied_json`, `controller`, `applied`, `applied_at_layer`).
- `StructureRecord.status` gets the value `stopped` (stopped by a monitor rule); `print_progress.json`
  reports it like `failed`, with the reason.
