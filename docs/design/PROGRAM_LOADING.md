# Program loading through the A3200 library within a memory budget (T129) — work order

Status: draft of 2026-11-24. The requirements below come from the maintainer. The open points are
decided by the lab tests in `docs/guides/PROGRAM_LOADING_LAB_TESTS.md`; their results are entered
in section 6 before implementation starts.

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

| Question | Lab step | Result |
|---|---|---|
| Memory per line and load time vs. program size (linear?) | `ladder` | open |
| Is memory freed by `A3200Disconnect`, or only at process exit? | `ladder` | open |
| Does a loaded program survive the end of the loading process? | `ladder`, `cycle` | open |
| Does `A3200ProgramRemove(<file name>)` remove it (added-program count)? | `ladder`, `cycle` | open |
| Do shorter numbers lower memory or load time? | `precision` | open |
| Can the library load a precompiled `.ogm`? | `ogm` | open |
| Gap between two parts with prefetch on the other task | `cycle` | open |
| Memory of the PC during a cycle with two loaded programs | `cycle`, `watch` | open |
| Is only the failed program name blocked after a refused ASCII LOAD? | `sticky` | open |
| Why is task 3 inactive? Is the ASCII interface a service that can be restarted alone? | checklist | open |

## 7 Acceptance

- A DOE layer of 1.25 M lines prints with the laser off on the work PC:
  - every part ends at its last line;
  - the PC stays within the budget during the whole layer (memory log);
  - the gaps between the parts are below 1 s.
- `python -m pytest` passes. The dummy backend covers task alternation, the budget split and the
  stop on failure.
- The golden command logs change only where R1/R7 require it, and deliberately.
