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
`SUBSTRATE_LABEL` (or None), `USER`. Leave the powers (0.25 / 0.75 mW), the dwells (10 / 50 / 200 ms) and the
10 repetitions as they are.

## Run

```
cd "C:\Users\Nanofactory\Documents\Automated Nanofactory\Code Github\NanoFactorySystem_automated\mains"
..\.venv\Scripts\Activate.ps1
python -m lab_checks.power_switch_check --layout     # areas inside the drop?
python -m lab_checks.power_switch_check              # plane fit and print after the message boxes
```

## After the print

- Develop as usual, SEM image of every structure (all three fit in one 200 µm field of view at medium
  magnification; then one close-up per structure of the first three pairs and the reference lines).
- Send the experiment folder (or only `experiment.h5` and the SEM images) and `checklist.txt`.

## What it decides

| Result | Consequence |
|---|---|
| no transition zone | D9: no dwell needed, `DWELL_AFTER_POWER_S = 0` stays |
| transition at the start of segments, gone with dwell X | `DWELL_AFTER_POWER_S = X` in `mains/parametertest/common.py` |
| the end of a segment already has the new width | new todo: synchronise the power change, then repeat T148 |
