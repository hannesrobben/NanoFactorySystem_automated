##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Command line: ``python -m experiment_analysis <command> …`` (run from the ``analysis`` folder).

Commands:

- ``unpack <experiment.h5 or folder> <output folder> [--zip] [--zdc] [--overwrite] [--csv en]``
- ``info <experiment.h5 or folder>``: identification, status and summary table
- ``tree <experiment.h5 or folder> [--depth N]``: groups and datasets of the file
"""
import argparse
import json
import logging
import sys

from .access import ExperimentFile
from .unpack import unpack_experiment


def main(argv=None) -> int:
    """ Run the command line; returns the exit code. """

    parser = argparse.ArgumentParser(prog="python -m experiment_analysis",
                                     description="Tools for experiment files (experiment.h5).")
    commands = parser.add_subparsers(dest="command", required=True)
    unpack = commands.add_parser("unpack", help="write the file as PNG/CSV/TXT/JSON files")
    unpack.add_argument("source", help="experiment.h5 or the experiment folder")
    unpack.add_argument("target", help="output folder")
    unpack.add_argument("--zip", action="store_true", help="also write <output folder>.zip")
    unpack.add_argument("--zdc", action="store_true", help="also export every capture as .zdc")
    unpack.add_argument("--overwrite", action="store_true", help="replace the content of the output folder")
    unpack.add_argument("--csv", choices=("de", "en"), default="de",
                        help="de: ';' and decimal comma (German Excel, default); en: ',' and decimal point")
    unpack.add_argument("--no-previews", action="store_true", help="no preview PNGs of number arrays")
    info = commands.add_parser("info", help="identification, status and summary")
    info.add_argument("source")
    tree = commands.add_parser("tree", help="groups and datasets of the file")
    tree.add_argument("source")
    tree.add_argument("--depth", type=int, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "unpack":
        result = unpack_experiment(args.source, args.target, overwrite=args.overwrite, archive=args.zip,
                                   zdc=args.zdc, csv_style=args.csv, previews=not args.no_previews)
        print(f"Unpacked into {result}")
    elif args.command == "info":
        file = ExperimentFile(args.source)
        print(json.dumps(file.info(), indent=2))
        print(file.summary_table())
    else:
        print(ExperimentFile(args.source).tree(max_depth=args.depth))
    return 0


if __name__ == "__main__":
    sys.exit(main())
