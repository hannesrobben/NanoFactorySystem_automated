# Design: DHM service integration and measurement recipes

Status: approved 2026-11-18 (decision session 2026-11-17/18, with the additions of §10.1). Implementation
todos: T82–T87, T105, T106. The decisions of this document were called D1–D4 in the draft; they are SI1–SI4
since 2026-11-18 to avoid a clash with the DHMConnect decisions D1–D13.

Context: `docs/system/SOFTWARE_PLAN_OVERVIEW.md` (data flow §2, contracts §4, G2 decided: contracts as
JSON Schema plus examples in `dhmconnect/schemas/`), the OffAxisHolo handover of 2026-11-16
(`docs/system/handover/from_offaxisholo_2026-11-16.md`), `EXPERIMENT_STORAGE.md` (amendment proposed in
its §15) and `INFORMATION_MODEL.md` (the DHM recipe is a structure setting with experiment default, §4).
DHMConnect's protocol design (DL-A2) and contract v0 (DL-A3) did not exist in this working copy when this
was written; names of contract fields follow the system plan and the OffAxisHolo draft 0.3 and are
adapted when DL-A3 is published (vendored examples, rule 9 of the system plan).

## 1. Goals and non-goals

Goals:
- `Experiment` talks to the DHM only through one role protocol, `DhmMeasurement`, with three adapters:
  legacy (today's `Dhm` / `DhmClient`, protocol v6), service (`dhmconnect.client`) and fake (dummy backend).
- A measurement is described by a **recipe** (what to acquire and compute) and a **context** (where, when,
  for which structure and layer); both travel to the DHM-PC.
- The DHM-PC delivers results asynchronously; this process stores them (single writer, T42) and
  acknowledges them; after a crash or restart unacknowledged results are fetched again (`sync`).
- The legacy mode stays the default and produces identical command logs and stored data.

Non-goals: reconstruction, frame selection, registration, fusion, stitching (OffAxisHolo, MIRA); the
service itself and its protocol (DHMConnect); capture planning for speckle sets and stitching rasters
(T85, only the fields are reserved here); the evaluation after a layer (T72).

## 2. As-is (legacy path, 2026-11-16)

- `devices/dhm.Dhm` wraps `dhm/dhmclient.DhmClient` (protocol v6, binary, lockstep, one client) to
  `DhmServ.exe` on the DHM-PC; the objective is selected by `dhmId`.
- `Experiment.measure()` per capture position: galvo to A = B = 0, stage to X/Y (Z unchanged, T58), read
  the actual position, then `Dhm.container(opt=False, image_count=n)` fetches `n` holograms one by one
  over the network (0.1 s pause between them) and the store writes them with a `CaptureRecord`. The call
  blocks until all holograms are on this PC.
- Hologram counts (`experiment.py`, `build_programs`): grid structures (`NORMAL`, `IFOV`, `STITCHING`,
  `REPEAT`) 10 before, 10 after each layer, 20 after the structure (`n + 10`); corners and QR code 1, 1
  and 11; `DUMMY` 0.
- Calibration runs on this PC: exposure optimisation (`dhm/optimage.py`) and the OPL motor scan
  (`dhm/motorscan.py`), every image fetched over the network; the OPL position is stored in `/opl_scan`
  (`write_opl_scan`). There is no background acquisition.
- `ExperimentStore.add_dhm_product()` exists (T47) but nothing calls it.

## 3. Role protocol `DhmMeasurement`

Defined in `backends/protocols.py` (T82). All methods are called from the experiment's main thread except
where noted.

```python
class DhmMeasurement(Protocol):
    mode: str                     # "legacy_raw" | "products" | "products_and_raw"
    def configure(self, session: SessionInfo) -> DhmInfo: ...
    def calibrate(self, kind: str, context: CaptureContext, parameters: dict) -> CalibrationResult: ...
    def acquire_background(self, context: CaptureContext, recipe: DhmRecipe) -> BackgroundInfo: ...
    def measure(self, context: CaptureContext, recipe: DhmRecipe) -> MeasurementHandle: ...
    def result(self, handle: MeasurementHandle, timeout_s: float | None = None) -> MeasurementResult | None: ...
    def acknowledge(self, job_id: str) -> None: ...
    def sync(self, experiment_uuid: str) -> list[MeasurementResult]: ...
    def close(self) -> None: ...
```

| Method | Meaning |
|---|---|
| `configure` | Opens the connection, selects the objective, reports `DhmInfo` (service and software versions, parameter-set name and hash, camera, pixel size and its source — stored once per session, T79). Raises `DhmUnavailableError` if the DHM-PC cannot be reached. |
| `calibrate` | `kind` = `exposure`, `opl_scan` (more later, e.g. `focus`). Returns the result with an id, stored under `/calibration/dhm/<kind>/<id>`. |
| `acquire_background` | Records an object-free background (the stage is at a structure-free place given by the caller) and returns `background_id`, `created_utc`. |
| `measure` | Starts one measurement at the current stage position and returns at once with a `MeasurementHandle`. |
| `result` | Returns the result when it is ready (None on timeout). |
| `acknowledge` | Tells the DHM-PC that the result is stored here; the service may then delete its copy (raw data follow `keep_raw`). |
| `sync` | Returns every result of the experiment that was not acknowledged (restart, §7). |

`MeasurementHandle`: `job_id`, `capture_id`, `frames_acquired` (a `threading.Event` set when the camera
has taken all frames, i.e. when the stage may move again), `done` (event), `state`.

`MeasurementResult` (here) = `ProductSet` (contract): `job_id`, `capture_id`, `context` (echoed),
`products` (`phase_rad`, `intensity`, optional `field`), `pixel_pitch_um`, `z_um`, `wavelength_um`,
`n_medium`, `frames` (one record per frame: `index`, `used`, `reject_reason`, `metrics`, `acquisition`),
`quality` (`n_obj`, `n_effective`, `n_bg`, `piston_std_rad`, selection summary, `background_id`,
`background_created_utc`, `background_age_s`), `timings_s`, `config_hash`, `config`, `versions`,
`warnings`, `created_utc`, `schema_version`, `raw` (the hologram stack, only with `keep_raw` transfer) or
`raw_ref` (`host`, `path`, `sha256`, `n_frames`), `error` (on failure).

## 4. Adapters

| Adapter | Where | Behaviour |
|---|---|---|
| `LegacyDhmAdapter` (T82) | `devices/dhm_adapters.py` | Wraps today's `Dhm`. `measure()` acquires the holograms synchronously exactly as `Dhm.container(opt=False, image_count=n)` does today and returns a handle that is already `done`; its result has `raw` and no products. `calibrate("exposure")` / `calibrate("opl_scan")` call `optImage` / `motorscan`. `acquire_background` is not supported (returns None, warning once). `acknowledge` / `sync` do nothing. Command logs and stored data are identical to today (the store path of `measure()` does not change for `legacy_raw`). |
| `ServiceDhmAdapter` (T84) | same module, imports `dhmconnect` lazily | Uses `dhmconnect.client` (protocol v1). Config section `dhm_service` (`host`, `port`, `connectTimeout`, `requestTimeout`, `resultTimeout`, `maxPending`). A receiver thread of the client fills the handles' events and a result queue; it never touches the experiment file. |
| `FakeDhmService` (T84) | `backends/dummy/` | Uses `dhmconnect.testing` if installed, otherwise an internal fake with the same interface; synthetic products from `SimulatedWorld` (later the process model of T92), deterministic job ids, configurable delays, failures and unreachability for tests. |

Selection: the recipe's `mode` of the experiment decides the adapter — `legacy_raw` → legacy (default),
`products` / `products_and_raw` → service. `off` → no DHM. One experiment uses one adapter; mixing
legacy and service captures in one experiment is not supported (they would need both servers on the
DHM-PC at once).

## 5. The recipe

`DhmRecipe` is the nanofactorysystem side of the contract `MeasurementRecipe`. It is a structure setting
with experiment default (`INFORMATION_MODEL.md` §4) and can differ per phase (`before`, `layer`, `after`).
Unknown keys are kept and passed to the service untouched, so new modes on the DHM-PC need no change here.

| Field | Meaning | Default |
|---|---|---|
| `mode` | `off`, `legacy_raw`, `products`, `products_and_raw` | `legacy_raw` |
| `n_frames` | number of holograms; per phase | as today: grid structures 10 / 10 / 20 (before / layer / after), corners and QR code 1 / 1 / 11 |
| `selection` | `{"policy": "all" \| "threshold" \| "robust" \| "best_k", …}` with `bounds`, `robust_metrics`, `robust_k`, `k`, `rank_by`, `min_frames`, `max_extra` | `{"policy": "all", "min_frames": 1}` until the N-study K13 |
| `metrics` | compute frame metrics | `true` |
| `keep_raw` | `none`, `rejected`, `selected`, `all` | `all` in V1.0 (D7; also training data); the service downgrades to `selected` at 95 % fill level with a clear message |
| `publication` | keep all raw data and transfer them to the Work-PC after the print (background, never during the print) | `false` |
| `raw_transfer` | raw frames sent here (`true`) or only referenced (`raw_ref`) | `false` for `products`, `true` for `products_and_raw` |
| `products` | subset of `phase`, `intensity`, `field` | `["phase", "intensity"]` |
| `exposure` | `{"policy": "fixed" \| "calibrated" \| "auto", "time_us": …}` | `calibrated` (value of the last exposure calibration) |
| `background` | `{"policy": "per_structure" \| "per_session" \| "manual", "max_age_s": 3600}` | `per_structure` (SI3, §8); `max_age_s` only warns |
| `z_hint` | `{"source": "parameter_set" \| "structure_top" \| "fixed", "z_um": …}` | `parameter_set` (§6) |
| `group` | `GroupSpec` from the plan generator (T85): ordered position list, per-position frames / shift pattern / exposure, stitching parameters, jitter seed | at least 9 positions per structure (M4); `single_shot` allowed |
| `reference_exclusion` | which printed matter is excluded from the reference region: `all_printed`, `since_background` | `all_printed` (G10) |
| `unwrap` | unwrapping in the group step: `fast2d`, `least_squares`, `none`, `temporal` | `fast2d` (O5) |
| `post` | free dict of post-processing steps on the DHM-PC | `{}` |
| `unavailable` | behaviour when the DHM-PC is lost during the print: `abort`, `continue` (§10, SI1) | `abort` after a failed reconnect (SI1) |

In `legacy_raw` only `n_frames` is used; the other fields are stored but have no effect (a warning lists
them once). The effective recipe of every capture is stored with it (§9), so a later reader knows what was
asked for.

## 6. Capture context

`CaptureContext` (contract) is built by `Experiment` for every capture:

| Field | Source here |
|---|---|
| `experiment_uuid`, `experiment_label`, `substrate_uuid`, `substrate_label`, `session` | experiment file |
| `structure`, `phase`, `layer_id`, `capture_id`, `image_index`, `group_id` | `measure()`; `capture_id` from `reserve_capture()` |
| `commanded_um` (X, Y, Z, A, B), `actual_um` | as stored today (T46, T58) |
| `objective` | key and DHM config id |
| `material` | snapshot of the resin (and medium) from the material registry (`INFORMATION_MODEL.md` §3.1, G7) |
| `z_hint_um` | from `recipe.z_hint`: `parameter_set` → not set (the service uses its parameter set); `structure_top` → height of the structure after layer n above the substrate, from the layer's z range (stage z of the last layer minus the substrate z at the capture position); `fixed` → `z_um` of the recipe. Which plane the result refers to is G4 / O1; the context only carries the hint. |
| `target_ref` | reserved: reference to the `LayerTarget` (T89) and, after K18 (G10 / SA1–SA2), the footprint for the reference mask |
| `schema_version` | contract version |

## 7. Capture sequence, jobs and acknowledgement

Per capture position in service mode:

```
main thread                                   DHM-PC (service)                 receiver thread
-----------                                   ----------------                 ---------------
move galvo A=B=0, stage X/Y; read position
capture_id = store.reserve_capture(record)    
handle = adapter.measure(context, recipe) --> job accepted, frames acquired
wait handle.frames_acquired (timeout)     <-- event frames_acquired ---------> sets event
continue: next capture position / next layer   reconstruction (GPU)
                                               result ready ----------------->  puts result in queue
drain queue (between layers, end of structure, end of experiment):
  store.add_dhm_result(capture_id, result)
  adapter.acknowledge(job_id) ------------->   may delete its copy
```

- **`reserve_capture()`** (T83) creates the capture group with its `CaptureRecord`, `job_state =
  "reserved"`, the effective recipe and the context before anything is sent, so a crash never leaves a
  result without a capture to belong to.
- **Job states** stored on the capture: `reserved` → `sent` (job id known) → `acquired` → `stored` →
  `acknowledged`; or `failed` (with `error`) / `missing` (not delivered by the end of the experiment and
  not found by `sync`).
- **Single writer:** only the main thread writes the file. The receiver thread of the client only fills
  a queue. The main thread drains the queue after every layer, after every structure, and at the end of
  the experiment, where it waits for all outstanding jobs up to `resultTimeout`; jobs that are still open
  then stay `sent`/`acquired` and are fetched by `sync` later.
- **Back pressure:** at most `maxPending` jobs may be open; before a new `measure()` the main thread
  waits for the queue to drop below it. No default number is assumed; it is set after a measurement on
  the DHM-PC (rule 6 of the system plan) — until then `maxPending = 1`, i.e. the print waits for every
  result (safe default, same timing as today plus reconstruction time).
- **Acknowledge after store:** `acknowledge(job_id)` is sent only after the write of the result has
  returned. A crash between the two leads to a second delivery in `sync`, which is detected by the job id
  (idempotent store: the capture is already `stored`, the duplicate is dropped and acknowledged).
- **Restart:** `restart_experiment()` calls `adapter.sync(experiment_uuid)` after `configure()`; results
  for captures in state `sent`/`acquired` are stored and acknowledged; results for unknown capture ids
  are logged and stored under `/dhm_orphans/<job_id>` (nothing is lost); captures still without a result
  stay as they are and are marked `missing` at the end of the session.

## 8. Calibration and background

- **Exposure and OPL scan** run as `calibrate("exposure")` / `calibrate("opl_scan")` at the place where
  `opl_scan()` runs today (grid center, before printing). In service mode the DHM-PC computes them
  locally (no images over the network). Stored per call under `/calibration/dhm/<kind>/<id>` with
  parameters, result and time; the existing `/opl_scan` keeps being written in legacy mode (and in
  service mode with the result of the latest OPL scan, so existing readers keep working).
- **Background** (OffAxisHolo O6 / handover §2): a background never expires; `max_age_s` only adds a
  warning to the result. Policy of the recipe: `per_structure` (**default, SI3**): before each structure **at the
  structure's own position**, before it is printed (current lab practice; drop surface and aberrations
  change with position); for large structures background tiles at the same raster positions as the
  later object tiles (one background group). `per_session`: one background per objective and session, recorded after the OPL scan at a structure-free place (the grid
  center before printing, or a place given by the spec); a new one is required after an optical change
  (objective change, OPL scan repeated, manual request). `manual`: only when the script calls `acquire_background()`. Every
  result names its `background_id`; backgrounds are listed under `/calibration/dhm/background/<id>`
  (metadata only; the background frames stay on the DHM-PC unless `keep_raw` asks otherwise).

## 9. Storage (summary; details in `EXPERIMENT_STORAGE.md` §15)

Per DHM capture: `job_id`, `job_state`, `recipe_json`, `context_json`; raw holograms as today when they
are transferred, otherwise `raw_ref_json` (host, path, SHA-256, frame count); a `frames` table (one row per
frame: index, used, reject reason, metric columns); per product dataset the traceability attributes
(`schema_version`, `config_hash`, `background_id`, `warnings_json`, `quality_json`, `pixel_pitch_um`,
`z_um`, `propagation_index`, `wavelength_um`, `timings_json`, `versions_json`); the `ProductSet` itself as
`header_json` + one dataset per buffer. Group results (the stitched `LayerProduct`, N1) go to
`/dhm_groups/<group_id>/product` in the same layout. Schema 1.3 (minor addition, T83); legacy captures are
unchanged.

## 10. Decisions

The table below is the proposal of the draft (2026-11-16); §10.1 records what was decided.

| ID | Question | Options | Proposal |
|---|---|---|---|
| SI1 | Behaviour when the DHM-PC is unreachable or the service fails (recipe field `unavailable`) | `abort`, `continue`, `legacy` | **Before the print:** always `abort` (the experiment refuses to start, `configure()` fails clearly). **During the print:** `continue` by default — the print goes on, the capture is stored with `job_state = "failed"` and the reason, a warning is logged and shown in the summary, and the adapter retries the connection before the next capture; `abort` stops after the current layer (the experiment can be restarted). `legacy` is not offered: the service replaces `DhmServ.exe` on the DHM-PC, so when the service is unreachable the legacy server is not reachable either. Operating modes other than `off` (T72) switch themselves to `off` for the rest of the structure when captures fail. |
| SI2 | May the next layer print while the DHM-PC still computes? | wait for the result; continue after `frames_acquired` | **Yes, after `frames_acquired`** (the stage must not move while frames are taken; the computation does not need the stage), bounded by `maxPending`. Exception: the future mode `correct` (F16) waits for the evaluation of the previous layer. Until `maxPending` is measured, the default 1 makes the print wait for every result. |
| SI3 | Background policy default | `per_session`, `per_structure`, `manual` | `per_session` with the place before printing (grid center or given), as proposed in the handover. |
| SI4 | Where do results of jobs with an unknown capture go? | drop, store separately | `/dhm_orphans/<job_id>` (nothing is lost; visible in the unpack tool). |

### 10.1 Decided 2026-11-18

| ID | Decision |
|---|---|
| general | Recipes with `mode = off` never connect to the DHM. "Abort before the print if the DHM is unreachable" applies only when the experiment uses the DHM. |
| SI1 | **Circuit breaker:** reconnect with backoff at layer boundaries, not before every capture; the summary reports the DHM coverage. **In-situ:** on connection loss try to restore the connection; if that fails, **abort the print with a clear reason**; resumable via the experiment structure (`restart_experiment` / spec). `continue` stays an explicit recipe option. `legacy` is not offered. |
| SI2 | **Depends on the job:** if the data are needed for the next layer (`correct`, F16, or `wait_for_evaluation = true`, OM2) the print waits for reconstruction + evaluation; otherwise the next layer prints after `frames_acquired`. Fallback: if `frames_acquired` does not arrive within `n_frames × exposure + margin`, poll `job_status`. |
| SI3 | Background **per structure at the structure's own position**, before the structure is printed; large structures: background tiles at the raster positions of the later object tiles. `max_age_s` = 3600 s, warning only. |
| SI4 | **Hybrid orphan handling:** results that were sent but never acknowledged are never deleted automatically and stay on the DHM-PC. On `restart_experiment` or the next connection nanofactorysystem asks the service for the orphans of this experiment: `LayerProduct`s are fetched, stored in full in `experiment.h5`, marked `recovered` (reason, original session) and acknowledged; tiles and raw data stay on the DHM-PC, `/dhm_orphans` holds references only (result id, structure, layer, time, host, path, SHA-256, size, reason). Never-restarted experiments: the archive tool (N7) lists the orphans, an offline tool can fetch them later (T106). |
| D6 | Calibration (exposure, OPL scan) runs in the service on the DHM-PC; the legacy procedures `optimage` / `motorscan` on the Work-PC stay selectable so that legacy artefacts stay traceable. |
| D7 | `keep_raw = all` in V1.0; raw data stay on the DHM-PC (D:), `raw_ref` (host, path, SHA-256, frame count) in `experiment.h5`; no automatic deletion; option `publication` transfers all raw data to the Work-PC after the print (T105). |
| DL-A3 a | Every message carries `config_hash` + parameter-set id; nanofactorysystem stores the full parameter set **once per hash** in `experiment.h5` (T79). |
| N1, N2 | The default result per structure and layer is the stitched `LayerProduct` (unwrapped phase + `intensity_rel`, complex field on request); member `ProductSet`s stay on the DHM-PC and are referenced. Groups follow `open_group(GroupSpec)` → `measure` per position → `close_group` (master plan v0.4 §2). |

## 11. Tests (dummy backend, no hardware)

- Legacy adapter: golden command logs (`commands_experiment_*.txt`) and stored captures unchanged (T82).
- Store: `reserve_capture`, result storage, idempotent duplicate, old files still read (T83).
- Fake service: dry run in `products` mode stores products with all traceability fields; delayed results
  are drained between layers; `maxPending` back pressure; failure during the print with `continue` and
  `abort`; unreachable service before the print; crash after store and before acknowledge → duplicate
  dropped; restart with `sync` (T84, T86).
- Tests pass without `dhmconnect` installed (internal fake).

## 12. Mapping to the todos

| Todo | Sections |
|---|---|
| T82 Role protocol and legacy adapter | §3, §4 (legacy), §11 |
| T83 Capture reservation, raw references, groups | §7 (`reserve_capture`, job states), §9, `EXPERIMENT_STORAGE.md` §15 |
| T84 Service adapter and fake | §4, config `dhm_service` |
| T85 Recipes and planner | §5, `group` field |
| T86 Experiment flow with the service | §6, §7, §8, SI1, SI2 |
| T87 Lab check | §11 against the real service |
| T79 Configuration record | `DhmInfo` from `configure()` |

## 13. Approval

Waiting for maintainer approval. Implementation (T82–T87) starts only when this line reads
`Status: approved <date>` at the top of the document, with the answers to SI1–SI4. **Done 2026-11-18** (§10.1).
