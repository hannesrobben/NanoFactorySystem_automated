# Work order: power switch inside a running program (T148, decision D9)

Status: work order for the lab check, 2026-11-26; test pattern redesigned 2026-11-27 (maintainer). Todo: T148. Lab script: `mains/lab_checks/power_switch_check.py`;
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
coordinated motion is intend## 3 Test pattern (maintainer decisions 2026-11-27, replaces the line pairs of 2026-11-26)

The line pairs with one IFOV block per segment did not test a power change inside running motion: between two
segments the full block header (`IFOV OFF/ON`, `RAPID`s, configuration) ran with the laser off, an implicit pause
of unknown length. The pattern was redesigned:

One IFOV experiment, Zeiss 63x, `REPETITIONS` (5-10, default 6) grid cells in two rows, each with the same line
group (`PowerSwitchLines`):

- **one line:** 50 µm along +x, x = -25 … 0 µm with 0.25 mW, x = 0 … +25 µm with 0.75 mW; the power command sits
  between the two `LINEAR` moves, so the switch is at x = 0 on every line;
- **five lines, 5 µm apart:** the first switches without a pause (`LINEAR` → `$AO` → `LINEAR`); the others wait
  for the motion and dwell (`LINEAR` → `WAIT MOVEDONE X Y A B` → `$AO` → `DWELL d` → `LINEAR`) with
  d = 5 / 20 / 100 / 500 ms;
- **z levels:** every line on 11 levels from -1 to +1 µm around the fitted interface (0.2 µm steps), one layer
  program (one IFOV block with all five lines) per level, so each line becomes a small wall;
- **before every line:** `WAIT MOVEDONE`, `$AO` low power, `DWELL 0.5 s` where the previous motion ended (end of
  the previous line, centre before the first), so the first half always starts with a settled low power;
- `LOOKAHEAD FAST` is removed from the block header (no function since 6.01, §2); everything else is the header
  of the parameter-test blocks, with `GALVO LASEROVERRIDE A AUTO`.

Points written while the line stands still (in a `DWELL`) are part of the result and are not moved away
(maintainer). A variant with the laser gated explicitly is F40.

## 4 Evaluation (SEM, or camera if the widths differ enough)

Along every line, compare the width around x = 0 with the middle of both halves (x = ±12.5 µm):

| Observation | Meaning | Consequence |
|---|---|---|
| line without pause: transition starts **before** x = 0 | `$AO` runs ahead of the buffered motion (§2); its lead ≈ length × IFOV speed | power changes in the parameter tests need `WAIT MOVEDONE` before `$AO` (new todo, decision D9) |
| line without pause: transition starts at x = 0 and extends over L after it | the power command keeps the order; the attenuator settles in ≈ L / v (IFOV speed of the 63x) | compare with the dwell lines |
| dwell lines: transition zone after x = 0 disappears from dwell d on | settling time ≤ d | `dwell_after_power_s` = d (with `WAIT MOVEDONE` before `$AO`) |
| no transition zone on any line, switch at x = 0 | `$AO` in order and settled in time | `dwell_after_power_s = 0` (D9) |
| point / bulge at x = 0 on the dwell lines | the laser stays on during `DWELL` (`AUTO`) | note it; F40 tests the explicit laser gate |

The 11 z levels show the same transition on every level (and the wall height shows the voxel length of both
powers); the repetitions give the spread.

The result and the value of `dwell_after_power_s` go into WORKLOG.md and `TEST_PRINT_PTD01.md` §12 (D9);
`DWELL_AFTER_POWER_S` in `mains/parametertest/common.py` is set from it.

`mains/parametertest/common.py` is set from it.

## 5 Sources

- Aerotech, "What's new in A3200 6.01" (blog, 2017-08-18), http://blog.aerotechmotioncontrol.com/2017/08/18/whats-new-in-a3200-6-01/ (via search index)
- Aerotech help, "AeroScript equivalents of AeroBasic commands for the A3200", https://help.aerotech.com/automation1/Content/AeroScript-Equivalents-of-AeroBasic-A3200.htm
