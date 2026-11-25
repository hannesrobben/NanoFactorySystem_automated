# Program loading through the A3200 library within a memory budget (T129) — work order

Status: draft of 2026-11-24, updated the same day with the results of lab session 1 (section 6), the
revised plan (section 7) and the health check and recovery (section 8). Updated on 2026-11-25 with the
results of lab session 2 (section 6.2) and the plan after it (section 7.2). The requirements below come
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

### 6.2 Lab session 2 (2026-11-25, T134)

Session folder `mains/lab_checks/program_loading_lab_20261125` (`log.txt`, `results.jsonl`,
`watch_094421.csv`, `api/`, `INtime.txt`, `NOTES_READ_ME.txt`), 09:42–11:54. Motion Composer
6.04.005.005, `A3200.dll` 6.4.5.5. The session folder is not versioned.

**Preconditions.** The A3200 processes were started on 2026-11-24 at 15:52 (the restart at the end of
session 1), not right before session 2; the `system` step warned. The ASCII LOAD probe worked and 2
programs were added. The library results are not affected. The A3200 software was restarted by hand at
11:19, between the second and the third `sticky` run, so the third run is the clean repeat that session 1
could not deliver.

| Question | Lab step | Result |
|---|---|---|
| Does our own `.OGM` load fast under a new name, and does a renamed copy? | `ogm-clean` | **Yes, both.** 400k lines of layer 68: compile through the library 38.9 s, 7.51 GB, 19.63 kB per line. Loading the resulting `.OGM` under a never-used name: **15.1 s, 0.61 GB (1.55 kB per line)**; the renamed copy: 15.3 s, the same memory. The `.OGM` is about **2.6× faster** to load (38 µs instead of 97 µs per line) and needs **1/13 of the memory**. |
| Full layers from `.ogm` (clean repeat of session 1) | `hold` | Layer 68 (1 253 745 lines): **47.5 s, 1.88 GB**; layer 69 (809 415 lines): 30.7 s, 1.22 GB, both 1.55 kB and 38 µs per line. The 5.9 s of session 1 is corrected: Motion Composer had loaded that layer just before. Both full layers stayed loaded on tasks 1 and 2 at the same time (4 added programs, both `program_ready`). |
| Under which name is an `.ogm` added? | `ogm-clean`, `hold` | Under **`<stem>.pgm`**: `A3200ProgramRemove("<stem>.ogm")` returns success but the added-program count does not change; `"<stem>.pgm"` removes it. A removal under a wrong name is silently ignored, so R7 (verify with the count) is required. |
| `A3200ProgramAdd` + `A3200ProgramAssociate` | `add-associate` | **Works.** 200k lines: add 19.3 s and 3.71 GB (19.33 kB per line, the same as a load), the task stays `idle`; associate to task 2 takes < 0.05 s and the task becomes `program_ready`. The compile can run ahead without a free task. |
| Is task 2 slower only with the bare header? | `taskspeed` | **No.** 100k galvo lines: task 1 1.399 ms per line, task 2 2.502 ms per line, **ratio 1.79 with the bare and with the real layer header** (identical times). |
| Which task parameters differ? (checklist item 2, Configuration Manager) | parameter files in `api/config` | Read from the `.prma` files instead of the Configuration Manager. In **every** parameter file of the controller (2021–2025, all objectives) task 1 is tuned and task 2 has the defaults: `MaxLookaheadMoves` 10000 / **100**, `ExecuteNumLines` 100 / **1**, `MotionUpdateRate` 48 / **1**, `DefaultCoordinatedSpeed` 12.5 / 50, `DefaultCoordinatedRampRate` 2000 / 500, `DefaultCoordinatedRampTime` 0.1 / 0.5 (task 1 / task 2; the Nikon 40x files differ slightly). `EnabledTasks` = 3, i.e. tasks 0–2: this is why task 3 is `inactive`. |
| Does the package loader (`ProgramRunner`) run every part? (P5, first half) | `runner` | **Yes.** 4 parts × 200k lines on tasks 1/2/1/2: every part ended at its last line, load 19.1 s per part, gaps **0.31–0.33 s**, the first part waited 20.5 s for its load, PC at 8.4 GB. Parts on task 2 ran 500.7 s, parts on task 1 279.6 s. |
| Is only the failed name blocked after a refused ASCII LOAD? | `sticky` (3 runs, the third after a restart) | **Yes, only the name.** In all three runs: the invalid program is refused ("Compiler Error: The program failed to compile."); a valid program of another name loads; **valid content under the failed name is refused again**; the first program loads again; the library loads. The probe at the start of the next run passed, so no global refusal remains. |
| Memory of the PC | `watch` | PC at most 13.8 GB (during the 400k compile, worker at most 7.3 GB). `A3200CallbackService.exe` at most 0.035 GB, `A3200AsciiInterface.exe` at most 0.053 GB: the 1.87 GB of session 1 did not recur. |
| INtime memory with two loaded full layers | `hold` | **Not answered.** The prompt took one line, so the pasted multi-line block of the INtime Explorer went into the next prompts. The copied block (`INtime.txt`, RT handle 0258, pool 512 MB, 122 MB used) is identical before and after; it is not the memory that holds the programs, or it was not refreshed. Practical result only: 2.06 M lines from `.ogm` loaded at the same time without an error. |
| .NET compile path of Motion Composer | `api` | **Found, not run.** `Aerotech.A3200.dll` 6.4.5.5 has `Aerotech.AeroBasic.Builder.Build(fileName[, BuildSettings])` and `BuildSource(...)`, returning `BuildResults` with `CompilerErrors`. The step's filter missed it (it only printed names containing "Compile"). `Controller.Reset()` and `Controller.LoadedPrograms` exist as well. |
| Library functions | `api` | `A3200Reset` is exported with the expected prototype; `A3200ProgramGetAddedPrograms` returns `A3200AddedProgram {name[128], associatedTasks}` (names and task association for R0); `A3200ProgramInitializeQueue` (queue mode, T126); `A3200ConfigurationCompilerOutputDirectoryGet/Set`. |

Recovery levels (T133):

| Level | Lab step | Result |
|---|---|---|
| R1: terminate `A3200AsciiInterface.exe` | `recover-ascii` | **Works and changes nothing else.** The CommService starts it again after 0.3 s, ASCII answers after 1.0 s, the LOAD probe passes. Tasks, added programs (2) and axes (enabled, homed, same position) are unchanged. Not tested: whether R1 clears a blocked name (there was no blocked state left to clear, see `sticky`). |
| R2: `~RESETCONTROLLER` | `reset` | **Works, but resets the machine state.** 7.9 s; ASCII and library usable right after. **All axes disabled and not homed**; the unpowered galvo drifted (A 0.043 mm, B 0.009 mm); the added programs went 2 → 0. Only between experiments, followed by enable, home and the setup initialisation (IFOV). |
| R3: `Restart-Service A3200CommService` | `restart-service` | **Not measured.** Refused: "Cannot open A3200CommService service on computer '.'" (PowerShell without administrator rights, or the service does not allow it). The manual restart of the A3200 software at 11:19 worked as usual. |

Further observations:

| Observation | Meaning |
|---|---|
| Session 1 wrote "every print so far ran on task 2". Wrong: `Experiment` loads every layer program on **task 1** (`run_program_as_task(part, task_id=1)`), the DOE log shows `PROGRAM 1 LOAD`. | The automated prints ran on the tuned task. The library loader is the first path that puts every second part on task 2. |
| The ASCII path loads every layer program under the **fixed name** `python_aerobasic_program.pgm` (T127). | Together with `sticky` this explains 2026-11-21: after the out-of-memory failure of one layer, every later layer was refused because it had the same name. The global refusal of 2026-11-24 ("Could not open AerParam.pgm" after an `.ogm` sent over ASCII) is a different state and was not reproduced. |
| 2 programs stayed added the whole day (also right after the restart at 11:19 and after many probe and `sticky` loads that were removed); after R2 the count was 0, after the next probe 1. | Probably the last program of each task stays added while it is associated with the task, even after `REMOVEPROGRAM`. Open: list the names (`A3200ProgramGetAddedPrograms`) in lab session 3. |
| The layer header (`LOOKAHEAD FAST`, `CRITICAL START`, …) does not change the task speed. | The limit is the task configuration (lookahead 100 moves, 1 line per execution cycle), not the program. The velocity profile at corners, and with it the dose, may differ between the tasks as well. |

### 6.3 Lab session 3 (2026-11-25, T153)

Three attempts, 14:01–14:23, folders `mains/lab_checks/program_loading_lab_20261125 - …` ("labrun3 failed",
"labrun3 again fail without system poli", "last lab run"). The maintainer restarted the PC between the
attempts; the second attempt ran without initialising the Femtika software. The folders are not versioned.

**Main finding: in every motion step the axes were disabled and not homed.** The `system` step reports
`enabled: False, homed: False` for all axes in all three attempts: in the first one still from the R2 reset of
session 2 (11:53, the A3200 processes were from 11:19), in the others after the PC restart. Only at 14:23, after
Motion Composer was opened, were the axes enabled and homed; no motion step ran after that. So the motion
results below say nothing about the loader.

| Question | Step | Result |
|---|---|---|
| Add-ahead on task 1 (T132) | `runner` (3×) | **Not answered.** Every compile and associate worked; the first part ended in a task error at line 6, its first motion line (`RAPID A0 B0`), each time. Matches the disabled axes. The runner did not report the error code (fixed for session 3b). |
| P5 with layer 68 | `layer-dry` (2×) | **Not answered**, same cause: task error at line 4 of the first part. The dry copy itself was as designed: layer 68 has 1 gate line, 1 `$AO` line and 2 stage lines (one start position), everything else is galvo. |
| T152 on the controller | `ascii-names` (2×) | **Not answered.** Every load was refused with "Compiler Error: The program file could not be opened". The execution copies were at a 191-character path (`programs\ascii_names\nfs_…`); the probe and `sticky` files in the same session folder (162–166 characters) loaded. Likely a path length limit of the ASCII interface. The print path copies to the home folder (about 50 characters), where loading always worked. Session 3b uses `~/nfs_lab`. |
| .NET compile path | `dotnet-build` (3×) | `Aerotech.AeroBasic.Builder.Build` is static and works (connected), 400k lines in 25.7 s, but **19.9 kB per line**, the same as the C library. The `.OGM` loads through the library in 12.0 s (30 µs per line) and is removed as `<stem>.pgm`. **Consequence:** no whole-layer compile within the budget; parts stay (T131 keeps the `.OGM` per part). |
| Programs that stay added | `system` | `ImmediateProgram0`, not associated with a task: the program of the immediate (ASCII) commands. Harmless; R0 leaves it. |
| Does R1 clear a blocked name? | `recover-blocked` | **No.** The name stays refused after the ASCII interface was restarted (back after 1.0 s). Fresh names per load (T152) are the remedy. |
| R3 as administrator | `restart-service` (2×) | **Works:** `Restart-Service` returns after 0.7 s, ASCII after 0.5–1.0 s, the library at once, LOAD probe passes; positions unchanged (the axes were already disabled, so the effect on enable/home is still unknown). |
| Library compile and load | all steps | **No failure** in any session: every compile through the library (C or .NET) and every `.OGM` load succeeded. |

Changes for session 3b (T153): every motion step stops unless all axes are enabled and homed; the runner reports
the decoded task error code; `ascii-names` copies to `~/nfs_lab`. The procedure is in
`docs/guides/PROGRAM_LOADING_LAB_TESTS.md`, section "Session 3b".

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

### 7.2 Plan after lab session 2 (2026-11-25)

What session 2 decides (the table "What session 2 decides" of the lab guide, applied):

| Result | Consequence |
|---|---|
| `sticky`: only the failed name is blocked | **T152 (new, first):** the ASCII path loads every program under a fresh name (as the library loader already does) and removes it under that name; the health check and R0 recognise the name pattern. This removes the cascade of 2026-11-21 (one failed layer → every later layer refused). |
| Task 2 is slower with both headers; task 1 is tuned, task 2 has defaults | **T132, decision (maintainer):** (a) align the task parameters of task 2 with task 1 in the active parameter file (Configuration Manager, backup first), or (b) **recommended:** print on task 1 only and compile ahead without a task (`A3200ProgramAdd`), then associate the next part to task 1 when the current one has completed (associate < 0.05 s, expected gap about 0.4 s). (b) needs no controller change, keeps one velocity profile for the whole structure and leaves task 2 free (z-line, T135). Until decided, the library loader is not used for real prints with alternation. |
| Add + Associate works and is fast | Enables (b) above: a `ProgramRunner` mode "single task, add ahead" (T129). |
| `.ogm` loads 2.6× faster with 1/13 of the memory; added as `<stem>.pgm` | **T131:** keep the `.OGM` the library writes anyway, load it for restarts and reprints; remove under `<stem>.pgm`. A whole-layer `.ogm` cannot be compiled through the C library within the budget (24.6 GB for layer 68). Whole layers without a split need the .NET path (below). |
| The .NET API has `Aerotech.AeroBasic.Builder.Build(fileName)` | **Lab session 3 (T153):** compile layer 68 with `Builder.Build` in a 64-bit process, record time and peak memory, and load the result through the library. At about 5.6 kB per line (Motion Composer) a full layer compiles in about 7 GB: then compile whole layers to `.ogm` ahead (build step) and load them in 48 s with 1.9 GB, without a split. |
| INtime memory not readable | Lab session 3, low priority: two full layers already fit. |
| R1 works without side effects | **T133:** R1 as an operator-confirmed level: terminate the ASCII interface, wait until it answers again (≤ 5 s), probe. |
| R2 disables and unhomes the axes | **T133:** R2 only between experiments, followed by enable, home and the setup initialisation; never during a print. |
| R3 not measured | Lab session 3 in an administrator PowerShell; until then the manual restart of the A3200 software. |

Order: T152 → T132 decision → T129 "single task, add ahead" (if (b)) and P5 with one real layer, laser
off, then with laser → default switch (R9) → T131 → T133 R1/R2 → lab session 3 (T153).

Status 2026-11-25: T152 done; T132 decided as (b) and implemented. `ProgramRunner` runs every part on
task 1: a worker compiles the next part with `A3200ProgramAdd` (no task) while the current part runs;
when the current part has completed, the task is stopped, the part removed, and the next part
associated (`A3200ProgramAssociate`) and started. At most two programs are added at a time. Execution
names use the T152 scheme with a session token, so a restart in a new process never reuses a name.
Expected gap per part: stop + remove + associate + start (lab session 2: associate < 0.05 s); to be
measured in lab session 3 (`runner` step). Lab session 3 is the next lab date (maintainer, option 2 of
2026-11-25): T152 on the real controller, the add-ahead runner, then P5.

## 8 Controller health check and recovery (maintainer idea 2026-11-24, T133)

Goal: our software detects a controller in a bad state before and during a print, and brings it back
in defined steps. Today the operator has to recognise this and restart the A3200 software by hand.

Implemented on 2026-11-24 (T133, partial): the health check and R0 in `nanofactorysystem/devices/aerotech/health.py`, called by `print_structure()` before every structure and after a failed layer, stored in `/logs/health`; `mains/controller_health.py`. R1–R3 follow after lab session 2. Lab session 2 (section 6.2): R1 works
without side effects; R2 works but disables and unhomes every axis; R3 was refused for lack of
administrator rights.

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
| R2 | Controller reset with the documented ASCII command `~RESETCONTROLLER` (the "Reset Controller" button of Motion Composer; `A3200Reset` of the library as alternative) | Axes disabled, home and IFOV/galvo settings possibly lost → enable axes, possibly home, re-initialise the setup | operator confirms on the console; homing only with the objective at a safe Z |
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
