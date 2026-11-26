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
| 6 | Information model | T75, T76, T77 (done), T78, T79, T80, T81, T101, T108 (T103 → F39) | – |
| 7 | DHM service integration | T82, T83, T84, T85, T86, T87, T105, T106 | T84 needs DHMConnect DL-C1, DL-C2; T87 needs DL-H2 and K14 |
| 8 | Operating modes and calibration | T88, T89, T90, T91, T92, T104, T107 | T90 needs MIRA MI-53 for the real evaluator; T104 needs MIRA MI-41 for the fit; T107 needs OffAxisHolo K10 for the sweep |
| 9 | Camera live feed | T102, T93, T94, T95 | T102 before T93 (hard prerequisite, `CAMERA_LIVE.md`) |
| 10 | Core ready for a GUI | T96, T97 | – |
| 11 | Standard test prints (PTD-01), **priority** (decision D7 of `TEST_PRINT_PTD01.md`) | T136–T161, T163 (done; T148/T149 open), T162 (in progress, T164), T164 | T148 before T149 |
| B | Backlog (from T19 `todo_notes.md`, lab checks, follow-ups) | T67, T69, T109, T111, T112, T114, T165, T166, T167 | – |

Phases 6, 9 and 10 are independent of each other. Phase 7 can start with T82, T83 and T85 before
`dhmconnect` exists. Phase 8 needs T83 and T85. Phase 11 is independent of phases 7–10 (it builds only on
the done phases 4 and 6), has priority over the other open phases (decision D7, 2026-11-25) and must not
change existing code (maintainer decision 2026-11-25). Target of all phases: Release V1.0 as defined by the
decision session of 2026-11-17/18 (`docs/system/SOFTWARE_PLAN_OVERVIEW.md` v0.4).

### Working rules for Claude Code (in addition to CLAUDE.md)
1. Phase 11 (PTD-01) goes first (decision D7 of 2026-11-25); lab blockers such as T134 stay with the
   maintainer. Otherwise pick the first open todo of the lowest unfinished phase whose dependencies are done. Phases 6, 9 and 10
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
| PTD-01 D9 | Does `SET_POWER` inside a running program wait for the attenuator? (`docs/design/TEST_PRINT_PTD01.md` §12.1) | lab check T148 (lines only, several dwell levels) before the parameter tests | `dwell_after_power_s` value; T149 |

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
| Parameter tests v2 | 2026-11-25 | `docs/design/PARAMETER_TESTS.md` §3–§8: single stage, absolute axes, 0.1–1.0 mW linear, 60 µm fields a/b, label and support power 0.5 mW, anchoring 1 µm, header 3 + 1 bits, Quick PT walls and pads, Full PT-01 values, Voxel PT-01 one power per experiment (gap cells 100 µm apart, 3 × 4), one material start file. |
| PTD-01 D1–D8, D10–D16 | 2026-11-25 | `docs/design/TEST_PRINT_PTD01.md` §12.2: DOWN order kept; reduced corners with QR; `p_ref_factor` 1.5; 1 replicate (later 3); gaps 2 / 4.5 µm; golden program F3; phase 11 with priority; stage-A start values in one JSON per material; F7 bases 6 × 6 µm with pillars 2–10 µm; F2 pedestals 2 × 3 × 3 µm with 2 µm gap; line middle only; polarisation measured before stage B; recalibration rule documented only; anchoring 1.5 µm for volume cells; in-layer order `row_by_row`. |
| Todo review | 2026-11-26 | Review with the maintainer of every todo of this repository outside the DHM / MIRA / real-time scope (phases 7–9 except T102 and T79 not reviewed): decisions recorded in T69, T81, T96, T97, T101, T102, T109, T111, T112, T114, T122, T124, T129, T130, T133, T135, T148, T149, T153, T154, T164; new T165–T167; T126 → F38, T103 → F39; T134 done. |
| X-A, X-B, X-C | 2026-11-18 | `Information_Mehrere_Experimente.txt` and `todo_claude/` moved to the local attic; `docs/ATTIC_INDEX.md`. |

## Open

- [ ] T131: Precompile layer parts to `.ogm` and load the compiled file while printing (follow-up of T129) [phase: B]
  - Priority: medium
  - Size: M
  - Depends on: T129
  - Background (lab 2026-11-24): `A3200ProgramLoad` writes the compiled `.OGM` next to the source (142 bytes per
    line). Loading Motion Composer's `.ogm` of layer 68 (1.25 M lines) took 5.9 s with a 1.87 GB peak; the `.pgm`
    took 129 s with 19.3 GB.
  - Lab session 2 (2026-11-25, `PROGRAM_LOADING.md` §6.2): clean repeat. Our own `.OGM` of 400k lines loads in
    15.1 s with 0.61 GB under a new name (a renamed copy the same), the compile took 38.9 s with 7.51 GB: 2.6×
    faster, 1/13 of the memory (38 µs and 1.55 kB per line). Full layer 68 from `.ogm`: 47.5 s, 1.88 GB (the 5.9 s
    above was a cache effect of Motion Composer). An `.ogm` is added under `<stem>.pgm`; a removal under the
    `.ogm` name returns success and does nothing. A whole-layer `.ogm` cannot be compiled through the C library
    within the budget (24.6 GB for layer 68); whole layers need the .NET `Builder.Build` path (T153).
  - Lab session 3 (2026-11-25, `PROGRAM_LOADING.md` §6.3): the .NET `Builder.Build` also needs 19.9 kB per line, so
    the cache stays per part (parts of the budget size), not per whole layer. Its `.OGM` of 400k lines loads in
    12.0 s (30 µs per line).
  - Maintainer 2026-11-25: keep the `.ogm` cache in view as a likely important future step, after the library loader
    runs robustly (T153 session 3b, first real layer with the laser). Expected gains: a part loads in about 1/3 of
    the compile time with 1/13 of the memory, so a restart (`restart_experiment`), `reprint_layers` and a repeated
    structure skip the compile; compiling in the build step moves the 19.6 kB-per-line peak out of the print.
  - Done when: parts are compiled ahead (build step or one layer ahead, within the T129 memory budget) and loaded
    as `.ogm` during the print; the cache entry is keyed by program hash and controller software version /
    configuration and recompiled when either changes; `.ogm` files of printed layers are deleted (option);
    an `.ogm` is removed under `<stem>.pgm` and the removal is verified with the added-program count; dummy loader
    simulates the cache; lab check of one real layer.

### Phase 5 — Concept

### Phase 6 — Information model

- [ ] T79: Experiment configuration record [phase: 6]
  - Priority: medium
  - Size: S
  - Depends on: T70
  - Done when:
    - objective, camera information and DHM information (service version, parameter set and hash,
      pixel size and its source) are stored once per session and shown in the summary;
    - the full DHM parameter set is stored **once per `config_hash`** in `experiment.h5` (DL-A3 a), so an
      experiment is traceable without the DHM-PC; products reference it by hash and parameter-set id.

- [ ] T101: Find out which controller states persist between programs and experiments (found during T70) [phase: 6]
  - Priority: medium
  - Size: S
  - Depends on: – (lab PC; A3200 manual, F11)
  - Decided 2026-11-26 (maintainer): the lab check runs as a step without laser in lab session 3b (T153).
  - Done when:
    - it is known from the A3200 manual and a check on the lab PC whether `GALVO ROTATION A -0.6`
      (`SetupIFOV`), `GALVO LASEROVERRIDE A AUTO`, `RAMP MODE RATE` / `RAMP RATE 0`, `LOOKAHEAD FAST` and
      `METRIC` (IFOV layer programs) persist after a program task ends, into the next program and into the
      next experiment of the same controller session (`DefaultSetup` resets none of them);
    - the result is recorded in `docs/design/INFORMATION_MODEL.md` §7 and WORKLOG.md, and the reset
      commands that `DefaultSetup` and `SetupIFOV` each need to reach a defined state regardless of what
      ran before are listed for T78 (the setup is sent before every structure, decision M2);
    - if a state leaks into `IFOV_off` experiments today, a `fix:` todo exists.
  - Status 2026-11-26: lab step `states` written (session 3b, commit `1c8d3d1`); open: the lab run and the evaluation
    into `INFORMATION_MODEL.md` §7.
  - Status 2026-11-26: lab step `states` written (session 3b, `1c8d3d1`); open: the lab run.

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

- [ ] T97: Run control and progress events [phase: 10]
  - Priority: low
  - Decided 2026-11-26 (maintainer): later, with the GUI (F15).
  - Size: M
  - Depends on: T74, T96
  - Done when:
    - a runner emits events for structure, layer and capture start and end, and accepts pause,
      resume and abort between layers from another thread;
    - a dummy test pauses and aborts a dry run and restarts it with `restart_experiment()`;
    - `stop_now()` stops the running task (documented as no safety function); a layer stopped mid-program
      is never reprinted automatically, the structure counts as `stopped`, `resume_stopped=True` resumes
      with a warning (P2); a pause longer than `max_pause_s` warns (P3).

### Phase 11 — Standard test prints

Design: `docs/design/TEST_PRINT_PTD01.md` (T136, approved 2026-11-25; decisions in §12, only D9 open). Review:
`docs/reviews/PTD01_PLAN_REVIEW_2026-11-25.md`. Rule for all phase-11 todos: no file outside
`nanofactorysystem/testprint/`, `mains/Experiments/ptd01/`, `analysis/experiment_analysis/` (new modules
only) and the new tests is changed, apart from documentation (`test/README.md`, READMEs, CLAUDE.md);
golden files stay untouched (except a new F3 golden file if D6 is accepted). Improvements of existing code
found on the way are future todos (F18–F30, F36), not part of these todos.

- [ ] T149: Lab print of the parameter tests version 2: Quick PT, Full PT-01, Voxel PT-01 (maintainer) [phase: 11]
  - Priority: high
  - Size: M
  - Depends on: T148, T162
  - Rewritten 2026-11-26 (maintainer): formerly the two-stage PTD-01 print (stages A/B), superseded by version 2
    (`docs/design/PARAMETER_TESTS.md`).
  - Done when:
    - Quick PT printed and evaluated (`mains/parametertest/quick_pt.py`), the material start file updated;
    - Full PT-01 (F1–F7) and Voxel PT-01 printed and evaluated with `analysis/experiment_analysis/ptd.py` and
      `voxel_fit.py`;
    - polarisation direction relative to x/y documented (D13);
    - actual vs. estimated time per experiment recorded in WORKLOG.md;
    - every problem found on the lab PC is a new todo `(found during T149)`.

### Phase B — Backlog (from T19 `todo_notes.md`, lab checks, follow-ups)

- [ ] T69: Run the lab check of the new features on the lab PC (follow-up of T68) [phase: B]
  - Priority: low
  - Size: S
  - Depends on: T68, T167
  - Decided 2026-11-26 (maintainer): second priority; runs on the prepared lab day T167.
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

- [ ] T165: Align the task-2 parameters with task 1 and run the base programs of an experiment on task 2 (maintainer request 2026-11-26) [phase: B]
  - Priority: medium
  - Size: M
  - Depends on: T135 (interim protection), lab PC
  - Background: the base programs of an experiment (interface scan z-line `Plane` → `Layer` → `Focus` →
    `System.zline`, corner markers, QR code) share task 1 with the layer programs. The maintainer wants them on
    task 2. Task 2 has the default parameters of the controller (T132: `MaxLookaheadMoves` 100, `ExecuteNumLines`
    1, `MotionUpdateRate` 1, ramp defaults), so the same program runs 1.8× slower; corners and QR code are galvo /
    IFOV programs and need the tuned values. This reconsiders T132 option (a) for the base programs only; print
    parts stay on task 1.
  - Done when:
    - the controller parameter file is backed up before the change; the task-2 parameters equal those of task 1,
      and the changed parameters are listed in `docs/design/PROGRAM_LOADING.md`;
    - lab: the same program runs on task 1 and task 2 with a time ratio of 1.0 (± 2 %);
    - z-line, corner markers and QR code run on task 2 and never on the task of a print part; dummy tests; golden
      command logs re-recorded with the reason.

- [ ] T167: Prepare and run an intensive lab day: new features and program types / commands (maintainer request 2026-11-26) [phase: B]
  - Priority: low (second priority until the parameter tests and program loading are done)
  - Size: L
  - Depends on: T112, T148
  - Background: the maintainer postponed T69 and wants one well-prepared lab day that tests the new features and
    the different program types and commands.
  - Done when:
    - a work order (`docs/design/…`), a lab guide (`docs/guides/…`) and lab scripts (`mains/lab_checks/…`) cover
      (1) the new features of T69 (overview in focus, camera captures, power per layer, repetition, restart after
      Ctrl+C) and (2) program types and commands: CW / CCW arcs, the effect of the velocity on small fine
      structures (steep edges, small pixels where the laser on/off timing matters) and further commands named by
      the maintainer;
    - the maintainer ran it; every checklist point is recorded in WORKLOG.md as working or as a new todo
      `(found during T167)`; T69 is closed with it.

## In Progress
<!-- Claude Code moves a todo here when starting work. -->

- [ ] T96: Remove blocking user interaction from the run path [phase: 10]
  - Priority: high
  - Decided 2026-11-26 (maintainer): soon, together with T133: the injectable confirmation callback (default a
    Tk pop-up) also asks for the recovery levels R2 and R3.
  - Size: S
  - Depends on: T74
  - Done when:
    - `messagebox_confirm` is an injectable callback (default as today);
    - the `plt.show()` calls in `experiment.py` and `substrate_plan.py` return the figure instead;
      the entry scripts show it.
  - Status 2026-11-26: the confirmation for recovery level R2 is an injectable callback (`Experiment(confirm_recovery=)`, default Tk message box, `09b79d4`); the plots return their figure and never open a window with `show=False` (T120); `run_experiment` / `run_substrate` take `confirm`. Open: `plot_experiment(show=True)` is still the default (changing it changes every old script; decide with T97).

- [ ] T148: Lab check: does `SET_POWER` inside a running program wait for the attenuator? (decision D9) [phase: 11]
  - Priority: high
  - Size: S
  - Depends on: T137 (a field with power steps can be built), lab PC (maintainer)
  - Decided 2026-11-26 (maintainer): lines only, no test blocks. Line pairs alternating 0.25 ↔ 0.75 mW: one
    line switches the power without dwell, the line next to it (2 µm apart) is written the same way with a dwell
    after the switch; several dwell levels (e.g. 0 / 10 / 50 / 200 ms); 10 repetitions. The attenuator type
    (motorised wave plate or AOM / Pockels cell) is unknown; the test is to show its settling time.
    `SET_POWER` writes `$AO[0].A` and the controller does not wait for the attenuator.
  - Done when:
    - first, the A3200 help is researched for how `$AO`, `DWELL`, `VELOCITY ON` and the lookahead interact, so
      that the dwell is executed and the moves around a power change are not blended (the maintainer has seen
      blended motion before); the findings are in the work order and the generated program follows them;
    - a short lab program (pattern of `mains/lab_checks/`: work order, guide, script) writes the line pairs
      above inside one IFOV program;
    - the width at the line start vs. the line middle (SEM or camera) shows whether the attenuator settles in
      time; the result and, if needed, the value of `dwell_after_power_s` are recorded in WORKLOG.md and in
      design §12 (D9);
    - runs before the lab print of the parameter tests (T149).
  - Status 2026-11-26: research and lab tooling done (`33ee66f`): `docs/design/POWER_SWITCH_CHECK.md`, `docs/guides/POWER_SWITCH_CHECK.md`, `mains/lab_checks/power_switch_check.py`, `testprint/power_switch.py`. Finding: since A3200 6.01 motion commands are buffered and `$AO` may run ahead of them; the pattern shows that too. Open: three questions in the A3200 help on the lab PC, the print and its evaluation (maintainer).

- [ ] T154: ASCII `PROGRAM LOAD` cannot open program files at long paths (found during T153) [phase: B]
  - Priority: low
  - Size: S
  - Depends on: T153 (session 3b confirms the short path)
  - Background: in lab session 3 every execution copy at a 191-character path was refused with "Compiler Error: The
    program file could not be opened", while files at 162-166 characters loaded. `run_program_as_task` copies to the
    home folder when no `program_dir` is set (the print path), so prints are not affected; a long `program_dir` is.
  - Maintainer 2026-11-26: approved as written.
  - Done when: the limit is known (lab: a few lengths between 166 and 191 characters) and `run_program_as_task`
    refuses or relocates execution copies above it with a clear message; a unit test.
  - Status 2026-11-26: execution copies above `MAX_LOAD_PATH_CHARS` (166) go to `~/nfs_exec` or are refused (`bbabb39`); lab step `path-limit` in session 3b (`ece4b9c`). Open: raise the limit to the measured value.

- [ ] T102: Camera image timeout uses the exposure in µs as if it were ms (found during T73) [phase: 9]
  - Priority: high
  - Size: S
  - Depends on: – (verification on the lab PC)
  - Decided 2026-11-26 (maintainer): implement the bounded timeout now; the unit of `ExposureTime` is confirmed
    in lab session 3b (T153).
  - Done when:
    - `CameraDevice.getimage()` waits at most a bounded time derived from the exposure in ms (e.g. twice the
      exposure plus a transfer margin, at least 50 ms) instead of `2000 × ExposureTime[µs]` ms (≈ 11 h at
      20 ms); the unit of `ExposureTime` returned by mvIMPACT is confirmed on the lab PC;
    - a missed frame raises a clear error instead of blocking; a unit test with the dummy driver checks
      the computed timeout; the camera service (T93) relies on it for its stop bound.
  - Status 2026-11-26: bounded timeout implemented (`image_timeout_ms`, `TimeoutError` on a missed frame, tests;
    commit `46994e1`). Open: the unit check on the lab PC (session 3b step `camera`, T153).
  - Status 2026-11-26 (later): unchanged; the unit check is step 7 (`camera`) of session 3b.

- [ ] T132: Task 2 runs the same program 1.8× slower than task 1 (found during T129) [phase: B]
  - Priority: high
  - Size: S
  - Depends on: –
  - Background: in the cycle of 2026-11-24 the same synthetic 200k-line galvo program ran 279.6 s on task 1 and
    500.5 s on task 2 (1.4 vs. 2.5 ms per line), twice each. Every automated print so far ran on task 2
    (`run_program_as_task` default). The synthetic program sets no `SECONDS`/`METRIC`/`LOOKAHEAD`/ramp, so task
    defaults may explain it.
  - Lab session 2 (2026-11-25, `PROGRAM_LOADING.md` §6.2): cause found. Ratio 1.79 with the bare and with the real
    layer header (1.399 vs. 2.502 ms per line). In every parameter file of the controller task 1 is tuned and task 2
    has the defaults: `MaxLookaheadMoves` 10000 / 100, `ExecuteNumLines` 100 / 1, `MotionUpdateRate` 48 / 1,
    `DefaultCoordinatedSpeed` 12.5 / 50, `DefaultCoordinatedRampRate` 2000 / 500, `DefaultCoordinatedRampTime`
    0.1 / 0.5. Correction: the ASCII print path of `Experiment` always used task 1, so earlier prints ran on the
    tuned task; only the library loader alternates onto task 2.
  - Decided 2026-11-25 (maintainer): option (b). Print on task 1 only; compile the next part ahead without a task
    (`A3200ProgramAdd`, lab: same time and memory as a load) and associate it to task 1 when the current part has
    completed (< 0.05 s). No change of the controller configuration; one velocity profile per structure; task 2
    stays free (z-line, T135). Rejected: (a) aligning the task-2 parameters.
  - Done when: the library loader prints on task 1 only with add-ahead (`ProgramRunner` mode, library wrapper for
    `A3200ProgramAdd`/`A3200ProgramAssociate`, dummy loader and tests: order, gap, failure in the middle) and never
    puts a print part on task 2; lab check of the gap with 4 synthetic parts (T153 runner step).
  - Status 2026-11-25: implemented. `ProgramRunner(task=1)` compiles the next part in a worker with `A3200ProgramAdd`
    while the current part runs, then stops the task, removes the finished part, associates the next one
    (`A3200ProgramAssociate`) and starts it; execution names use the T152 scheme with a session token; `LibraryLoader`
    has `add_async`/`associate` (replacing `load_async`); the dummy loader simulates both; tests in
    `test/devices/test_program_loader.py` and `test/test_experiment.py`. Open: the lab check of the gap (T153).

- [ ] T129: Load layer programs through the A3200 C library instead of `PROGRAM LOAD` over ASCII (found during T125) [phase: B]
  - Priority: high
  - Size: M
  - Depends on: lab result of `mains/lab_checks/library_load_check.py`
  - Background: on 2026-11-21 `PROGRAM 1 LOAD` over the ASCII interface answered "An out of memory error occurred."
    (FAULT, 1.6 s and 19 s) for layer 70 after layer 71 (81 751 lines) had loaded in 10 s; every later LOAD was
    refused with `!` within 0.4 s until the A3200 software was restarted. On 2026-11-23 the maintainer loaded the
    full layers 69 and 68 (millions of lines) by hand in Motion Composer 6.04.005 on tasks 1 and 2 while layer 69
    ran ("Program Running", not queue mode). Hypothesis: the ASCII interface compiles inside the process serving
    port 8000 (possibly 32 bit), Motion Composer through the library in its own process.
  - Lab result 2026-11-24 (`mains/lab_checks/library_load_check_2026112*`): confirmed. Port 8000 is served by
    `A3200AsciiInterface.exe`, a 32-bit process. `A3200ProgramLoad` from 64-bit Python (`A3200C64.dll`) loaded the
    full layer 68 (1 253 745 lines, 45.8 MB) in 129 s to `program_ready`; the Python process peaked at 19.3 GB
    (about 15 kB per line) and still held 12.4 GB after the load. `PROGRAM LOAD` of Motion Composer's `.ogm` over
    ASCII is refused ("Build Result: -536325553" = 0xE008524F, it is compiled as source); after that every LOAD over
    ASCII (also the `.pgm`, tasks 1 and 2) was refused within 0.1 s with the same text until a restart. Task 3 is
    `inactive` (not enabled on this controller); tasks 1 and 2 are usable.
  - Work order: `docs/design/PROGRAM_LOADING.md` (requirements R1-R10: memory budget 20-25 GB for the whole PC,
    compilation bounded by a memory-based split, tasks 1/2 alternating with prefetch); lab tests:
    `docs/guides/PROGRAM_LOADING_LAB_TESTS.md` with `mains/lab_checks/program_loading_lab.py`.
  - Lab session 1 of the work order (2026-11-24, details in section 6 of `docs/design/PROGRAM_LOADING.md`):
    compiling costs 19.6 kB and 96 µs per line (linear up to 400k lines); the memory is freed at `A3200Disconnect`;
    a program stays loaded after the worker process exits and can be started and removed by another process;
    removal works for `.pgm` loads (count verified); the cycle of 4 × 200k lines alternating on tasks 1/2 with
    prefetch had gaps of 0.15 s and every part ended at its last line. Default part size for the library path:
    400 000 lines (from the budget, not fixed). Follow-ups T131 (precompiled `.ogm`), T132 (task 2 1.8× slower),
    T133 (health check and recovery), T134 (lab session 2).
  - Design consequences: load through the library in a short-lived 64-bit worker process (memory returned after
    each load); alternate tasks 1 and 2 so the next layer compiles while the current one prints (about 2 min per
    1.25 M-line layer); check the PC's RAM against the 19 GB peak; keep ASCII for START/status.
  - Done when: the lab check confirms or refutes the hypothesis; if confirmed, `run_program_as_task` loads through
    `A3200C64.dll` (ctypes, signatures from the installed headers) behind a loader seam with the ASCII path as
    fallback, the next layer is loaded on a second task while the current one prints, the T125 split is only used
    for the ASCII path, the dummy backend simulates the library loader, and the T126 queue mode is reconsidered.
  - Status 2026-11-24: P1 (T127/T128) done; P2-P4 implemented opt-in: `Experiment(program_loader="library")`
    (`devices/aerotech/library.py`, `loader.py`: worker process, `MemoryBudget`, `ProgramRunner` on tasks 1/2 with
    prefetch; dummy loader), commit `0a4e261`. Open: lab check of the integrated path (`program_loading_lab.py
    runner`, then one real layer with laser off, P5), then switch the default (R9, maintainer decision).
  - Status 2026-11-25 (lab session 2): the integrated `ProgramRunner` ran 4 × 200k galvo lines on tasks 1/2 to
    their last lines with gaps of 0.31-0.33 s (P5, first half passed). Task 2 is untuned (T132): no real print with
    alternation before the T132 decision; with option (b) the runner gets a single-task add-ahead mode. Next: T152,
    T132 decision, one real layer with laser off.
  - Status 2026-11-25 (later): T152 done (`5b856bb`); T132 decided as option (b): task 1 only with add-ahead. Next:
    the add-ahead mode (T132), then P5 with one real layer, laser off, on task 1.
  - Status 2026-11-25 (T132): the library loader runs every part on task 1 with add-ahead; next is lab session 3
    (T153) with the runner check and P5.
  - Decided 2026-11-26 (maintainer): the library loader may become the default later, but the current ASCII path
    stays and remains selectable. No default switch and no change of the add-ahead behaviour before the lab test
    (T153 session 3b) has shown that add-ahead works.

## Blocked
<!-- Format: todo as above, plus the line "Blocked by: <reason or T<n>>". -->
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
  - Blocked by: T101 (the reset commands of `DefaultSetup` / `SetupIFOV` come from the lab run of the `states` step in session 3b, 2026-11-26).



- [ ] T153: Lab session 3 for program loading: .NET compile path, added-program names, R1 and R3 (follow-up of
  T134) [phase: B]
  - Priority: medium
  - Size: S
  - Depends on: T132 decision (the runner check uses the chosen task mode)
  - Background: the gaps of lab session 2 (`PROGRAM_LOADING.md` §6.2): the .NET `Aerotech.AeroBasic.Builder.Build`
    was found but not run; INtime memory not readable (the prompt took one line of a pasted block); R3 refused
    without administrator rights; 2 programs stayed added all day (names unknown); R1 not tested on a blocked name.
  - Scope extended 2026-11-25 (maintainer, option 2: one lab date for everything open): also T152 on the real
    controller (fresh names; a refused load, then the next program loads) and the runner in the add-ahead mode of
    T132 (gap per part), then P5 of T129 (one real layer, laser off).
  - Done when: `program_loading_lab.py` has the steps and the lab run answers: T152 and the add-ahead gap as above;
    compile of layer 68 with `Builder.Build` in a 64-bit process (time, peak memory, does the library load the result); the names and
    task association of the added programs (`A3200ProgramGetAddedPrograms`) before and after `REMOVEPROGRAM`;
    whether R1 clears a name blocked by `sticky`; R3 in an administrator PowerShell (time, axis state); the INtime
    prompt reads a pasted multi-line block or a file; the `api` filter also lists `Build` methods; the runner
    check in the add-ahead mode of T132; results entered in `docs/design/PROGRAM_LOADING.md`.
  - Status 2026-11-25: lab tooling done (commits `461f4f2`, `6cc29c1`): steps `ascii-names`, `recover-blocked`,
    `dotnet-build`, `layer-dry` (P5 with a dry copy of layer 68: laser gate off, `$AO` 0, no Z, stage XY around the
    current position), added-program names in `system`, INtime prompt for pasted blocks, Build methods in the
    `api` log; guide section "Session 3" in `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`.
  - Status 2026-11-25 (lab session 3, `PROGRAM_LOADING.md` §6.3): run in three attempts, all motion steps with
    disabled, unhomed axes, so `runner`, `layer-dry` (task error at the first motion line) and `ascii-names` (copies
    at a 191-character path not opened) answered nothing. Answered: .NET `Builder.Build` 19.9 kB per line (no
    whole-layer compile), `ImmediateProgram0` is the program that stays added, R1 does not clear a blocked name, R3
    works as administrator, no library compile or load failed. Session 3b prepared (commits `2b0fdec`, `ad6f1f8`,
    `47f3147`): motion steps require homed axes, the runner names the task error code, `ascii-names` uses
    `~/nfs_lab`; guide section "Session 3b" (about 35 minutes).
  - Scope extended 2026-11-26 (todo review): session 3b also runs the controller-state check of T101 (no laser)
    and confirms the unit of the camera `ExposureTime` (T102).
  - Blocked by: lab session 3b on the lab PC (maintainer).
  - Status 2026-11-26: steps `states` (T101) and `camera` (T102) added, guide section "Session 3b" updated (about
    45 minutes; commit `1c8d3d1`).

## Done
<!-- Claude Code adds: - [x] T<n>: title — YYYY-MM-DD — 1–2 sentences on what changed — commits: `<sha>`, … -->
- [x] T133: Controller health check and recovery levels — 2026-11-26 — Health check and R0 (`1d969e6`); R1 automatic after a detected error with `max_r1_per_structure` (2), R2 only between experiments after consent in a message box (`confirm_recovery`), R3 and all levels in `mains/controller_health.py` (maintainer decision 2026-11-26). — commits: `1d969e6`, `09b79d4`
- [x] T130: Program optimiser — 2026-11-26 — Optimiser (`b063502`) plus the opt-in build option `Experiment(optimize_programs=)` (maintainer decision; golden files unchanged). — commits: `b063502`, `1adf8b4`
- [x] T81: Extension point for dynamic slicing and hatching — 2026-11-26 — `print_strategies.py` registry (`static` only), `StructureSpec(strategy=, strategy_params=)` stored with the spec, unknown names refused; new strategies are registered without changing the core (maintainer requirement). — commits: `52ca47c`
- [x] T80: Layout of an experiment as data — 2026-11-26 — `nanofactorysystem/layout.py` (`spec_layout`, `experiment_layout`, `draw_layout`, `layout_figure` without pyplot); `plot_experiment()` and `plot_substrate(layouts=)` use it. — commits: `ce4935d`
- [x] T135: The z-line program and the layer programs share task 1 — 2026-11-26 — Interim protection (maintainer decision): the controller counts loads per task and `zline()` loads its program again after another program ran on its task; moving to task 2 is T165. — commits: `4ab6354`
- [x] T124: Whole-structure program duplicated uncompressed — 2026-11-26 — Stored gzip-compressed by default, `Experiment(structure_program="reference")` stores only hash and file; old files read; schema 1.2. — commits: `8f6a872`
- [x] T109: Tuple `raise` in the v6 client (finding B19) — 2026-11-26 — `AttributeError` instead of `raise (AttributeError, …)`; golden command logs unchanged. — commits: `3a2fde8`
- [x] T111: Clear error for an incomplete user section — 2026-11-26 — `Parameter.__init__` raises a `KeyError` naming the user and the missing keys of `USER_KEYS`. — commits: `dcfd497`
- [x] T114: `Rectangle3D_IFOV` objective and stateless alternating hatch — 2026-11-26 — `objective=` (default 63x, golden files unchanged) and `layer_direction(i)`; two iterations give identical programs. — commits: `81a98c7`
- [x] T166: `mains/main_3D_model.py` on the experiment environment — 2026-11-26 — One IFOV `ExperimentSpec` with `ProgramSource.SLICER` (model file as input with SHA-256, settings from `main.py`, `--dry-run`), test with a box STL. — commits: `2b8d4e7`
- [x] T112: Realistic accelerations in the stage examples — 2026-11-26 — Template and new-features lab check use named factories with the controller X acceleration (maintainer decision); the lab run is part of T69 on the lab day T167. — commits: `015f763`
- [x] T122: Entry-script tests independent of the lab settings — 2026-11-26 — `test_main_entry.py` sets its own resin drop, `test_main_png.py` sets `CENTER = None`; the full suite passes again. — commits: `bfef02d`
- [x] T162: Scripts and chain of the three parameter tests — 2026-11-26 — `mains/parametertest/` (Quick PT, Full PT-01, Voxel PT-01, chain, margin 90 µm, marker clearance check); version 1 removed with T164. — commits: `7d472f1`, `197f0c7`
- [x] T164: Move the two-stage PTD-01 version 1 to the attic — 2026-11-26 — Scripts, `ptd01`, `factories`, `StageAAxes`, their tests and the golden file `ptd01_f3.txt` moved to the local attic and listed in `docs/ATTIC_INDEX.md`; the analysis tests use Full PT-01 F1 of version 2. — commits: `197f0c7`
- [x] T134: Lab session 2 for program loading and controller recovery — 2026-11-26 — Lab session 2 evaluated in `docs/design/PROGRAM_LOADING.md` §6.2 (`sticky`, `.ogm` load and name, Add + Associate, untuned task 2, R1/R2, runner check); the gaps (.NET compile, INtime memory, R3) went to T153. Closed in the todo review 2026-11-26. — commits: `d4093ae`
- [x] T158: Absolute axes and a/b sub-fields in the test-print library — 2026-11-26 — `testprint/inputs.py` (`ParameterTestInputs`, the material start file), sub-field bit in the header and `half` column in the cell table; builders need no calibration or fit model to print. — commits: `63e32d2`
- [x] T159: Quick PT: walls and pads — 2026-11-26 — Builders `quick_pt.walls` (two groups of three 8 µm walls 1.5 µm apart, z −1 … +1 µm) and `quick_pt.pads` (5 × 5 µm, hatch 0.1/0.2/0.4/0.6 µm) as sub-fields a/b; script `mains/parametertest/quick_pt.py`, dry run. — commits: `89b7232`, `7d472f1`
- [x] T160: Full PT-01: fields F1–F7 on absolute axes — 2026-11-26 — Builders `full_pt01.f1` … `f7` with the decided absolute values in 60 µm sub-fields a/b, all valid; layer programs about 25 min for F1–F7; script `mains/parametertest/full_pt01.py`. The F3 golden program of version 1 stays (version-1 builder unchanged); a golden file for version 2 was not requested. — commits: `89b7232`, `7d472f1`
- [x] T161: Voxel PT-01: gap test for the voxel height — 2026-11-26 — Builder `voxel_pt01.gap` (20 × 20 µm base to 2 µm at 0.5 mW, gap 0 … 2.0 µm, lid of four 0.25 µm layers at the tested power, gap 0 = double exposure); one experiment per power, cells 100 µm apart in a 3 × 4 grid; script `mains/parametertest/voxel_pt01.py`. — commits: `89b7232`, `7d472f1`
- [x] T163: Evaluation of the parameter tests on absolute axes — 2026-11-26 — `ptd.cell_table` for all test prints, `add_relative_columns` (P/P_th, h/w, s/w, Δz/l after the measurement), `voxel_lengths_from_gaps` (l from the gap test), `voxel_fit.points_from_parameter_tests`. — commits: `62c252b`
- [x] T157: Design version 2 of the parameter tests: Quick PT, Full PT-01, Voxel PT-01 (maintainer review 2026-11-25) — 2026-11-25 — `docs/design/PARAMETER_TESTS.md` approved: single-stage tests on absolute axes, power 0.1–1.0 mW linear, 60 µm fields with sub-fields a/b, Voxel PT-01 with one power per experiment and gap cells 100 µm apart in a 3 × 4 grid; T158–T163 may start. — commits: `e992b6e`, `cf2a3ab`, this docs commit
- [x] T155: Decision: layer count of the PTD-01 volume fields F4, F5, F7 (found during T142) — 2026-11-25 — Obsolete: version 2 of the parameter tests (T157) uses absolute slice distances, so the rows of a field share their layers. — commits: this docs(todo) commit
- [x] T156: Decision: scales of the `threshold_ln` fit (found during T151) — 2026-11-25 — Decided by the maintainer: n_eff = 1 as placeholder in the parameter tests; n_eff is determined in a later dose-matrix test with several velocities (F31). — commits: this docs(todo) commit
- [x] T137: `ParameterFieldStructure`: toolpath IR → IFOV programs without changing existing code — 2026-11-25 — `nanofactorysystem/testprint/structure.py`: one IFOV layer per z level, one block per run of equal power and leaf kind, element order kept, `dwell_after_power_s`, built from a registered field builder (JSON round trip); no existing file changed. — commits: `a191b60`
- [x] T138: Cell primitives for test fields with aligned z grid and substrate anchoring — 2026-11-25 — `cells.py`: line primitives, woodpile, analytic height maps and `sliced` on the aligned grid `k·Δz` with anchoring by repeating the first slice (D15); `dot` is an in-plane short line (IFOV writes in one plane); slicing cache for identical maps. — commits: `7c2622a`, `2d66f3e`
- [x] T150: Voxel fit models w(P), l(P) — 2026-11-25 — `voxel_fit.py`: `VoxelFitModel` with registered kinds `threshold_ln`, `power_law`, `tabulated`, no extrapolation, slicer `VoxelModel` protocol (works in `Model3D_Slicer`). — commits: `8a50a07`
- [x] T140: `ProcessCalibration` and `StageAAxes` with their JSON files — 2026-11-25 — `calibration.py`: conversions with the voxel size at the cell power, schemas `nanofactory.process_calibration/1` and `nanofactory.ptd_stage_a/1`, `MissingPropertyError` / `SpecSerialisationError`, example sources refused for real prints. — commits: `a36a19b`
- [x] T139: `ParameterField`: layout, header, merge by z, ordering, validation, cell table — 2026-11-25 — `field.py` and `ordering.py`: header (L mark, 3-bit id, REF pad), merge by z, named in-layer ordering (`row_by_row`, D16), validation of every problem, cell table / CSV, plot. — commits: `da90ec9`
- [x] T141: PTD-01 field builders F0–F2 — 2026-11-25 — `ptd01.py` F0 (80 cells, 8 layers, 81 blocks), F1, F2 (pedestals 2 × 3 × 3 µm, 2 µm gap, bridge inside the pedestal top). — commits: `c662a1b`, `61eaa91`
- [x] T142: PTD-01 field builders F3–F5 — 2026-11-25 — F3 (s = s_rel·w(P)), F4 (3 layers, ramp, `linear_x`), F5 (wedges and caps); fields needing w/l at the cell power start at p_rel 1.25; golden program `test/golden/ptd01_f3.txt` (D6). F5 has 229 layers with the example calibration (T155). — commits: `c662a1b`, `7b2d8fe`
- [x] T143: PTD-01 field builders F6–F7 — 2026-11-25 — F6 (star, grid, woodpile) and F7 (pillars 2–10 µm on 6 × 6 × 1.4 µm bases, D10); F7 has 127 layers with the example calibration (T155). — commits: `c662a1b`
- [x] T144: Named factories `ptd01.f0` … `ptd01.f7` — 2026-11-25 — `factories.py`: JSON arguments only, power check only with a known attenuator range, objective from the context; spec round trip gives identical programs. — commits: `7334c06`
- [x] T145: One experiment script per field in `mains/Experiments/ptd01/` — 2026-11-25 — `common.py`, `f0_interface.py` … `f7_pillars.py`, stage-A start values and example calibration files, README; dry run of every field on the dummy backend. — commits: `7c97bce`
- [x] T146: Chain `chain_ptd01.py` with stages A/B — 2026-11-25 — Stages A / B / all, `--only`, `--replicates`, `--layout`, `--dry-run`; stage B refuses missing, mismatching or example calibrations; calibration copied into stage-B folders; time summary. — commits: `0c8ae6f`
- [x] T147: Cell table from the experiment file and measurement import — 2026-11-25 — `analysis/experiment_analysis/ptd.py`: cell table from `/spec` (incl. REPEAT copies, stage positions), CSV template, voxel import of F0–F2, result via `ExperimentFile` (`/analysis/experiment/ptd01_cell_table`); fixed cell parameters that clashed with measurement columns. — commits: `7b2d8fe`, `3e6b81a`
- [x] T151: Fit procedure for the voxel model from PTD measurements — 2026-11-25 — `analysis/experiment_analysis/voxel_fit.py`: weighted least squares of all kinds, standard errors, AIC, plot, calibration file, storage via `ExperimentFile`; n_eff only identifiable with fixed scales (T156). — commits: `dc42135`
- [x] T136: Design of the standard parameter test print PTD-01 (maintainer request 2026-11-25) — 2026-11-25 — `docs/design/TEST_PRINT_PTD01.md` approved with the decisions D1–D8, D10–D16 (D9 by the lab check T148); phase 11 todos T137–T151 scheduled with priority, improvement ideas F18–F37 in `future_todo.md`. — commits: `5881afa`, `0d4bb72`, this decision commit
- [x] T152: The ASCII path loads every layer program under one fixed name, so one refused compile blocks every later layer (found during T134) — 2026-11-25 — `run_program_as_task` loads every program under a fresh name `nfs_<session>_<counter>_<stem>.pgm`, removes it under that name and deletes the copy; R0 in `Experiment` removes the names still listed; the dummy controller blocks a name after a failed LOAD like the real one, and a test shows that the following layers still print. Golden command logs re-recorded (name lines only). — commits: `5b856bb`
- [x] T127: `REMOVEPROGRAM` names the layer file instead of the loaded program (found during T125) — 2026-11-24 — Programs are removed under the loaded name `python_aerobasic_program.pgm` (`Task.finish()`/`abort()`, failures logged); the dummy controller records loaded programs and unknown removals; golden command logs updated deliberately. — commits: `79a789d`
- [x] T128: Load failures: log `~LASTERROR` for `!` replies and stop instead of skipping the layer (found during T125) — 2026-11-24 — Refusals carry the `~LASTERROR` text, `PROGRAM LOAD` has a response timeout (`controller.loadTimeout`, connection reopened), task errors are decoded, an early "complete" is a failure; `Experiment(stop_on_failure=True)` (default) stops at the first failed layer with `PrintStoppedError` and `restart_experiment()` prints it again. — commits: `79a789d`, `3f773a3`
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
