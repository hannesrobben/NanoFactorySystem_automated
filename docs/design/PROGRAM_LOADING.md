# Program loading through the A3200 library within a memory budget (T129) — work order

Status: draft of 2026-11-24, updated the same day with the results of lab session 1 (section 6), the
revised plan (section 7) and the health check and recovery (section 8). The requirements below come
from the maintainer. The lab tests are in `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`.

Related todos:
- T125: split of too long programs (hotfix, done);
- T126: queue mode `BUFFEREDRUN`, now the second choice;
- T127: remove the program under its loaded name;
- T128: refusal reasons, and stopping instead of skipping;
- T130: program optimiser.

## 1 Findings

| Date | Observation | Source |
|---|---|---|
| 2026-11-21 | `PROGRAM 1 LOAD` over ASCII: layer 71 (81 751 lines) loads in 10 s. The next layer gets "An out of memory error occurred." (FAULT, after 1.6 s and 19 s). Every later LOAD is refused with `!` within 0.4 s until restart. | `A3200.log` of the DOE print |
| 2026-11-22 | T125 parts of 79 992 lines: some refused, some loaded but "complete" after 4–10 % of their lines, one in task error right after START | `A3200.log` of the reprint |
| 2026-11-23 | Motion Composer 6.04.005 compiles the full layers 69 and 68 (`.pgm` → `.ogm`) and runs layer 69 on task 1 while loading 68 on task 2, without problems | maintainer |
| 2026-11-24 | Port 8000 is served by `A3200AsciiInterface.exe`, **32 bit**. Motion Composer is 64 bit. | `library_load_check.py inspect` |
| 2026-11-24 | `A3200ProgramLoad` (`A3200C64.dll`) from 64-bit Python: layer 68 (1 253 745 lines, 45.8 MB) loads in **129 s**. The loading process peaks at **19.3 GB** (≈ 15 kB per line) and still holds 12.4 GB afterwards. | `library_load_check.py load` |
| 2026-11-24 | `PROGRAM LOAD` of the `.ogm` over ASCII: refused, "Build Result: -536325553" (0xE008524F). Afterwards every LOAD over ASCII is refused within 0.1 s, also valid `.pgm` files and on other tasks. | `library_load_check.py ascii-load` |
| 2026-11-24 | Task 3 is `inactive` on this controller; tasks 1 and 2 are usable | `library_load_check.py` |

Conclusion:
- The ~80 000-line limit is the address space of the 32-bit ASCII interface, which compiles the
  program itself. It is not a controller limit.
- A failed compile leaves the ASCII interface refusing every later LOAD.
- Compiling in a 64-bit process works, but needs about 15 kB of RAM per line.

## 2 Goal

Layer programs of any length are printed by the automated workflow:
- without the load failures above;
- without exceeding the memory budget of the work PC;
- without load pauses between the parts of a layer or between layers.

## 3 Requirements (maintainer, 2026-11-24)

| ID | Requirement |
|---|---|
| R1 | Programs are loaded through the A3200 C library (`A3200C64.dll`, 64 bit), not with `PROGRAM LOAD` over ASCII. The ASCII interface remains for immediate commands and status. |
| R2 | **Memory budget:** the PC has 32 GB RAM. All processes together use at most 20–25 GB (configurable, default 22 GB). This includes the experiment process (writing `experiment.h5`, monitoring, camera). |
| R3 | **Compilation is bounded:** a program is compiled only if the current use plus its estimated peak stays within the budget. A layer whose compile would exceed the budget is split into parts. The part size follows from the measured memory per line (`max_lines = compile budget / (kB per line × safety factor)`), not from the fixed 80 000 lines of T125. |
| R4 | **Alternating tasks:** the parts of a layer, and the layers one after another, run alternately on task 1 and task 2. While a part runs on one task, the next part is compiled and loaded on the other. The next part starts as soon as the current one has completed. |
| R5 | Only one compile runs at a time, and never on the task that is running. |
| R6 | A part that cannot be loaded, ends before its last line, or ends in an error stops the structure: progress is recorded and the programs are removed. No structure is printed with gaps (T128, phase 1 of the T125 follow-up plan). |
| R7 | Every program is removed under the name it was loaded with, after it has run or failed. The removal is verified with the added-program count (T127). |
| R8 | Every part is monitored: task state, program line, start and end time, the gap to the next part, and the memory of the PC. The data goes into the experiment log. |
| R9 | The ASCII path stays available as fallback (`program_loader="ascii"`, with the T125 split at 80 000 lines). The default switches to the library after the lab validation. |
| R10 | The dummy backend simulates the library loader (load time and memory per line, two tasks, removal), so that `python -m pytest` covers the workflow without hardware. |

## 4 Design sketch

- `devices/aerotech/library.py`: a ctypes wrapper of the functions used. The prototypes are
  checked in the lab: `A3200Connect`, `A3200Disconnect`, `A3200ProgramLoad`, `A3200ProgramStart`,
  `A3200ProgramStop(AndWait)`, `A3200ProgramRemove`, `A3200ProgramGetTaskState`,
  `A3200ProgramGetAddedProgramCount`, `A3200GetLastErrorString`.
- `devices/aerotech/loader.py`: compiles and loads one program in a **separate 64-bit worker
  process**, so that the memory is returned to Windows afterwards.
  - The worker reports load time, peak memory and the task state as JSON.
  - If the lab shows that a program disappears when its loading process ends, there is one
    long-lived worker per task instead (R4 and R5 still hold).
- `MemoryBudget`: current PC use plus the estimated peak against the budget.
  - kB per line comes from the lab measurement and is updated from every load.
  - The values come from the config section `controller`.
- `ProgramRunner`: runs a list of program files on tasks 1 and 2 with prefetch (R4–R8). It is
  called by `Experiment.print_structure` / `_run_layer` and by `reprint_layers`.
  - The layer split (T125) gets its `max_lines` from the budget.
  - Several small layers may share a task cycle; the order of the layers (drop direction) is kept.
- Seam: a `ProgramLoader` protocol in `backends/protocols.py`, with the real loader and a dummy
  loader in `backends/dummy/`.

## 5 Work packages

Superseded by section 7 after lab session 1; kept for reference.

1. **P1 — Safety (T128/T127)**:
   - an early end counts as a failure;
   - task error with error code;
   - stop the structure on the first failure;
   - removal under the loaded name.

   Needed for every load path.
2. **P2** — the library wrapper and the worker process, with the dummy loader and unit tests.
3. **P3** — `MemoryBudget` and `ProgramRunner` with task alternation and prefetch, with tests on
   the dummy backend: gaps, failure in the middle, over-budget split.
4. **P4** — integration into `Experiment` and `reprint_layers`:
   - `program_loader` option;
   - log data in `experiment.h5`;
   - mark layers printed by hand in Motion Composer (maintainer request);
   - documentation (CLAUDE.md, `test/README.md`).
5. **P5** — a lab check of the integrated loader with the laser off, then one real layer.
6. **T130** (separate): optimiser. It lowers lines and bytes and with them memory and load time.

## 6 Open points, decided by the lab tests

Lab session 1 of this work order: 2026-11-24, 11:56–12:51, `mains/lab_checks/program_loading_lab_20261124`
(`log.txt`, `results.jsonl`, `watch_115709.csv`, `cycle_memory.csv`) and the console output
`console_log_loading_lab.txt`. The session folder and the console log are not versioned.

**Precondition not met:** the A3200 software was not restarted before the session. The processes had
the same PIDs as in the session of the morning (`A3200CommService` 4568, `A3200CallbackService`
7264, `A3200AsciiInterface` 7712), one program was still added on the controller, and the ASCII
interface was still in the state left by the failed `.ogm` load of the morning. This does not affect
the library results. It does make the `sticky` result unusable (see below).

| Question | Lab step | Result |
|---|---|---|
| Memory per line and load time vs. program size (linear?) | `ladder` | **Linear.** 50k / 100k / 200k / 400k lines of layer 68: 4.9 / 9.6 / 19.1 / 38.3 s and 0.96 / 1.89 / 3.77 / 7.51 GB peak in the loading process. That is **19.6 kB and 96 µs per line**. The text grows as 37 bytes per line. 800k lines was skipped by the budget check (estimated 18 GB). |
| Is memory freed by `A3200Disconnect`, or only at process exit? | `ladder` | **At `A3200Disconnect`**: 0.02–0.03 GB remain in the process afterwards. |
| Does a loaded program survive the end of the loading process? | `ladder`, `cycle` | **Yes.** After the worker exits, the task is still `program_ready`. A different process (the parent) can start, stop and remove it. The short-lived worker of section 4 works. |
| Does `A3200ProgramRemove(<file name>)` remove it (added-program count)? | `ladder`, `cycle` | **Yes, for `.pgm` loads.** The count goes 1 → 2 → 1. After the `.ogm` load it stayed at 2 although the call returned success. The name under which an `.ogm` is added is probably not the `.ogm` file name (Motion Composer had loaded the same layer before; see below). **Consequence:** remove by the name listed by `A3200ProgramGetAddedPrograms`, and verify with the count. |
| Do shorter numbers lower memory or load time? | `precision` | **Memory yes, time hardly.** For 200k synthetic lines with 10 decimals / 5 decimals / 5 decimals trimmed: 7.3 / 5.3 / 4.4 MB text, 19.3 / 16.7 / 15.2 kB per line, 18.5 / 18.0 / 17.7 s. That is −21 % memory and −4 % time. The compiled `.OGM` is 28.4 MB in all three cases (142 bytes per line). Only fewer lines lower the time (T130: merge moves). |
| Can the library load a precompiled `.ogm`? | `ogm` | **Yes, and quickly.** Motion Composer's `.ogm` of layer 68 (178 MB, 1 253 745 source lines) went to `program_ready` in **5.9 s with a 1.87 GB peak** (≈ 1.5 kB and 5 µs per line). Loading the `.pgm` took 129 s and 19.3 GB. The script's figure "7.29 kB/line" is wrong, because it counted line breaks in the binary file. Caveat: the same layer had been loaded by Motion Composer 3 minutes earlier and was still added. A clean repeat is needed (lab session 2). |
| Gap between two parts with prefetch on the other task | `cycle` | **0.15–0.17 s.** 4 parts × 200k lines alternating on tasks 1/2. Each load (18.6 s) ran completely while the previous part was running. Every part ended at its last line. |
| Memory of the PC during a cycle with two loaded programs | `cycle`, `watch` | PC between 8.7 and 11.8 GB. The loaded programs do not show in Windows memory; only the compile does, and only while it runs. Where the loaded programs live (INtime memory of the controller?) and how much room is left there is open. |
| Is only the failed program name blocked after a refused ASCII LOAD? | `sticky` | **Not answered.** The ASCII interface was not restarted. The first, valid program was already refused (0.13 s, "Compiler Error: Could not open AerParam.pgm."). The second LOAD (deliberately invalid program) got **no reply within 600 s**, and the script stopped with a socket timeout. New finding: an ASCII `PROGRAM LOAD` can block for more than 10 minutes. Our client waits without a time limit (`responseTimeout` None). |
| Why is task 3 inactive? Is the ASCII interface a service that can be restarted alone? | checklist | Checklist not returned. `A3200CommService` is a Windows service (Auto). `A3200AsciiInterface.exe` and `A3200CallbackService.exe` are its child processes, so there is no separate service for the ASCII interface. Open: does the CommService restart a terminated ASCII interface? |

Further observations of the session:

| Observation | Meaning |
|---|---|
| The library's `A3200ProgramLoad` writes the compiled `.OGM` next to the source (`programs/CYCLE_PART1OF4.OGM`, …, 142 bytes per line). | Every library load already produces the precompiled file. A later load of the same part can use it (5 µs instead of 96 µs per line, about 1/13 of the memory). Disk use: about 178 MB per layer of 1.25 M lines. |
| Motion Composer, layer 68 by hand (step 3b): the compile phase grows to 3.4 GB in about 4.5 min, the load adds 1.8 GB, the peak is 7.06 GB, and 6.4 GB stay held until Motion Composer closes. That is **5.6 kB per line at the peak**, a third of the C library. | Motion Composer compiles in a way that needs less memory (probably the .NET API in `A3200\DotNet`). If our software can use the same path, whole layers fit into the budget without splitting. Open (lab session 2). |
| **The same program runs 1.8× slower on task 2 than on task 1**: 279.6 s on task 1 and 500.5 s on task 2 for the same 200k lines (1.4 vs. 2.5 ms per line), reproduced twice. | Task-specific settings (e.g. default ramp/rapid speed, time units, execution settings) or a task priority. Every print so far ran on task 2 (`run_program_as_task` default). Lab session 2: compare the task parameters, and repeat with the real layer header (`SECONDS`, `METRIC`, `LOOKAHEAD FAST`, `CRITICAL START`). |
| `A3200CallbackService.exe` (32 bit) held 1.87 GB in this session, constant. In the morning it held 10 MB (same PID). | It grew between the two sessions (library load of the whole layer or Motion Composer?). A 32-bit process near 2 GB can run out of address space. Monitor it; it is part of the health check (section 8). |
| A program loaded by Motion Composer stays added after Motion Composer is closed (count 2 until the end of the session). | Before a print, the added programs must be listed and cleaned up (health check). |

## 7 Plan after lab session 1

What the cycle proved is already enough to print large layers safely:
- the library compiles in our own 64-bit process;
- parts are bounded by the budget;
- tasks 1/2 alternate with prefetch.

The `.ogm` and Motion Composer findings make it faster and lighter. Work packages, replacing section 5
(P1 stays first):

1. **P1 — Safety (T127, T128)**:
   - an early end is a failure;
   - task error with error code;
   - stop the structure on the first failure;
   - remove under the listed name and verify the count;
   - **response timeout for ASCII `PROGRAM LOAD`** (a LOAD can block for more than 10 min).
2. **P2 — Library wrapper and worker (T129):**
   - `A3200Connect`/`Disconnect`, `ProgramLoad`, `Start`, `StopAndWait`, `Remove`, `GetTaskState`,
     `GetAddedProgramCount`/`GetAddedPrograms`, `GetLastErrorString`;
   - the worker loads and exits; the parent starts and monitors;
   - dummy loader.
3. **P3 — Budget and runner (T129):**
   - default part size 400 000 lines (7.5 GB compile peak at 19.6 kB per line). It is computed by
     `MemoryBudget`: budget 22 GB − current use − reserve for the experiment process (default 3 GB),
     ÷ (kB per line × 1.2);
   - the T125 split cuts at this size instead of 80 000;
   - tasks 1/2 alternate with prefetch.
4. **P4 — Integration (T129):**
   - `Experiment` and `reprint_layers`;
   - log data;
   - layers printed in Motion Composer;
   - documentation.
5. **P5 — Lab:** a real layer split into 400k parts, laser off, then with laser.
6. **T131 — Precompiled `.ogm`:**
   - compile parts in the build step or one layer ahead;
   - while printing, load only the `.ogm` (12× faster, 1/13 of the memory);
   - cache keyed by program hash and controller configuration;
   - clean up after printing.
7. **T132 — Task speed:** explain and remove the 1.8× slower task 2; until then, prefer task 1 for long
   parts or compare both.
8. **T133 — Health check and recovery** (section 8, maintainer idea).
9. **T134 — Lab session 2:**
   - clean restart;
   - `sticky` repeated;
   - clean `.ogm` load;
   - `A3200ProgramAdd`/`Associate`;
   - task parameters and speed;
   - INtime memory;
   - .NET compile path of Motion Composer;
   - recovery levels.
10. Later, if the .NET path compiles whole layers with about 3 kB per line: drop the split for the
    library path (decision after T134).

T126 (queue mode) stays in the backlog: loading with prefetch already gives gaps of 0.15 s.

## 8 Controller health check and recovery (maintainer idea 2026-11-24, T133)

Goal: our software detects a controller in a bad state before and during a print, and brings it back
in defined steps. Today the operator has to recognise this and restart the A3200 software by hand.

**Health check** (no side effects, before every experiment and after every failure):
- ASCII reachable (`~VERSION`);
- tasks 1/2 idle;
- added programs (number and names; foreign ones are reported);
- axis faults;
- memory of the PC and of the A3200 processes (`A3200CallbackService` above 1.5 GB of its 2 GB
  address space is a warning);
- start time of the A3200 processes;
- optional: a test LOAD of a tiny program through the library and over ASCII. A refusal or a missing
  reply means the ASCII interface is blocked.

**Recovery levels.** Every level is logged to the experiment log. Never while a task is running, never
with the laser on: the laser is set to 0 and the gate closed first.

| Level | Action | Side effects | Who triggers it |
|---|---|---|---|
| R0 | Stop tasks 1/2, remove every added program (by listed name), `ACKNOWLEDGEALL` | none on axes or positions | automatic before a print and after a failure |
| R1 | Restart only the ASCII interface (terminate `A3200AsciiInterface.exe`, if the CommService starts it again; lab session 2) | ASCII connection lost, reconnect | software after operator confirmation |
| R2 | Controller reset through the library (`A3200Reset`, if present in the headers, like "Reset Controller" in Motion Composer) | Axes disabled, home and IFOV/galvo settings possibly lost → enable axes, possibly home, re-initialise the setup | operator confirms on the console; homing only with the objective at a safe Z |
| R3 | Restart the A3200 software (`Restart-Service A3200CommService`, admin rights) | as R2, plus all connections | operator confirms; only if R1/R2 do not help |

Each level is followed by the health check again. The experiment continues only if it passes. The
print resumes with `restart_experiment()` from the recorded progress; double exposure of the
interrupted layer is accepted. Lab session 2 measures for R1–R3:
- whether the level works;
- how long it takes;
- whether axis positions, the home state and the galvo/IFOV settings survive.

## 9 Acceptance

- A DOE layer of 1.25 M lines prints with the laser off on the work PC:
  - every part ends at its last line;
  - the PC stays within the budget during the whole layer (memory log);
  - the gaps between the parts are below 1 s.
- `python -m pytest` passes. The dummy backend covers task alternation, the budget split and the
  stop on failure.
- The golden command logs change only where R1/R7 require it, and deliberately.
