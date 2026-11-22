# TODO

<!--
Format rules (for humans and Claude):
- ID: T<number>, never reused. Follow-ups reference their origin: "(follow-up of T3)" or "(found during T3)".
- Phase: every open todo carries "[phase: <n>]" (see "Phase plan"). Backlog todos carry "[phase: B]".
- Priority: high | medium | low
- Size (optional): S (hours) | M (about a day) | L (several days)
- Depends on: IDs or "–". IDs of the other repositories are allowed: K…/L… (OffAxisHolo),
  DL-… (DHMConnect), MI-… (MIRA); G… are the global decisions in docs/system/SOFTWARE_PLAN_OVERVIEW.md.
- Done when: one line or sub-bullets; every criterion must be verifiable.
- "Decision:" marks a question to the maintainer (working rule 3).
- Sort "Open" by phase, then by blockers/dependencies, then priority.
- "Done" is a staging area: the status review routine moves entries to ARCHIVE.md.
- Ideas that are not scheduled yet live in `future_todo.md` (F<number>). Never implement them
  unless they are moved into this file.
-->

## Phase plan

Target state of phases 0–4 (reached 2026-10-01): one `main.py` per substrate lists several experiments.
Each experiment is stored in a self-contained HDF5 file (plus redundant JSON copies) under a default
location, can be restarted, and has a short summary. Structures are sliced with measured voxel dimensions
from a voxel database.

Target state of phases 5–10 (added 2026-11-15 from the system plan, `docs/system/SOFTWARE_PLAN_OVERVIEW.md`):
an information model material → substrate → experiment → structure with settings per structure; DHM
captures through measurement recipes and the `dhmconnect` service on the DHM-PC (products instead of raw
holograms, legacy path still selectable); operating modes `off` / `monitor` / `shadow` (later `correct`)
with an evaluation after every layer capture; a camera live feed; a core that a GUI can drive.

| Phase | Topic | Todos | Gate before the dependent todos start |
|---|---|---|---|
| 0 | Concept: metadata audit, storage and substrate design | T41, T42 (done) | T42 approved by the maintainer |
| 1 | Consistent execution parameters | T43, T44, T45, T46, T58 (done) | – |
| 2 | Experiment storage | T47, T48, T49, T50, T55, T56, T57, T59 (done) | – |
| 3 | Experiment scripts and substrate main | T51, T52 (done) | – |
| 4 | Voxel database and voxel-aware slicing | T53, T54, T31 (done) | T53 design approved by the maintainer |
| 5 | Concept for phases 6–10 | T70, T71, T72, T73, T74, T100 (done; all approved 2026-11-18) | – |
| 6 | Information model | T75, T76, T77 (done), T78, T79, T80, T81, T101, T103, T108 | – |
| 7 | DHM service integration | T82, T83, T84, T85, T86, T87, T105, T106 | T84 needs DHMConnect DL-C1, DL-C2; T87 needs DL-H2 and K14 |
| 8 | Operating modes and calibration | T88, T89, T90, T91, T92, T104, T107 | T90 needs MIRA MI-53 for the real evaluator; T104 needs MIRA MI-41 for the fit; T107 needs OffAxisHolo K10 for the sweep |
| 9 | Camera live feed | T102, T93, T94, T95 | T102 before T93 (hard prerequisite, `CAMERA_LIVE.md`) |
| 10 | Core ready for a GUI | T96, T97 | – |
| B | Backlog (from T19 `todo_notes.md`, lab checks, follow-ups) | T67, T69, T109, T111, T112, T114 | – |

Phases 6, 9 and 10 are independent of each other. Phase 7 can start with T82, T83 and T85 before
`dhmconnect` exists. Phase 8 needs T83 and T85. Target of all phases: Release V1.0 as defined by the
decision session of 2026-11-17/18 (`docs/system/SOFTWARE_PLAN_OVERVIEW.md` v0.4).

### Working rules for Claude Code (in addition to CLAUDE.md)
1. Pick the first open todo of the lowest unfinished phase whose dependencies are done. Phases 6, 9 and 10
   may run in parallel once their design is approved. Take phase B todos only when nothing else is
   available or the maintainer names one; T69 (lab check) is done by the maintainer on the lab PC.
2. Design todos end with a document in `docs/design/`. After writing it, move the todo to "Blocked" with
   "Blocked by: waiting for maintainer approval". Implementation that depends on it starts only when the
   document contains the line `Status: approved <date>`. T70–T74 are approved (2026-11-18); where a design
   document's proposal table and its "Decided" section differ, the "Decided" section wins.
3. If a todo leaves a decision open (marked "Decision:"), propose an answer in the todo or design
   document and ask the maintainer before implementing the part that depends on it.
4. The real-hardware path stays the default. Every behaviour change gets a dummy-backend test; golden
   files may only change when the todo says so, and the reason goes into WORKLOG.md.
5. Keep extension points that a todo names (e.g. for DHM products, dip-in, phase data), but do not
   implement items from `future_todo.md`.
6. At the end of each phase run `python -m pytest` (incl. the dry run in `test/integration/`) and append a
   WORKLOG.md entry "[Phase <n>] Phase summary" with the finished todos, open follow-ups and anything the
   maintainer has to check on the lab PC.
7. `dhmconnect` and `mira` are optional dependencies. `python -m pytest` keeps passing without them.
8. The legacy DHM path (`Dhm`, `DhmClient`, protocol v6) and today's hologram counts stay the default until
   the maintainer switches. Golden command logs must not change in the legacy mode.
9. No reconstruction, registration, fusion or stitching code here: these belong to OffAxisHolo and MIRA.
   If a todo seems to need it, add a todo in the other repository's `TODO.md` instead (or ask).

## Open decisions (maintainer)

All global decisions G1–G10 and the decisions of the design documents T70–T74 are taken (decision
session 2026-11-17/18, master plan v0.4). Still deferred and relevant here:

| ID | Decision | When / by what | Blocks |
|---|---|---|---|
| M7 | Tolerances / thresholds for registration and comparison | after a sufficient data base (M4 study with OffAxisHolo K13, MIRA MI-31) | default thresholds of T91 (stay empty until then) |
| – | `pose_tolerance_um` for 20x / 63x | measure (T104) | final values in T89 |
| – | Final defaults for positions / frames / offset of the plan generator | after the speckle / position study (M4) | final values in T85 (start values exist) |
| – | Final default z per objective | focus study OffAxisHolo K10 | fallback value of T107 |

## Decided

| ID | Date | Result (details: master plan v0.4 §6 and the design documents) |
|---|---|---|
| G2 | 2026-11-16 | JSON Schema plus example messages in `dhmconnect/schemas/`, vendored here as test fixtures. |
| G3 | 2026-11-18 | PySide6 + pyqtgraph for the system GUI (F15) and the OffAxisHolo GUI. |
| G4 | 2026-11-18 | Separate `propagation_index` and `n_surround`; z stored with its index; in-situ only resin indices; focus from the corner markers (T107), fallback 63x −2.6 µm at n = 1.0; `phase_sign` in the parameter set. |
| G5 | 2026-11-18 | G5-new: compute on the DHM-PC, control on the Work-PC; stitched `LayerProduct` per structure and layer (N1), group protocol (N2). |
| G6 | 2026-11-18 | Target comparison on the Work-PC (this side calls `mira.evaluate_layer`). |
| G7 | 2026-11-18 | Material registry here = master; snapshot in `CaptureContext` / `experiment.h5`; JSON export for offline use; states `uncured`, `cured_in_resin`, `cured_developed` with `wavelength_nm`; SZ2080 at 674.994 nm: uncured 1.508, cured 1.52 (T108); no silent defaults. |
| G8 | 2026-11-18 | V1.0 on the Koala SDK (DHMConnect DL-H1 chooses pythonnet or a C# gateway). |
| G9 | 2026-11-18 | Lab PCs install tagged releases from GitHub with a lock file; DHM-PC Python 3.14; this repository keeps `requires-python >= 3.12`; the Work-PC follows after the mvIMPACT / NumPy 2 check. |
| G10 | 2026-11-18 | SA1 a-priori mask (default); `occupied_um` + `pose_tolerance_um` in `CaptureContext`; calibration cross + square (T104); SA6 stitching algorithm in MIRA; background tiles at the object raster positions (SI3). |
| SI1–SI4 | 2026-11-18 | `DHM_SERVICE_INTEGRATION.md` §10.1 (formerly D1–D4). |
| OM1–OM5 | 2026-11-18 | `OPERATING_MODES.md` §8.1 (formerly O1–O5). |
| C1–C5 | 2026-11-18 | `CAMERA_LIVE.md` §8.1; T102 before T93. |
| P1–P3 | 2026-11-18 | `GUI_READINESS.md` §7.1; restart rule after `stop_now()`. |
| D6, D7 | 2026-11-18 | Calibration in the service, legacy `optimage` / `motorscan` stay selectable; `keep_raw = all` in V1.0, `publication` option (T105). |
| DL-A3 a | 2026-11-18 | `config_hash` + parameter-set id in every message; the full parameter set once per hash in `experiment.h5` (T79). |
| M4 / T85 | 2026-11-18 | One plan generator here (T85), one algorithm in MIRA; at least 9 positions per structure; jitter with stored seed; start values in T85. |
| M6 | 2026-11-18 | This side rasterises the target at least as fine as the product (T89). |
| X-A, X-B, X-C | 2026-11-18 | `Information_Mehrere_Experimente.txt` and `todo_claude/` moved to the local attic; `docs/ATTIC_INDEX.md`. |

## Open

- [ ] T126: Run layer programs in queue mode (`PROGRAM 1 BUFFEREDRUN`) instead of `PROGRAM LOAD` (follow-up of T125) [phase: B]
  - Priority: high
  - Size: M
  - Depends on: –
  - Background (maintainer research 2026-11-22, A3200 help 6.04 / library 6.4.5.5): `PROGRAM LOAD` compiles the
    whole file and keeps it resident; the knowledge base names 60 000–80 000 lines as the usual limit; "An out of
    memory error occurred." is ErrorCode 88 OutOfMemory (CoreLibrary, Windows side). Queue mode
    (`PROGRAM <task> BUFFEREDRUN <file>` sent from task 0, task state 9 while running, `QueueBufferSize` per task,
    `QueueStatus` bits 0x01 active / 0x02 empty / 0x04 full / 0x10 paused) runs programs of any size. Starvation
    stops LINEAR moves in VELOCITY ON (dose peaks). `LOOKAHEAD FAST` has no function since 6.01; a `CRITICAL`
    section over the whole layer may starve the Windows side that refills the queue. Open: whether IFOV commands,
    `CRITICAL` and `$AO[...]` are allowed in queue mode (lab test first).
  - Done when: layer programs run with `BUFFEREDRUN` (queue pre-filled, e.g. `PROGRAM PAUSE` as first line and
    `PROGRAM 1 START` once `QueueLineCount` ≥ 90 % of `QueueLineCapacity`; progress and end markers via `$global`;
    queue-empty events logged with time and line); generated programs without `LOOKAHEAD FAST` and without a
    whole-layer `CRITICAL START/END` (golden files updated deliberately); the dummy backend simulates
    `BUFFEREDRUN` and the queue status; the T125 split is kept only for the LOAD path or removed; lab check with the
    largest DOE layer (2.2 M lines, 78 MB) without load error and without queue-empty events.

- [ ] T127: `REMOVEPROGRAM` names the layer file instead of the loaded program (found during T125) [phase: B]
  - Priority: high
  - Size: S
  - Depends on: –
  - Done when: after a layer the task is stopped, idle is awaited and `REMOVEPROGRAM "python_aerobasic_program.pgm"`
    (the name given to `PROGRAM LOAD`, without path) is sent instead of the original layer file name
    (`Task.finish`, `devices/aerotech/task.py`); the same after a failed load; the dummy transport records
    which programs are loaded and refuses or flags removing an unknown name; a test checks the name; golden
    command logs updated deliberately.

- [ ] T128: Load failures: log `~LASTERROR` for `!` replies and stop instead of skipping the layer (found during T125) [phase: B]
  - Priority: high
  - Size: S
  - Depends on: –
  - Done when: after every `!` or `#` reply the ASCII client sends `~LASTERROR` on the same connection and puts the
    text into the `AerotechError` (the INVALID case of 2026-11-21 logged only "has an invalid syntax!", a text of
    this client, not of the controller); `Experiment` stops printing a structure when a layer program cannot be
    loaded (option, default on), so that no structure with gaps is printed; dummy-backend tests.

- [ ] T124: Whole-structure program duplicated uncompressed in `experiment.h5` (found during T123) [phase: B]
  - Priority: medium
  - Size: S
  - Depends on: –
  - Done when: `Experiment` no longer stores `structures/<name>/program` as a second uncompressed copy
    of the layer programs (e.g. stored compressed, or only a reference/hash when it is the concatenation
    of the layers); a 48-million-line structure (main_PNG print 2026-11-21, > 2 GB text) is stored
    and read back by `ExperimentStore` and `ExperimentFile` without a 2 GB scalar string; old files still read.

- [ ] T122: Entry-script tests depend on the lab settings in `main.py` / `main_PNG.py` (found during T121) [phase: B]
  - Priority: medium
  - Size: S
  - Depends on: –
  - Done when: `test_main_entry.py::test_main_substrate_layout_is_valid`, `::test_main_layout_and_materials_dry_run`
    and `test_main_png.py::test_spec_is_one_ifov_structure_in_the_drop_center` pass whatever lab values
    (`RESIN_EDGES`, `CENTER`) are set in the SETTINGS blocks (tests patch the settings they rely on);
    they fail on `main_HR` since `bdba4c6` / `973c166` (areas leave the drop, `CENTER` no longer `None`).

### Phase 5 — Concept

### Phase 6 — Information model

- [ ] T78: Settings per structure with experiment defaults [phase: 6]
  - Priority: high
  - Size: L
  - Depends on: T70, T77
  - Done when:
    - a structure can set program source, slicing and hatching parameters, power, velocity, voxel
      model, DHM recipe and operating mode itself; unset values come from the experiment;
    - `spec.resolved()` shows the effective values per structure and validates combinations;
    - setup per structure as decided in T70 (M2): default `IFOV_on`, the structure's setup program is
      sent before its first printed layer in every session (also after a restart), never changed within
      a structure, IFOV layer programs refused under `IFOV_off`; accelerations per structure setup;
      resets in the setup programs as found by T101;
    - camera captures per structure only before and after the structure, no layer captures (M6);
    - the ported scripts that rely on today's default get an explicit `setup="IFOV_off"`; existing specs
      give identical programs (golden program files unchanged); the golden command logs are re-recorded
      with the reason (one setup per structure).

- [ ] T79: Experiment configuration record [phase: 6]
  - Priority: medium
  - Size: S
  - Depends on: T70
  - Done when:
    - objective, camera information and DHM information (service version, parameter set and hash,
      pixel size and its source) are stored once per session and shown in the summary;
    - the full DHM parameter set is stored **once per `config_hash`** in `experiment.h5` (DL-A3 a), so an
      experiment is traceable without the DHM-PC; products reference it by hash and parameter-set id.

- [ ] T80: Layout of an experiment as data [phase: 6]
  - Priority: medium
  - Size: S
  - Depends on: T77
  - Done when:
    - a function returns cells, structure areas, corner markers and QR code of an experiment as
      plain data, and a figure without `plt.show()`;
    - `plot_experiment()` and the substrate plot use it.

- [ ] T81: Extension point for dynamic slicing and hatching [phase: 6]
  - Priority: low
  - Size: S
  - Depends on: T78
  - Done when:
    - a structure names a strategy and its parameters, the name and parameters are stored in the
      metadata, and an unknown strategy is refused; no new strategy is implemented (F7, F12, F17).

- [ ] T101: Find out which controller states persist between programs and experiments (found during T70) [phase: 6]
  - Priority: medium
  - Size: S
  - Depends on: – (lab PC; A3200 manual, F11)
  - Done when:
    - it is known from the A3200 manual and a check on the lab PC whether `GALVO ROTATION A -0.6`
      (`SetupIFOV`), `GALVO LASEROVERRIDE A AUTO`, `RAMP MODE RATE` / `RAMP RATE 0`, `LOOKAHEAD FAST` and
      `METRIC` (IFOV layer programs) persist after a program task ends, into the next program and into the
      next experiment of the same controller session (`DefaultSetup` resets none of them);
    - the result is recorded in `docs/design/INFORMATION_MODEL.md` §7 and WORKLOG.md, and the reset
      commands that `DefaultSetup` and `SetupIFOV` each need to reach a defined state regardless of what
      ran before are listed for T78 (the setup is sent before every structure, decision M2);
    - if a state leaks into `IFOV_off` experiments today, a `fix:` todo exists.

- [ ] T103: Rebuild a spec from an experiment file without `/spec` (follow-up of T77) [phase: 6]
  - Priority: low
  - Size: S
  - Depends on: T77
  - Done when:
    - `ExperimentSpec.from_record(record)` rebuilds a spec from `/metadata/experiment` and the structure
      `config`s of an experiment file 1.0 (or 1.1 without `/spec`), marked `reconstructed: true`; factories
      become `drawing` geometries (INFORMATION_MODEL.md §6.4);
    - a test rebuilds the spec of a dry-run file whose `/spec` was removed and compares the built structures.

### Phase 7 — DHM service integration

- [ ] T82: Role protocol `DhmMeasurement` and legacy adapter [phase: 7]
  - Priority: high
  - Size: M
  - Depends on: T71
  - Done when:
    - `backends/protocols.py` defines `DhmMeasurement` (`configure`, `calibrate`,
      `acquire_background`, `measure`, `result`, `close`);
    - `LegacyDhmAdapter` wraps today's `Dhm`; `Experiment` talks only to the protocol;
    - golden command logs and stored data of the legacy mode are unchanged.

- [ ] T83: Capture reservation, raw references and groups in the store [phase: 7]
  - Priority: high
  - Size: M
  - Depends on: –
  - Done when:
    - `ExperimentStore.reserve_capture()` returns the capture id before the acquisition;
    - a `LayerProduct` (contract `GroupProduct`, master plan v0.4 N1) is stored in full per structure and
      layer; its member `ProductSet`s and raw frames are stored as references only (`raw_ref` / product
      id, host, path, SHA-256); results recovered after a restart are marked `recovered` (SI4);
      `/dhm_orphans` holds references only;
    - a capture can be stored without holograms but with `raw_ref` (host, path, SHA-256), `job_id`,
      frame records (metrics, `used`, `reject_reason`) and selection mask; group products are stored
      under `/dhm_groups/<group_id>`;
    - every product carries `schema_version`, `config_hash`, `background_id` and `warnings` (handover
      2026-11-16 §3), so it can be traced to its background and parameter set;
    - the schema version is raised and old files are still read; `json_copies` and the unpack tool
      in `analysis/` know the new entries; `docs/design/EXPERIMENT_STORAGE.md` is current (OffAxisHolo
      K12 reads the file with `h5py` only, without file locking, by that document).
  - Note (from MIRA MI-10, 2026-11-18): MIRA `LayerProduct.to_h5` / `from_h5` (`h5py` only) use the
    layout attribute `header_json` (the contract header) + one dataset per buffer under its contract name
    (`phase_rad`, `intensity_rel`, `valid` as uint8, optional `field`). Proposal for the `LayerProduct`
    group under `/dhm_groups/<group_id>`; if T83 chooses another layout, add a MIRA todo to adapt the reader.

- [ ] T84: Service adapter and fake service [phase: 7]
  - Priority: high
  - Size: M
  - Depends on: T82, T83, DL-C1, DL-C2
  - Done when:
    - `ServiceDhmAdapter` uses `dhmconnect.client`; configuration section `dhm_service` (host, port,
      timeouts) exists; `dhm` stays for the legacy mode;
    - the dummy backend offers `FakeDhmService` (uses `dhmconnect.testing` when installed, otherwise
      an internal fake with the same interface);
    - a dry run of an experiment in service mode passes and stores products with
      `add_dhm_product()`.

- [ ] T85: Measurement recipes and capture-position plan generator [phase: 7]
  - Priority: high
  - Size: L
  - Depends on: T78, T83
  - Done when:
    - a `DhmRecipe` with the fields of `DHM_SERVICE_INTEGRATION.md` §5 exists at experiment level with an
      override per structure and per phase (before, layer, after); today's counts 10 / 20 / 1 stay the
      defaults of the legacy mode;
    - **one plan generator** (pure function) turns footprint, field of view, `min_positions`, overlap,
      offset and jitter into a `GroupSpec` (ordered position list + per-position frames / shift pattern
      / exposure + stitching parameters + seed): small structure ≥ 9 positions around the centre; large
      structure a ring of tiles with ≈ 50 % substrate, then inwards, extra positions until
      `min_coverage`; background groups at the same raster positions (SI3); `single_shot` allowed;
    - start values (configurable, replaced after the M4 study): `min_positions` 9,
      `frames_per_position` 10, `min_coverage` 4, step for small structures ≈ 10 % of the field of view
      (≈ 9 µm at 63x), overlap ≥ 2 × border band + 10 µm, jitter ± 1 µm (63x) / ± 3 µm (20x), seed per
      capture stored;
    - recipe, `GroupSpec` and seed are stored; unknown recipe keys are passed to the service untouched;
      tests check coverage, ring anchoring and reproducibility from the seed.

- [ ] T86: Experiment flow with the service [phase: 7]
  - Priority: high
  - Size: L
  - Depends on: T84, T85
  - Done when:
    - `measure()` reserves the capture, sends context and recipe, continues after the event
      `frames_acquired` as the design allows, collects results in the writing process and
      acknowledges them after they are stored;
    - calibration (exposure, OPL scan, background) runs through the service and is stored;
    - groups follow `open_group(GroupSpec)` → per position stage move + `measure(CaptureContext with
      actual position, tile index)` → `close_group` → `LayerProduct`; the stage moves on after
      `frames_acquired`; the print waits for the result only when the job needs it (SI2, OM2), with the
      `job_status` fallback;
    - a lost service follows SI1: reconnect with backoff at layer boundaries, otherwise abort the print
      with a clear reason (resumable with `restart_experiment`); recipe `off` never connects; orphan
      recovery is T106; all of it is covered by dummy tests.
  - Note: the integration with the control script and the reference measurement is done together with
    the GPU validation OffAxisHolo K14 on the DHM-PC (handover 2026-11-16 §6.2; Python is not yet
    installed there).

- [ ] T87: Lab check of the service mode [phase: 7]
  - Priority: high
  - Size: M
  - Depends on: T86, DL-H2, K14
  - Done when:
    - a lab-check script has run on the lab PC against the real service and every point of its
      checklist is recorded in `WORKLOG.md`, including a comparison of the products with an offline
      reconstruction of the same raw data.

#### Reference: DHM recipe fields

The approved field list with defaults is `docs/design/DHM_SERVICE_INTEGRATION.md` §5 (2026-11-18:
`keep_raw = all`, `publication`, background `per_structure`, `group` as `GroupSpec`, `reference_exclusion`,
`unwrap`, `unavailable = abort` after a failed reconnect). Selection policies offered by OffAxisHolo
(`realtime/selection.py`): `all`, `threshold`, `robust` (median / MAD on `robust_metrics`, factor
`robust_k` 3.5), `best_k`; `min_frames` (default 1) is always enforced and reported. The propagation
distance comes from the experiment focus (T107) or the parameter set and is stored with its
`propagation_index` (G4).

- [ ] T105: Transfer of raw data to the Work-PC for publication experiments (D7) [phase: 7]
  - Priority: medium
  - Size: M
  - Depends on: T86, DL-B12
  - Done when:
    - with `publication: true` all raw data of the experiment are transferred from the DHM-PC after the
      print (background, never during the print) to a configurable target (data root or archive /
      network drive); SHA-256 checked; progress and result stored in `experiment.h5`;
    - a dummy test transfers from the fake service.

- [ ] T106: Orphan recovery on restart (SI4) [phase: 7]
  - Priority: high
  - Size: M
  - Depends on: T83, T86, DL-B6
  - Done when:
    - on `restart_experiment` or the next connection the orphans of this experiment are listed by the
      service; `LayerProduct`s are fetched, stored in full, marked `recovered` (reason, original session)
      and acknowledged; tiles and raw data are stored as references under `/dhm_orphans`;
    - nothing is deleted on the DHM-PC; a dummy test covers a crash after `result` and before `ack`.

### Phase 8 — Operating modes and calibration

- [ ] T88: Operating mode in specification and storage [phase: 8]
  - Priority: high
  - Size: S
  - Depends on: T72, T78
  - Done when:
    - `FeedbackMode` (`off`, `monitor`, `shadow`, `correct`) is a field of the experiment with an
      override per structure, default `off`, stored and shown in the summary;
    - `correct` is refused with a clear error while no controller is registered.

- [ ] T89: Layer targets [phase: 8]
  - Priority: high
  - Size: M
  - Depends on: T78
  - Done when:
    - a pure rasteriser produces a `LayerTarget` (expected height map and exact mask after layer n in µm,
      grid with `pixel_um = min(half hatch distance, product pitch)`, area-weighted edges, position,
      material, `domain`) for sliced structures from the toolpath job, and it is stored (M6);
    - drawn structures: toolpath + voxel model, otherwise footprint only with a warning; `shadow` stays
      allowed with a footprint target (OM1);
    - the capture context carries `occupied_um` (all printed matter in the field of view, stage µm) and
      `pose_tolerance_um` for the a-priori reference mask (G10 SA1 / SA2), with `reference_exclusion`;
    - a test checks the target of a simple block against its analytic shape, including edge weights.
  - Later (not V1.0): target source `design_heightmap` (grey-value height map, explicit grey → height
    mapping, pixel ≤ 50 nm, area-averaged down).

- [ ] T90: Evaluation hook after a layer capture [phase: 8]
  - Priority: high
  - Size: M
  - Depends on: T86, T88, T89, MI-53
  - Done when:
    - after `measure(layer)` an `Evaluator` receives product, target and context and returns a
      `DeviationReport`, which is stored under `/analysis` (uses the access layer of T66 / T67);
    - the default evaluator is an adapter to `mira`; without `mira` the modes other than `off` are
      refused with a clear message; the dummy backend has a fake evaluator;
    - the hook can run without blocking the print (OM2); `wait_for_evaluation` per structure (default
      `false`, always `true` in `correct`) makes the next layer wait;
    - the comparison domain is chosen automatically (phase preferred, else height) or fixed per spec
      (OM4); reports go to `/analysis/captures/<id>/deviation` with `source = "nanofactorysystem.feedback"`
      (OM5).
  - Note (2026-11-18): MIRA MI-53 is done: `mira.api.evaluate_layer(product, target, context, settings)`
    with `LayerProduct` / `LayerTarget` from `mira.products` / `mira.targets` (`from_message`); `context`
    needs `parameter_set.phase_sign` (or `phase_sign`), `source`, optional `registration`; `settings` keys:
    `domain`, `sigma`, `k`, `shift_um`, `min_coverage`, `segments` (MIRA commit `f513ef0`).

- [ ] T91: Behaviour of `monitor` and `shadow` [phase: 8]
  - Priority: medium
  - Size: M
  - Depends on: T90
  - Done when:
    - `monitor` logs RMSE, MAE and validity per layer, warns above the threshold of the spec and can
      stop the structure by rule (opt-in, OM3); the default thresholds stay empty until M7 is decided;
    - `shadow` additionally asks a `Controller` for a `CorrectionPlan` and stores it without
      applying it; the default controller returns an empty plan;
    - both are shown in the summary and covered by dummy tests.

- [ ] T92: Simple process model in the simulated world [phase: 8]
  - Priority: low
  - Size: M
  - Depends on: T90
  - Done when:
    - the dummy world can produce layer products from the printed programs with a simple height per
      dose model and a configurable disturbance, so that the modes can be dry-run end to end.

- [ ] T104: Calibration procedure writing field ↔ camera ↔ DHM (G10 SA2) [phase: 8]
  - Priority: high
  - Size: L
  - Depends on: T83, MI-41 (fit)
  - Done when:
    - a simple program prints a cross + square; the cross gives the offset of the centres, the square
      rotation / scale / shear; the cross is additionally imaged at known stage offsets (e.g. 3×3) for an
      affine least-squares fit independent of the galvo scale; per objective, camera and DHM separately;
    - the result is a versioned calibration file (date, objective, id, residuals) loaded with the
      parameter set; id + copy are stored in `/calibration/dhm/mapping`; it stays valid until someone
      touches the hardware; manual recalibration at any time; optional quick check at the start of an
      experiment;
    - until a calibration exists: rotation 0, nominal pixel size, generous tolerance (documented);
    - dummy test with a synthetic mapping; `pose_tolerance_um` for 20x / 63x measured on the lab PC.
  - Note (2026-11-19, MIRA MI-11 / MI-41): the model, the file format (`StageImageCalibration` 1.0, proposed
    in `mira/geometry.py`, contract todo DHMConnect DL-A11) and the fit exist in MIRA:
    `mira.calibration_marks.detect_cross` / `detect_square` / `fit_cross_raster` → `mira.geometry.save_calibration`.

- [ ] T107: Focus determination from the corner markers (G4) [phase: 8]
  - Priority: high
  - Size: M
  - Depends on: T86, K10 (z sweep in OffAxisHolo)
  - Done when:
    - after the corner markers are written a DHM capture is taken; z is determined from a z sweep of the
      reconstructed amplitude with a sharpness metric (e.g. minimum of std / mean) and stored per
      experiment under `/calibration/dhm/focus` as the default z of the experiment, with its
      `propagation_index`;
    - fallback: z per objective from the parameter set (63x: −2.6 µm at n = 1.0 until K10);
    - per-capture autofocus values are only reported in `quality`; a dummy test with a synthetic stack.

### Phase 9 — Camera live feed

- [ ] T102: Camera image timeout uses the exposure in µs as if it were ms (found during T73) [phase: 9]
  - Priority: high
  - Size: S
  - Depends on: – (verification on the lab PC)
  - Done when:
    - `CameraDevice.getimage()` waits at most a bounded time derived from the exposure in ms (e.g. twice the
      exposure plus a transfer margin, at least 50 ms) instead of `2000 × ExposureTime[µs]` ms (≈ 11 h at
      20 ms); the unit of `ExposureTime` returned by mvIMPACT is confirmed on the lab PC;
    - a missed frame raises a clear error instead of blocking; a unit test with the dummy driver checks
      the computed timeout; the camera service (T93) relies on it for its stop bound.

- [ ] T93: Camera service with one owner [phase: 9]
  - Priority: medium
  - Size: M
  - Depends on: T102
  - Done when:
    - one thread owns the camera driver and offers the latest frame and subscriptions;
    - `measure()`, the overview and the focus tools get their images through it; no behaviour change
      when the feed is off (default); the dummy camera supports it.

- [ ] T94: Recording of the print process [phase: 9]
  - Priority: low
  - Size: M
  - Depends on: T93
  - Done when:
    - a recording can be started per experiment or structure, is written next to the experiment
      file, and a table in `experiment.h5` maps frame times to structures and layers;
    - the recording stops cleanly on abort;
    - container MP4 `mp4v` by default, lossless `h5` opt-in, no AVI / MJPG (C2); check whether `avc1`
      (H.264, QuickSync on the Work-PC) works directly, otherwise an export step;
    - the camera overview before / after the print runs through the camera service and has an optional
      downscale factor for the stored mosaic.
  - Note: the maintainer wants a video of each structure while it prints (2026-11-16, with T70 M6).

- [ ] T95: Live feed interface [phase: 9]
  - Priority: medium
  - Size: S
  - Depends on: T93
  - Done when:
    - a consumer can subscribe to frames with timestamps while an experiment prints; a headless
      test on the dummy backend receives frames during a dry run.

### Phase 10 — Core ready for a GUI

- [ ] T96: Remove blocking user interaction from the run path [phase: 10]
  - Priority: medium
  - Size: S
  - Depends on: T74
  - Done when:
    - `messagebox_confirm` is an injectable callback (default as today);
    - the `plt.show()` calls in `experiment.py` and `substrate_plan.py` return the figure instead;
      the entry scripts show it.

- [ ] T97: Run control and progress events [phase: 10]
  - Priority: medium
  - Size: M
  - Depends on: T74, T96
  - Done when:
    - a runner emits events for structure, layer and capture start and end, and accepts pause,
      resume and abort between layers from another thread;
    - a dummy test pauses and aborts a dry run and restarts it with `restart_experiment()`;
    - `stop_now()` stops the running task (documented as no safety function); a layer stopped mid-program
      is never reprinted automatically, the structure counts as `stopped`, `resume_stopped=True` resumes
      with a warning (P2); a pause longer than `max_pause_s` warns (P3).

### Phase B — Backlog (from T19 `todo_notes.md`, lab checks, follow-ups)

- [ ] T69: Run the lab check of the new features on the lab PC (follow-up of T68) [phase: B]
  - Priority: high
  - Size: S
  - Depends on: T68
  - Done when:
    - `mains/lab_checks/new_features_check.py` has run on the lab PC and every point of its checklist is
      recorded in WORKLOG.md as working or as a new todo;
    - in particular: the overview before printing is in focus (it is taken at the Z where the plane fit
      ended; if not, a todo for a defined overview Z), and a restart after Ctrl+C prints only the missing layers.

- [ ] T67: Evaluation pipeline on top of `ExperimentFile` (follow-up of T66) [phase: B]
  - Priority: medium
  - Size: M
  - Depends on: T66
  - Done when:
    - the maintainer has named the first evaluations (e.g. structure heights from DHM products, camera
      image comparison before/after, voxel sizes for the voxel database);
    - each evaluation reads its inputs with `ExperimentFile` and stores its results under `/analysis` with
      its parameters, with a test on a dummy experiment;
    - results can be compared over several experiments of a substrate (`find_experiments`).
  - Note: T90 stores its `DeviationReport` through the same access layer; keep the `/analysis` layout
    compatible.

- [ ] T109: Check the active v6 client for the tuple `raise` of finding B19 (found during DHMConnect DL-A8) [phase: B]
  - Priority: low
  - Size: S
  - Depends on: –
  - Done when:
    - the v6 client in `nanofactorysystem/dhm/` raises `AttributeError(...)` instead of
      `raise(AttributeError, "…")` (a `TypeError` in Python 3), with a unit test; golden command logs
      unchanged.

- [ ] T111: Clear error for an incomplete user section in the configuration (found during T110) [phase: B]
  - Priority: low
  - Size: S
  - Depends on: –
  - A `user:<name>` section without `email`, `organization` or `orcid` makes every `System`/`Experiment`
    fail inside `scidatacontainer.load_config` with `AttributeError: 'NoneType' object has no attribute
    'strip'` (`nanofactorysystem/parameter.py`, `Parameter.__init__`), which does not name the missing key.
  - Done when:
    - `Parameter.__init__` (or `Config.user`) raises an error naming the user and the missing keys, with a
      unit test; complete user sections behave as before.

- [ ] T112: Realistic accelerations in the stage examples of the template and the lab check (found during T110) [phase: B]
  - Priority: medium
  - Size: S
  - Depends on: –
  - `Rectangle3D(..., velocity=1000, acceleration=500)` with `axes="XYZ"` in
    `mains/Experiments/old_experiment/experiment_template.py` (`drawing_spec`, "rectangle"; moved in T113) and
    `mains/lab_checks/new_features_check.py` (`rect`, `ramp`) gives a run-up of 2·v²/(2a) = 2 mm before
    every 50/30 µm hatch line (`_Lines.iterate_layers`, a in µm/s²); the time estimate says about 49 min
    for one 50×50×3 µm block. The dry runs do not show it (simulated motion time).
  - Decision: use the controller acceleration through a named factory (as `default_experiment.rectangle`,
    T110) or a fixed realistic value? Proposal: the factory, because the controller value is the one the
    stages really use.
  - Done when:
    - both scripts use the chosen acceleration and the expected printing time of these structures is in the
      range of minutes; T69 (lab check) is run with the corrected values.

- [ ] T114: `Rectangle3D_IFOV`: objective of the IFOV configuration and stateless alternating hatch (found during T113) [phase: B]
  - Priority: medium
  - Size: S
  - Depends on: –
  - `Rectangle2D_IFOV` / `Rectangle3D_IFOV` (`aerobasic/programs/drawings/ifov_gratings.py`) create `IFOV_Lines`
    without an objective, so their layer programs always use the IFOV configuration and writing speed of the
    Zeiss 63x (`IFOV_Lines.iterate_layers(objective="Zeiss 63x")`), also in a 20x experiment.
    `HeightMap_IFOV` already takes `objective=`.
  - With `alternate_hatching=True`, `Rectangle3D_IFOV.iterate_layers` flips `self.hatching_direction` after
    every layer. With an odd number of layers (e.g. 6 µm / 0.25 µm → 25 layers) a second iteration (time
    estimate, plot, rebuild) starts with the other direction, and `to_json()` may store the flipped start
    direction.
  - Done when:
    - both classes take `objective=` (default `"Zeiss 63x"`, stored in `to_json()`) and pass it on;
    - the alternating direction is computed from the layer index without changing the object; iterating twice
      gives identical programs (unit test); golden files unchanged.

## In Progress
<!-- Claude Code moves a todo here when starting work. -->


## Blocked
<!-- Format: todo as above, plus the line "Blocked by: <reason or T<n>>". -->

## Done
<!-- Claude Code adds: - [x] T<n>: title — YYYY-MM-DD — 1–2 sentences on what changed — commits: `<sha>`, … -->
- [x] T125: DOE print printed only 16 of 73 layers: `PROGRAM LOAD` refused every layer program above about 80 000 lines (maintainer report 2026-11-22, `surface_16bit`) — 2026-11-22 — Hotfix: `build_programs()` splits every layer program with more than `max_program_lines` (default 80 000) lines into parts (whole layer setup and footer repeated, cut with the laser off at an absolute move, power/feed replayed) and stops if one cannot be split; printing prepares all layers before the first one; interim solution `Experiment.reprint_layers()` / `mains/reprint_layers.py` prints the missing layers from the experiment file, split, in drop-direction order (DOWN: highest first). Real fix: T126; follow-ups T127, T128; lab check of the parts open. — commits: `76b8839`, `d46ad4a`, `a6db390`, `9974a31`, `2e7ad3a`
- [x] T123: Unpacking aborted with `string too large to store inside array` (maintainer report 2026-11-22, main_PNG experiment) — 2026-11-22 — `write_dataset` takes scalar-ness from the dataset shape and writes scalar text unchanged, so text over 2 GB (the whole-structure program of a 48-million-line print) unpacks. Storage side: T124. — commits: `314d634`
- [x] T121: Lab run aborted with `'tuple' object has no attribute 'as_tuple'` in `experiment_area` (maintainer report 2026-11-21, main_PNG) — 2026-11-21 — `CENTER` in `main_PNG.py` was a plain tuple; `ExperimentSpec` now converts an `(x, y)` center to `Point2D` (TypeError for anything else) and the script writes `Point2D` again. — commits: `e460cf5`
- [x] T117: IFOV prints only a cross ("+") of every filled area (found during the chain print HR-26-002, 2026-11-20) — 2026-11-21 — Cause found by the maintainer in the lab: a wrong configuration on the A3200 controller, not the generated programs; no change to `IFOV_Lines` / `initialise_IFOV_configuration` and the golden files. The lab test `mains/Experiments/ifov_laser_test.py` and the switches `ASK_EACH_STEP` / `ASK_BETWEEN` / `SHOW_PLOTS` stay; IFOV prints (incl. `main_PNG.py`) are cleared again. — commits: `114c55b`, `7cf1403`, `4719134`, `c936384`, `6020906`
- [x] T120: Lab run aborted with `Tcl_AsyncDelete` during plane detection (maintainer report 2026-11-21, main_PNG with SHOW_PLOTS = False) — 2026-11-21 — Hidden plots are built without pyplot (no Tk objects), shown plots and the message box free their Tk objects in the main thread right away. — commits: `7360a3c`
- [x] T119: `SUBSTRATE_LABEL` in `main_PNG.py` and the import error `No module named 'main'` (maintainer report 2026-11-21) — 2026-11-21 — With `SUBSTRATE_LABEL` the PNG experiment runs through `run_substrate` (substrate created below `dataRoot` if new, overlap checked, layout files updated); `None` keeps `OUTPUT_ROOT`; the script puts `mains/` on `sys.path` itself. — commits: `b2cff99`
- [x] T118: Substrate layout as JSON and image in the substrate folder (maintainer request 2026-11-21) — 2026-11-21 — Every write of the substrate index rewrites `substrate_layout.json` (drops, every experiment with label, name, status, center and area in stage µm) and `substrate_layout.png` (no window); a planned entry keeps its name after registration; task `overview` regenerates both for older substrates. — commits: `1b110d0`, `b191ac0`
- [x] T116: Entry script for printing a PNG height map (maintainer request 2026-11-20) — 2026-11-20 — `mains/main_PNG.py` needs only the PNG path, pixel size and µm per gray value; user, objective, drop and output come from `main.py`, the structure is placed in the drop center; `--preview` and `--dry-run`; tested incl. dry run. — commits: `f6efbac`
- [x] T115: Maintainer decisions on the experiment chain and the remaining old entry scripts (follow-up of T113, maintainer request 2026-11-20) — 2026-11-20 — The chain keeps 5 µm written height above the substrate (totals incl. the 1 µm overlap), uses cross hatching with one hatch distance per cell in every layer (DOE base explicit) and captures the overview mosaic; `dhm_paper.py`, `dhm_paper_pillowProblem_63.py`, `grating_try.py` moved from `mains/` to `mains/Experiments/old_experiment/`. — commits: `21806e8`, `1ee08c1`
- [x] T113: Older experiment scripts to `old_experiment/` and a rectangle → DOE → lens experiment chain (maintainer request 2026-11-20) — 2026-11-20 — `mains/Experiments/` holds only `default_experiment.py` and `chain_rectangle_doe_lens.py`; everything else is in `mains/Experiments/old_experiment/`. The chain prints three IFOV experiments (rectangle 50×50×6 µm, DOE 5×5 on a 3.5 µm base, aspheric lens R 30 µm / k 2.3 / sag 6 µm, all 1 µm in the substrate, slice 0.25 µm), each a 3×3 grid power × hatch; dry run of the whole chain finished. Follow-up T114. — commits: `6c82ef8`, `1e4c3f9`, `75c3d19`
- [x] T110: Main entry point for every task and a fully documented default experiment (maintainer request 2026-11-19) — 2026-11-19 — `mains/main.py` runs the tasks experiment / slicer / layout / substrate / spec_file / restart / overview / analyse / materials, each also as dry run (`--task demo --dry-run` runs all, checked end to end); `mains/Experiments/default_experiment.py` writes out every spec field and slicer option with an explanation; `backends.dummy.dry_run` for dry runs from scripts; the former main is `mains/main_legacy.py`. Follow-ups T111, T112. — commits: `9bd6c74`, `76138ba`, `e374b12`, `268f1c4`
- [x] T108: Material states and the SZ2080 seed — 2026-11-18 — States `uncured` / `cured_in_resin` / `cured_developed` / `any` with schema migration 2 → 3 (`cured` → `cured_in_resin`, old CSV files and snapshots still load); SZ2080 at 674.994 nm in `config/material_seed.csv`; versioned JSON export `MaterialRegistry.export_json`; `require_refractive_index` / `contract_snapshot` raise `MissingPropertyError` instead of a default — commits: `e79a531`, `0108f7f`, `698cc5c`.
- [x] T98: Turn `Information_Mehrere_Experimente.txt` into an English user guide — 2026-11-18 — Guide `docs/guides/SUBSTRATE_AND_EXPERIMENT_SPECS.md` (`3101a96`); the German original moved to the local attic per X-A / X-B and is listed in `docs/ATTIC_INDEX.md` (`32d04e2`).
- [x] T100: Prepare the nanofactorysystem input for the planning session K18 — 2026-11-18 — The note `docs/system/handover/to_offaxisholo_k18_2026-11-16.md` was reviewed in the decision session 2026-11-17/18; G10 is decided (SA1–SA7), master plan v0.4 (`dbd4e67`).
- [x] T71: Design the DHM service integration and measurement recipes — 2026-11-18 — Approved with additions (SI1–SI4, formerly D1–D4; recipe defaults), `DHM_SERVICE_INTEGRATION.md` §10.1 (`3048e1f`).
- [x] T72: Design the operating modes and feedback hooks — 2026-11-18 — Approved with additions (OM1–OM5, formerly O1–O5), `OPERATING_MODES.md` §8.1 (`3048e1f`).
- [x] T73: Design the camera live feed and recording — 2026-11-18 — Approved (C1–C5, MP4 default, T102 prerequisite), `CAMERA_LIVE.md` §8.1 (`3048e1f`).
- [x] T74: Design the headless core for a GUI — 2026-11-18 — Approved (P1–P3, restart rule, G3 PySide6 + pyqtgraph), `GUI_READINESS.md` §7.1 (`3048e1f`).
- [x] T99: Translate the German comments in `mains/` and `test/manual/` — 2026-11-17 — the named folders were already English; the German left in active package code (`calc_polygons.py` demo, exception messages in `height_function_structures/structures.py`) and the package README of `height_function_structures/` were translated; legacy folders, commented-out code and the personal notes `drawings/Plan.md`, `TODO_default_origin.md` stay German on purpose. — commits: `49b1fc6`, `3101a96`
- [x] T76: Substrate record v2 and experiment overview — 2026-11-17 — `substrate.json` version 2 holds substrate material, type and dimensions and material/batch/thickness/application per resin drop (version 1 read as 2); `run_substrate()` enters experiments as `planned`, each experiment replaces its entry with area and drop, and `substrate_overview()` lists them with the status of their files; existing substrate mains run unchanged. — commits: `31ae2b2`, `dd1bc9a`

- [x] T77: Serialisable experiments and structures — 2026-11-17 — `ExperimentSpec`/`StructureSpec` are project files (`to_json`/`from_json`, `save`/`load`, schema `nanofactory.experiment_spec/1`, slicer inputs with SHA-256), structures that need the running experiment use named factories (`structure_factories.py`, `BuildContext`), unstorable fields raise an error naming structure and field; `run_experiment()` stores the spec as `experiment_spec.json` and in `/spec` + `/inputs`; all ported scripts round-trip. Follow-up T103 (`from_record()`). — commits: `2c9bd1b`, `d431bbd`, `4f83dd7`, `e749109`

- [x] T75: Material registry for photopolymers — 2026-11-16 — The voxel database (schema 2) holds materials (resin/substrate/medium) with extensible properties (value, unit, wavelength, state, source, date; new keys without code change) behind `MaterialRegistry`; every new experiment file stores a snapshot per role in `/metadata/materials` (schema 1.1), `SubstrateSpec.material` accepts a registry name. Which index is `n_medium` stays G4. — commits: `1a78f06`, `5953d36`

- [x] T70: Design the information model v2 — 2026-11-16 — `docs/design/INFORMATION_MODEL.md` defines material (registry in the voxel SQLite, M1), substrate record v2 (material per resin drop, M3), experiment spec as project file and structures with their own settings; setup per structure, sent before every structure, default `IFOV_on` (M2), camera only before/after a structure (M6); approved by the maintainer. — commits: `2709356`, `2f72064`, `c68d2a3`, `893202c`, `42313ef`

- [x] T1: Record baseline and review the code — 2026-09-28 — Recorded the test baseline (global env: all 40 files fail on a NumPy ABI mismatch; clean venv: 16 passed / 20 failed / 16 errors over `test/`) in WORKLOG.md and wrote `docs/reviews/CODE_REVIEW_2026-09-28.md`; follow-ups T9–T18 added. — commits: `bf98f78`

- [x] T2: Design the dummy hardware backend — 2026-09-28 — Wrote `docs/design/DUMMY_BACKEND.md` (seam/role protocols, explicit `backend=` switch, socket-level fake controller, deterministic simulated world with call log); approved by the maintainer with three decisions (controller merge later as T20, no env var, `plane_fit(plane=...)` instead of simulated detection). — commits: `46ae4b1`, `b6340a4`

- [x] T12: Rename `devices/aerotech_old.py` to `devices/a3200.py` — 2026-09-28 — Pure `git mv` plus the import in `devices/__init__.py`; hardware-free test results unchanged (16 passed / 11 failed / 3 errors, as in baseline B). — commits: `6b43511`

- [x] T3: Implement the dummy hardware backend — 2026-09-28 — Added `nanofactorysystem.backends` (protocols, RealBackend, DummyBackend with socket-level fake A3200, simulated camera/DHM/attenuator, deterministic world and call log), lazy config with built-in default, device injection parameters, `System/Experiment(backend=...)` and `plane_fit(plane=...)`; 40 new tests, real-hardware path verified unchanged. — commits: `df14fd7`, `65cd58c`, `8dc0b46`, `597b8ba`

- [x] T4: pytest configuration and shared fixtures — 2026-09-28 — Added `[tool.pytest.ini_options]` (testpaths, norecursedirs, markers `hardware`/`slow`) and `test/conftest.py` with `--run-hardware` and the fixtures `test_config`, `tmp_program_dir`, `dummy_backend`, `no_sleep`, `dummy_controller`, `dummy_system`; 7 fixture tests. — commits: `97c5612`

- [x] T15: Repair failing hardware-free unit tests — 2026-09-28 — Fixed `create_variable`/`AerotechVariable` (separate fix commit) and updated outdated tests with justification (axis names, Python 3.12 changes, timestamp header, removed `CornerRectangle`, wrong cm value); `test_prevent_mixed_axes` is strict xfail (T23). 31 passed, 1 xfailed. — commits: `69827fd`, `22e8e7e`

- [x] T5: Triage and convert the device tests — 2026-09-28 — Every device/DHM/Femtika/tools/system/slicer test file is converted (dummy + `hardware` tests with assertions) or moved to `test/manual/`, reasons in WORKLOG.md; `python -m pytest` passes without hardware or config (104 passed, 14 skipped, 1 xfailed) and `-m hardware --run-hardware` collects 13 tests. — commits: `96d54a4`, `4cbda21`

- [x] T6: Dry-run an experiment with the dummy backend — 2026-09-28 — `default_exp_file.py` runs end to end on the dummy backend (plane_fit with known plane, build_programs, print_experiment); integration test writes only to `tmp_path`; the dry run found and fixed a tuple bug in the template. — commits: `c6179d0`, `2e911c2`, `43cb532`

- [x] T7: Golden-file tests for AeroBasic generation — 2026-09-28 — 11 representative programs (DefaultSetup and SetupIFOV, incl. corners, stair, QR code, IFOV grating) are compared against `test/golden/*.txt`; `--update-golden` regenerates them deliberately. — commits: `175af6b`

- [x] T8: Write `test/README.md` and update the documentation — 2026-09-28 — `test/README.md` documents the four test categories with per-module tables, run commands, markers, dummy backend usage and artefact locations; CLAUDE.md Commands, Architecture (and the outdated Configuration) sections updated. — commits: `1705ca4`

- [x] T9: Fix packaging and pin a working environment — 2026-09-29 — `pyproject.toml` discovers all subpackages, declares all runtime dependencies (OpenCV pinned for NumPy 2) and a `test` extra; a fresh venv with `pip install ".[test]"` passes the suite. — commits: `7aecd16`

- [x] T10: Fix defects in the experiment flow — 2026-09-29 — `opl_scan` uses `motorscan`, a failed layer is logged (task stopped, printing continues) via the new `TaskFailedError`, substrate information is merged, empty structures work, and the experiment dictionary stores the right objective and log file; 6 new dummy tests. — commits: `b1d19a2`, `b0ed53e`

- [x] T21: Stop `Parameter` from mutating the caller's argument dictionaries — 2026-09-29 — `Parameter` works on a copy of each section, so `sys_args` can be reused; also fixed `Camera` ignoring `product`/`deviceID`. — commits: `4911149`, `5af8e45`

- [x] T13: Add timeouts to hardware communication and wait loops — 2026-09-29 — Configurable connect timeouts (10 s), optional response timeouts, responses read until the terminator, bounded axis/z-line waits and stall/stop bounds for tasks; terminated `~LASTERROR`; 12 dummy tests. — commits: `1ee7ef0`, `8d9d4dc`

- [x] T14: Remove the hardcoded calibration path from `IFOV_Lines` — 2026-09-29 — `IFOV_Lines` takes a `PowerCalibration` (explicit, active context, or configured file); `Experiment.build_programs()` uses its attenuator calibration; golden files unchanged; 8 new tests. — commits: `eb26199`, `69547ba`

- [x] T11: Fix small defects in `System` and the `A3200` controller — 2026-09-29 — Fixed `object_pos`/`camera_pos`, `A3200.home`, `A3200.container`, `self.z` before an absolute z move and the recursive `send_one`; a dummy test per fix. — commits: `6ef8d37`, `b65b604`

- [x] T22: Fix NumPy 2.5 deprecation in `Attenuator` — 2026-09-29 — `reshape` instead of assigning `array.shape` in `Attenuator` and `CameraDevice` (the `IFOV_Lines` case went away in T14); the suite passes with the deprecation as error. — commits: `daa757e`

- [x] T16: Fix always-true `assert (path, Path)` in experiment scripts — 2026-09-29 — The 48 always-true asserts in `mains/` are replaced by `path = Path(path)`, which accepts the str paths the callers pass; no warnings remain. — commits: `d1f1f67`

- [x] T17: Clean up logging — 2026-09-29 — `getLogger()` no longer duplicates handlers (one console handler, one log file that is replaced for a new file); command failures are logged instead of printed. — commits: `2da7be2`, `cdcee08`

- [x] T24: Fix `utils.visualization.plot_movements` — 2026-09-29 — Arcs, ragged segments, empty programs, degenerate axes and RAPID/variables are handled; all program plots work and plotting errors fail the tests again; 5 new tests. — commits: `da404d1`, `e2df115`

- [x] T25: Fix argument passing in experiment scripts — 2026-09-29 — The restart script now rebuilds the experiment from `experiment_dictionary.json` via the new `Experiment.parameters_from_dictionary()` (the original finding about the logger was inaccurate, see WORKLOG), and the template passes substrate information; dummy restart test added. — commits: `56e4d9a`, `412c763`

- [x] T23: Decide and implement axis validation for `SingleAxis` — 2026-09-29 — Maintainer decision: mixing stages allowed; `~`, `^` and an empty `&` raise `AxisError`; the xfail test is replaced by `test_axis_combinations`. — commits: `6d4009a`

- [x] T20: Merge `A3200` and `Aerotech3200` into one controller class — 2026-09-29 — `A3200` builds on the new `AerotechController` and one ASCII interface; `System.controller is System.a3200_new`; golden command logs recorded before the merge are unchanged; maintainer decision: `.api` Z moves beyond zMax are refused. — commits: `f49d935`, `fdb0719`, `dcf80dc`, `5f8e203`

- [x] T19: Identify each and every todo and note in all of the documents — 2026-09-29 — All 535 work markers (94 distinct) and the slicer roadmap are recorded in `todo_notes.md` with meaning, locations and 15 work packages (T26–T40), then removed from the active code; explanatory notes kept (maintainer decision). — commits: `b2d2f05`, `5f8af15`

- [x] T18: Translate German identifiers and comments — 2026-09-29 — German comments/docstrings in the package and test modules translated, `run_testzweck_altesSystem` renamed to `send_with_simple_protocol`, one module per commit; `mains/` and `test/manual/` scripts left (see WORKLOG). — commits: `118a095` … `7d973e9` (15)

- [x] T41: Audit the experiment metadata — 2026-09-29 — `docs/reviews/METADATA_AUDIT.md` lists every file an experiment writes and rates each metadata item, checked against two dummy dry runs of the template; defects outside T42–T50 were added as T55–T60. — commits: `bf5565a`

- [x] T42: Design the experiment storage and substrate model — 2026-09-29 — `docs/design/EXPERIMENT_STORAGE.md` defines one self-contained HDF5 file per experiment below the per-user default root, substrate/experiment labels and UUIDs, write strategy, JSON copies, legacy reading and the store API; approved by the maintainer with all proposals D1–D8. — commits: `ef2ff63`, `3f75e0a`

- [x] T46: Record the stage position of every capture — 2026-09-29 — `measure()` stores a `CaptureRecord` (commanded and actual XYZAB position, structure, phase, layer, image index/count, UTC time) in every camera/DHM container and in `captures.json`, and accepts a list of capture offsets; golden command logs unchanged. — commits: `c16f5ae`

- [x] T47: Implement the HDF5 experiment store — 2026-09-30 — New `nanofactorysystem.storage` (`ExperimentStore`, records, JSON copies, lock file, software info); `Experiment` writes metadata, calibration, plane fit, OPL scan, layout, structures, layer programs, progress and captures (no more `.zdc`/`.npy`) into `experiment.h5`, exports the JSON copies from it, and refuses an existing experiment folder unless `resume=True`. — commits: `bc371eb`, `fe6036a`, `bed280b`

- [x] T55: Store the controller command log with the experiment — 2026-09-30 — `A3200.log` is written into the experiment folder, and the command log and the session's console log are stored per session under `/logs` in `experiment.h5`, also after an exception or abort. — commits: `b624a66`

- [x] T57: Store paths relative to the experiment folder — 2026-09-30 — Layer/structure program files and the log file are stored relative to the experiment folder (file and JSON copies); `parameters_from_dictionary()` uses the given folder, so a moved experiment can be restarted; old absolute entries still work. — commits: `e07db5a`

- [x] T48: Substrate model, default location and experiment index — 2026-09-30 — `SubstrateStore` (substrate.json with record and experiment index, labels `HR-26-001`/`-A`, `find_experiments`, `default_root` with `dataRoot` and refused synced folders); `Experiment(path=None, substrate=...)` creates a new folder per print and keeps the index up to date; `substrate_information.json` merging replaced (old files importable). — commits: `1014892`, `cf5ed05`

- [x] T49: Experiment summary — 2026-09-30 — `storage/summary.py` builds a summary (UUID, one row per user structure with position, slice, hatch, power, velocity, IFOV, DHM, camera, status); written into `/summary` and `experiment_summary.json` after building and after every structure and logged as table. — commits: `92b9bcc`

- [x] T50: Restart and repetitions on the new storage — 2026-09-30 — Restart reads parameters and per-layer progress from `experiment.h5` (resumes correctly after any number of aborts, keeps the UUID); old JSON folders are imported into a new experiment file on restart; `REPEAT` fixed (own grid cell, `<name>_rep<n>`, `repeat_of`). — commits: `7aaee04`

- [x] T59: Correct the print-progress record — 2026-09-30 — `print_progress.json` is exported from the experiment file (schema `nanofactory.print_progress/2`): printed/failed layer counts, start/end time per layer and structure; UP and DOWN tested after a complete and an aborted structure. — commits: `154d85d`

- [x] T56: Make structure serialisation complete and reversible — 2026-09-30 — `to_json()` stores only constructor parameters (with `__module__`, reversible encoding of enums/points/calibrations, lost parameters reported), `structure_from_json()` rebuilds structures; all golden-test structures round-trip to identical programs, golden files unchanged. — commits: `1f379ae`

- [x] T60: Experiment plots: corners, QR code and structure plots — 2026-09-30 — `plot_experiment()` draws corners (double corner highlighted, positions labelled), QR code and the UUID and returns the figure; `build_programs(plot_structures=True)` replaces the hard-coded switch. — commits: `f729324`

- [x] T38: Visualization: laser power and axis formatting — 2026-09-30 — Movements carry the attenuator value read from `$AO[0].A=`, laser-on lines are coloured by power (mW with a calibration) with a colour bar, and mm axes have no offset or scientific notation. — commits: `f688a61`

- [x] T39: Manual DHM helper: implement reset — 2026-09-30 — `DHMBackend.reset()` closes the client, restores the start state (motor position, flags, counter) and reconnects; tested on the dummy DHM. — commits: `b875fe0`

- [x] T43: Make the drop direction consistent everywhere — 2026-09-30 — `Orientation` merged into `DropDirection`: the scanner keeps the lowest focus range for DOWN and the highest for UP (maintainer's description), `Experiment` passes it via `sys_args['layer']['dropDirection']`, QR pixel lines follow it; z coordinates never depend on it (decision), only the order; docstring lists all places. — commits: `97e2345`

- [x] T44: Restructure how plane fitting is run — 2026-09-30 — `PlaneFitMode` (GRID/CORNERS/new BORDER, old integers accepted), `plane_fitting.sample_points/measure_plane` for plane fits outside `Experiment`, center validated against the resin edges, tilt warning with `tilt_warning_um`; the +1 of mode 0 is correct. — commits: `c619b7e`

- [x] T45: Take camera images only on request — 2026-09-30 — `Experiment(camera_capture=False)` (maintainer decision: Experiment argument); `measure()` skips the camera and returns None without it; stored, shown in the summary and used on restart; the 57 existing script calls pass True. — commits: `0315df1`, `314a30b`

- [x] T58: Define the capture position of `measure()` — 2026-09-30 — Before every capture the galvo is set to A = B = 0, Z is not moved (maintainer decision); the commanded position (X, Y, Z=None, A=0, B=0) is stored; golden command logs re-recorded (one added galvo command per capture). — commits: `fc9c425`

- [x] T53: Voxel database (SQLite) — 2026-09-30 — Design approved; `nanofactorysystem.voxel.VoxelDatabase` (tables material/voxel_measurement, PRAGMA user_version with migrations, CSV import/export, `voxel_size()` with exact hit, 2-D (ln P, ln v) interpolation inside the hull, dose fallback, no extrapolation); path `system.voxelDatabase`, seed CSV versioned. — commits: `b45a7d2`, `2de4367`, `9c52f15`

- [x] T51: New template for experiment scripts — 2026-09-30 — `ExperimentSpec`/`StructureSpec` (structure, slicer height data, or a factory of the running experiment; empty cells), `ProgramSource` (DRAWING/SLICER, stored) and `run_experiment()` with `mains/Experiments/experiment_template.py`; the 11 scripts named by the maintainer are ported (dry-run tested), all others moved to `mains/Experiments/historical/`. — commits: `acb2fe2`, `6462705`, `854bc8c`, `6d9afc1`, `905d1c2`

- [x] T52: Substrate-specific `main.py` — 2026-09-30 — `nanofactorysystem/substrate_plan.py` (`SubstrateSpec`, `SubstrateExperiment`, `run_substrate`): overlap, existing-experiment, resin-drop, objective and name checks before printing, sequential runs into the substrate index with optional confirmation; template `mains/substrate_main.py`; dummy dry run with two experiments on one substrate. — commits: `b46bed8`, `1796164`, `ff6d3a0`

- [x] T54: Voxel-aware slicing and hatching — 2026-09-30 — Voxel models (no data, fixed, database) behind the slicer protocol `VoxelModel`; contour offset, first/last slice at half the voxel height, spacing per `spacing_mode` (maintainer decision: `voxel_overlap` default, `static_hatching` with gap warnings); strategies get a `VoxelContext`; values in job metadata, structure JSON and summary; `ExperimentSpec(voxel_material=)`; no-data path and golden files unchanged. — commits: `e5a2173`, `e7ec542`

- [x] T31: Laser power per structure, layer and line — 2026-10-01 — Power per structure shown in a dummy test; `add_structure(layer_power=)`/`StructureSpec.layer_power` let every layer program set its own power (stored as `layer_powers_mw`, summary column); `Model3D_Slicer` prints toolpath elements with a power override (or `power_map(z_um, role)`) in their own IFOV blocks, unchanged without overrides. — commits: `a01c64b`, `1e6cf41`

- [x] T37: Replace the hotfixes in tools and devices — 2026-10-01 — Azimuth fix, motor-scan loop with limits, capture-time analysis and stored height profiles; the focus threshold and N088 went to T61 (maintainer decision: close T37). — commits: `8444d70`, `b396a38`, `040e831`, `72114eb`

- [x] T61: Justify the focus-detection threshold and clarify the layer result object — 2026-10-01 — Closed without code change (maintainer decision): the focus detection is reworked later with example data (F10); N088 is dropped and kept in `todo_notes.md` for the maintainer.

- [x] T32: Clean up the AeroBasic API and task handling — 2026-10-01 — Closed without code change (maintainer decision): moved to F11, to be done with the A3200 manual.

- [x] T63: Use the real IFOV writing speed for the voxel lookup (found during T54) — 2026-10-01 — The job of `Model3D_Slicer` records the fixed IFOV writing speed (5/10 mm/s), so the voxel lookup and the time estimate use it; the speeds are defined once in `lines.IFOV_WRITING_SPEED_MM_S`. — commits: `b2b07cd`

- [x] T62: Check experiment areas against the shape of the resin drop (found during T52) — 2026-10-01 — Experiment areas (substrate plan) and the experiment center (`Experiment(resin_edges=)`) are checked against the ellipse through the four edge points (`resin_drop.py`); no check for dip-in; the edges are stored with the experiment. — commits: `b9d8cfd`

- [x] T35: Clarify line and rectangle details (from T19) — 2026-10-01 — IFOV writing speed stays fixed and is documented; non-IFOV velocities (µm/s → mm/s in programs) are pinned by a test; the N069 hotfix is replaced: flat rectangles print nothing, steps use `step_slice_size` (no division by zero); `IFOV_Lines` no longer raises `Warning`. N068 moved to F12. — commits: `3edbae7`

- [x] T64: Port the experiment scripts imported by `main.py` and `main_IFOV.py` (found during T51) — 2026-10-01 — `Kailas/power_z_pitch_lines.py` and `Big_substrate_20x/grating_ifov_test.py` are back in `mains/Experiments/`, ported to `experiment_spec()` and tested; `main.py`/`main_IFOV.py` import them (main_IFOV.py failed on import before). — commits: `b90d42f`

- [x] T28: Overview images and time estimate (from T19) — 2026-10-01 — Expected printing time (path length / speed per layer program + 5 s per layer) logged after building, stored and shown next to the actual time; `overview_capture=True` stores a stitched camera mosaic (with corners, or only the grid with `skip_corner`) before and after printing, optionally with the single images. — commits: `6dca352`, `909d2e7`

- [x] T36: Z-line: offset, global variables and focal-point script (from T19) — 2026-10-01 — The focal-point script is finished (`mains/Experiments/focal_points/`; z-lines with FocusDetect containers, only via `Focus.run`); N014–N020 resolved; N072 was already done; N071 would change the plane fitting and moved to F14 (maintainer decision). — commits: `9498bee`

- [x] T65: Contour mask fails in OpenCV with NumPy 2 on Windows (found during the first lab-PC run) — 2026-10-18 — `contour_mask` builds its mask as uint8 instead of `int` (int64 under NumPy 2), so the focus detection of the plane fit runs again; unit test added. — commits: `31b77fd`

- [x] T66: Unpacker and live access for experiment files (maintainer request) — 2026-10-18 — New folder `analysis/` with `unpack_experiment()` (whole `experiment.h5` as PNG/CSV/TXT/JSON/ZDC plus summary and tables, optional zip, snapshot while printing) and `ExperimentFile` (reading at any time without HDF5 lock, results stored under `/analysis` with the lock file, refused while an experiment process holds it); the store can read without file locking. — commits: `6b26274`, `4687c0a`

- [x] T68: Lab check script for the new features (maintainer request) — 2026-10-18 — `mains/lab_checks/new_features_check.py` runs two small experiments on one substrate that exercise the features of phases 1–4 and B and prints a checklist; dry-run test in `test/integration/test_lab_check.py`; running it on the lab PC is T69. Entry added during the reorganisation of 2026-11-15 (the commit had not been logged here). — commits: `ed4e769`
