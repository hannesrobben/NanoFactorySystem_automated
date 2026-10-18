##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Live access to an experiment file for analyses.

:class:`ExperimentFile` reads an ``experiment.h5`` at any time, also while
the experiment is being printed, and stores analysis results in the same file.

Rules that keep the printing process safe (design §6.3 of
``docs/design/EXPERIMENT_STORAGE.md``):

- Every call opens the file, reads or writes, and closes it again.
- Reads use no HDF5 file lock, so a reader never blocks a write of the
  printing process. A read that hits a write in progress is repeated.
- Writes take the lock file ``experiment.lock`` for the duration of the write.
  While an experiment process holds it (printing or restart), writes raise
  :class:`ExperimentBusyError`, or wait up to ``wait_s`` seconds.
- Analysis results go to ``/analysis`` only; the groups written by the
  printing process are never changed (except DHM products via
  :meth:`ExperimentFile.add_dhm_product`, the interface the design provides).
"""
import json
import os
import socket
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Union

import h5py
import numpy as np

from nanofactorysystem.storage import ExperimentStore, LockError, schema, utc_timestamp
from nanofactorysystem.storage.experiment_store import COMPRESSION, TEXT
from nanofactorysystem.storage.locking import ExperimentLock, pid_alive

from .convert import attributes, plain

ANALYSIS_GROUP = "analysis"
PathLike = Union[str, os.PathLike]


class ExperimentBusyError(RuntimeError):
    """ The experiment file is being written by an experiment process. """


def resolve_file(path: PathLike) -> Path:
    """ Return the experiment file for a file or folder path.

    Parameters
    ----------
    path : str or Path
        ``experiment.h5`` (or a renamed copy of it), or the experiment folder.

    Returns
    -------
    Path

    Raises
    ------
    FileNotFoundError
        If no experiment file exists there.
    """

    path = Path(path)
    if path.is_dir():
        path = path / schema.FILE_NAME
    if not path.is_file():
        raise FileNotFoundError(f"No experiment file: {path}")
    return path


def lock_holder(file: PathLike) -> Optional[dict]:
    """ Return the process that holds the lock of an experiment, or None.

    A lock file of a process that no longer runs on this computer is stale
    and ignored (it is not removed).

    Parameters
    ----------
    file : str or Path
        Experiment file.

    Returns
    -------
    dict or None
        ``host``, ``pid``, ``started`` of the holder.
    """

    lock = Path(file).with_name(schema.LOCK_NAME)
    if Path(file).name != schema.FILE_NAME or not lock.is_file():
        return None
    try:
        info = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"host": "?", "pid": -1, "started": ""}  # lock file is just being written
    if info.get("host") == socket.gethostname() and not pid_alive(int(info.get("pid", -1))):
        return None
    return info


def _result_path(name: str, structure: Optional[str], capture: Optional[str]) -> str:
    if not name or "/" in name:
        raise ValueError(f"Invalid result name {name!r}")
    if structure is not None and capture is not None:
        raise ValueError("Give either structure or capture, not both")
    if structure is not None:
        return f"{ANALYSIS_GROUP}/structures/{structure}/{name}"
    if capture is not None:
        return f"{ANALYSIS_GROUP}/captures/{capture}/{name}"
    return f"{ANALYSIS_GROUP}/experiment/{name}"


def _set_result_attrs(obj, attrs: dict) -> None:
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)) and not _is_numeric_sequence(value):
            obj.attrs[f"{key}_json"] = json.dumps(plain(value))
        else:
            obj.attrs[key] = value


def _is_numeric_sequence(value) -> bool:
    if isinstance(value, dict):
        return False
    try:
        return np.asarray(value).dtype.kind in "biuf"
    except (ValueError, TypeError):
        return False


def _write_data(group: h5py.Group, name: str, value) -> None:
    if isinstance(value, str):
        group.create_dataset(name, data=value, dtype=TEXT)
        return
    if isinstance(value, bytes):
        group.create_dataset(name, data=np.frombuffer(value, dtype=np.uint8))
        return
    data = np.asarray(value)
    if data.dtype.kind in "OUS":
        raise TypeError(f"Cannot store {name!r} of type {type(value).__name__}; use numbers, text or arrays")
    if data.ndim == 0 or data.size < 16:
        group.create_dataset(name, data=data)
    else:
        group.create_dataset(name, data=data, **COMPRESSION)


def _read_value(dataset: h5py.Dataset):
    data = dataset[()]
    if h5py.check_string_dtype(dataset.dtype) is not None:
        return data.decode("utf-8") if isinstance(data, bytes) else data
    return data


class ExperimentFile:
    """ Read and extend an experiment file while it may be in use.

    Parameters
    ----------
    path : str or Path
        ``experiment.h5`` or the experiment folder.
    retries : int
        How often a failed read is repeated (a write of the printing process
        may be in progress).
    retry_delay_s : float
        Wait between two attempts.

    Examples
    --------
    >>> exp = ExperimentFile(r"D:/Femtika_Experiment/Hannes/HR-26-001/HR-26-001-A_20261018-1015")
    >>> print(exp.summary_table())
    >>> for capture in exp.captures(kind="camera", phase="after"):
    ...     image = exp.image(capture.capture_id)
    ...     exp.save_result("mean_grey", float(image.mean()), capture=capture.capture_id)
    """

    def __init__(self, path: PathLike, *, retries: int = 10, retry_delay_s: float = 0.2):
        self.path = resolve_file(path)
        self.folder = self.path.parent
        self.retries = int(retries)
        self.retry_delay_s = float(retry_delay_s)
        self.store = ExperimentStore(self.folder, read_locking=False)
        self.store.path = self.path  # the file may be a renamed copy
        self._seen_update: Optional[str] = None
        info = self._retry(lambda f: (attributes(f).get("file_type"), attributes(f).get("schema_version")))
        if info[0] != schema.FILE_TYPE:
            raise ValueError(f"Not an experiment file: {self.path}")
        if schema.schema_major(info[1]) != schema.schema_major(schema.SCHEMA_VERSION):
            raise ValueError(f"Unsupported schema version {info[1]} of {self.path}")

    def __repr__(self) -> str:
        return f"ExperimentFile({str(self.path)!r})"

    # ------------------------------------------------------------- low level

    def _open(self, mode: str = "r") -> h5py.File:
        if mode == "r":
            return h5py.File(self.path, "r", locking=False)
        return h5py.File(self.path, mode)

    def _retry(self, function: Callable[[h5py.File], Any]) -> Any:
        """ Call ``function(file)`` on the file opened for reading; repeat on read errors. """

        for attempt in range(self.retries + 1):
            try:
                with self._open() as f:
                    return function(f)
            except (OSError, RuntimeError):
                if attempt == self.retries:
                    raise
                time.sleep(self.retry_delay_s)

    def _store_call(self, method: str, *args, **kwargs) -> Any:
        """ Call a read method of the store; repeat on read errors. """

        for attempt in range(self.retries + 1):
            try:
                return getattr(self.store, method)(*args, **kwargs)
            except (OSError, RuntimeError):
                if attempt == self.retries:
                    raise
                time.sleep(self.retry_delay_s)

    @contextmanager
    def _locked(self, wait_s: float = 0.0) -> Iterator[None]:
        """ Hold the lock file of the experiment; wait up to ``wait_s`` for it. """

        lock = ExperimentLock(self.folder / schema.LOCK_NAME)
        deadline = time.monotonic() + wait_s
        while True:
            try:
                lock.acquire()
                break
            except LockError as error:
                if time.monotonic() >= deadline:
                    raise ExperimentBusyError(
                        f"The experiment is being written by an experiment process ({error}); analysis "
                        f"results can be stored when its session has ended (or pass wait_s=...).") from error
                time.sleep(min(1.0, max(0.05, deadline - time.monotonic())))
        try:
            yield
        finally:
            lock.release()

    @contextmanager
    def _writing(self, wait_s: float = 0.0) -> Iterator[h5py.File]:
        """ Take the lock file and open the file for writing; release both afterwards. """

        with self._locked(wait_s), self._open("a") as f:
            yield f
            f.attrs["updated"] = utc_timestamp()

    # ------------------------------------------------------------------ state

    @property
    def lock_info(self) -> Optional[dict]:
        """ Holder of the experiment lock (``host``, ``pid``, ``started``), or None. """

        return lock_holder(self.path)

    @property
    def is_busy(self) -> bool:
        """ True while an experiment process holds the file (printing, restart). """

        return self.lock_info is not None

    @property
    def updated(self) -> str:
        """ Time of the last write to the file (ISO 8601, UTC). """

        return self._retry(lambda f: plain(f.attrs.get("updated", "")))

    def info(self) -> dict:
        """ Identification and state of the experiment.

        Returns
        -------
        dict
            UUIDs and labels, ``status``, ``created``, ``updated``,
            ``schema_version``, ``path`` and ``busy``.
        """

        def read(f):
            names = ("experiment_uuid", "experiment_label", "substrate_uuid", "substrate_label", "status",
                     "created", "updated", "schema_version")
            return {name: plain(f.attrs.get(name, "")) for name in names}

        data = self._retry(read)
        data.update(path=str(self.path), busy=self.is_busy)
        return data

    def has_changed(self) -> bool:
        """ Return True if the file was written since the previous call (True on the first call). """

        updated = self.updated
        changed = updated != self._seen_update
        self._seen_update = updated
        return changed

    def wait_for_change(self, timeout_s: Optional[float] = None, poll_s: float = 2.0) -> bool:
        """ Wait until the file is written (e.g. the next layer or capture).

        Parameters
        ----------
        timeout_s : float, optional
            Maximum wait; None waits without limit.
        poll_s : float
            Interval between two checks.

        Returns
        -------
        bool
            True if the file changed, False on timeout.
        """

        if self._seen_update is None:
            self._seen_update = self.updated
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while True:
            if self.has_changed():
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(poll_s if deadline is None else max(0.0, min(poll_s, deadline - time.monotonic())))

    # --------------------------------------------------------------- records

    def record(self, include_captures: bool = True):
        """ All metadata as :class:`nanofactorysystem.storage.ExperimentRecord` (no image data). """

        return self._store_call("read", include_captures)

    def summary(self) -> Optional[dict]:
        """ The stored experiment summary (one row per user structure), or None. """

        return self._store_call("read_summary")

    def summary_table(self) -> str:
        """ The summary as fixed-width text table (as in the console log). """

        from nanofactorysystem.storage.summary import format_table, summary
        return format_table(summary(self.record(include_captures=False)))

    def structures(self) -> list:
        """ All structures (:class:`StructureRecord`) in print order, including corners and QR code. """

        return self.record(include_captures=False).structures

    def structure(self, name: str):
        """ One structure by name (:class:`StructureRecord`). """

        return self.record(include_captures=False).structure(name)

    def captures(self, structure: Optional[str] = None, kind: Optional[str] = None,
                 phase: Optional[str] = None, layer_id: Optional[int] = None) -> list:
        """ Capture records, optionally filtered.

        Parameters
        ----------
        structure : str, optional
            Structure name.
        kind : {"camera", "dhm"}, optional
        phase : {"before", "layer", "after"}, optional
        layer_id : int, optional

        Returns
        -------
        list of CaptureRecord
            Sorted by capture id; ``capture_id`` is used by :meth:`image`,
            :meth:`capture` and :meth:`save_result`.
        """

        def keep(c) -> bool:
            return ((structure is None or c.structure == structure) and (kind is None or c.kind == kind)
                    and (phase is None or c.phase == phase) and (layer_id is None or c.layer_id == layer_id))

        return [c for c in self.record().captures if keep(c)]

    def capture(self, capture_id: str) -> tuple:
        """ Metadata, data and device parameters of a capture.

        Returns
        -------
        tuple
            ``(CaptureRecord, ndarray, dict)``; the array is the camera image
            (H×W) or the hologram series (n×H×W).
        """

        return self._store_call("read_capture", capture_id)

    def image(self, capture_id: str) -> np.ndarray:
        """ The image (camera) or hologram series (DHM) of a capture. """

        return self.capture(capture_id)[1]

    def product(self, capture_id: str, name: str) -> tuple[np.ndarray, dict]:
        """ A DHM product (phase, amplitude, …) of a capture: ``(data, metadata)``. """

        return self._store_call("read_dhm_product", capture_id, name)

    def program(self, structure: str, layer_id: int) -> str:
        """ The AeroBasic program text of one layer. """

        return self._store_call("read_program", structure, layer_id)

    def plane(self):
        """ The substrate plane as z function (``PlaneFit``/``Plane``/``StaticOffset``), or None. """

        from nanofactorysystem.storage import z_function_from_json
        plane = self.record(include_captures=False).plane_fit
        return None if plane is None else z_function_from_json(plane.function, plane.function_json)

    def overview(self, phase: str) -> Optional[tuple[np.ndarray, dict]]:
        """ The overview mosaic of a phase (``"before"``/``"after"``) and its metadata, or None. """

        return self._store_call("read_overview", phase)

    def logs(self, kind: str = "console") -> dict[str, str]:
        """ Logs per session; ``kind`` is ``"console"`` or ``"a3200"`` (controller commands). """

        return self._store_call("read_logs", kind)

    # ---------------------------------------------------------- generic access

    def keys(self, path: str = "/") -> list[str]:
        """ Names of the members of a group. """

        return self._retry(lambda f: list(f[path].keys()))

    def read(self, path: str):
        """ Read any object of the file.

        Parameters
        ----------
        path : str
            HDF5 path, e.g. ``"/structures/rect/programs/layer_000"``.

        Returns
        -------
        ndarray, str or dict
            Dataset content (text as str), or the attributes of a group.
        """

        def read(f):
            obj = f[path]
            return attributes(obj) if isinstance(obj, h5py.Group) else _read_value(obj)

        return self._retry(read)

    def attributes(self, path: str = "/") -> dict:
        """ Attributes of an object (``<x>_json`` attributes decoded as ``<x>``). """

        return self._retry(lambda f: attributes(f[path]))

    def tree(self, path: str = "/", max_depth: Optional[int] = None) -> str:
        """ Text listing of the groups and datasets below ``path`` with shape and type. """

        def walk(f):
            lines = []

            def visit(group, depth):
                for key, obj in group.items():
                    indent = "  " * depth
                    if isinstance(obj, h5py.Group):
                        lines.append(f"{indent}{key}/")
                        if max_depth is None or depth + 1 < max_depth:
                            visit(obj, depth + 1)
                    else:
                        lines.append(f"{indent}{key}  {obj.shape} {obj.dtype}")

            lines.append(path)
            visit(f[path], 1)
            return "\n".join(lines)

        return self._retry(walk)

    # -------------------------------------------------------------- writing

    def save_result(self, name: str, data=None, *, attrs: Optional[dict] = None, structure: Optional[str] = None,
                    capture: Optional[str] = None, overwrite: bool = True, wait_s: float = 0.0) -> str:
        """ Store an analysis result in the experiment file.

        Results of the experiment go to ``/analysis/experiment/<name>``, of a
        structure to ``/analysis/structures/<structure>/<name>``, of a capture
        to ``/analysis/captures/<capture>/<name>``. Each result is a group:
        one array, number or text is stored as dataset ``data``; a dict of
        them as one dataset per key; ``attrs`` as attributes (nested values
        as JSON). ``created``/``updated`` and ``source`` (the running script)
        are added.

        Parameters
        ----------
        name : str
            Result name (no ``/``).
        data : array, number, str, bytes or dict, optional
            Result data.
        attrs : dict, optional
            Scalar results and parameters of the analysis.
        structure, capture : str, optional
            Structure name or capture id the result belongs to.
        overwrite : bool
            Replace an existing result of that name; False raises
            ``FileExistsError``.
        wait_s : float
            How long to wait if an experiment process holds the file.

        Returns
        -------
        str
            HDF5 path of the result.

        Raises
        ------
        ExperimentBusyError
            If the experiment is being printed (after ``wait_s``).
        KeyError
            If the structure or capture does not exist.
        """

        path = _result_path(name, structure, capture)
        with self._writing(wait_s) as f:
            if structure is not None and f"structures/{structure}" not in f:
                raise KeyError(f"No structure {structure!r} in {self.path}")
            if capture is not None and ("capture_index" not in f or capture not in f["capture_index"].attrs):
                raise KeyError(f"No capture {capture!r} in {self.path}")
            created = utc_timestamp()
            if path in f:
                if not overwrite:
                    raise FileExistsError(f"Result {path} exists; pass overwrite=True to replace it")
                created = plain(f[path].attrs.get("created", created))
                del f[path]
            group = f.require_group(path)
            values = data if isinstance(data, dict) else ({} if data is None else {"data": data})
            for key, value in values.items():
                if not key or "/" in str(key):
                    raise ValueError(f"Invalid data name {key!r}")
                _write_data(group, str(key), value)
            _set_result_attrs(group, attrs or {})
            group.attrs["created"] = created
            group.attrs["updated"] = utc_timestamp()
            group.attrs["source"] = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "interactive"
        return "/" + path

    def load_result(self, name: str, *, structure: Optional[str] = None,
                    capture: Optional[str] = None) -> tuple[Any, dict]:
        """ Read a result stored with :meth:`save_result`.

        Returns
        -------
        tuple
            ``(data, attrs)``: data is the single value of ``data``, a dict
            for several datasets, or None.
        """

        path = _result_path(name, structure, capture)

        def read(f):
            group = f[path]
            values = {key: _read_value(dataset) for key, dataset in group.items()}
            data = values["data"] if set(values) == {"data"} else (values or None)
            return data, attributes(group)

        return self._retry(read)

    def results(self) -> list[str]:
        """ HDF5 paths of all stored analysis results. """

        def read(f):
            found = []
            if ANALYSIS_GROUP not in f:
                return found

            def visit(name, obj):
                if isinstance(obj, h5py.Group) and "created" in obj.attrs:
                    found.append(f"/{ANALYSIS_GROUP}/{name}")

            f[ANALYSIS_GROUP].visititems(visit)
            return sorted(found)

        return self._retry(read)

    def delete_result(self, name: str, *, structure: Optional[str] = None, capture: Optional[str] = None,
                      wait_s: float = 0.0) -> None:
        """ Remove a stored result (the file does not shrink; HDF5 reuses the space later). """

        path = _result_path(name, structure, capture)
        with self._writing(wait_s) as f:
            if path not in f:
                raise KeyError(f"No result {path}")
            del f[path]

    def add_dhm_product(self, capture_id: str, name: str, data: np.ndarray, metadata: dict,
                        wait_s: float = 0.0) -> None:
        """ Store a DHM product (phase, amplitude, height, …) of a capture (design §5.6, F4).

        Parameters
        ----------
        capture_id : str
        name : str
            Product name, e.g. ``"phase"``.
        data : ndarray
        metadata : dict
            ``source`` (e.g. ``"offline"``), ``unit``, reconstruction parameters.
        wait_s : float
            How long to wait if an experiment process holds the file.
        """

        with self._locked(wait_s):
            self.store.add_dhm_product(capture_id, name, data, metadata)

    # ---------------------------------------------------------------- export

    def unpack(self, target: PathLike, **options) -> Path:
        """ Unpack the experiment into common file formats (see :func:`unpack_experiment`). """

        from .unpack import unpack_experiment
        return unpack_experiment(self.path, target, **options)
