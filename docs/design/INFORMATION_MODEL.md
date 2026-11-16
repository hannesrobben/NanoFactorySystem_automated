# Design: Information model v2 (material, substrate, experiment, structure)

Status: draft 2026-11-16, waiting for maintainer approval (T70). Implementation todos: T75–T81.

Builds on `EXPERIMENT_STORAGE.md` (approved 2026-09-29) and `VOXEL_DATABASE.md` (approved 2026-09-30).
Neither is replaced; this document adds the material level, settings per structure and a stored
experiment description, and proposes the amendments listed in §10. System context:
`docs/system/SOFTWARE_PLAN_OVERVIEW.md` (G7: material registry here, snapshot in `CaptureContext`).

## 1. Goals and non-goals

Goals:
- One model with four levels: **material → substrate → experiment → structure**, each with an identity,
  fixed fields, a place where it is stored, and a rule for reading older data.
- Settings that today belong to the experiment (setup, program source, slicing, power, voxel model, …)
  can be set per structure; unset values come from the experiment.
- An experiment and a structure can be written to a file and read back (project file), so that a GUI
  (F15), a restart or a later analysis does not need the Python script that created them.
- Material properties (first of all refractive indices) can be added at any time without a code change,
  with unit and source; the material used is copied into every experiment file.

Non-goals:
- No GUI (F15), no recipe fields (T71), no operating-mode logic (T72), no new slicing strategies (F17).
- No change to the printed programs of existing specs (golden files stay unchanged, T78).
- The config file (`nanofactory.json`) keeps users, objectives and devices; it gets no material data.

## 2. As-is (2026-11-16)

| Information | Where today | Remarks |
|---|---|---|
| Resin and substrate material | `SubstrateSpec.material` (free dict) → `substrate.json`; `sys_args["sample"]` (`material`, `substrate`, thicknesses; default `SZ2080`, boro-silicate glass) → `/metadata/system/sys_args_json`; `material` table of the voxel database (`name`, `supplier`, `notes`) | Three unrelated places; no refractive index anywhere. |
| Substrate | `substrate.json` (`SubstrateRecord`: label, UUID, user, material dict, resin drops with edges, notes, experiment index, extra) | No type or dimensions; experiment index has `status` but it is only updated by `Experiment`. |
| Experiment description | Python: `ExperimentSpec` in a script in `mains/Experiments/` | Not stored; `factory` callables cannot be stored. |
| Experiment as run | `experiment.h5`: `/metadata/experiment` (constructor parameters, `schema.PARAMETERS`), `/metadata/system`, layout, structures, captures, … | Complete for what was printed, but the spec it came from is lost. |
| Structure | `StructureSpec` (script) → `/structures/<name>` (`StructureRecord`: type, axes, setup, power, `config` = `DrawableObject.to_json()`, layer files, …) | `setup` is copied from the experiment. |
| Voxel data | voxel SQLite (`system.voxelDatabase`), keyed by material name, objective, setup | |
| Objective defaults | `OBJECTIVE_DEFAULTS` in `experiment_spec.py`; objective section of the config | |

## 3. The four levels

```
Material registry (SQLite, per PC; seed CSV in git)
   │  referenced by name, copied as snapshot
   ▼
Substrate  ── substrate.json ─────────────── resin drops (material + batch per drop)
   │  experiment index
   ▼
Experiment ── experiment_spec.json (project file, written before the run)
   │          experiment.h5 (single writer; spec, material snapshot, everything printed)
   ▼
Structure  ── inside the experiment spec; resolved settings in /structures/<name>
```

Identity: material = unique `name` (e.g. `"SZ2080"`); substrate = label + UUID (unchanged); experiment =
label + UUID (unchanged; the UUID is assigned when the experiment file is created); structure = unique name
within the experiment (unchanged).

### 3.1 Material

A material is a photoresist, a substrate material or another medium (immersion oil, developer).

| Field | Type | Meaning |
|---|---|---|
| `name` | str, unique | Registry key, e.g. `"SZ2080"`, `"IP-Dip"`, `"boro-silicate glass"`. |
| `kind` | `resin` \| `substrate` \| `medium` | What the material is used as. |
| `supplier` | str | |
| `notes` | str | |
| `properties` | list of `MaterialProperty` | Extensible, see below. |

`MaterialProperty`:

| Field | Type | Meaning |
|---|---|---|
| `key` | str | e.g. `refractive_index`, `density`, `shrinkage`, `viscosity`. Free text; new keys need no code change. |
| `value` | float or str | Number in the unit below; a str for non-numeric facts. |
| `unit` | str | Required for numbers (`"1"` for dimensionless). |
| `wavelength_nm` | float, optional | For optical properties. |
| `state` | `uncured` \| `cured` \| `any` | Liquid resin vs. polymerised; `any` for properties that do not depend on it. |
| `temperature_c` | float, optional | |
| `uncertainty` | float, optional | Same unit. |
| `source` | str | Data sheet, publication (DOI), own measurement (experiment UUID). |
| `date` | str | When the value was determined or entered (ISO 8601). |
| `notes` | str | |

A small table `KNOWN_PROPERTY_KEYS` in the code lists the expected unit of common keys
(`refractive_index` → `"1"`, `density` → `"g/cm3"`, …) and only **warns** on a mismatch, so new keys
can be used immediately.

The **batch** (bottle, lot number, opening date) belongs to the use of a material, not to the material:
it is a field of the resin drop (§3.2), not of the registry.

**Lookup:** `registry.material(name).property(key, wavelength_nm=None, state=None)` returns the matching
property; with several matches the most recent `date` wins; a wavelength must match exactly (no
interpolation or dispersion fit in v2; a Cauchy fit could follow later). It returns None if nothing
matches. Which refractive index is the `n_medium` of a DHM result (liquid resin, cured resin, or
developed structure in air) is decision G4 / O1 / O11; the snapshot carries all of them so that this
decision does not change the stored data.

**Snapshot:** when an experiment is created, the full record of every material it uses (resin of the
drop, substrate material, medium) is copied into `experiment.h5` and into the `CaptureContext` of every
DHM capture (G7). The snapshot has `schema_version`, `registry_file`, `registry_schema_version` and
`taken` (UTC). Later changes in the registry never change a stored experiment.

### 3.2 Substrate (record v2)

`substrate.json` keeps its layout; v2 adds fields and the attribute `record_version: 2`.

| Field | New | Meaning |
|---|---|---|
| `label`, `uuid`, `created`, `user`, `notes`, `experiments`, `extra` | | unchanged |
| `substrate_material` | yes | Registry name (kind `substrate`), or free text if not in the registry. |
| `substrate_type` | yes | `cover_slip`, `slide`, `wafer`, `other`. |
| `dimensions` | yes | `{"shape": "rectangle"\|"round", "width_mm", "length_mm", "diameter_mm", "thickness_um"}` (only the fields of the shape). |
| `resin_drops[]` | extended | Per drop: `edges_um`, `added` (unchanged), plus `material` (registry name), `batch`, `thickness_um`, `application` (`drop` \| `dip_in`). |
| `material` | kept | The v1 free dict; still written when a script passes it, so nothing is lost. |

Material per drop instead of per substrate: a substrate can carry several drops (`resin_drops` is a list
today), and dip-in (no drop boundary, T62) is a property of the application, not of the substrate.

**Experiment index entry** (T76): unchanged fields plus `status` with the values `planned` (written by a
substrate main before the run, no experiment file yet), and the file statuses `created`, `built`,
`printing`, `finished`, `aborted`, `failed`; plus `area_um` (the experiment rectangle incl. corners, from
`/layout`) and `resin_drop` (index of the drop). The status in the index is a cache; the experiment file
is the truth (`find_experiments()` may refresh it).

### 3.3 Experiment

An experiment is described by `ExperimentSpec` (what should be printed and how) and recorded by
`experiment.h5` (what happened). v2 groups the existing spec fields; it does not rename them in Python
(scripts keep working).

| Group | Fields (existing names) | New |
|---|---|---|
| Identity | `name` | `description` (free text), `tags` |
| Placement | `objective`, `center`, `grid`, `structure_size_um`, `fov_um`, `margin_um`, `padding_um`, `drop_direction`, `corner`, `skip_corner`, `z_max_um` | `resin_drop` (index on the substrate) |
| Calibration steps | `plane_fit_mode`, `tilt_warning_um`, `opl_start_um`, `n_mid_points` | |
| Captures | `dhm_usage`, `camera_capture`, `overview_capture`, `overview_single_images` | `dhm_recipe` (T71) |
| Structure defaults | `program_source`, `setup`, `default_power_mw`, `low_speed_um_s`, `high_speed_um_s`, `voxel_material`, `voxel_database` | `defaults: StructureSettings` (§4); the old fields stay as shortcuts that fill it |
| Runtime | `sys_args`, `layer_overhead_s` | |
| Materials | (`sys_args["sample"]`) | `materials`: names of resin, substrate material, medium; default: from the substrate's resin drop |
| Feedback | – | `feedback_mode` (T72, default `off`) |

`sys_args["sample"]` stays for the tools that read it; when a registry material is known, `material` and
`substrate` in it are filled from the registry names (decision M4).

### 3.4 Structure

`StructureSpec` v2 = name + **geometry** + **settings** + repetition.

| Part | Content |
|---|---|
| `name` | unique in the experiment (unchanged) |
| `geometry` | exactly one of: `drawing` (a `DrawableObject`, stored with `to_json()`), `slicer` (height map or mesh plus slicer parameters), `factory` (registered name plus JSON arguments, §6.3), `empty` (empty grid cell) |
| `settings` | `StructureSettings` with only the values that differ from the experiment (§4) |
| `repeat` | number of repetitions in the following grid cells (unchanged) |
| `structure_type` | unchanged; derived from the geometry when not given |

## 4. Settings per structure with experiment defaults

`StructureSettings` is one dataclass used twice: as `ExperimentSpec.defaults` (complete) and as
`StructureSpec.settings` (sparse, every field None by default).

| Setting | Today | Experiment default | Per structure | Validation |
|---|---|---|---|---|
| `setup` (`IFOV_off` / `IFOV_on`) | experiment | yes | yes, derived from the geometry if not set (§7) | IFOV needs an objective with IFOV support |
| `program_source` (`DRAWING` / `SLICER`) | experiment | yes (shortcut) | derived from the geometry kind | `SLICER` ⇒ `IFOV_on` |
| `axes` (`ABZ` / `XYZ`) | structure | yes | yes | ignored by IFOV programs (warning if set) |
| `slicing` (`slice_size`, `spacing_mode`, `voxel_overlap`, `strategy`, …) | `StructureSpec.slicer` | yes | yes, merged key by key | only for `SLICER`; `strategy` from the registry of T81 |
| `hatching` (`hatch_size`, `hatch_angle`, …) | `StructureSpec.slicer` / drawing arguments | yes | yes, merged key by key | as above |
| `power_mw` | `default_power_mw` / `power_mw` | yes | yes | > 0 and inside the attenuator calibration |
| `layer_power` | structure | no | yes | |
| `velocity_um_s` | `low/high_speed_um_s`, drawing arguments, slicer `velocity` | yes | yes | IFOV writes with the fixed speed of the objective (F13): a different value is refused for IFOV structures |
| `voxel_model` (`none` / `fixed` / `database`) + parameters | `voxel_material` | yes (default `database` with the drop's resin if data exist, else `none`) | yes | `database` needs a material |
| `dhm_recipe` | `dhm_usage` + counts per structure type | yes (T71) | yes, per phase (before / layer / after) | needs `dhm_usage` |
| `camera_capture` | experiment | yes | yes (decision M6) | |
| `feedback_mode` (`off` / `monitor` / `shadow` / `correct`) | – | yes (`off`) | yes | `correct` refused without controller (T88); modes other than `off` need a DHM recipe with products |

**Resolution** (`spec.resolved()`, T78): built-in defaults < objective defaults (`OBJECTIVE_DEFAULTS`) <
experiment `defaults` < structure `settings`. Scalars are replaced; dict-valued settings (`slicing`,
`hatching`, `dhm_recipe`) are merged one level deep. The result per structure is a complete
`StructureSettings` plus a `source` map (`"structure"`, `"experiment"`, `"objective"`, `"builtin"` per
field), which the summary can show. Invalid combinations raise `ValueError` naming the structure and
the field. Existing specs (no `settings`) resolve to exactly today's values, so their programs do not
change.

**Stored:** the resolved settings and the source map go into `/structures/<name>` as `settings_json` and
`settings_source_json` (minor schema addition).

## 5. Where everything is stored

| Item | Config | Material/voxel SQLite | `substrate.json` | Project file | `experiment.h5` |
|---|---|---|---|---|---|
| Users, objectives, devices | ✔ (master) | | | | copy (`/metadata/user`, `/objective`) |
| Material records | | ✔ (master) | name | names | snapshot (`/metadata/materials`) |
| Voxel measurements | | ✔ (master) | | | values used (`job.meta["voxel"]`, unchanged) |
| Substrate record | | | ✔ (master) | label | copy at start (`/metadata/substrate`, unchanged) |
| Experiment spec | | | | ✔ (written before the run) | ✔ (`/spec`, copy at start) |
| Structure geometry and settings | | | | ✔ | spec + resolved settings + `config` (unchanged) |
| Run data (layout, programs, captures, progress) | | | | | ✔ (master, unchanged) |
| Index of experiments | | | ✔ (cache) | | status (master) |

**Project file** `experiment_spec.json` lies in the experiment folder next to `experiment.h5` and is
exported from `/spec` like the other JSON copies; `run_experiment()` writes it at creation. A spec file
can also live anywhere else (e.g. a library of standard experiments) and be run from there.

## 6. Serialised form

Conventions as in `EXPERIMENT_STORAGE.md` §5 and the system plan §4: English keys, units in names, enums
by name, `schema` string in every file, no `pickle`.

### 6.1 Experiment (project file)

```json
{
  "schema": "nanofactory.experiment_spec/1",
  "name": "power_speed_63x",
  "description": "",
  "objective": "Zeiss 63x",
  "center_um": [1200.0, -350.0],
  "grid": [3, 4],
  "placement": {"structure_size_um": null, "fov_um": null, "margin_um": null, "padding_um": null,
                "drop_direction": null, "z_max_um": null, "corner": null, "skip_corner": false,
                "resin_drop": 0},
  "calibration": {"plane_fit_mode": "CORNERS", "tilt_warning_um": 1.0, "opl_start_um": null,
                  "n_mid_points": 0},
  "captures": {"dhm_usage": true, "camera_capture": false, "overview_capture": false,
               "overview_single_images": false},
  "materials": {"resin": "SZ2080", "substrate": "boro-silicate glass"},
  "defaults": {"setup": "IFOV_off", "power_mw": 0.7, "velocity_um_s": 1000.0,
               "voxel_model": {"type": "none"}, "feedback_mode": "off"},
  "runtime": {"sys_args": {"focus": {"...": "..."}}, "layer_overhead_s": 5.0},
  "structures": [ { "...": "see 6.2" } ]
}
```

`null` means "default of the objective or of the code". `from_json()` refuses an unknown major schema
and unknown top-level keys (typos), but accepts unknown keys inside `runtime.sys_args` and `dhm_recipe`
(passed on untouched).

### 6.2 Structure

```json
{"name": "rect_0", "repeat": 1,
 "geometry": {"kind": "drawing",
              "structure": {"__class__": "Rectangle3D",
                            "__module__": "nanofactorysystem.aerobasic.programs.drawings.lines",
                            "width": 50, "...": "DrawableObject.to_json()"}},
 "settings": {"power_mw": 1.2}}
```

Other geometry kinds:
- `{"kind": "slicer", "source": {"file": "inputs/lens.stl", "sha256": "…"}, "slicer": {…}}` or
  `{"source": {"array": "inputs/lens_height.npy", "unit": "um", "pixel_size_um": 0.5, "sha256": "…"}}`. Input
  files are copied into `inputs/` of the experiment folder and stored in `experiment.h5` under
  `/inputs/<name>` (decision M5); `.npy` is written with `allow_pickle=False`.
- `{"kind": "factory", "name": "parameter_study.rectangle", "arguments": {"hatch": 0.3, "slice_size": 0.5,
  "velocity": 1000}}` (§6.3).
- `{"kind": "empty"}`.

A structure file on its own (`schema: "nanofactory.structure_spec/1"`) has the same form, so a library of
structures can be reused across experiments.

### 6.3 Named factories instead of callables

Eight ported scripts use `factory=` today; they all read only values of the running experiment that exist
after the setup (mostly `experiment.accel_a_um`). v2:

```python
@structure_factory("parameter_study.rectangle")
def rectangle(context: BuildContext, *, hatch: float, slice_size: float, velocity: float) -> DrawableObject:
    return Rectangle3D(..., acceleration=context.accel_a_um)
```

- `BuildContext` holds what a factory may read: `objective`, `setup` of the structure, `accel_x_um`,
  `accel_a_um`, `accel_z_um`, `power_calibration`, `drop_direction`. Not the whole `Experiment` (keeps
  factories testable and the build independent of hardware objects).
- The registry maps the name to the function; the stored form records `name`, `arguments` and the
  module, which is imported on load. An unregistered callable or non-JSON arguments raise an error that
  names the structure and the field (T77).

### 6.4 Reading old data

| Old data | Rule |
|---|---|
| `experiment.h5` 1.0 without `/spec` | `ExperimentSpec.from_record()` rebuilds a spec from `/metadata/experiment` and the structure `config`s, marked `reconstructed: true`; factories become `drawing` geometries (the built structure is stored). Enough for a restart and for the GUI; it cannot regenerate a factory with other arguments. |
| JSON-only folders | via `storage/legacy.py` into an experiment file (unchanged), then as above. |
| `substrate.json` v1 | read as v2: `material["resin"]` → `resin_drops[*].material`, `material["substrate"]` → `substrate_material`, thicknesses → `dimensions.thickness_um` / drop `thickness_um`; the dict is kept in `material`. Written back as v2 only when the record changes. |
| Voxel database v1 | migration 1 → 2 on open (existing mechanism), see §8. |
| Scripts | Python fields of `ExperimentSpec`/`StructureSpec` are kept; `factory=` with a plain callable keeps working for running, but such a spec cannot be saved (clear error on `to_json()`). |

## 7. Setup IFOV on / off per structure — investigation (decision M2)

What the code does today:

1. **The setup is sent once.** `Experiment.__init__` sends `DefaultSetup` (`PRIMARY`, `SECONDS`,
   `ABSOLUTE`, `VELOCITY ON`, `IFOV OFF`) or `SetupIFOV` (`SECONDS`, `ABSOLUTE`, `VELOCITY ON`, `WAIT MODE
   AUTO`, `GALVO LASEROVERRIDE A AUTO`, IFOV axis pairs and settings, `GALVO ROTATION A -0.6`) through the
   immediate command interface (`experiment.py:341`). Layer programs carry no setup header.
2. **IFOV layer programs are self-contained.** `IFOV_AeroBasicProgram.initialise_IFOV_configuration()`
   sets `LOOKAHEAD FAST`, `CRITICAL START`, `METRIC`, `ABSOLUTE`, `VELOCITY ON`, `WAIT MODE AUTO`, `IFOV
   OFF`, `GALVO LASEROVERRIDE A AUTO`, `RAMP MODE RATE` with `RAMP RATE 0` (also A, B), axis pairs,
   encoder outputs, `IFOV SYNCAXES Z` and IFOV time / size / tracking, and every IFOV program ends with
   `CRITICAL END`, `IFOV OFF` and the encoders off. Its IFOV values even differ from `SetupIFOV` (63x:
   size 0.15 vs 0.075, tracking speed 16.5 vs 7.5 mm/s; golden `binary_grating_ifov_63x.txt`) and win,
   because they come later.
3. **Mixing happens already.** In an `IFOV_on` experiment the corners and the QR code are non-IFOV
   programs (`Corner`, `QRCode`; golden `commands_experiment_ifov_on.txt`). They run after `SetupIFOV`
   with its galvo rotation and after any IFOV layer program with its ramp and look-ahead settings.
4. **What remains experiment-wide in the code:**
   - `accel_a_mm` is read from the controller for `IFOV_off`, but set to `accel_x_mm / 2` for `IFOV_on`
     (workaround of 2026-05-07 after an error); every non-IFOV galvo structure of an `IFOV_on`
     experiment (QR code, factories reading `accel_a_um`) uses this value.
   - The voxel lookup (`DatabaseVoxelModel`), the `StructureRecord.setup` and the summary column `ifov`
     take the experiment setup, so corners and QR code of an `IFOV_on` experiment are reported as IFOV.
5. **State that is never reset:** `DefaultSetup` does not undo `GALVO ROTATION A -0.6`, `GALVO
   LASEROVERRIDE A AUTO`, `RAMP RATE 0`, `LOOKAHEAD FAST` or `METRIC`. Whether these persist after a
   program task ends, and whether they affect a following non-IFOV program or the next experiment in the
   same controller session, depends on A3200 task and axis parameter semantics that the code does not
   document (F11). Found during T70 → T101.

Conclusion: technically the experiment already mixes both kinds of programs; what is missing is (a) a
defined controller state at the start of every non-IFOV program, (b) per-structure accelerations and
reporting, (c) knowing which states persist.

Options:
- **A (recommended): per-structure setup.** `setup` becomes a structure setting, derived from the
  geometry (IFOV structures → `IFOV_on`, everything else → `IFOV_off`) unless set. The experiment-wide
  setup is still sent at the start (legacy behaviour, golden logs unchanged). In addition, before the
  first non-IFOV structure that follows an IFOV structure, the experiment sends `DefaultSetup` plus the
  resets that T101 identifies; experiments without a switch send nothing new. Both accelerations are read
  once before the IFOV setup, and each structure gets the one of its own setup. Voxel lookup, records and
  summary use the structure's setup. Lab check needed (T101) before T78 implements the switch.
- **B: keep one setup per experiment** and only report corners / QR code correctly. Simple, but mixed
  experiments (e.g. IFOV gratings next to stage-written reference blocks) stay impossible.
- **C: a setup header in every layer program.** Most robust, but changes every golden program file and
  makes each layer program longer.

## 8. Material store (decision M1)

Options:
- **A (recommended): extend the voxel SQLite database** to "material and voxel database" (same file
  `system.voxelDatabase`). The `material` table exists already and the voxel measurements reference it by
  id, so material names cannot diverge. Migration 1 → 2:
  - `material`: add `kind TEXT NOT NULL DEFAULT 'resin' CHECK (kind IN ('resin','substrate','medium'))`
    and `created TEXT NOT NULL DEFAULT ''`;
  - new table `material_property` (`id`, `material_id` → `material(id)`, `key`, `value_real`, `value_text`,
    `unit`, `wavelength_nm`, `state CHECK IN ('uncured','cured','any')`, `temperature_c`, `uncertainty`,
    `source`, `date`, `notes`; `CHECK (value_real IS NOT NULL OR value_text IS NOT NULL)`; index on
    `(material_id, key)`);
  - seed `config/material_seed.csv` (versioned, like `voxel_seed.csv`); CSV import/export of properties.
  - Python API `MaterialRegistry` next to `VoxelDatabase` (same connection handling, same migrations).
  - Risk: the file is per PC; a material entered on one PC is missing on the other until exported /
    imported. The snapshot in each experiment file keeps old experiments complete anyway.
- **B: YAML/JSON registry in `config/`** (versioned in git). Easy to review, but voxel data reference
  materials by name in another store, and adding a value needs a commit.
- **C: separate SQLite file.** Clean separation, but two files with the same material names.

## 9. Relation to the other repositories

- `CaptureContext` (DHMConnect schema) carries the material snapshot (or the part a capture needs) — G7;
  OffAxisHolo presets stay the offline fallback.
- `LayerTarget` (T72/T89) names the resin by registry name and carries its snapshot reference.
- `n_medium` of a result comes from the snapshot once G4 / O1 / O11 decide which index applies.
- `experiment.h5` additions (§10) are minor schema additions; OffAxisHolo K12 reads the file by
  `EXPERIMENT_STORAGE.md`, which is updated with them.

## 10. Proposed amendments to `EXPERIMENT_STORAGE.md` (schema 1.0 → 1.1, minor)

- `/metadata/materials/<role>` (`resin`, `substrate`, `medium`): material snapshot as attributes plus a
  `properties` table; `registry_file`, `registry_schema_version`, `taken`.
- `/spec`: `spec_json` (the project file), `schema`, `written`; `reconstructed` for rebuilt specs.
- `/inputs/<name>`: copied slicer inputs (mesh bytes or height map) with `sha256`.
- `/structures/<name>`: `settings_json`, `settings_source_json`; `setup` becomes the structure's own setup.
- Substrate index entry: `status` values incl. `planned`, `area_um`, `resin_drop` (§3.2).

## 11. Decisions for the maintainer

| ID | Question | Proposal |
|---|---|---|
| M1 | Where is the material registry stored? | Option A of §8: extend the voxel SQLite database (migration 1 → 2), seed CSV in `config/`. |
| M2 | Can structures with IFOV on and off be mixed in one experiment? | Yes, option A of §7: setup per structure, derived from the geometry; a `DefaultSetup` (plus resets from T101) only when switching from IFOV to non-IFOV; implementation of the switch only after the lab check T101. |
| M3 | Material per substrate or per resin drop? | Per resin drop (with batch); the substrate material separately. |
| M4 | What happens to `sys_args["sample"]`? | Kept for the tools; `material` / `substrate` filled from the registry names when known. |
| M5 | Where are slicer inputs (meshes, height maps) stored? | Copied into `inputs/` of the experiment folder and into `/inputs` of the file, with SHA-256. |
| M6 | Camera capture per structure? | Yes, as a structure setting (cheap, useful for test structures). |

## 12. Mapping to the todos

| Todo | Sections |
|---|---|
| T75 Material registry | §3.1, §8 (M1), §10 snapshot |
| T76 Substrate record v2 | §3.2 (M3), §6.4 |
| T77 Serialisable experiments and structures | §3.3, §3.4, §5, §6 (M5) |
| T78 Settings per structure | §4, §7 (M2, after T101), §10 |
| T79 Experiment configuration record | §5 (unchanged groups `/metadata/objective`, `/metadata/system`); DHM part with T71 |
| T80 Layout as data | §3.2 `area_um` |
| T81 Strategy extension point | §4 `slicing.strategy` |
| T101 Persistent controller state (new) | §7 item 5 |

## 13. Approval

Waiting for maintainer approval. Implementation (T75–T81) starts only when this line reads
`Status: approved <date>` at the top of the document, with the answers to M1–M6.
