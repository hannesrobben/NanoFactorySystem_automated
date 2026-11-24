# Lab tests: loading layer programs through the A3200 library (T129)

These tests collect the data the library loader (work order `docs/design/PROGRAM_LOADING.md`) needs:
memory per program line, load time, whether a loaded program survives the end of the loading
process, how alternating tasks 1 and 2 behaves, and why the ASCII interface keeps refusing after
one failed load. Run them in one session; plan about 45 minutes plus two restarts of the A3200
software.

Script: `mains/lab_checks/program_loading_lab.py` (standard library only). All steps write into
one session folder `mains/lab_checks/program_loading_lab_<date>/` (`log.txt`, `results.jsonl`,
CSV files). **Send that folder back**, together with the answers of the manual checklist.

## Safety

- No step switches the laser on. Load-only steps (`ladder`, `precision`, `ogm`, `sticky`) move
  nothing.
- `cycle` runs synthetic programs that move only the galvo axes A and B by at most ±0.05 mm, with
  the laser gate forced off (`GALVO LASEROVERRIDE A OFF`). It uses no stage axis and no `$AO`
  power. Close the shutter anyway.
- The script loads only on idle tasks. Tasks 1 and 2 are usable; task 3 is `inactive` on this
  controller.

## Preparation

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

## Steps, in this order

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

## Manual checklist (write the answers into `checklist.txt` in the session folder)

1. A3200 software version (Motion Composer, Help → About).
2. Configuration Manager: the value of the task parameter that enables tasks (e.g. `EnabledTasks`).
   Why is task 3 `inactive`? Do not change it.
3. Configuration Manager: compiler settings, if any (e.g. compiler output directory).
4. Task Manager → Performance → Memory: installed RAM, "Committed" (limit) and the page file size.
5. Is `A3200AsciiInterface.exe` listed as a Windows service (`services.msc`)? If it is, after
   step 8 restart only that service and run `python library_load_check.py ascii-load --file <a
   small .pgm> --task 2` once more: does a restart of the interface alone clear the refusals?
6. During step 6, the galvo stops between parts: audible or visible?

## What the results decide

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
