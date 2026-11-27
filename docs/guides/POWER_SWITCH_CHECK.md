# Lab guide: power switch check (T148)

Background and evaluation: `docs/design/POWER_SWITCH_CHECK.md`. About 45 minutes plus the SEM.

## Before the lab

1. `git pull` on `main_HR`, restart the A3200 software, start the Femtika software, enable and home all axes.
2. Read §2 of the work order and answer its three questions (a)–(c) from the A3200 help 6.04 on the lab PC
   (index: "Motion Command Buffering", `$AO`, `DWELL`, `SYNCCALL`, `CRITICAL START`, `WAIT MOVEDONE`).
   Write the answers into `checklist.txt` in the experiment folder afterwards. **If the help says that
   `$AO` runs ahead of buffered motion and nothing in the block header flushes the buffer, print anyway:**
   the pattern shows the effect, and the fix is planned from the result.

## Settings

In `mains/lab_checks/power_switch_check.py`, SETTINGS block: `RESIN_EDGES` and `CENTER` of the current drop,
`SUBSTRATE_LABEL` (or None), `USER`, `REPETITIONS` (5-10, default 6). Leave the powers (0.25 / 0.75 mW), the
dwells (5 / 20 / 100 / 500 ms), the line length (50 µm, switch at the middle) and the z levels (-1 … +1 µm in
0.2 µm steps) as they are.

## Run

```
cd "C:\Users\Nanofactory\Documents\Automated Nanofactory\Code Github\NanoFactorySystem_automated\mains"
..\.venv\Scripts\Activate.ps1
python -m lab_checks.power_switch_check --layout     # areas inside the drop?
python -m lab_checks.power_switch_check              # plane fit and print after the message boxes
```

## After the print

- Develop as usual, SEM image of every grid cell (the five 50 µm lines of a cell fit in one 60 µm field), then
  a close-up of x = 0 of every line (tilted view if possible: the lines are 2 µm high walls).
- Send the experiment folder (or only `experiment.h5` and the SEM images) and `checklist.txt`.

## What it decides

| Result | Consequence |
|---|---|
| switch at x = 0, no transition zone on any line | D9: no dwell needed, `DWELL_AFTER_POWER_S = 0` stays |
| transition after x = 0, gone on the dwell lines from dwell X on | `DWELL_AFTER_POWER_S = X` (with `WAIT MOVEDONE` before `$AO`) in `mains/parametertest/common.py` |
| line without pause: transition already before x = 0 | `$AO` runs ahead of the motion: new todo, power changes need `WAIT MOVEDONE` |
| point at x = 0 on the dwell lines | laser on during `DWELL`; note it (F40) |
