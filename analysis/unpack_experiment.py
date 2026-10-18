##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Unpack an experiment file into PNG/CSV/TXT/JSON files.

Set the variables below and run the script (from any working directory),
or use the command line: ``python unpack_experiment.py <experiment.h5> <output folder> [--zip] …``
"""
import sys
from pathlib import Path

# ----------------------------------------------------------------------------- settings
SOURCE = r"C:\Users\<user>\Documents\Femtika_Experiment\<user>\<substrate>\<experiment folder>\experiment.h5"
TARGET = r"C:\Users\<user>\Desktop\unpacked_experiment"
OVERWRITE = False   # replace the content of an existing output folder
ARCHIVE = False     # also write <TARGET>.zip
ZDC = False         # also export every capture as SciDataContainer (.zdc)
CSV_STYLE = "de"    # "de": ';' and decimal comma (German Excel); "en": ',' and decimal point
# --------------------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_analysis import unpack_experiment  # noqa: E402
from experiment_analysis.__main__ import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(main(["unpack", *sys.argv[1:]]))
    result = unpack_experiment(SOURCE, TARGET, overwrite=OVERWRITE, archive=ARCHIVE, zdc=ZDC, csv_style=CSV_STYLE)
    print(f"Unpacked into {result}")
