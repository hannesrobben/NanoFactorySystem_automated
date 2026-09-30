##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Lock file that ensures a single writing process per experiment (design §6.3)."""
import json
import logging
import os
import socket
import sys
from pathlib import Path

from .records import utc_timestamp


class LockError(RuntimeError):
    """ The experiment is already being written by another process. """


def pid_alive(pid: int) -> bool:
    """ Return True if a process with the given id runs on this computer.

    Parameters
    ----------
    pid : int
        Process id.

    Returns
    -------
    bool
        Whether the process exists.
    """

    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) would terminate the process on Windows; ask the kernel instead
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        process_query_limited_information = 0x1000
        still_active = 259
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class ExperimentLock:
    """ Exclusive lock file of an experiment folder.

    The file holds host name, process id and start time. A lock of a
    process that no longer runs on this computer is stale; it is replaced
    with a warning. A lock of a running process, or of another computer,
    raises :class:`LockError`.

    Parameters
    ----------
    path : Path
        Lock file.
    logger : logging.Logger, optional
        Logger for the warning about a stale lock.
    """

    def __init__(self, path: Path, logger=None):
        self.path = Path(path)
        self.log = logger or logging.getLogger(__name__)
        self.acquired = False

    def acquire(self) -> None:
        """ Create the lock file.

        Raises
        ------
        LockError
            If another process holds the lock.
        """

        info = {"host": socket.gethostname(), "pid": os.getpid(), "started": utc_timestamp()}
        for _ in range(2):
            try:
                with open(self.path, "x", encoding="utf-8") as fp:
                    json.dump(info, fp)
                self.acquired = True
                return
            except FileExistsError:
                self._remove_if_stale()
        raise LockError(f"Experiment is locked by another process: {self.path}")

    def _remove_if_stale(self) -> None:
        try:
            other = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            other = {}
        if other.get("pid") == os.getpid() and other.get("host") == socket.gethostname():
            raise LockError(f"Experiment is already open for writing in this process: {self.path}")
        if other.get("host") != socket.gethostname() or pid_alive(int(other.get("pid", -1))):
            raise LockError(f"Experiment is being written by host {other.get('host')!r}, "
                            f"process {other.get('pid')} (since {other.get('started')}): {self.path}")
        self.log.warning(f"Removing stale lock of process {other.get('pid')} (since {other.get('started')}): "
                         f"{self.path}")
        self.path.unlink(missing_ok=True)

    def release(self) -> None:
        """ Remove the lock file if this object created it. """

        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False
