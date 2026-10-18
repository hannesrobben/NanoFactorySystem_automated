##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Analysis tools for experiment files (``experiment.h5``).

- :func:`unpack_experiment`: write the whole file as PNG/CSV/TXT/JSON/ZDC files.
- :class:`ExperimentFile`: read the file at any time (also while printing) and
  store analysis results in it.
"""

from .access import ExperimentBusyError, ExperimentFile, lock_holder, resolve_file
from .unpack import unpack_experiment

__all__ = ["ExperimentBusyError", "ExperimentFile", "lock_holder", "resolve_file", "unpack_experiment"]
