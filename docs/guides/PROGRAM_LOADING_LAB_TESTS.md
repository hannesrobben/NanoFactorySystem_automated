# Lab tests: loading layer programs through the A3200 library (T129, T134)

Session 1 (2026-11-24) is described from "Session 1" on; its results are in section 6 of
`docs/design/PROGRAM_LOADING.md`. Session 2 (T134) follows here.

## Session 2 (T134)

Goal: answer what session 1 left open:
- the `sticky` test after a real restart;
- loading our own `.ogm` under a new name;
- `A3200ProgramAdd`/`Associate`;
- why task 2 is slower (T132);
- the INtime memory with two full layers;
- the compile path of Motion Composer (.NET);
- the recovery levels R1–R3 for the health check (T133).

Plan about 75 minutes. The session needs one restart of the A3200 software at the start, and possibly
one more after step 11.

### Safety

- No step switches the laser on. `ogm-clean`, `add-associate`, `hold`, `api`, `sticky` and
  `recover-ascii` move nothing.
- `taskspeed` moves only the galvo (A/B, at most ±0.05 mm, laser gate forced off), like `cycle`.
  Close the shutter anyway.
- `reset` (R2) and `restart-service` (R3) can disable the axes. A Z axis without a brake may move
  when it is disabled.
  - Before these steps: move the objective to a safe Z and close the shutter.
  - Afterwards: enable the axes and home them as after a normal start of the A3200 software.
  - Both steps ask you to type a confirmation word.
- Motion Composer stays closed, except in the preparation.

### Preparation

1. **Restart the A3200 software.** In session 1 it was not restarted: the processes had the same IDs
   as in the morning. Step 1 now checks this. It warns if the A3200 processes are older than 60
   minutes or if LOAD over ASCII is refused.
2. If the `.ogm` of layer 69 does not exist: compile layer 69 once in Motion Composer, unload it there
   and close Motion Composer.
3. Open PowerShell **as administrator** (needed for step 12):
   ```
   cd "C:\Users\Nanofactory\Documents\Automated Nanofactory\Code Github\NanoFactorySystem_automated"
   git pull
   .venv\Scripts\Activate.ps1
   cd mains\lab_checks
   $layer = "C:\Users\Nanofactory\Documents\Femtika_Experiment\Hannes\DOE_circle_V1\DOE_circle_V1-B_20261121-2020\structures\surface_16bit\programs\program_surface_16bit.068.pgm"
   $ogm68 = $layer -replace '\.pgm$', '.ogm'
   $ogm69 = $ogm68 -replace '\.068\.', '.069.'
   ```

### Steps, in this order

| # | Command | Time | Answers |
|---|---|---|---|
| 1 | `python program_loading_lab.py system` | 1 min | Start time of the A3200 processes (restart check), added programs (expected 0), axis states, **ASCII LOAD probe** with a tiny program. If it warns: restart the software and repeat. |
| 2 | `python program_loading_lab.py watch` in a **second** window, until step 9 | – | Memory timeline |
| 3 | `python program_loading_lab.py api` | 2 min | Copies the A3200 headers, the controller parameter files and `AerParam.pgm` into `<session>/api`. Lists the reset, added-program, associate and compiler functions and the `A3200AddedProgram` struct. Dumps the public .NET API (`dotnet_64bit.txt`, `dotnet_32bit.txt`). |
| 4 | `python program_loading_lab.py ogm-clean --file $layer --lines 400000` | 3 min | Compiles 400k lines of layer 68 through the library (writes the `.OGM`) and removes the program. Then loads that `.OGM` and a renamed copy, both under names never used before. Records the load time and memory of each, and **which name removes each program** (`removed_as`). |
| 5 | `python program_loading_lab.py add-associate` | 1 min | `A3200ProgramAdd` (compile without a task) and `A3200ProgramAssociate` (bind to task 2): time, memory, and which name works |
| 6 | `python program_loading_lab.py hold --file $ogm68 --file2 $ogm69` | 5 min | Loads the full layers 68 and 69 on tasks 1 and 2 at the same time. The script asks three times for the INtime memory (before, loaded, after removal). Read it in the INtime tool (tray icon "INtime Status" or INtime Explorer: memory of the node) and type what you see. |
| 7 | `python program_loading_lab.py taskspeed --axes-safe` | 15 min | Runs the same 100k-line galvo program on task 1 and task 2, first with the bare header and then with the header of a real layer (`SECONDS`, `METRIC`, `LOOKAHEAD FAST`, `CRITICAL START`, …). Reports the time per line and the ratio task 2 / task 1. |
| 8 | Configuration Manager → task parameters of task 1 and task 2: note every value that differs (checklist item 2) | 5 min | Cause of T132 |
| 9 | stop `watch` with Ctrl+C | – | – |
| 10 | `python program_loading_lab.py sticky` | 2 min | Starts with a probe and stops if LOAD over ASCII is already refused. Then loads a valid program, an invalid program, a valid program of another name, valid content under the failed name, the first program again, and finally a program through the library. Each reply waits at most 60 s. **This leaves the ASCII interface refusing.** |
| 11 | `python program_loading_lab.py recover-ascii --confirm` (type `R1`) | 3 min | **R1:** terminates `A3200AsciiInterface.exe`. Does the A3200 service start it again, how fast, and does LOAD over ASCII work afterwards? |
| 12 | If step 11 did not end with a working LOAD probe: `python program_loading_lab.py restart-service --confirm` (type `RESTART`; administrator) | 3 min | **R3:** restarts `A3200CommService`. Time until ASCII and the library work again; axis states before and after. If it fails, restart the A3200 software as usual. |
| 13 | optional, objective at a safe Z: `python program_loading_lab.py reset --confirm` (type `RESET`) | 3 min | **R2:** `A3200Reset` through the library, if the headers declare it. Which states survive: axis enable, home, position, task states, added programs? |
| 14 | enable and home the axes as usual, then `python program_loading_lab.py system` | 2 min | Final state |

Send back the session folder `program_loading_lab_<date>` (including `api/`), `checklist.txt`, and the
console output.

### Manual checklist for session 2 (`checklist.txt` in the session folder)

1. A3200 software version (Motion Composer, Help → About).
2. Configuration Manager:
   - every task parameter whose value differs between task 1 and task 2 (name, value on task 1,
     value on task 2);
   - the parameter that enables tasks (why is task 3 inactive?).
3. Configuration Manager: compiler settings (output directory, include paths), if any.
4. INtime: the memory configured for the INtime node (INtime Configuration → node), and the values
   you typed in step 6.
5. Step 7: did the galvo motion look or sound different on task 2?
6. Steps 11–13: anything Motion Composer or the A3200 tray icon showed (errors, axis faults).

### What session 2 decides

| Result | Consequence |
|---|---|
| The `.OGM` of our own compile loads fast under a new name, and so does the renamed copy | T131: compile once, load the `.ogm` while printing |
| The name in `removed_as` | The name the loader uses to remove programs (T127/T129) |
| Add + Associate works and is fast | Prefetch can compile ahead without a free task |
| The INtime memory drops a lot with two full layers | Limit on the parts loaded at the same time |
| Task 2 slower only with the bare header | The generated programs already set the needed modes; T132 closes after a check with a real part |
| Task 2 slower with both headers | A task parameter differs (checklist item 2) → align the configuration (maintainer decision) |
| The .NET dump shows a compile method | Lab session 3: compile layer 68 through .NET and compare the memory with the C library |
| `sticky`: only the failed name is blocked | The ASCII fallback uses a fresh name per load |
| R1 restores LOAD over ASCII | The health check (T133) can repair the ASCII interface without a restart |
| R2/R3 keep home and positions | Recovery is possible during an experiment; otherwise only between experiments, with homing |

## Session 1 (2026-11-24)

These tests collect the data the library loader (work order `docs/design/PROGRAM_LOADING.md`) needs:
memory per program line, load time, whether a loaded program survives the end of the loading
process, how alternating tasks 1 and 2 behaves, and why the ASCII interface keeps refusing after
one failed load. Run them in one session; plan about 45 minutes plus two restarts of the A3200
software.

Script: `mains/lab_checks/program_loading_lab.py` (standard library only). All steps write into
one session folder `mains/lab_checks/program_loading_lab_<date>/` (`log.txt`, `results.jsonl`,
CSV files). **Send that folder back**, together with the answers of the manual checklist.

### Safety

- No step switches the laser on. Load-only steps (`ladder`, `precision`, `ogm`, `sticky`) move
  nothing.
- `cycle` runs synthetic programs that move only the galvo axes A and B by at most ±0.05 mm, with
  the laser gate forced off (`GALVO LASEROVERRIDE A OFF`). It uses no stage axis and no `$AO`
  power. Close the shutter anyway.
- The script loads only on idle tasks. Tasks 1 and 2 are usable; task 3 is `inactive` on this
  controller.

### Preparation

1. Restart the A3200 software. The ASCII interface is still in the refusing state of 2026-11-24.
2. Close Motion Composer. It held 3.2 GB in the last test and would distort the memory numbers.
   Step 3b is the exception: there you open it on purpose.
3. Open PowerShell **as administrator**:
   ```
   cd "C:\Users\Nanofactory\Documents\Automated Nanofactory\Code Github\NanoFactorySystem_automated"
   git pull
   .venv\Scripts\Activate.ps1
   cd mains\lab_checks
   ```
4. Set the layer file once:
   ```
   $layer = "C:\Users\Nanofactory\Documents\Femtika_Experiment\Hannes\DOE_circle_V1\DOE_circle_V1-B_20261121-2020\structures\surface_16bit\programs\program_surface_16bit.068.pgm"
   $ogm = $layer -replace '\.pgm$', '.ogm'
   ```

### Steps, in this order

| # | Command | Time | Answers |
|---|---|---|---|
| 1 | `python program_loading_lab.py system` | 1 min | RAM and commit limit (RAM + page file); A3200 processes with bitness, memory, parent and command line; services (is `A3200AsciiInterface.exe` a service?); task states 1–4; number of programs added on the controller |
| 2 | `python program_loading_lab.py watch` in a **second** PowerShell window, left running until step 6 | – | Memory timeline of the PC, the A3200 processes and every Python process |
| 3 | `python program_loading_lab.py ladder --file $layer` | 5–10 min | Load time and peak memory for the first 50k, 100k, 200k, 400k and 800k lines of layer 68, each in a fresh worker process. Also: is the memory freed by `A3200Disconnect` or only when the process ends? Does the program stay loaded after the worker has exited? Does `A3200ProgramRemove` remove it (added-program count)? Sizes that would exceed the budget (22 GB for the whole PC) are skipped automatically. |
| 3b | optional: in Motion Composer, compile and load layer 68 on task 2 by hand while `watch` runs, then unload and close Motion Composer | 3 min | Memory of Motion Composer for the same file (comparison) |
| 4 | `python program_loading_lab.py precision` | 2 min | The same 200k-line synthetic program with 10 decimals, 5 decimals and trimmed numbers: do shorter numbers lower memory and load time? (Input for the optimiser T130.) |
| 5 | `python program_loading_lab.py ogm --file $ogm` | 1–3 min | Can the library load Motion Composer's compiled `.ogm` directly? If so, programs could be compiled ahead of the print. |
| 6 | `python program_loading_lab.py cycle --axes-safe` | 6–8 min | The planned operation, dry: 4 parts of 200k lines alternate between tasks 1 and 2, and the next part is loaded while the current one runs. Records the gap between two parts (target: about 0 s), whether every part ends at its last line, and the memory timeline (`cycle_memory.csv`). |
| 6b | optional: `python program_loading_lab.py cycle --axes-safe --lines 600000 --parts 3` | 10–15 min | The same near the planned part size (refused automatically if over budget) |
| 7 | stop `watch` with Ctrl+C | – | – |
| 8 | `python program_loading_lab.py sticky` (run this step last: it leaves the ASCII interface refusing every LOAD) | 1 min | After one refused `PROGRAM LOAD` over ASCII: does a valid program of another name still load? Does valid content under the failed name load? Does the library still load while ASCII refuses? |
| 9 | restart the A3200 software | – | Leaves the ASCII interface usable for the next user |

If a step stops with "Task … is not idle": stop the task in Motion Composer (or restart the A3200
software) and repeat the step. The other results are kept, because every step appends to the
session folder.

### Manual checklist (write the answers into `checklist.txt` in the session folder)

1. A3200 software version (Motion Composer, Help → About).
2. Configuration Manager: the value of the task parameter that enables tasks (e.g. `EnabledTasks`).
   Why is task 3 `inactive`? Do not change it.
3. Configuration Manager: compiler settings, if any (e.g. compiler output directory).
4. Task Manager → Performance → Memory: installed RAM, "Committed" (limit) and the page file size.
5. Is `A3200AsciiInterface.exe` listed as a Windows service (`services.msc`)? If it is, after
   step 8 restart only that service and run `python library_load_check.py ascii-load --file <a
   small .pgm> --task 2` once more: does a restart of the interface alone clear the refusals?
6. During step 6, the galvo stops between parts: audible or visible?

### What the results decide

| Result | Consequence for the loader |
|---|---|
| Peak memory per line (ladder) | Maximum part size: `max_lines = compile budget / (kB per line × 1.2)` |
| Memory freed only at process exit | One worker process per load, which is the plan |
| Program gone after the worker exits | The worker must stay alive until the part has run (one worker per task) |
| Remove does not lower the added-program count | The name passed to remove must change (T127) |
| `.ogm` loads through the library | Compile ahead of time (during the build or before the print) and load only `.ogm` files |
| Gap > 1 s in the cycle | Prefetch timing or the start path has to change |
| Shorter numbers lower memory | The optimiser (T130) goes before the loader |
| Sticky refusal only for the failed name | Use a fresh program name per load on the ASCII fallback path |
