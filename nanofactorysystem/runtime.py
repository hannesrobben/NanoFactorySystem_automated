##########################################################################
# Copyright (c) 2024 Reinhard Caspary                                    #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
#
# This module contains some useful functions for the usage of the
# NanoFactorySystem package.
#
##########################################################################

import logging
from pathlib import Path
from shutil import rmtree

LOGFMT = logging.Formatter(fmt="%(asctime)s / %(levelname)s / %(message)s",
                           datefmt="%Y-%m-%d %H:%M:%S")


def getLogger(logfile=None):
    """ Configure and return the package logger.

    The logger is shared, so repeated calls do not add handlers again:
    there is one console handler, and at most one log file. A call with a
    different ``logfile`` replaces the previous log file (e.g. for the next
    experiment in the same process); a call without ``logfile`` keeps it.

    Parameters
    ----------
    logfile : str or Path, optional
        File to which all messages are written.

    Returns
    -------
    logging.Logger
        The configured logger.
    """

    # Initialize logger object
    logger = logging.getLogger('dummy')
    logger.setLevel(logging.DEBUG)
    own = [h for h in logger.handlers if getattr(h, "_nanofactory", False)]

    # Console output
    if not any(not isinstance(h, logging.FileHandler) for h in own):
        consolehandler = logging.StreamHandler()
        consolehandler.setLevel(logging.DEBUG)
        consolehandler.setFormatter(LOGFMT)
        consolehandler._nanofactory = True
        logger.addHandler(consolehandler)

    # Optional file output
    if logfile:
        path = str(Path(logfile).resolve())
        for handler in own:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename != path:
                logger.removeHandler(handler)
                handler.close()
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == path for h in logger.handlers):
            filehandler = logging.FileHandler(logfile)
            filehandler.setLevel(logging.DEBUG)
            filehandler.setFormatter(LOGFMT)
            filehandler._nanofactory = True
            logger.addHandler(filehandler)

    # Return logger object
    return logger


def mkdir(path, clean=True):
    """ Make sure that the given folder exists and is empty. """

    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    if clean:
        for sub in p.iterdir():
            if sub.is_file():
                sub.unlink()
            elif sub.is_dir():
                rmtree(sub)
    return path
