# Work order: power switch inside a running program (T148, decision D9)

Status: work order for the lab check, 2026-11-26. Todo: T148. Lab script: `mains/lab_checks/power_switch_check.py`;
guide: `docs/guides/POWER_SWITCH_CHECK.md`. Pattern: `nanofactorysystem/testprint/power_switch.py`.

## 1 Question

The parameter tests change the laser power inside one layer program: every IFOV block starts with
`$AO[0].A=<value>` (`SET_POWER`), optionally followed by `DWELL dwell_after_power_s` (`ParameterFieldStructure`).
`$AO` only writes the analog output; the controller does not wait for the attenuator. Two things can go wrong:

1. **The attenuator settles slower than the next line starts.** The beginning of the line after a switch is
   written with a power between the old and the new value. A dwell after `$AO` helps.
2. **The power command runs before the preceding motion has finished.** Then the end of the previous line is
   already written with the new power. A dwell does not help (it may even run at the wrong time).

The maintainer has seen motion blended over a command before. So the program structure is checked against the
A3200 documentation first (T148 done-when), then the print shows which of the two effects exists.

## 2 What the documentation says (research 2026-11-26)

Found (web, secondary sources; the A3200 help 6.04 on the lab PC is the primary source to confirm):

- **Motion buffering since A3200 6.01.** The release notes of 6.01 state that the controller buffers the
  AeroBasic motion commands `RAPID`, `LINEAR`, `CW`, `CCW`, `BEZIER`, `MOVEDELAY` and `DWELL` automatically in
  certain modes, that **other commands are not part of this buffer and can be executed ahead of the buffered
  motion commands**, and that global, task and program variables are not synchronised to motion (virtual
  registers / binaries recommended). For an action synchronised to a motion sequence the notes name `SYNCCALL`.
  (Aerotech blog "What's new in A3200 6.01", 2017; the page itself was not reachable, the text is from the
  search index.)
- `$AO` is such a non-motion command. In AeroScript (Automation1) it became `AnalogOutputSet()`; the
  synchronised form there is the `sync` keyword (Aerotech help, "AeroScript equivalents of AeroBasic commands
  for the A3200").
- `LOOKAHEAD FAST` has no function since 6.01 (maintainer research 2026-11-22, T126).
- `DWELL` itself is buffered: it pauses the motion queue, not the execution of a following `$AO`.

Consequences for the program structure:

- In the current blocks the order is `$AO` → (`DWELL`) → IFOV block with its `LINEAR` moves. If `$AO` is
  executed ahead of the buffered motion, it changes the power while the **previous block** is still moving
  (effect 2), and a `DWELL` after it does not delay the `$AO` of the next block either.
- Each block also starts with the full IFOV configuration (`CRITICAL START`, `IFOV OFF/ON`, ramps). Whether
  `CRITICAL START`, `IFOV OFF` or `WAIT MODE AUTO` force the controller to finish the buffered motion before
  the next non-motion command is **not documented in the sources found**.

To confirm in the A3200 help 6.04 on the lab PC before the print (10 minutes, note the answers in the
checklist): index entries "Motion Command Buffering" / "Lookahead", `$AO`, `DWELL`, `SYNCCALL`,
`CRITICAL START`, `WAIT MOVEDONE`, `VELOCITY ON`. Questions: (a) is `$AO` executed ahead of buffered motion in
`VELOCITY ON`; (b) does `IFOV OFF` or `CRITICAL START/END` flush the motion buffer; (c) is `WAIT MOVEDONE A B`
(or `WAIT INPOS`) before `$AO` the documented way to keep the order, and what does it cost (stop of the
coordinated motion is intended here, the laser gate is off between blocks).

## 3 Test pattern (maintainer decision 2026-11-26: lines only)

One IFOV experiment, Zeiss 63x, writing plane z = 0, three structures in a 1 × 3 grid, one per dwell level
(10 / 50 / 200 ms). Each structure (`PowerSwitchLines`):

- 10 line pairs, pairs 6 µm apart. Each line has four 6 µm segments along +x with 0.25, 0.75, 0.25, 0.75 mW;
  **every segment is its own IFOV block starting with `$AO`**, built with `IFOV_Lines` like the blocks of the
  parameter tests;
- the first line of a pair switches without a pause, the second line **2 µm below** is written the same way
  with `DWELL <dwell>` right after each `$AO`;
- two reference lines (0.25 and 0.75 mW constant) 4 µm below the last pair.

Every power change happens in both directions (low → high, high → low), at three positions per line.

## 4 Evaluation (SEM, or camera if the widths differ enough)

Per segment boundary, compare the width at the end of a segment, at the start of the next one and in the
middle of both against the reference lines:

| Observation on the line without dwell | Meaning | Consequence |
|---|---|---|
| no transition zone | the attenuator settles before the next line starts | `dwell_after_power_s = 0` (D9) |
| start of the next segment has the old width over a length L, the dwell line does not | settling time ≈ L / v (IFOV speed of the 63x) | `dwell_after_power_s` = the shortest dwell level without the zone |
| **end** of the previous segment already has the new width | `$AO` runs ahead of the buffered motion (§2) | a dwell does not help: synchronise the power change (`WAIT MOVEDONE` before `$AO` or `SYNCCALL`) in a new todo, repeat T148 |

The result and the value of `dwell_after_power_s` go into WORKLOG.md and `TEST_PRINT_PTD01.md` §12 (D9);
`DWELL_AFTER_POWER_S` in `mains/parametertest/common.py` is set from it.

## 5 Sources

- Aerotech, "What's new in A3200 6.01" (blog, 2017-08-18), http://blog.aerotechmotioncontrol.com/2017/08/18/whats-new-in-a3200-6-01/ (via search index)
- Aerotech help, "AeroScript equivalents of AeroBasic commands for the A3200", https://help.aerotech.com/automation1/Content/AeroScript-Equivalents-of-AeroBasic-A3200.htm
