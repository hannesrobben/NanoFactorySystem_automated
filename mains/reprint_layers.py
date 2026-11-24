"""Print the missing layers of a structure of a stored experiment (interim solution, T125).

The DOE print of 2026-11-21 (``surface_16bit``) printed only 16 of 73 layers: the controller
refused to load every layer program with more than about 80 000 lines ("out of memory" or "!"),
and the experiment went on with the next layer. ``restart_experiment.py`` does not print a failed
layer that lies behind a printed one (since T128 a failed layer stops printing, and the restart prints
it again). This script prints such layers now:

- the layers come from the experiment file (default: every layer without a successful print),
- they are printed in the order of the drop direction (DOWN: the highest missing layer first, as in
  the original print; the socket below is already there),
- every layer program with more than ``MAX_PROGRAM_LINES`` lines is split into parts before the first
  layer is printed; if one cannot be split, nothing is printed. The parts are loaded and run one after
  another; each part carries the whole setup of the layer program (IFOV configuration, modes, power,
  feed rates, move to the layer start, IFOV ON) and the laser is off at every cut,
- progress, captures and the controller log go into the same experiment file (a new session).

Before printing, check:

- The sample has not been moved or remounted since the original print. The programs hold the
  absolute stage coordinates of the original plane fit; no new plane fit is done.
- You accept the physical consequences: with drop direction DOWN the missing middle layers are
  written now, after the socket below them has been printed.

Usage (``mains/`` as working directory):

    python reprint_layers.py --plan     # show the layers and line counts, no hardware
    python reprint_layers.py            # show the plan, ask, then print on the lab hardware
"""
import argparse

from nanofactorysystem.aerobasic.programs.split import MAX_PROGRAM_LINES
from nanofactorysystem.experiment import Experiment
from nanofactorysystem.reprint import format_plan, reprint_plan

# ---------------------------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------------------------
# Experiment folder (the one containing experiment.h5). For the DOE print of 2026-11-21 it is
# <dataRoot of Hannes>\DOE_circle_V1\DOE_circle_V1-B_<YYYYMMDD-HHMM> on the lab PC.
EXP_PATH = r"C:\Users\Nanofactory\Documents\Femtika_Experiment\Hannes\DOE_circle_V1\DOE_circle_V1-B_20261121-2020"
# Structure whose layers are printed
STRUCTURE = "surface_16bit"
# None: every layer without a successful print; or a list of layer ids, e.g. [70, 69, 68]
LAYER_IDS = None
# A layer program with more lines is printed in parts (PROGRAM LOAD fails above about 80 000 lines)
# MAX_PROGRAM_LINES_SETTING = MAX_PROGRAM_LINES
MAX_PROGRAM_LINES_SETTING = 20_000
# Ask on the console before the printing starts
ASK_BEFORE_PRINT = False


def plan(path=EXP_PATH, structure=STRUCTURE, layer_ids=LAYER_IDS, max_program_lines=MAX_PROGRAM_LINES_SETTING):
    """ Return the reprint plan as text (reads the experiment file only, no hardware). """

    return format_plan(reprint_plan(path, structure, layer_ids, max_program_lines), structure)


def reprint(path=EXP_PATH, structure=STRUCTURE, layer_ids=LAYER_IDS, max_program_lines=MAX_PROGRAM_LINES_SETTING,
            backend=None, ask=ASK_BEFORE_PRINT):
    """ Print the selected layers of ``structure`` in the stored experiment ``path``.

    Parameters
    ----------
    path : str
        Experiment folder.
    structure : str
        Structure name.
    layer_ids : list of int, optional
        Layers to print; default: every layer without a successful print.
    max_program_lines : int or None
        Programs with more lines are printed in parts.
    backend : optional
        Hardware backend (None: lab hardware; "dummy" or a DummyBackend for a dry run).
    ask : bool
        Ask on the console before printing.

    Returns
    -------
    list of int
        The printed (or attempted) layers.
    """

    print(plan(path, structure, layer_ids, max_program_lines))
    if ask and input("Print these layers now? [yes/no] ").strip().lower() not in ("y", "yes", "j", "ja"):
        print("Nothing printed.")
        return []
    # note kontrollieren qr code und abspeichern der uuid - vergleichen ob gleich wie in experiment.h5 - vergleich alt neu
    with Experiment(**Experiment.parameters_from_dictionary(path), backend=backend,
                    max_program_lines=max_program_lines) as experiment:
        return experiment.reprint_layers(structure, layer_ids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", action="store_true", help="only show the layers that would be printed")
    parser.add_argument("--path", default=EXP_PATH, help="experiment folder (default: EXP_PATH)")
    parser.add_argument("--structure", default=STRUCTURE, help="structure name (default: STRUCTURE)")
    args = parser.parse_args()
    if not args.path:
        parser.error("set EXP_PATH in the SETTINGS block or pass --path")
    if args.plan:
        print(plan(args.path, args.structure))
    else:
        reprint(args.path, args.structure)
