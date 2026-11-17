# Design: Operating modes and feedback hooks

Status: draft 2026-11-16, waiting for maintainer approval (T72). Implementation todos: T88–T92.

Context: `docs/system/SOFTWARE_PLAN_OVERVIEW.md` (data flow §2: `LayerTarget` + product → MIRA compare →
`DeviationReport` → controller → `CorrectionPlan`; G6 recommendation: comparison on the Working-PC; G10:
reference mask from the target footprint, K18), `DHM_SERVICE_INTEGRATION.md` (T71: asynchronous results,
single writer), `INFORMATION_MODEL.md` (approved: `feedback_mode` is a structure setting with experiment
default), F16 (controller and mode `correct`, not scheduled).

## 1. Goals and non-goals

Goals:
- Four modes per structure (experiment default, override per structure): `off`, `monitor`, `shadow`,
  `correct`. `off` is the default and changes nothing.
- After every DHM layer capture with a product, an evaluation hook compares the product with the expected
  geometry (`LayerTarget`) and stores a `DeviationReport`.
- `monitor` warns and may stop a structure by rule; `shadow` also asks a controller for a correction plan
  and stores it without applying it. `correct` is defined (interfaces, limits) but refused until F16.
- `LayerTarget` is defined for sliced and drawn structures and can provide the footprint for the
  reference mask of the DHM reconstruction (G10 / SA1).

Non-goals: the comparison algorithm (MIRA MI-53), a real controller or process model (F16; the dummy
process model is T92), applying corrections (F16).

## 2. Modes

| Mode | Captures | Evaluation | Controller | Effect on the print |
|---|---|---|---|---|
| `off` | as the recipe says | none | none | none |
| `monitor` | needs DHM products after layers | every layer capture with a product | none | log, warnings, optional stop rule (§6) |
| `shadow` | as `monitor` | as `monitor` | `Controller.plan()` after each report | plans stored with `applied = false`; stop rule as `monitor` |
| `correct` | as `monitor` | as `monitor`, the print waits for it | plan applied within hard limits (§7) | refused with a clear error while no controller is registered (T88); implementation F16 |

Validation when the spec is resolved (`spec.resolved()`, T78/T88): a mode other than `off` needs a DHM
recipe whose `mode` delivers products (`products` or `products_and_raw`) and layer captures, a target
source for the structure (§4), and an available evaluator (the MIRA adapter, or the fake on the dummy
backend). Otherwise the spec is refused with a message that names structure, mode and missing part.

## 3. Evaluation hook

The hook runs where the main thread stores a DHM result (`DHM_SERVICE_INTEGRATION.md` §7, queue drain),
not right after `measure()`, because results arrive asynchronously:

```
result stored for capture c (structure s, layer n)
  └─ mode(s) != off and result has products
       ├─ target = targets.layer_target(s, printed_layers(s, up to n))       (§4, cached per structure)
       ├─ submit Evaluation(product, target, context, history(s)) to the evaluation worker
       └─ main thread continues printing (monitor, shadow) / waits for it (correct)
evaluation worker: report = evaluator.evaluate(...)  → report queue
main thread (next drain): store report; apply monitor rule; shadow: plan = controller.plan(state) → store
```

- **Worker:** one evaluation thread (MIRA's comparison may take longer than a layer); it never writes the
  file. Reports go to a queue that the main thread drains together with the DHM results. Order is kept per
  structure.
- **Lag:** in `monitor` and `shadow` a report can arrive one or more layers after its capture (bounded by
  `maxPending` of T71 plus the evaluation time). The stop rule therefore acts at the next layer boundary
  after the report; the report names the layer it belongs to, the stop event names the layer at which the
  print stopped.
- **Failures:** an evaluator exception gives a report with `status = "error"` and the message; it never
  stops the print by itself (it counts as an invalid layer for the stop rule only if the rule says so).
- **End of a structure / experiment:** the main thread waits for outstanding evaluations with a timeout
  (`evaluationTimeout`), then stores what arrived; missing reports are listed in the summary.

### 3.1 Protocols (in `nanofactorysystem/feedback/`, T90)

```python
class Evaluator(Protocol):
    name: str; version: str
    def evaluate(self, product: ProductView, target: LayerTarget, context: CaptureContext,
                 history: Sequence[DeviationReport]) -> DeviationReport: ...

class Controller(Protocol):
    name: str; version: str
    def plan(self, state: FeedbackState) -> CorrectionPlan: ...
```

- `ProductView`: read-only view of the stored product (arrays, pixel pitch, z, n_medium, quality,
  background id) — the evaluator sees what was stored, not the raw message.
- Default evaluator: `MiraEvaluator`, an adapter to `mira` (MI-53), imported lazily; without `mira`
  modes other than `off` are refused. If G6 places the comparison on the DHM-PC instead, a
  `RemoteEvaluator` reads a `DeviationReport` delivered with the `ProductSet` (recipe `post` step); the
  rest of this design does not change.
- Dummy backend: `FakeEvaluator` (deterministic comparison of the synthetic product with the target) and
  `NullController` (empty plan).
- `FeedbackState`: structure, mode, layer, target, the reports so far, the plans so far, the structure
  settings (power, velocity, voxel model), the hard limits.

### 3.2 `DeviationReport` (contract, MIRA → here)

Fields as in the system plan: `schema_version`, `capture_id`, `structure`, `layer_id`, `domain` (`height`
or `phase`), `deviation` map (float32, product grid, NaN outside the valid region) with its grid
(`origin_um`, `pixel_um`), `rmse_um`, `mae_um`, `sigma_um` (or `_rad` in the phase domain), `validity`
(fraction of the target footprint with a valid comparison), `registration` (transform product ↔ target,
residual), `versions`, `warnings`, plus here: `status` (`ok`, `warning`, `stop`, `error`, set by the
monitor rule) and `evaluator` (name, version).

### 3.3 `CorrectionPlan` (here → here, F16)

`schema_version`, `structure`, `based_on` (capture ids), `actions` (list; kinds `power_factor`,
`z_offset_um`, `extra_layers`, `skip_layers`, `reexpose` with a region in target coordinates),
`rationale` (text), `limits_applied` (which limit clipped which action), `controller` (name, version),
`applied` (bool), `applied_at_layer`. In `shadow` `applied` is always false.

## 4. `LayerTarget`

The expected geometry of a structure after the layers printed so far, in µm, in stage coordinates.

| Field | Content |
|---|---|
| `schema_version`, `experiment_uuid`, `structure`, `layer_id` | the capture's layer |
| `printed_layers` | ids of the layers printed so far (order independent: the drop direction reverses the print order, T43) |
| `grid` | `origin_um` (stage X, Y of the center of pixel [0, 0]), `pixel_um`, `shape` (ny, nx); axis 0 = y, axis 1 = x |
| `thickness_um` | float32 map: sum of the thicknesses of the printed layers that cover the pixel — what an optical path difference integrates; 0 outside |
| `top_um`, `bottom_um` | float32 maps: extent of printed material along the build direction relative to the substrate surface (NaN outside); with gaps between printed layers `top − bottom > thickness` |
| `mask` | bool map: footprint (pixels with `thickness_um > 0`) |
| `footprint_um` | the footprint as polygons in stage µm (list of rings) — small enough to travel in `CaptureContext` (G10, T100) |
| `substrate_z_um` | substrate z at the structure center (plane fit) |
| `material` | registry name and snapshot reference (`INFORMATION_MODEL.md` §3.1) |
| `source` | `slicer_contours`, `toolpath_voxel`, `footprint_only` |
| `voxel` | voxel model and the width/height used (or none) |
| `uncertainty_um` | height uncertainty from the source (half a slice for contours, voxel height std for toolpaths, if known) |

**Grid:** the target's own grid; MIRA resamples it onto the product grid after registration. Proposal:
`pixel_um` = half the hatch distance of the structure, clipped to 0.1–1.0 µm, and the extent = footprint
of the whole structure plus the reference margin. Values to be confirmed with MIRA (MI-50).

### 4.1 Sliced structures (`source = slicer_contours`)

The slicer keeps the design cross-section of every layer group (`ElementGroup.contours`, `z_um`; T54 stores
the job in `/structures/<name>/slicer`). A printed layer covers its contour polygons with a slab of
thickness `h` around `z_um`: `h` = voxel height of the job's power and velocity if the voxel model knows
it, else the slice distance. The maps are rasterised from the union of the printed layers' contours.
Shell groups (no contours) are rasterised from their toolpath as in §4.2. Exact up to the slicing; no
hardware or images needed, so targets can be computed before the print and on demand.

### 4.2 Drawn structures (`DrawableObject`) — decision O1

Options:
- **A (recommended):** rasterise the laser-on toolpath of the layer programs with the voxel model
  (`source = toolpath_voxel`). The layer programs are already parsed for plots (`utils/visualization.
  read_text`: movements with laser state and power, T38). Each laser-on segment is drawn as a line of the
  voxel width with the voxel height at its z. Needs a voxel model with data for the structure's power
  and velocity; this gives full targets for `monitor` and `shadow`.
- **B:** limit drawn structures to `monitor` without a target height: only the footprint (laser-on
  segments dilated by a fixed width, `source = footprint_only`) is used for validity and the reference
  mask; `shadow` is refused.
- Proposal: A when the voxel model gives width and height, otherwise B automatically, with a warning
  naming the missing voxel data.

### 4.3 Storage of targets

Targets are reproducible from stored data (slicer job, layer programs, voxel values used), so they are not
stored for every layer. The target used for an evaluated capture is stored with its report (§5); the
structure's target settings (`pixel_um`, extent, source, voxel values) are stored once in
`/feedback/<structure>`.

### 4.4 Reference mask (G10 / SA1, input for T100)

The footprint after layer n is known on this PC before the capture (it does not need the product). For the
a priori reference mask the context can carry `footprint_um` (polygons in stage µm) plus a margin; the
service turns it into a pixel mask with the stage ↔ camera mapping (MIRA MI-41, MI-50). Who sets the
margin (recipe or material/process data) and whether the mask travels in the context or the recipe are
decided in K18; T100 prepares this side's answer.

## 5. Storage

| Path | Content |
|---|---|
| `/feedback/<structure>` | attributes `mode`, `evaluator` (name, version), `controller` (name, version), `rules_json` (monitor thresholds), `limits_json` (hard limits), `target_json` (grid and source settings); dataset `events` (table: `layer_id`, `capture_id`, `time`, `rmse`, `mae`, `validity`, `status`, `action`) |
| `/feedback/<structure>/plans/<layer_id>` | `CorrectionPlan` (attributes, `actions_json`), `applied` |
| `/analysis/captures/<capture_id>/deviation` | `DeviationReport`: datasets `deviation`, `target_thickness_um`, `target_mask`; attributes for the scalars, `registration_json`, `versions_json`, `warnings_json`, `source = "nanofactorysystem.feedback"` — the result layout of T66 (§5.9), so the analysis tools (T67) read reports like other analysis results |

This needs an amendment of `EXPERIMENT_STORAGE.md` §5.9: the printing process may write results under
`/analysis/captures/<id>/deviation` with `source = "nanofactorysystem.feedback"` (it holds the lock
anyway); analysis tools never overwrite results of that source. Proposed as §16 there.

**Summary** (T91): per structure `mode`, number of evaluated layers, last and maximal RMSE, number of
warnings, stop event, number of plans (shadow).

## 6. Monitor rules

Set per experiment with override per structure (`feedback` settings):

| Setting | Meaning | Default |
|---|---|---|
| `warn_rmse_um` | warning above this RMSE | none (only logged) |
| `stop_rmse_um` | stop candidate above this RMSE | none |
| `min_validity` | a layer with lower validity counts as invalid | none |
| `stop_after` | consecutive stop candidates or invalid layers before the structure is stopped | none |
| `on_stop` | `stop_structure` (skip its remaining layers, status `stopped`, continue with the next structure) or `stop_experiment` | `stop_structure` |

Default (decision O3): only log and warn; stopping is opt-in, because thresholds need real data first.
A stopped structure keeps its progress; `restart_experiment()` does not resume it unless asked
(`resume_stopped=True`).

## 7. Hard limits of a correction (`correct`, F16)

Defined now so that `shadow` plans are checked against the same limits:
- every action kind has an explicit limit in the spec (`max_power_factor`, `min_power_factor`,
  `max_abs_z_offset_um`, `max_extra_layers`, `max_skip_layers`, `max_reexpose_dose_factor`) — **no
  defaults**: an action kind without a limit is not allowed;
- limits per layer and cumulative per structure; an action that exceeds a limit is clipped and recorded
  in `limits_applied`;
- the attenuator calibration range and `zMax` always apply;
- over-exposure cannot be undone: re-exposure is refused where the target is already reached;
- stop rule: a structure whose plans hit a limit `n` times in a row is stopped as in §6.

## 8. Decisions for the maintainer

| ID | Question | Proposal |
|---|---|---|
| O1 | Drawn structures: target rasterised from the toolpath with the voxel model, or `monitor` without a target? | Toolpath with voxel model when voxel data exist, otherwise automatically footprint only (no `shadow`), with a warning (§4.2). |
| O2 | Does the print wait for the evaluation in `monitor` / `shadow`? | No; the stop rule acts at the next layer boundary after the report. `correct` waits. |
| O3 | Default of the monitor rule | Log and warn only; stopping is opt-in (§6). |
| O4 | Comparison domain | Target in height (µm); the evaluator converts with `n_medium` from the snapshot and states the domain in the report (depends on G4). |
| O5 | Reports in `/analysis` written by the printing process | Yes, under `/analysis/captures/<id>/deviation` with source `nanofactorysystem.feedback` (amendment §16 of `EXPERIMENT_STORAGE.md`). |
| G6 | Where the comparison runs | Assumed Working-PC (system plan recommendation); a remote evaluator keeps the design valid otherwise. |

## 9. Tests (dummy backend)

- Target of a sliced block and a sliced cylinder against their analytic shapes (thickness, mask,
  footprint area), for UP and DOWN print order (T89).
- Target of a drawn `Rectangle3D` with a fixed voxel model; footprint-only fallback without voxel data.
- Dry run with the fake service and `FakeEvaluator`: reports stored per layer capture, monitor warning,
  stop rule stops the structure and the next structure prints, shadow plans stored with `applied =
  false`, `correct` refused (T88, T90, T91).
- Spec validation errors for missing products, target source or evaluator.
- `python -m pytest` passes without `mira` and `dhmconnect`.

## 10. Mapping to the todos

| Todo | Sections |
|---|---|
| T88 Mode in spec and storage | §2, §5 (`/feedback` attributes, summary) |
| T89 Layer targets | §4 (O1) |
| T90 Evaluation hook | §3, §5, O2, O5 |
| T91 `monitor` and `shadow` | §3.3, §6, §7 (limits checked in shadow) |
| T92 Process model in the dummy world | §9 (products to compare against targets) |
| T100 K18 input | §4.4 |

## 11. Approval

Waiting for maintainer approval. Implementation (T88–T92) starts only when this line reads
`Status: approved <date>` at the top of the document, with the answers to O1–O5.
