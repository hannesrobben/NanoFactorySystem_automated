# Design: Headless core for a GUI

Status: approved 2026-11-18 (decision session 2026-11-17/18, with the additions of §7.1). Implementation
todos: T96, T97.

Context: F15 (system GUI, details follow from the maintainer), G3 (GUI framework; recommendation PySide6
with pyqtgraph, not decided — this design is framework-neutral), `INFORMATION_MODEL.md` (experiments as
project files, T77), `DHM_SERVICE_INTEGRATION.md` and `OPERATING_MODES.md` (worker threads and the single
writer), `CAMERA_LIVE.md` (camera service).

## 1. Goals and non-goals

Goals:
- The print can be started, followed, paused, resumed and aborted from another thread (a GUI) without the
  GUI ever blocking on hardware, and without the GUI touching hardware or writing the experiment file.
- The run path contains no call that waits for a person (message box, `plt.show()`) unless the caller
  injected it.
- Scripts in `mains/` keep working unchanged (defaults as today).

Non-goals: the GUI itself (F15), remote control over the network, a new hardware emergency stop.

## 2. Blocking calls (inventory 2026-11-16)

### 2.1 Waiting for a person

| Place | Call | In the run path? | Plan |
|---|---|---|---|
| `experiment_spec.py:436` `messagebox_confirm()` | tkinter `askyesno` | only when a script passes it as `confirm` to `run_experiment()` / `run_substrate()` (both already take a `confirm` callable; 16 scripts in `mains/` import `messagebox_confirm`) | keep the callable; define it as protocol `Confirm(question: ConfirmRequest) -> bool` with an id and a default answer; the GUI passes its own implementation (T96) |
| `experiment.py:907` `plot_experiment(show=True)` | `plt.show()` | only with `run_experiment(show_plot=True)` (default False) | return the figure only; the entry scripts show it (T96) |
| `substrate_plan.py:277` substrate plot with `show=True` | `plt.show()` | only with `show=True` | as above (T96) |
| `drawings/cell_geometry_2.py:67`, `dots/cell_dot_grid.py:75`, `dots/cell_dot_grid_1.py:84` (`show()` helpers), `hollow_structure.py:113` (`analyze_structure`), `lens.py:229` (`plot_surface`), `qr_code.py:198` and `tile_manager.py:1220` (`__main__` blocks) | `plt.show()` | no (helpers for interactive inspection) | unchanged |

### 2.2 pyplot state in the run path

`plot_experiment()` (`experiment.py:841`, `plt.subplots`), `build_programs(plot_structures=True)`
(`experiment.py:1403`, `plt.savefig` / `plt.close`), `utils/visualization.py:313/372` (`plt.figure`) and
the substrate plot (`substrate_plan.py:257`) use pyplot's global state. With a Qt GUI, pyplot must only be
used in the GUI thread; from a worker thread it can start a GUI backend in the wrong thread. Plan (T96):
these functions build `matplotlib.figure.Figure` objects with an Agg canvas (object-oriented API, no
pyplot), save them and return them; a script or GUI decides how to show them.

### 2.3 Long device waits (block the calling thread, not a person)

`AerotechTask.wait_to_finish()` (poll every 0.5 s, stall bound 600 s), plane fit (`plane_fit()`, focus and
layer tools), OPL scan, overview mosaic, `measure()` (camera, DHM), the `opl_scan` z move. They stay
blocking but run in the worker thread (§3); pause and abort act between them (§5).

## 3. Threads and ownership

```
GUI thread            worker thread (runner)                      helper threads
----------            ----------------------                      --------------
commands ──RunControl──> checkpoints ── System, A3200, DHM adapter
events  <──EventBus────  ExperimentStore (only writer)  <── queues ── DHM receiver (T71)
                                                         <── queues ── evaluation worker (T72)
camera view <──Subscription──────────────────────────────────────────  camera thread (T73)
read-only views: ExperimentFile (T66, no file locking)
```

Rules:
1. **One worker thread per run** owns `Experiment`, `System` and all device objects. Only it calls the
   controller, the DHM adapter (except the adapter's own receiver) and the camera service's snapshot API.
2. **Only the worker thread writes `experiment.h5`** (and `substrate.json`). Helper threads hand data to it
   through queues (T71, T72); the GUI never opens the store for writing. The GUI reads with
   `ExperimentFile` / `ExperimentStore(read_locking=False)` (T66) or from events.
3. **The GUI thread never blocks on the worker.** Commands are non-blocking calls on `RunControl`; answers
   come as events. A `Confirm` callback that the GUI provides is called in the worker thread, posts the
   question to the GUI and waits there (the worker waits, the GUI does not).
4. Events and commands are plain, JSON-serialisable dataclasses, so the runner can later move into its own
   process without changing the GUI side (decision P1).

## 4. Progress events (T97)

`RunEvent`: `kind`, `time_utc`, `run_id`, `experiment_uuid`, `structure`, `layer_id`, `capture_id`,
`done`, `total`, `message`, `data` (small dict), `schema_version`.

| Kind | When | `data` |
|---|---|---|
| `run_started`, `run_finished` | around the whole run | `reason` (`finished`, `aborted`, `failed`) |
| `step_started`, `step_finished` | plane fit, OPL scan, background, build, overview before/after | `step` |
| `structure_started`, `structure_finished` | per structure | `status` (`printed`, `failed`, `stopped`, `skipped`) |
| `layer_started`, `layer_finished` | per layer program | `status`, `duration_s`, `expected_remaining_s` (from the time estimate, T28) |
| `capture_started`, `capture_finished` | per camera / DHM capture | `kind`, `phase` |
| `result_stored` | DHM result stored (T71) | `job_id`, `job_state` |
| `report_stored` | deviation report stored (T72) | `rmse`, `status` |
| `paused`, `resumed`, `abort_requested` | run control | `requested_by`, `mode` |
| `confirm_requested` | a `Confirm` question is open | `question`, `id` |
| `warning`, `error` | logged warnings and errors (logging handler) | `logger`, `exception` |

`EventBus.subscribe(callback)`: callbacks are called in the worker thread and must return at once (a GUI
adapter re-emits them as a signal in the GUI thread; a list collector is used in tests). A failing
callback is logged and unsubscribed; it never stops the print. Without subscribers the bus does nothing
(scripts unchanged).

## 5. Pause, resume, abort (T97)

`RunControl` (thread-safe): `pause()`, `resume()`, `abort(after="layer" | "structure")`, `stop_now()`.

- **Checkpoints** in the worker: before each step, before each structure, before each layer, after each
  capture. Pause and abort take effect only there — never while a layer program runs or a capture is
  taken, so the stage, the laser and the stored progress are always consistent.
- **Pause:** at the next checkpoint the worker waits (laser off, no task running) until `resume()` or an
  abort; while it waits it keeps draining the DHM result and report queues, so asynchronous results are
  stored and acknowledged. Pause intervals are stored (`/run_control` table: `time`, `action`, `structure`,
  `layer_id`, `requested_by`) and their sum appears in the summary next to the printing time.
- **Abort after layer / structure:** at the corresponding checkpoint the run ends like a Ctrl+C today:
  session `end_reason = "aborted"`, status `aborted`, logs stored, substrate index updated; the experiment
  can be continued with `restart_experiment()`.
- **`stop_now()`** (decision P2): stops the running layer program immediately through the existing task
  stop (`_stop_failed_task`, `PROGRAM 1 STOP`), marks the layer `failed` with reason `stopped by user`,
  then aborts as above. It is a software stop, not a safety function; the hardware emergency stop stays
  the safety device.
- **Scripts:** `RunControl` defaults to a no-op object, so the flow and the command logs of scripts and
  dry runs stay unchanged. Ctrl+C keeps working as today.

## 6. Runner API (T97)

```python
runner = ExperimentRunner(spec, user=..., resin_edges=..., backend=None, events=bus, control=control,
                          confirm=confirm)                      # or SubstrateRunner(substrate_spec, plan)
thread = runner.start()          # worker thread; runner.result() → experiment folder or exception
```

`run_experiment()` and `run_substrate()` stay as they are and become thin wrappers that run the runner in
the calling thread. The runner takes an `ExperimentSpec` (or a project file, T77), so a GUI needs no
Python script.

## 7. Decisions

The table below is the proposal of the draft (2026-11-16); §7.1 records what was decided.

| ID | Question | Options | Proposal |
|---|---|---|---|
| P1 | Runner in a thread of the GUI process or in its own process? | thread (simple; a GUI crash ends the process, the controller finishes the running layer program on its own, the session is not closed cleanly); own process (a GUI crash does not touch the print; needs a local IPC) | Start with a thread (T97), keep events and commands serialisable (§3 rule 4) so that F15 can move the runner into its own process if the GUI turns out to be unstable. |
| P2 | Offer `stop_now()` (immediate task stop) in addition to abort between layers? | yes; no | Yes, with the clear note that it is no safety function. |
| P3 | May a pause happen in the middle of a structure? | between layers; only between structures | Between layers (resin and drift effects of a long pause show up in the stored pause times; the GUI can warn). |
| G3 | GUI framework | PySide6 + pyqtgraph (recommendation of the system plan) | Not needed for this design; decided with F15. |

### 7.1 Decided 2026-11-18

| ID | Decision |
|---|---|
| P1 | Runner in a worker thread (T97); events and commands stay serialisable so the runner can move into its own process later (F15). |
| P2 | `stop_now()` yes, with the note that it is no safety function. **Restart rule:** a layer stopped in the middle of its program is never reprinted automatically (double dose); the structure counts as `stopped`, resuming is opt-in (`resume_stopped=True`) with a warning. |
| P3 | Pause between layers; warning threshold `max_pause_s`; an optional (not default) interface / focus check after a long pause. |
| G3 | **PySide6 + pyqtgraph** for all GUIs (system GUI F15 and `offaxisholo.gui`); the PyQt5 legacy (`DHM_User_Interface`) is migrated when touched; napari is evaluated in OffAxisHolo L0 for the offline analysis GUI, not mandatory. DHM + stage operation is part of the system GUI (O9). |

## 8. Tests (dummy backend)

- No pyplot figure is created in the worker during a dry run with plots enabled (checked with a
  non-interactive backend and `plt.get_fignums()`); `plot_experiment()` returns a `Figure` (T96).
- A dry run in a worker thread: events arrive in order (`run_started` … `run_finished`) with layer counts;
  pause after the first layer, resume, then abort after a layer: status `aborted`, progress consistent;
  `restart_experiment()` prints only the missing layers (T97).
- `stop_now()` during a layer on the fake controller: layer `failed` with reason, run aborted.
- A failing event callback does not stop the run; a `Confirm` that answers False ends the run as today.

## 9. Mapping to the todos

| Todo | Sections |
|---|---|
| T96 Remove blocking user interaction | §2.1, §2.2 |
| T97 Run control and progress events | §3, §4, §5, §6, P1–P3 |
| F15 System GUI | uses §3–§6; G3 |

## 10. Approval

Waiting for maintainer approval. Implementation (T96, T97) starts only when this line reads
`Status: approved <date>` at the top of the document, with the answers to P1–P3. **Done 2026-11-18** (§7.1).
