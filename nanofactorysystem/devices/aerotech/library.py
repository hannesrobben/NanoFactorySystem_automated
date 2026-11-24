"""Functions of the A3200 C library (``A3200C64.dll``) used to load programs (T129).

``PROGRAM LOAD`` over the ASCII interface compiles inside ``A3200AsciiInterface.exe``, a 32-bit
process that runs out of memory at about 80 000 lines and then refuses every later load. The C
library compiles in the calling 64-bit process instead. Lab session 1 (2026-11-24,
``docs/design/PROGRAM_LOADING.md`` section 6) measured with exactly these prototypes: 19.6 kB and
96 µs per line, the memory is returned at ``A3200Disconnect``, a loaded program stays loaded after
the loading process has exited, and ``A3200ProgramRemove(<file name>)`` removes a loaded ``.pgm``.
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional

from nanofactorysystem.aerobasic.constants.tasks import TaskState

DEFAULT_DLL = r"C:\Program Files (x86)\Aerotech\A3200\CLibrary\Bin64\A3200C64.dll"
GB = 1024 ** 3


class LibraryUnavailableError(RuntimeError):
    """The A3200 C library cannot be loaded or connected (not Windows, not installed, controller not running)."""


class A3200Library:
    """ Connection to the controller through the A3200 C library.

    Parameters
    ----------
    dll : str or Path
        Path of ``A3200C64.dll`` (64-bit Python needs the 64-bit library).

    Raises
    ------
    LibraryUnavailableError
        If the library cannot be loaded or ``A3200Connect`` fails.
    """

    def __init__(self, dll: str | Path = DEFAULT_DLL):
        if sys.platform != "win32":
            raise LibraryUnavailableError("The A3200 C library is only available on Windows")
        dll = Path(dll)
        try:
            self._dll_directory = os.add_dll_directory(str(dll.parent))
            self.lib = lib = ctypes.WinDLL(str(dll))
        except OSError as error:
            raise LibraryUnavailableError(f"Cannot load {dll}: {error}") from error
        handle, task, text, dword = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_ulong
        signatures = {
            "A3200Connect": [ctypes.POINTER(ctypes.c_void_p)], "A3200Disconnect": [handle],
            "A3200ProgramLoad": [handle, task, text], "A3200ProgramStart": [handle, task],
            "A3200ProgramStop": [handle, task], "A3200ProgramStopAndWait": [handle, task, dword],
            "A3200ProgramRemove": [handle, text],
            "A3200ProgramGetTaskState": [handle, task, ctypes.POINTER(ctypes.c_int)],
            "A3200ProgramGetAddedProgramCount": [handle, ctypes.POINTER(dword)],
            "A3200GetLastErrorString": [ctypes.c_char_p, dword],
        }
        for name, argtypes in signatures.items():
            function = getattr(lib, name)
            function.argtypes, function.restype = argtypes, ctypes.c_int
        self.handle = ctypes.c_void_p()
        if not lib.A3200Connect(ctypes.byref(self.handle)):
            raise LibraryUnavailableError(f"A3200Connect failed: {self.error()}")

    def __enter__(self) -> "A3200Library":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def error(self) -> str:
        """ Text of the last library error. """

        buffer = ctypes.create_string_buffer(2048)
        self.lib.A3200GetLastErrorString(buffer, 2048)
        return buffer.value.decode(errors="replace")

    def load(self, task_id: int, path: Path) -> tuple[bool, str]:
        """ Compile and load a program file on a task (``A3200ProgramLoad``); returns (ok, error text). """

        ok = self.lib.A3200ProgramLoad(self.handle, task_id, str(Path(path).resolve()).encode("mbcs"))
        return bool(ok), "" if ok else self.error()

    def start(self, task_id: int) -> tuple[bool, str]:
        ok = self.lib.A3200ProgramStart(self.handle, task_id)
        return bool(ok), "" if ok else self.error()

    def stop(self, task_id: int, timeout_ms: int = 10_000) -> bool:
        """ Stop the task and wait until it has stopped (``A3200ProgramStopAndWait``). """

        return bool(self.lib.A3200ProgramStopAndWait(self.handle, task_id, timeout_ms))

    def remove(self, name: str) -> tuple[bool, str]:
        ok = self.lib.A3200ProgramRemove(self.handle, name.encode("mbcs"))
        return bool(ok), "" if ok else self.error()

    def state(self, task_id: int) -> TaskState:
        value = ctypes.c_int(-1)
        if not self.lib.A3200ProgramGetTaskState(self.handle, task_id, ctypes.byref(value)):
            raise RuntimeError(f"A3200ProgramGetTaskState({task_id}) failed: {self.error()}")
        return TaskState(value.value)

    def added_programs(self) -> Optional[int]:
        """ Number of programs added (loaded) on the controller, None if the query fails. """

        count = ctypes.c_ulong(0)
        return count.value if self.lib.A3200ProgramGetAddedProgramCount(self.handle, ctypes.byref(count)) else None

    def close(self) -> None:
        """ Disconnect; this returns the memory of a compile to Windows. """

        if getattr(self, "handle", None):
            self.lib.A3200Disconnect(self.handle)
            self.handle = ctypes.c_void_p()


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def used_memory_gb() -> Optional[float]:
    """ Physical memory in use on this PC in GB (Windows), None elsewhere. """

    if sys.platform != "win32":
        return None
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return (status.ullTotalPhys - status.ullAvailPhys) / GB


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def peak_private_gb() -> Optional[float]:
    """ Peak private memory of this process in GB (Windows), None elsewhere. """

    if sys.platform != "win32":
        return None
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not kernel32.K32GetProcessMemoryInfo(ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb):
        return None
    return counters.PeakPagefileUsage / GB
