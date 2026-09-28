# Code Review — 2026-09-28

Scope: `nanofactorysystem/`, `test/`, the tests `pytest` would collect under `mains/`, and packaging
(`pyproject.toml`). Legacy code (`old_to-delete/`, `new/`, `*_old.py`) is excluded, with one
exception. `devices/aerotech_old.py` is **not** legacy in practice: `devices/__init__.py:13`
imports the active `A3200` class from it (see I4).

This is a report only; no code was changed. The baseline test results are in `WORKLOG.md` (entry [T1]).

The **Todo** column names the todo that resolves each finding. T2–T8 are the
`testing-infrastructure` group. T9–T17 were created during this review.

Severity: **high** blocks testing without hardware or causes wrong results on the machine;
**medium** is a real defect or a coupling with limited impact; **low** is a code-quality issue.

## 1. Hardware coupling

| Severity | File:line | Issue | Recommendation | Todo |
|---|---|---|---|---|
| high | `nanofactorysystem/system.py:55-90` | `System.__init__` opens the camera, DHM and controller, loads the z-line program onto the controller (`:79`), and **physically moves the galvo** (`:85` `moveabs(100, a=0, b=0)`). No construction path avoids hardware. | Inject device instances via a single backend switch (`backend="real" \| "dummy"`); keep motion out of construction or make it part of an explicit `open()`/`home()` step. | T2, T3 |
| high | `nanofactorysystem/devices/aerotech_old.py:119-128` | `A3200.__init__` opens a TCP socket (no timeout). On `ConnectionRefusedError` it logs and **returns early**, leaving `attenuator` and `task_pgms` unset and `opened=False`; `System` then fails later with `RuntimeError: Not connected!` (seen in baseline for `test/devices/test_aerotech.py`). | Fail fast with a clear exception; separate transport from protocol so a fake transport can be injected. | T2, T3 |
| high | `nanofactorysystem/system.py:80-82` | The new `Aerotech3200` interface is created with default host/port and then **shares the old `A3200` socket** by attribute assignment (`api.socket = controller.socket`). Two independent protocol parsers use one socket. If the old controller failed to connect, `api.is_opened` still returns True for an unconnected socket. | Define one transport object owned by `System` and hand it to both controller facades; take host and port from the config instead of the defaults. | T2, T3 |
| medium | `nanofactorysystem/dhm/dhmclient.py:93-94` | `DhmClient.__init__` connects to `192.168.22.2:27182` without a timeout. In the baseline, `test/dhm/test_dhm.py` hung for about 21 s before `WinError 10060`. | Connect with a timeout; for tests, simulate the DHM behind the `Dhm` role (T2). | T2, T13 |
| medium | `nanofactorysystem/aerobasic/ascii.py:182` | `send()` does one `recv(4096)` and assumes the complete response arrives in one TCP segment; there is no timeout. | Read until the terminating character, with a timeout. | T13 |
| medium | `nanofactorysystem/devices/aerotech/__init__.py:150-158` | `run_program_as_task` writes temporary programs into the **current working directory** (`:150`) and copies each program to `Path.home()/python_aerobasic_program.pgm` (`:157`). | Make the staging directory a constructor parameter; tests use `tmp_path`. | T2, T3 |
| medium | `nanofactorysystem/devices/aerotech_old.py:419-439` | `init_zline` writes `__zline__.pgm` into the current working directory. This is where the stray `test/__zline__.pgm`, `test/dhm/__zline__.pgm` and `test/tools/__zline__.pgm` files come from. | Same staging-directory parameter as above. | T2, T3 |
| medium | `nanofactorysystem/aerobasic/programs/drawings/lines.py:15,71` | `IFOV_Lines` hardcodes the lab path `C:/Software/3DPoli Fabrication/Calibration/Calibration.dat` and opens it in the constructor. A **drawing** class therefore depends on a lab file. | Pass the calibration (or the `Attenuator`) in, or read the path from the config. | T14 |
| medium | `mains/**` (6 files, e.g. `mains/main.py:40`) | Experiment scripts hardcode lab output paths (`C:\Users\Nanofactory\Desktop\...`) and use `tkinter.messagebox`. | Accept for lab scripts; the dry run (T6) passes `path=tmp_path` and `ask_continue_box=False`. | T6 |
| low | `nanofactorysystem/aerobasic/ascii.py:74`, `devices/aerotech/__init__.py:23` | Default host and port `127.0.0.1:8000` are duplicated in code instead of coming from `sysConfig.controller`. | Read them from the config in `System`. | T3 |
| low | `test/dhm/test_dhm.py:17-18`, `test/tools/test_grid.py:40-41`, `test/dhm/DHMUserBackend.py:24-25` | Tests hardcode the DHM address `192.168.22.2:27182`. | Hardware tests take the address from the config; mark them `hardware`. | T5 |

## 2. Import-time side effects and dependencies

| Severity | File:line | Issue | Recommendation | Todo |
|---|---|---|---|---|
| high | `nanofactorysystem/config.py:132` together with `system.py:26`, `devices/attenuator.py:30-31`, `devices/camera.py:20`, `devices/dhm.py:24`, `devices/aerotech_old.py:98` | `sysConfig = Config()` reads `~/nanofactory.json` at import. If the file is missing, only a warning is issued, but class bodies evaluate `sysConfig.<section>` at class-definition time and raise `AttributeError: Unknown attribute 'attenuator'`. **Verified:** without the file, `import nanofactorysystem.aerobasic.programs.drawings` fails too, so even pure program generation needs the lab config. | Resolve config sections lazily (at instantiation); provide a built-in default config for the dummy backend; allow an explicit config path. | T2, T3 |
| medium | `nanofactorysystem/__init__.py:13-29` | The package `__init__` eagerly imports `System`, all devices and tools (`cv2`, `skimage`, `scidatacontainer`, `scipy`). Every `nanofactorysystem.aerobasic.*` import pays for, and can fail on, these. | Lazy attribute imports (`__getattr__`) for the hardware-facing classes. | T3 |
| medium | `nanofactorysystem/camera/camera.py:36-40,166-167` | `mvIMPACT` is imported optionally, but a `UserWarning` is emitted on **every** package import, and the later error `ImportError("mvIMPACT not imported")` gives no hint about how to install it or how to use the dummy backend. | Import on first use and raise an error that names the package and the dummy alternative. | T3 |
| low | `test/devices/test_dhm_objective.py:8`, `test/devices/live_tilt*.py:11-12`, `nanofactorysystem/dhm/motorscan.py:18` | `OffAxisHolo` (`offaxisholo`) is hard-imported only in test scripts; in the package the import is commented out. `PlotFont` is not imported anywhere. | Move these scripts to `test/manual/`, or guard them with `pytest.importorskip`. | T5 |
| medium | `nanofactorysystem/devices/__init__.py:13`; `devices/aerotech_old_1.py` | The **active** `A3200` controller lives in `aerotech_old.py`, which the `*_old.py` convention marks as legacy (and CLAUDE.md forbids modifying it). `aerotech_old_1.py` is a near-duplicate that nothing imports. | Maintainer decision: rename `aerotech_old.py` → `devices/a3200.py` (not legacy) and delete or archive `aerotech_old_1.py`. | T12 |
| high | `pyproject.toml:15-17,27-34` | `packages = ["nanofactorysystem"]` lists only the top-level package, so `pip install .` **does not install the subpackages** (`aerobasic`, `devices`, …). The dependencies omit `scipy`, `shapely`, `trimesh`, `qrcode` and `h5py`, which are all imported by active modules. | Use `[tool.setuptools.packages.find]`; complete the dependencies; split hardware extras (`mvIMPACT`) out as optional. | T9 |
| high | environment (global Python 3.12) | `opencv-python 4.10.0.82` and `SciDataContainer`'s dependency chain were built against NumPy 1.x while NumPy 2.4.6 is installed, so `import nanofactorysystem` fails with `numpy.core.multiarray failed to import`. **Every** test file failed at collection with the global interpreter (baseline A). | Constrain the versions in `pyproject.toml` (`opencv-python>=4.10.0.84` supports NumPy 2) and document a reproducible environment. | T9 |
| low | `nanofactorysystem/runtime.py:24-38` | `getLogger()` adds a new console handler (and file handler) to the same `'dummy'` logger on **every** call, so log lines are duplicated when several scripts or tests run in one process. | Configure handlers once; use a module-specific logger name. | T17 |

## 3. Existing dummy, mock or simulation code

Search: `rg -i "dummy|mock|fake|simulat|offline|virtual"` (legacy excluded).

| Severity | File:line | Issue | Recommendation | Todo |
|---|---|---|---|---|
| medium | `nanofactorysystem/aerobasic/ascii.py:282-291`, `devices/aerotech/__init__.py:23-25` | `DummyAsciiInterface` is the **only** existing simulation. Its `send()` returns the command string itself, so every query (`~STATUS`, `AXISSTATUS`, `~VERSION`) returns unparsable data: `Aerotech3200(dummy=True).xyz`, `.axis_status` and `Task.update()` all fail. It keeps no state, and its `history` stays empty because `send()` bypasses the recording. It is not usable as a test backend. | Replace it with a fake **transport** (socket-level) that answers with protocol-correct return codes and holds simulated state; keep `AerotechAsciiInterface` unchanged so the command strings stay under test. | T2, T3 |
| low | `experiment.py:44,593,612,840`; `runtime.py:24`; `parameter.py:52` | Other matches are unrelated to simulation: `StructureType.DUMMY` is a placeholder grid slot, `'dummy'` is a logger name, and `{"dummy": None}` is a base-class default. | None needed. | – |
| low | `test/dhm/DHMUserBackend.py` | This is an interactive user helper that talks to the real DHM, not a simulator. | Move it to `test/manual/`. | T5 |
| – | – | There is **no** simulation for the camera, DHM, attenuator or old `A3200` controller, and no test doubles (`unittest.mock`) anywhere in `test/`. | Implement them in T3. | T2, T3 |

## 4. Correctness defects found while reviewing

| Severity | File:line | Issue | Recommendation | Todo |
|---|---|---|---|---|
| high | `nanofactorysystem/experiment.py:485` | `opl_scan()` calls `self.system.dhm.opl_scan(m0)`, but `Dhm` only defines `motorscan()` (`devices/dhm.py:121`). Every run with the DHM and no cached `opl.txt` raises `AttributeError`. | Call `motorscan(m0)`; cover it with a dummy-backend test. | T10 |
| high | `nanofactorysystem/devices/aerotech/task.py:139` together with `experiment.py:972` | `Task.wait_to_finish` raises `ValueError` for a failed program, but `print_structure` catches only `AerotechError`. A failing layer aborts the whole experiment without writing the error to the progress log. | Raise a dedicated `AerotechError` subclass (e.g. `TaskFailedError`). | T10 |
| medium | `nanofactorysystem/experiment.py:213-217` | If `substrate_information.json` exists, the new information is **silently discarded** (the merge is a `todo`, and the old data is written back). | Merge the new data into the existing file, or keep a list of entries with timestamps. | T10 |
| low | `nanofactorysystem/experiment.py:986` | `layer_id`/`layer_count` are undefined if a structure has no layer files, which gives an `UnboundLocalError`. | Guard against an empty layer list. | T10 |
| medium | `nanofactorysystem/system.py:147,159` | `object_pos`/`camera_pos` use `self.system.controller`, which does not exist on `System`, so they raise `AttributeError` whenever `vs` is None. | Use `self.controller`. | T11 |
| medium | `nanofactorysystem/devices/aerotech_old.py:227` | `if axes in None:` raises `TypeError`, so `A3200.home()` can never run. | `if axes is None:` | T11 (after T12) |
| medium | `nanofactorysystem/devices/aerotech_old.py:516` | `for name, task in self["tasks"]:` iterates dict **keys**. `container()` fails as soon as a task is registered, which `System` always does via `init_zline`. | `.items()` | T11 (after T12) |
| low | `nanofactorysystem/devices/aerotech_old.py:261,459` | `self.z` is only set in `moveabs`; calling `moveinc` or `zline` first raises `AttributeError`. | Initialise `self.z` from `position("Z")` in the constructor. | T11 (after T12) |
| medium | `nanofactorysystem/aerobasic/ascii.py:158-162` | `send_one()` calls itself, which is infinite recursion. It also uses the German-named fallback `run_testzweck_altesSystem` (`:125`). | Remove it, or implement it with `send()`. | T11 |
| low | `devices/aerotech_old.py:328,472`, `devices/aerotech/task.py:122,150` | Busy-wait and polling loops have no upper time bound; the program hangs if the controller never reports the expected state. | Add timeouts. | T13 |
| low | `mains/**` (48 occurrences, e.g. `mains/Experiments/default_exp_file.py:71`) | `assert (path, Path)` is always true (pytest warns about it); `isinstance(path, Path)` was intended. | Fix it, or convert with `Path(path)`. | T16 |
| low | `nanofactorysystem/aerobasic/ascii.py:195,208`; `devices/aerotech/task.py:144` | `print()` calls sit next to the logger in library code. | Use the logger. | T17 |

## 5. State of the tests

| Severity | File:line | Issue | Recommendation | Todo |
|---|---|---|---|---|
| high | repository root (no pytest config) | `python -m pytest` collects `mains/**/*_test.py`, `mains/debugging/test_*.py`, the legacy `drawings/new/test_*.py` and `drawings/test/*.py`. `test/test_model3d.py:305` calls `sys.exit()` at module level, which gives an **INTERNALERROR that aborts the whole collection**. | `testpaths = ["test"]`, `norecursedirs`, markers. | T4 |
| high | `test/devices/*.py`, `test/tools/*.py`, `test/test_system.py`, `test/test_config.py` | 12 `test_*.py` files are **scripts**: hardware access at module level, no test functions, no assertions. They run (and fail) during *collection*. | Triage each one: convert it to a dummy-based test, mark it `hardware` with real assertions, or move it to `test/manual/`. | T5 |
| medium | same scripts, e.g. `test/devices/test_aerotech.py:18` | `mkdir(".test/<name>")` uses the default `clean=True`, which **deletes the contents** of a directory relative to the current working directory. | Use `tmp_path`. | T5 |
| medium | `test/test_femtika/__init__.py:10-11` | The skip guard is inverted (it raises when `EXECUTE_FEMTIKA_TESTS` **is** set) and raises `RuntimeError` instead of skipping, so the tests run and fail without hardware (8 failed in baseline). | Use the `hardware` marker and `--run-hardware`. | T5 |
| medium | `test/test_femtika/test_device_WITH_laser.py:3-4` | Imports the top-level `aerobasic` package (an outdated layout), and `AeroBasicProgram` is used without an import. | Fix the imports; mark it `hardware`. | T5 |
| high | `test/test_aerobasic/test_constants.py`, `test_program.py`, `test/test_utils/test_units.py`, `test_drawings/test_corners.py` | Hardware-free tests fail in baseline B: `SingleAxis` flag parsing and axis-string format changed (3 failures); `AerotechVariable` is abstract (`__call__`) and `to_text()` now adds a timestamp header (3 failures); `assertAlmostEquals` was removed in Python 3.12 (3 failures); `CornerRectangle` no longer exists (collection error). | Decide per failure whether the test or the code is wrong; fix it, or mark it `xfail(strict=True)` with a todo. | T15 |
| medium | `test/test_aerobasic/test_program.py:30-45,58-73` | Tests depend on each other and on leftover state: `tearDown` writes into the shared `test/_programs/` and starts **non-daemon** plotting threads; `test_write_*` call `mkdir()` without `exist_ok`, so they pass only in a clean tree and only once (2 failures + 2 teardown errors in baseline). | Use `tmp_path`/`tmp_program_dir`; drop the threads. | T15 |
| low | `test/test_aerobasic/test_drawings/test_circles.py`, `test_corners.py` | These have no assertions; they only write programs to disk. | Golden-file comparison. | T7 |
| low | `test/tools/test_stitch.py:41`, `test/tools/eval_grid.py` | They depend on data files (`focus-2/…`) that are not in the repository. | Move them to `test/manual/`. | T5 |
| low | `test/tools/test_63x_focus.py` | Uses user `'Hannes'`, which is not in `~/nanofactory.json` on this machine (collection error). | Use the `test_config` fixture. | T5 |
| low | `nanofactorysystem/aerobasic/programs/drawings/new/test_workflow.py` | This legacy file is collected and writes to `/home/claude/workflow_test.png`, which fails on Windows. | Exclude it via `norecursedirs`. | T4 |
| low | `mains/debugging/test_plot.py:19`; `mains/Experiments/Kailas/*_dose_test.py` | A `SyntaxError`, and `testprint(absolute_center, …)` is collected as a test and fails with "fixture not found". | Exclude `mains/` from collection. | T4 |
| low | `nanofactorysystem/aerobasic/programs/drawings/test/*.py` | Slicer and height-structure check scripts sit inside the package (not legacy, not in `test/`). pytest collects them but finds no tests; `test_heightstructure.py` runs about 135 s of module-level code during collection. | Triage them in T5 as "slicer tests". | T5 |

## 6. Language

| Severity | File:line | Issue | Recommendation | Todo |
|---|---|---|---|---|
| low | e.g. `aerobasic/ascii.py:125`, `devices/aerotech/task.py:11-20`, `experiment.py:927-928,959`, `lines.py:40-45` | German identifiers and comments remain outside the scope of this todo group. | Translate them per the maintainer's language rule. | T18 |
