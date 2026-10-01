##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""HDF5 experiment file (docs/design/EXPERIMENT_STORAGE.md §5–§7, §11).

Every public write method opens the file, writes one event and closes it
again, so no file handle stays open while the stage moves or a layer prints.
"""
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import h5py
import numpy as np

from . import schema
from .locking import ExperimentLock
from .records import (CaptureRecord, CornerRecord, ExperimentRecord, LayoutRecord, PlaneFitRecord,
                      StructureRecord, utc_timestamp)

COMPRESSION = dict(compression="gzip", compression_opts=4, shuffle=True)
TEXT = h5py.string_dtype(encoding="utf-8")


def _json(value) -> str:
    return json.dumps(value, default=_json_default)


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def _text(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _attr(obj, name: str, default=None):
    """ Return an attribute as plain Python value. """

    if name not in obj.attrs:
        return default
    value = obj.attrs[name]
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8")
    if isinstance(value, np.ndarray):
        return value
    if isinstance(value, np.generic):
        return value.item()
    return value


def _set_attrs(obj, values: dict) -> None:
    """ Set attributes; None removes an attribute, dicts and lists of dicts become ``<name>_json``. """

    for name, value in values.items():
        if value is None:
            if name in obj.attrs:
                del obj.attrs[name]
        elif isinstance(value, dict) or (isinstance(value, list) and any(isinstance(v, dict) for v in value)):
            obj.attrs[f"{name}_json"] = _json(value)
        else:
            obj.attrs[name] = value


def _get_json_attrs(obj) -> dict:
    """ Read all attributes, decoding ``<name>_json`` attributes to ``<name>``. """

    values = {}
    for name in obj.attrs:
        value = _attr(obj, name)
        if name.endswith("_json"):
            values[name[:-5]] = json.loads(value)
        else:
            values[name] = value.tolist() if isinstance(value, np.ndarray) else value
    return values


def _replace_text(group: h5py.Group, name: str, text: str) -> h5py.Dataset:
    if name in group:
        del group[name]
    return group.create_dataset(name, data=text, dtype=TEXT)


def _group(parent: h5py.Group, name: str) -> h5py.Group:
    return parent.require_group(name)


class ExperimentStore:
    """ The HDF5 file of one experiment.

    The store keeps only the path; every write opens and closes the file.

    Parameters
    ----------
    folder : Path
        Experiment folder that contains ``experiment.h5``.
    logger : logging.Logger, optional
        Logger for warnings.
    """

    def __init__(self, folder: Path, logger=None):
        self.folder = Path(folder)
        self.path = self.folder / schema.FILE_NAME
        self.log = logger or logging.getLogger(__name__)
        self._lock: Optional[ExperimentLock] = None
        self._session: Optional[str] = None

    # ------------------------------------------------------------------ files

    @classmethod
    def create(cls, folder: Path, record: ExperimentRecord, logger=None) -> "ExperimentStore":
        """ Create a new experiment file and write the metadata of ``record``.

        Parameters
        ----------
        folder : Path
            Experiment folder; it is created if needed.
        record : ExperimentRecord
            Identification and metadata (``uuid``, ``parameters``, ``user``,
            ``objective``, ``system``, ``software``, labels).
        logger : logging.Logger, optional

        Returns
        -------
        ExperimentStore

        Raises
        ------
        FileExistsError
            If the folder already contains an experiment file.
        """

        store = cls(folder, logger)
        store.folder.mkdir(parents=True, exist_ok=True)
        if store.path.exists():
            raise FileExistsError(f"Experiment file exists already: {store.path}")
        now = utc_timestamp()
        with h5py.File(store.path, "x") as f:
            _set_attrs(f, {
                "file_type": schema.FILE_TYPE,
                "schema_version": schema.SCHEMA_VERSION,
                "experiment_uuid": record.uuid,
                "experiment_label": record.label,
                "substrate_uuid": record.substrate_uuid,
                "substrate_label": record.substrate_label,
                "created": now,
                "updated": now,
                "status": schema.STATUS_CREATED,
                "next_capture": 0,
            })
        store.write_metadata(record)
        return store

    @classmethod
    def open(cls, folder: Path, logger=None) -> "ExperimentStore":
        """ Open an existing experiment file.

        Raises
        ------
        FileNotFoundError
            If there is no experiment file in the folder.
        ValueError
            If the file is not an experiment file or has an unknown major
            schema version.
        """

        store = cls(folder, logger)
        with h5py.File(store.path, "r") as f:
            if _attr(f, "file_type") != schema.FILE_TYPE:
                raise ValueError(f"Not an experiment file: {store.path}")
            version = _attr(f, "schema_version")
            if schema.schema_major(version) != schema.schema_major(schema.SCHEMA_VERSION):
                raise ValueError(f"Unsupported schema version {version} of {store.path}")
        return store

    @staticmethod
    def exists(folder: Path) -> bool:
        """ Return True if the folder contains an experiment file. """

        return (Path(folder) / schema.FILE_NAME).is_file()

    @contextmanager
    def _write(self) -> Iterator[h5py.File]:
        with h5py.File(self.path, "a") as f:
            yield f
            f.attrs["updated"] = utc_timestamp()

    # --------------------------------------------------------------- sessions

    def begin_session(self, kind: str) -> str:
        """ Lock the experiment for this process and record a new session.

        Parameters
        ----------
        kind : {"new", "restart"}
            Why the file is opened for writing.

        Returns
        -------
        str
            Session id.
        """

        lock = ExperimentLock(self.folder / schema.LOCK_NAME, self.log)
        lock.acquire()
        self._lock = lock
        from .software import software_info
        info = software_info()
        with self._write() as f:
            sessions = _group(f, "metadata/sessions")
            session = f"{len(sessions):03d}"
            _set_attrs(sessions.create_group(session), {
                "kind": kind, "started": utc_timestamp(), "pid": os.getpid(),
                "git_commit": info["git_commit"], "package_version": info["package_version"],
            })
        self._session = session
        return session

    def end_session(self, reason: str) -> None:
        """ Close the current session and release the lock.

        Parameters
        ----------
        reason : {"finished", "aborted", "exception"}
            How the session ended.
        """

        try:
            if self._session is not None:
                with self._write() as f:
                    _set_attrs(f[f"metadata/sessions/{self._session}"], {"ended": utc_timestamp(),
                                                                         "end_reason": reason})
        finally:
            self._session = None
            if self._lock is not None:
                self._lock.release()
                self._lock = None

    def write_log(self, kind: str, text: str) -> None:
        """ Store a log of the current session below ``/logs/<kind>/<session>``.

        Parameters
        ----------
        kind : {"a3200", "console"}
            Controller command log or console (logger) output.
        text : str
            Log text of this session.
        """

        with self._write() as f:
            _replace_text(_group(f, f"logs/{kind}"), self._session or "none", text)

    def read_logs(self, kind: str) -> dict[str, str]:
        """ Return the logs of one kind, keyed by session id. """

        with h5py.File(self.path, "r") as f:
            group = f.get(f"logs/{kind}")
            return {} if group is None else {name: _text(dataset[()]) for name, dataset in sorted(group.items())}

    @property
    def session(self) -> str:
        """ Id of the current session, or ``""``. """

        return self._session or ""

    # --------------------------------------------------------------- metadata

    def write_metadata(self, record: ExperimentRecord) -> None:
        """ Write parameters, user, objective, system and software metadata. """

        with self._write() as f:
            meta = _group(f, "metadata")
            for name, values in (("experiment", record.parameters), ("user", record.user),
                                 ("objective", record.objective), ("system", record.system),
                                 ("software", record.software), ("substrate", record.substrate)):
                group = _group(meta, name)
                group.attrs.clear()
                _set_attrs(group, values)

    def set_status(self, status: str) -> None:
        """ Set the experiment status (``schema.STATUS_*``). """

        with self._write() as f:
            f.attrs["status"] = status

    def write_calibration(self, table: np.ndarray, fit_kind: str, source_file: Optional[str]) -> None:
        """ Store the attenuator calibration (columns: attenuator value, power in mW). """

        with self._write() as f:
            group = _group(f, "calibration")
            if "attenuator" in group:
                del group["attenuator"]
            dataset = group.create_dataset("attenuator", data=np.asarray(table, dtype=float))
            _set_attrs(dataset, {"columns": "attenuator_value, power_mw", "fit_kind": fit_kind,
                                 "source_file": source_file or "", "recorded": utc_timestamp()})

    def write_plane_fit(self, plane: PlaneFitRecord, containers: Optional[dict[str, bytes]] = None) -> None:
        """ Store the substrate plane and, for a measurement, its container files.

        Parameters
        ----------
        plane : PlaneFitRecord
        containers : dict, optional
            File name → content of SciDataContainer files (``back.zdc``,
            ``plane.zdc``, …), stored unchanged as byte datasets.
        """

        with self._write() as f:
            if "plane_fit" in f:
                del f["plane_fit"]
            group = f.create_group("plane_fit")
            _set_attrs(group, {"mode": plane.mode, "source": plane.source, "function": plane.function,
                               "interface": plane.interface, "time": plane.time})
            group.attrs["function_json"] = _json(plane.function_json)
            group.create_dataset("sample_points_um", data=np.asarray(plane.sample_points_um, dtype=float).reshape(-1, 2))
            group.create_dataset("interface_points_um",
                                 data=np.asarray(plane.interface_points_um, dtype=float).reshape(-1, 3))
            blobs = group.create_group("containers")
            for name, content in (containers or {}).items():
                dataset = blobs.create_dataset(name, data=np.frombuffer(content, dtype=np.uint8))
                dataset.attrs["format"] = "zdc"

    def write_time_estimate(self, data: dict) -> None:
        """ Store the expected printing time (``TimeEstimate.to_dict()``) in ``/time_estimate``. """

        with self._write() as f:
            group = _group(f, "time_estimate")
            group.attrs.clear()
            _set_attrs(group, {"layer_overhead_s": float(data["layer_overhead_s"]), "total_s": float(data["total_s"]),
                               "time": utc_timestamp()})
            group.attrs["structures_json"] = _json(data["structures"])

    def write_opl_scan(self, motor_pos_um: float, source: str) -> None:
        """ Store the OPL motor position of the DHM (``source``: ``"measured"``/``"loaded"``). """

        with self._write() as f:
            _set_attrs(_group(f, "opl_scan"), {"motor_pos_um": float(motor_pos_um), "source": source,
                                              "time": utc_timestamp()})

    def write_layout(self, layout: LayoutRecord, plot_png: Optional[bytes] = None) -> None:
        """ Store the experiment geometry and optionally the overview plot (PNG bytes). """

        with self._write() as f:
            old_plot = None
            if "layout" in f:
                if plot_png is None and "plot" in f["layout"]:
                    old_plot = f["layout/plot"][()]
                del f["layout"]
            group = f.create_group("layout")
            group.create_dataset("experiment_rectangle_um", data=np.asarray(layout.rectangle_um, dtype=float))
            group.create_dataset("grid_positions_um",
                                 data=np.asarray(layout.grid_positions_um, dtype=float).reshape(-1, 2))
            corners = group.create_group("corners")
            for i, corner in enumerate(layout.corners):
                _set_attrs(corners.create_group(f"{i}"), {
                    "name": corner.name, "position": corner.position,
                    "reference_um": np.asarray(corner.reference_um, dtype=float),
                    "center_um": np.asarray(corner.center_um, dtype=float),
                    "rotation_deg": float(corner.rotation_deg), "double": bool(corner.double)})
            double = layout.double_corner
            if double is not None:
                _set_attrs(group.create_group("double_corner"), {
                    "name": double.name, "center_um": np.asarray(double.center_um, dtype=float),
                    "rotation_deg": float(double.rotation_deg)})
            if layout.qrcode_um is not None:
                _set_attrs(group.create_group("qrcode"), {"center_um": np.asarray(layout.qrcode_um, dtype=float),
                                                          "text": layout.qrcode_text})
            plot = np.frombuffer(plot_png, dtype=np.uint8) if plot_png is not None else old_plot
            if plot is not None:
                group.create_dataset("plot", data=plot).attrs["format"] = "png"

    # ------------------------------------------------------------- structures

    def add_structure(self, structure: StructureRecord) -> None:
        """ Store a structure configuration; an existing structure of that name is replaced.

        Raises
        ------
        ValueError
            If the name contains ``/`` (it would be read as an HDF5 path).
        """

        if "/" in structure.name or not structure.name:
            raise ValueError(f"Invalid structure name {structure.name!r}")
        with self._write() as f:
            structures = _group(f, "structures")
            if structure.name in structures:
                del structures[structure.name]
            group = structures.create_group(structure.name)
            _set_attrs(group, {
                "index": structure.index, "name": structure.name, "type": structure.type,
                "grid_index": structure.grid_index, "corner_position": structure.corner_position,
                "axes": structure.axes, "setup": structure.setup,
                "center_um": np.asarray(structure.center_um, dtype=float),
                "reference_um": np.asarray(structure.reference_um, dtype=float),
                "power_mw": float(structure.power_mw), "class": structure.structure_class,
                "n_layers": structure.n_layers, "layer_order": structure.layer_order,
                "dhm_image_count": structure.dhm_image_count, "status": structure.status,
                "program_file": structure.program_file, "repeat_of": structure.repeat_of,
            })
            group.attrs["config_json"] = _json(structure.config)
            group.attrs["layer_files_json"] = _json(structure.layer_files)
            group.attrs["layer_powers_json"] = _json(list(structure.layer_powers_mw))
            for name in ("programs", "progress", "captures"):
                group.create_group(name)

    def write_layer_program(self, structure: str, layer_id: int, text: str, file: str) -> None:
        """ Store the text of a layer program and the file it was written to. """

        import hashlib
        with self._write() as f:
            dataset = _replace_text(f[f"structures/{structure}/programs"], f"layer_{layer_id:03d}", text)
            _set_attrs(dataset, {"layer_id": int(layer_id), "file": file,
                                 "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})

    def write_structure_program(self, structure: str, text: str) -> None:
        """ Store the whole-structure program text. """

        with self._write() as f:
            _replace_text(f[f"structures/{structure}"], "program", text)

    def write_slicer_job(self, structure: str, job, time_estimate=None) -> None:
        """ Copy a slicer ``ToolpathJob`` into the structure (schema of ``slicer/storage.py``). """

        from ..aerobasic.slicer.storage import write_job
        with self._write() as f:
            group = f[f"structures/{structure}"]
            if "slicer" in group:
                del group["slicer"]
            write_job(group.create_group("slicer"), job, time_estimate)

    def set_structure_status(self, structure: str, status: str) -> None:
        """ Set the status of a structure (``pending``/``printing``/``printed``/``failed``).

        ``printing`` records the start time (the first time only, so that a
        restart keeps it), ``printed`` and ``failed`` the end time.
        """

        with self._write() as f:
            group = f[f"structures/{structure}"]
            group.attrs["status"] = status
            if status == "printing" and not _attr(group, "started"):
                group.attrs["started"] = utc_timestamp()
            elif status in ("printed", "failed"):
                group.attrs["ended"] = utc_timestamp()

    def update_progress(self, structure: str, layer_id: Optional[int], status: str, *,
                        started: Optional[str] = None, error: Optional[str] = None) -> None:
        """ Record the end of a layer.

        Parameters
        ----------
        structure : str
        layer_id : int or None
            Printed layer.
        status : {"ok", "failed"}
        started : str, optional
            Start time of the layer.
        error : str, optional
            Error message of a failed layer.
        """

        with self._write() as f:
            group = f[f"structures/{structure}/progress"]
            _set_attrs(group.create_group(f"{len(group):04d}"), {
                "layer_id": -1 if layer_id is None else int(layer_id), "session": self.session,
                "started": started or "", "ended": utc_timestamp(), "status": status, "error": error or ""})
            printed = sum(1 for g in group.values() if _attr(g, "status") == "ok")
            _set_attrs(_group(f, "progress"), {"current_structure": structure,
                                               "current_layer_id": -1 if layer_id is None else int(layer_id),
                                               "printed_layers": printed, "updated": utc_timestamp()})

    def write_summary(self, data: dict) -> None:
        """ Store the experiment summary (see :func:`storage.summary.summary`) in ``/summary``. """

        with self._write() as f:
            group = _group(f, "summary")
            group.attrs.clear()
            _set_attrs(group, {k: v for k, v in data.items() if k != "structures" and v is not None})
            group.attrs["structures_json"] = _json(data["structures"])
            group.attrs["written"] = utc_timestamp()

    def read_summary(self) -> Optional[dict]:
        """ Return the stored summary, or None if none was written. """

        with h5py.File(self.path, "r") as f:
            if "summary" not in f:
                return None
            data = _get_json_attrs(f["summary"])
            data.pop("written", None)
            return data

    # --------------------------------------------------------------- captures

    def add_capture(self, capture: CaptureRecord, data: np.ndarray, *, device: dict,
                    capture_times_s: Optional[list[float]] = None) -> str:
        """ Store a camera image or a DHM hologram series.

        Parameters
        ----------
        capture : CaptureRecord
            Metadata; ``capture_id`` is set by this method.
        data : ndarray
            Camera image (H×W) or hologram series (n×H×W).
        device : dict
            Device parameters (camera settings or DHM parameters).
        capture_times_s : list of float, optional
            Duration of each hologram capture.

        Returns
        -------
        str
            Capture id.
        """

        data = np.asarray(data)
        with self._write() as f:
            number = int(_attr(f, "next_capture", 0))
            capture.capture_id = f"{number:04d}"
            f.attrs["next_capture"] = number + 1
            group = f[f"structures/{capture.structure}/captures"].create_group(capture.capture_id)
            record = capture.to_dict()
            record["actual_um"] = [float(capture.actual_um.get(axis, np.nan)) for axis in "XYZAB"]
            record["commanded_um"] = [np.nan if v is None else float(v) for v in capture.commanded_um]
            record["session"] = self.session
            _set_attrs(group, {k: v for k, v in record.items() if k not in ("capture_id",)})
            group.attrs["device_json"] = _json(device)
            name = "image" if capture.kind == "camera" else "holograms"
            chunks = data.shape if data.ndim == 2 else (1,) + data.shape[1:]
            group.create_dataset(name, data=data, chunks=chunks, **COMPRESSION)
            if capture_times_s is not None:
                group.create_dataset("capture_times_s", data=np.asarray(capture_times_s, dtype=float))
            group.create_group("products")
            _group(f, "capture_index").attrs[capture.capture_id] = group.name
        return capture.capture_id

    def add_dhm_product(self, capture_id: str, name: str, data: np.ndarray, metadata: dict) -> None:
        """ Store a product derived from a DHM capture (phase, amplitude, …).

        This is the receiving side of the interface to the DHM PC (F4): only
        the process that owns the experiment writes the file.

        Parameters
        ----------
        capture_id : str
            Capture the product belongs to.
        name : str
            Product name, e.g. ``"phase"``.
        data : ndarray
            Product data.
        metadata : dict
            ``source``, ``unit``, reconstruction parameters, … (JSON-compatible).
        """

        with self._write() as f:
            products = f[_attr(f["capture_index"], capture_id)]["products"]
            if name in products:
                del products[name]
            dataset = products.create_dataset(name, data=np.asarray(data), **COMPRESSION)
            _set_attrs(dataset, {"created": utc_timestamp()})
            dataset.attrs["metadata_json"] = _json(metadata)

    # ---------------------------------------------------------------- reading

    def read_uuid(self) -> str:
        """ Return the experiment UUID without reading the whole file. """

        return self.read_identification()["experiment_uuid"]

    def read_identification(self) -> dict[str, str]:
        """ Return UUID and label of the experiment and of its substrate. """

        with h5py.File(self.path, "r") as f:
            return {name: _attr(f, name, "") for name in ("experiment_uuid", "experiment_label",
                                                          "substrate_uuid", "substrate_label")}

    def read_status(self) -> str:
        """ Return the experiment status. """

        with h5py.File(self.path, "r") as f:
            return _attr(f, "status", "")

    def has_structure(self, name: str) -> bool:
        """ Return True if a structure of that name is stored. """

        with h5py.File(self.path, "r") as f:
            return f"structures/{name}" in f

    def read(self, include_captures: bool = True) -> ExperimentRecord:
        """ Reconstruct all experiment metadata from the file (without image data).

        Parameters
        ----------
        include_captures : bool
            Read the capture metadata as well. Their number grows with every
            layer; the JSON copies and the summary do not need them.

        Returns
        -------
        ExperimentRecord
        """

        with h5py.File(self.path, "r") as f:
            meta = f["metadata"]
            record = ExperimentRecord(
                uuid=_attr(f, "experiment_uuid"),
                parameters=_get_json_attrs(meta["experiment"]),
                user=_get_json_attrs(meta["user"]),
                objective=_get_json_attrs(meta["objective"]),
                system=_get_json_attrs(meta["system"]),
                software=_get_json_attrs(meta["software"]),
                substrate=_get_json_attrs(meta["substrate"]) if "substrate" in meta else {},
                label=_attr(f, "experiment_label", ""),
                substrate_uuid=_attr(f, "substrate_uuid", ""),
                substrate_label=_attr(f, "substrate_label", ""),
                created=_attr(f, "created", ""),
                updated=_attr(f, "updated", ""),
                status=_attr(f, "status", ""),
                schema_version=_attr(f, "schema_version", ""),
                sessions=[_get_json_attrs(g) for _, g in sorted(meta.get("sessions", {}).items())],
            )
            if "calibration/attenuator" in f:
                dataset = f["calibration/attenuator"]
                record.calibration = {"table": dataset[()], "fit_kind": _attr(dataset, "fit_kind"),
                                      "source_file": _attr(dataset, "source_file")}
            if "plane_fit" in f:
                group = f["plane_fit"]
                record.plane_fit = PlaneFitRecord(
                    mode=_attr(group, "mode"), source=_attr(group, "source"), function=_attr(group, "function"),
                    function_json=json.loads(_attr(group, "function_json")), interface=_attr(group, "interface"),
                    sample_points_um=group["sample_points_um"][()],
                    interface_points_um=group["interface_points_um"][()], time=_attr(group, "time"))
            if "opl_scan" in f:
                record.opl_scan = _get_json_attrs(f["opl_scan"])
            if "layout" in f:
                record.layout = self._read_layout(f["layout"])
            if "time_estimate" in f:
                record.time_estimate = _get_json_attrs(f["time_estimate"])
            for name, group in f.get("structures", {}).items():
                record.structures.append(self._read_structure(group))
                record.progress[name] = [_get_json_attrs(g) for _, g in sorted(group["progress"].items())]
                if include_captures:
                    for _, capture in sorted(group["captures"].items()):
                        record.captures.append(self._read_capture(capture))
            record.structures.sort(key=lambda s: s.index)
            record.captures.sort(key=lambda c: c.capture_id)
        return record

    @staticmethod
    def _read_layout(group: h5py.Group) -> LayoutRecord:
        corners = []
        for _, corner in sorted(group["corners"].items(), key=lambda item: int(item[0])):
            corners.append(CornerRecord(
                name=_attr(corner, "name"), position=_attr(corner, "position"),
                reference_um=tuple(float(v) for v in _attr(corner, "reference_um")),
                center_um=tuple(float(v) for v in _attr(corner, "center_um")),
                rotation_deg=float(_attr(corner, "rotation_deg")), double=bool(_attr(corner, "double"))))
        qrcode = group.get("qrcode")
        return LayoutRecord(
            rectangle_um=group["experiment_rectangle_um"][()],
            grid_positions_um=group["grid_positions_um"][()],
            corners=corners,
            qrcode_um=tuple(float(v) for v in _attr(qrcode, "center_um")) if qrcode is not None else None,
            qrcode_text=_attr(qrcode, "text", "") if qrcode is not None else "")

    @staticmethod
    def _read_structure(group: h5py.Group) -> StructureRecord:
        return StructureRecord(
            index=int(_attr(group, "index")), name=_attr(group, "name"), type=_attr(group, "type"),
            grid_index=int(_attr(group, "grid_index")), corner_position=_attr(group, "corner_position"),
            axes=_attr(group, "axes"), setup=_attr(group, "setup"),
            center_um=tuple(float(v) for v in _attr(group, "center_um")),
            reference_um=tuple(float(v) for v in _attr(group, "reference_um")),
            power_mw=float(_attr(group, "power_mw")), structure_class=_attr(group, "class"),
            config=json.loads(_attr(group, "config_json")),
            layer_files=json.loads(_attr(group, "layer_files_json")),
            program_file=_attr(group, "program_file"), layer_order=int(_attr(group, "layer_order")),
            dhm_image_count=int(_attr(group, "dhm_image_count")), status=_attr(group, "status"),
            repeat_of=_attr(group, "repeat_of", ""), started=_attr(group, "started", ""),
            ended=_attr(group, "ended", ""),
            layer_powers_mw=json.loads(_attr(group, "layer_powers_json", "[]")))

    @staticmethod
    def _read_capture(group: h5py.Group) -> CaptureRecord:
        commanded = [None if np.isnan(v) else float(v) for v in _attr(group, "commanded_um")]
        return CaptureRecord(
            kind=_attr(group, "kind"), structure=_attr(group, "structure"), phase=_attr(group, "phase"),
            layer_id=int(_attr(group, "layer_id")), image_index=int(_attr(group, "image_index")),
            image_count=int(_attr(group, "image_count")),
            offset_um=tuple(float(v) for v in _attr(group, "offset_um")),
            commanded_um=tuple(commanded),
            actual_um={axis: float(v) for axis, v in zip("XYZAB", _attr(group, "actual_um"))},
            time=_attr(group, "time"), file=_attr(group, "file"), capture_id=group.name.rsplit("/", 1)[-1])

    def read_capture(self, capture_id: str) -> tuple[CaptureRecord, np.ndarray, dict]:
        """ Return metadata, image data and device parameters of a capture. """

        with h5py.File(self.path, "r") as f:
            group = f[_attr(f["capture_index"], capture_id)]
            name = "image" if _attr(group, "kind") == "camera" else "holograms"
            return self._read_capture(group), group[name][()], json.loads(_attr(group, "device_json"))

    def read_dhm_product(self, capture_id: str, name: str) -> tuple[np.ndarray, dict]:
        """ Return data and metadata of a DHM product. """

        with h5py.File(self.path, "r") as f:
            dataset = f[_attr(f["capture_index"], capture_id)]["products"][name]
            return dataset[()], json.loads(_attr(dataset, "metadata_json"))

    def read_program(self, structure: str, layer_id: int) -> str:
        """ Return the text of a stored layer program. """

        with h5py.File(self.path, "r") as f:
            return _text(f[f"structures/{structure}/programs/layer_{layer_id:03d}"][()])

    def plane_fit_container(self, name: str) -> bytes:
        """ Return a stored plane-fit container file (e.g. ``"plane.zdc"``) as bytes. """

        with h5py.File(self.path, "r") as f:
            return f[f"plane_fit/containers/{name}"][()].tobytes()

    # ---------------------------------------------------------------- exports

    def export_capture(self, capture_id: str, path: Path) -> Path:
        """ Write a capture as SciDataContainer file (``.zdc``) as it was written before the store.

        Parameters
        ----------
        capture_id : str
        path : Path
            Target file.

        Returns
        -------
        Path
            The written file.
        """

        from scidatacontainer import load_config

        from ..hologram import HoloContainer
        from ..image import ImageContainer

        capture, data, device = self.read_capture(capture_id)
        record = self.read()
        user = record.user
        config = load_config(author=user.get("name"), email=user.get("email"),
                             organization=user.get("organization"), orcid=user.get("orcid"))
        objective = {k: v for k, v in record.objective.items() if k != "key"}
        location = {axis: value for axis, value in capture.actual_um.items() if not np.isnan(value)}
        if capture.kind == "camera":
            container = ImageContainer(img=data, params=device, objective=objective, loc=location, config=config)
        else:
            times = self._capture_times(capture_id)
            container = HoloContainer(holo_get=data[0], holo_images=list(data[1:]), capture_time=times[0],
                                      capture_times=times[1:], params=device, objective=objective,
                                      loc=location, config=config)
        container["data/capture.json"] = capture.to_dict()
        container.write(str(path))
        return Path(path)

    def _capture_times(self, capture_id: str) -> list[float]:
        with h5py.File(self.path, "r") as f:
            group = f[_attr(f["capture_index"], capture_id)]
            return group["capture_times_s"][()].tolist() if "capture_times_s" in group else [0.0]
