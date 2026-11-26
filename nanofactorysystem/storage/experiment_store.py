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


#: Storage forms of the whole-structure program (T124)
STRUCTURE_PROGRAM_MODES = ("compressed", "reference")


def _replace_text(group: h5py.Group, name: str, text: str) -> h5py.Dataset:
    if name in group:
        del group[name]
    return group.create_dataset(name, data=text, dtype=TEXT)


def _group(parent: h5py.Group, name: str) -> h5py.Group:
    return parent.require_group(name)


# Columns of the material property table (/metadata/materials/<role>/properties, T75)
PROPERTY_COLUMNS = (("key", TEXT), ("value_real", "f8"), ("value_text", TEXT), ("unit", TEXT),
                    ("wavelength_nm", "f8"), ("state", TEXT), ("temperature_c", "f8"), ("uncertainty", "f8"),
                    ("source", TEXT), ("date", TEXT), ("notes", TEXT))


def _nan_if_none(value) -> float:
    return np.nan if value is None else float(value)


def _none_if_nan(value) -> Optional[float]:
    value = float(value)
    return None if np.isnan(value) else value


def _property_table(properties: list[dict]) -> np.ndarray:
    """ Material properties (``MaterialProperty.to_dict()``) as a compound array. """

    rows = []
    for p in properties:
        text = isinstance(p["value"], str)
        rows.append((p["key"], np.nan if text else float(p["value"]), p["value"] if text else "", p.get("unit", ""),
                     _nan_if_none(p.get("wavelength_nm")), p.get("state", "any"),
                     _nan_if_none(p.get("temperature_c")), _nan_if_none(p.get("uncertainty")),
                     p.get("source", ""), p.get("date", ""), p.get("notes", "")))
    return np.array(rows, dtype=list(PROPERTY_COLUMNS))


def _frames_table(frames: list[dict]) -> np.ndarray:
    """ ``FrameRecord`` 1.0 dicts as the compound table of §15.1 (one float column per metric key). """

    keys = sorted({key for frame in frames for key in (frame.get("metrics") or {})})
    dtype = [("index", "i4"), ("used", "?"), ("reject_reason", TEXT)] + [(f"metric_{k}", "f8") for k in keys]
    rows = []
    for frame in frames:
        metrics = frame.get("metrics") or {}
        rows.append((int(frame["index"]), bool(frame["used"]), frame.get("reject_reason") or "",
                     *[_nan_if_none(metrics.get(k)) for k in keys]))
    return np.array(rows, dtype=dtype)


def _frames_from_table(table: np.ndarray, acquisition: list) -> list[dict]:
    """ Inverse of :func:`_frames_table`; ``acquisition`` is the stored list of per-frame objects. """

    metric_names = [name for name in table.dtype.names if name.startswith("metric_")]
    frames = []
    for i, row in enumerate(table):
        reason = _text(row["reject_reason"])
        frame = {"index": int(row["index"]), "used": bool(row["used"]), "reject_reason": reason or None,
                 "metrics": {name[7:]: _none_if_nan(row[name]) for name in metric_names}}
        if i < len(acquisition) and acquisition[i] is not None:
            frame["acquisition"] = acquisition[i]
        frames.append(frame)
    return frames


def _write_product(group: h5py.Group, header: dict, buffers) -> None:
    """ Write a contract product: attribute ``header_json`` and one dataset per buffer (§15). """

    for name, data in buffers:
        data = np.asarray(data)
        if data.dtype == bool:
            data = data.astype(np.uint8)
        if name in group:
            del group[name]
        dataset = group.create_dataset(name, data=data, **COMPRESSION)
        dataset.attrs["created"] = utc_timestamp()
    group.attrs["header_json"] = _json(header)


def _read_product(group: h5py.Group) -> tuple[dict, dict[str, np.ndarray]]:
    """ Inverse of :func:`_write_product`: the header and the buffers named in its descriptors. """

    header = json.loads(_attr(group, "header_json"))
    descriptors = header.get("buffers") or (header.get("reconstruction") or {}).get("buffers") or []
    names = [d["name"] for d in descriptors] or [n for n in group if isinstance(group[n], h5py.Dataset)]
    return header, {name: group[name][()] for name in names if name in group}


def _properties_from_table(table: np.ndarray) -> list[dict]:
    """ Inverse of :func:`_property_table`. """

    properties = []
    for row in table:
        value_text = _text(row["value_text"])
        properties.append({
            "key": _text(row["key"]),
            "value": value_text if np.isnan(row["value_real"]) else float(row["value_real"]),
            "unit": _text(row["unit"]), "wavelength_nm": _none_if_nan(row["wavelength_nm"]),
            "state": _text(row["state"]), "temperature_c": _none_if_nan(row["temperature_c"]),
            "uncertainty": _none_if_nan(row["uncertainty"]), "source": _text(row["source"]),
            "date": _text(row["date"]), "notes": _text(row["notes"])})
    return properties


class ExperimentStore:
    """ The HDF5 file of one experiment.

    The store keeps only the path; every write opens and closes the file.

    Parameters
    ----------
    folder : Path
        Experiment folder that contains ``experiment.h5``.
    logger : logging.Logger, optional
        Logger for warnings.
    read_locking : bool, optional
        HDF5 file locking for reads (h5py ``locking``). None keeps the h5py
        default. A reader in another process (analysis while printing) passes
        False, so that it never blocks a write of the printing process.
    """

    def __init__(self, folder: Path, logger=None, read_locking: Optional[bool] = None):
        self.folder = Path(folder)
        self.path = self.folder / schema.FILE_NAME
        self.log = logger or logging.getLogger(__name__)
        self.read_locking = read_locking
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
    def open(cls, folder: Path, logger=None, read_locking: Optional[bool] = None) -> "ExperimentStore":
        """ Open an existing experiment file.

        Parameters
        ----------
        folder : Path
            Experiment folder.
        logger : logging.Logger, optional
        read_locking : bool, optional
            HDF5 file locking for reads, see :class:`ExperimentStore`.

        Raises
        ------
        FileNotFoundError
            If there is no experiment file in the folder.
        ValueError
            If the file is not an experiment file or has an unknown major
            schema version.
        """

        store = cls(folder, logger, read_locking)
        with store._read() as f:
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

    def _read(self) -> h5py.File:
        if self.read_locking is None:
            return h5py.File(self.path, "r")
        return h5py.File(self.path, "r", locking=self.read_locking)

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

        with self._read() as f:
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

    def write_materials(self, materials: dict[str, dict]) -> None:
        """ Write the material snapshots of the experiment (T75).

        Parameters
        ----------
        materials : dict
            ``{role: MaterialSnapshot.to_dict()}``. Each role becomes
            ``/metadata/materials/<role>`` with the snapshot fields as
            attributes and the material's properties as table ``properties``.
            Existing snapshots are replaced.
        """

        with self._write() as f:
            if "metadata/materials" in f:
                del f["metadata/materials"]
            group = _group(f, "metadata/materials")
            for role, snapshot in materials.items():
                entry = group.create_group(role)
                material = snapshot.get("material") or {}
                _set_attrs(entry, {
                    "schema": snapshot.get("schema", ""), "role": role, "name": snapshot["name"],
                    "known": bool(snapshot.get("known", False)), "batch": snapshot.get("batch", ""),
                    "name_source": snapshot.get("name_source", ""),
                    "registry_file": snapshot.get("registry_file", ""),
                    "registry_schema_version": int(snapshot.get("registry_schema_version", 0)),
                    "taken": snapshot.get("taken", ""),
                    "kind": material.get("kind", ""), "supplier": material.get("supplier", ""),
                    "notes": material.get("notes", ""), "created": material.get("created", ""),
                })
                entry.create_dataset("properties", data=_property_table(material.get("properties", [])))

    def read_materials(self) -> dict[str, dict]:
        """ Return the material snapshots as written by :meth:`write_materials` (empty for older files). """

        with self._read() as f:
            return self._read_materials(f)

    @staticmethod
    def _read_materials(f: h5py.File) -> dict[str, dict]:
        materials = {}
        for role, entry in f.get("metadata/materials", {}).items():
            attrs = _get_json_attrs(entry)
            snapshot = {key: attrs.get(key, "") for key in ("schema", "name", "batch", "name_source",
                                                            "registry_file", "taken")}
            snapshot |= {"role": role, "known": bool(attrs.get("known", False)),
                         "registry_schema_version": int(attrs.get("registry_schema_version", 0))}
            snapshot["material"] = None
            if snapshot["known"]:
                snapshot["material"] = {"name": snapshot["name"], "kind": attrs.get("kind", ""),
                                        "supplier": attrs.get("supplier", ""), "notes": attrs.get("notes", ""),
                                        "created": attrs.get("created", ""),
                                        "properties": _properties_from_table(entry["properties"][()])}
            materials[role] = snapshot
        return materials

    def write_spec(self, spec: dict, inputs: Optional[dict[str, Path]] = None) -> None:
        """ Store the experiment spec and its input files (T77, INFORMATION_MODEL.md §5, §6.2).

        Parameters
        ----------
        spec : dict
            ``ExperimentSpec.to_json()``; stored as text dataset
            ``/spec/spec_json`` with the attributes ``schema`` and ``written``.
            An existing spec is replaced.
        inputs : dict, optional
            Input files (slicer height maps, meshes) by their path relative to
            the experiment folder; each is stored byte for byte as
            ``/inputs/<file name>`` (uint8) with the attributes ``file`` and
            ``sha256``.
        """

        import hashlib

        with self._write() as f:
            group = _group(f, "spec")
            _replace_text(group, "spec_json", json.dumps(spec))
            group.attrs["schema"] = spec.get("schema", "")
            group.attrs["written"] = utc_timestamp()
            for relative, path in (inputs or {}).items():
                data = Path(path).read_bytes()
                name = Path(relative).name
                target = _group(f, "inputs")
                if name in target:
                    del target[name]
                dataset = target.create_dataset(name, data=np.frombuffer(data, dtype=np.uint8), **COMPRESSION)
                dataset.attrs["file"] = Path(relative).as_posix()
                dataset.attrs["sha256"] = hashlib.sha256(data).hexdigest()

    def read_spec(self) -> Optional[dict]:
        """ Return the stored experiment spec (JSON form), or None if none was written. """

        with self._read() as f:
            if "spec/spec_json" not in f:
                return None
            return json.loads(_text(f["spec/spec_json"][()]))

    def read_input(self, name: str) -> bytes:
        """ Return an input file stored by :meth:`write_spec` (by file name). """

        with self._read() as f:
            return f[f"inputs/{name}"][()].tobytes()

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

    def write_overview(self, phase: str, image: np.ndarray, metadata: dict,
                       single_images: Optional[np.ndarray] = None) -> None:
        """ Store an overview image of the experiment (T28) in ``/overview/<phase>``.

        Parameters
        ----------
        phase : {"before", "after"}
            Before or after printing; an earlier overview of the phase is replaced.
        image : ndarray
            Stitched grey image.
        metadata : dict
            Position and calibration of the image (``origin_um``,
            ``pixel_matrix_um``, ``positions_um``, ``area_um``, …).
        single_images : ndarray, optional
            The camera images (n×H×W) the overview was stitched from, to check
            the stitching.
        """

        with self._write() as f:
            group = _group(f, "overview")
            if phase in group:
                del group[phase]
            target = group.create_group(phase)
            target.create_dataset("image", data=np.asarray(image), **COMPRESSION)
            _set_attrs(target, {**metadata, "time": utc_timestamp()})
            if single_images is not None:
                single_images = np.asarray(single_images)
                target.create_dataset("single_images", data=single_images,
                                      chunks=(1,) + single_images.shape[1:], **COMPRESSION)

    def read_overview(self, phase: str) -> Optional[tuple[np.ndarray, dict]]:
        """ The overview image of a phase and its metadata, or None. """

        with self._read() as f:
            if f"overview/{phase}" not in f:
                return None
            group = f[f"overview/{phase}"]
            metadata = _get_json_attrs(group)
            if "single_images" in group:
                metadata["single_images"] = group["single_images"][()]
            return group["image"][()], metadata

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

    def write_structure_program(self, structure: str, text: str, *, mode: str = "compressed",
                                file: str = "") -> None:
        """ Store the whole-structure program (T124).

        The program is the concatenation of the layer programs, which are stored separately; for a
        large structure (main_PNG print of 2026-11-21: 48 million lines) a second uncompressed copy
        was a single text scalar of more than 2 GB.

        Parameters
        ----------
        structure : str
            Structure name.
        text : str
            Program text.
        mode : {"compressed", "reference"}
            ``"compressed"`` (default): UTF-8 bytes in a chunked gzip dataset (attribute
            ``format = "txt"``, so the unpack tool writes it as a text file). ``"reference"``: only the
            SHA-256, the line count and ``file`` are stored (for a later queue mode, F38).
        file : str
            Program file relative to the experiment folder (stored as attribute).

        Raises
        ------
        ValueError
            For another mode.
        """

        import hashlib
        if mode not in STRUCTURE_PROGRAM_MODES:
            raise ValueError(f"Structure program mode must be one of {STRUCTURE_PROGRAM_MODES}, not {mode!r}")
        data = text.encode("utf-8")
        attrs = {"storage": mode, "sha256": hashlib.sha256(data).hexdigest(), "n_lines": text.count("\n"),
                 "n_bytes": len(data), "file": file, "encoding": "utf-8"}
        with self._write() as f:
            group = f[f"structures/{structure}"]
            if "program" in group:
                del group["program"]
            if mode == "compressed":
                array = np.frombuffer(data, dtype=np.uint8)
                dataset = group.create_dataset("program", data=array, compression="gzip", compression_opts=4,
                                               chunks=(min(max(len(array), 1), 1 << 20),))
                attrs["format"] = "txt"
            else:
                dataset = group.create_dataset("program", data=np.zeros(0, dtype=np.uint8))
            _set_attrs(dataset, attrs)

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

        with self._read() as f:
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
            group = self._new_capture_group(f, capture)
            group.attrs["device_json"] = _json(device)
            name = "image" if capture.kind == "camera" else "holograms"
            chunks = data.shape if data.ndim == 2 else (1,) + data.shape[1:]
            group.create_dataset(name, data=data, chunks=chunks, **COMPRESSION)
            if capture_times_s is not None:
                group.create_dataset("capture_times_s", data=np.asarray(capture_times_s, dtype=float))
        return capture.capture_id

    def _new_capture_group(self, f: h5py.File, capture: CaptureRecord) -> h5py.Group:
        """ Create the group of a new capture with its record, ``products`` and index entry; set the id. """

        number = int(_attr(f, "next_capture", 0))
        capture.capture_id = f"{number:04d}"
        f.attrs["next_capture"] = number + 1
        group = f[f"structures/{capture.structure}/captures"].create_group(capture.capture_id)
        record = capture.to_dict()
        record["actual_um"] = [float(capture.actual_um.get(axis, np.nan)) for axis in "XYZAB"]
        record["commanded_um"] = [np.nan if v is None else float(v) for v in capture.commanded_um]
        record["session"] = self.session
        _set_attrs(group, {k: v for k, v in record.items() if k not in ("capture_id",)})
        group.create_group("products")
        _group(f, "capture_index").attrs[capture.capture_id] = group.name
        return group

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

    # ------------------------------------------------- DHM service results (T83)

    def reserve_capture(self, capture: CaptureRecord, *, recipe: dict, context: dict, adapter: str = "service",
                        group_id: str = "", config_hash: str = "", parameter_set_id: str = "") -> str:
        """ Create a DHM capture before the acquisition (``job_state = "reserved"``, §15.1).

        The group exists before anything is sent to the DHM service, so a
        result can always be matched to its capture, also after a crash.

        Parameters
        ----------
        capture : CaptureRecord
            Metadata (``kind = "dhm"``); ``capture_id`` is set by this method.
        recipe : dict
            Effective recipe of this capture (unknown keys included).
        context : dict
            ``CaptureContext`` as it will be sent.
        adapter : {"service", "fake", "legacy"}
            Adapter that takes the capture.
        group_id : str
            Group (``/dhm_groups``) the capture belongs to, empty if none.
        config_hash, parameter_set_id : str
            Parameter set of the reconstruction, if known before the job.

        Returns
        -------
        str
            Capture id.

        Raises
        ------
        ValueError
            For a capture that is not a DHM capture or an unknown adapter.
        """

        if capture.kind != "dhm":
            raise ValueError(f"reserve_capture() is for DHM captures, not {capture.kind!r}")
        if adapter not in schema.DHM_ADAPTERS:
            raise ValueError(f"Unknown DHM adapter {adapter!r}; expected one of {schema.DHM_ADAPTERS}")
        with self._write() as f:
            group = self._new_capture_group(f, capture)
            _set_attrs(group, {"adapter": adapter, "job_id": "", "job_state": "reserved", "error": "",
                               "group_id": group_id, "config_hash": config_hash,
                               "parameter_set_id": parameter_set_id})
            group.attrs["recipe_json"] = _json(recipe)
            group.attrs["context_json"] = _json(context)
            group.attrs["raw_ref_json"] = _json({})
        return capture.capture_id

    def update_capture_job(self, capture_id: str, *, job_state: str, job_id: Optional[str] = None,
                           error: Optional[str] = None, raw_ref: Optional[dict] = None) -> None:
        """ Record a state change of the job of a reserved capture.

        Parameters
        ----------
        capture_id : str
        job_state : str
            One of :data:`schema.DHM_JOB_STATES`.
        job_id : str, optional
            Job id of the service (set when the job is sent).
        error : str, optional
            Reason of a failed job.
        raw_ref : dict, optional
            Raw frames that stayed on the DHM-PC (``host``, ``path``, ``sha256``, ``n_frames``, ``keep_raw``).
        """

        if job_state not in schema.DHM_JOB_STATES:
            raise ValueError(f"Unknown job state {job_state!r}; expected one of {schema.DHM_JOB_STATES}")
        with self._write() as f:
            group = f[_attr(f["capture_index"], capture_id)]
            # None keeps the stored value (_set_attrs would delete the attribute)
            _set_attrs(group, {k: v for k, v in (("job_state", job_state), ("job_id", job_id), ("error", error))
                               if v is not None})
            if raw_ref is not None:
                group.attrs["raw_ref_json"] = _json(raw_ref)

    def add_dhm_result(self, capture_id: str, header: dict, buffers, *, raw_ref: Optional[dict] = None,
                       recovered: Optional[dict] = None) -> bool:
        """ Store the ``ProductSet`` of a capture (§15.2) and its frame records (§15.1).

        Idempotent: a second delivery of the same job (after a restart, ``sync``)
        is recognised by the job id and dropped.

        Parameters
        ----------
        capture_id : str
            Reserved capture the result belongs to.
        header : dict
            ``ProductSet`` 1.0 header as delivered (incl. ``reconstruction``
            with its ``buffers`` descriptors).
        buffers : iterable of (str, ndarray)
            Buffers by contract name (``phase_rad``, ``intensity_rel``, ``valid``, ``field``).
        raw_ref : dict, optional
            Reference to the raw frames on the DHM-PC; default: ``header["raw_ref"]``.
        recovered : dict, optional
            ``reason``, ``original_session`` when the result was fetched after a restart (SI4).

        Returns
        -------
        bool
            True if stored, False if this job's result was stored already.
        """

        buffers = [(name, np.asarray(data)) for name, data in buffers]
        reconstruction = header.get("reconstruction") or {}
        quality = reconstruction.get("quality") or {}
        job_id = header.get("job_id", "")
        with self._write() as f:
            group = f[_attr(f["capture_index"], capture_id)]
            if _attr(group, "job_state") in ("stored", "acknowledged") and _attr(group, "job_id") == job_id:
                return False
            products = group["products"]
            _write_product(products, header, buffers)
            _set_attrs(products, {"message_type": header.get("message_type", "ProductSet"),
                                  "schema_version": header.get("schema_version", ""),
                                  "product_id": header.get("product_id", ""), "job_id": job_id})
            flat = {
                "schema_version": reconstruction.get("schema_version", ""),
                "config_hash": reconstruction.get("config_hash") or header.get("config_hash") or "",
                "parameter_set_id": reconstruction.get("parameter_set_id") or header.get("parameter_set_id") or "",
                "background_id": quality.get("background_id") or header.get("background_id") or "",
                "background_created": quality.get("background_created_utc") or "",
                "background_age_s": _nan_if_none(quality.get("background_age_s")),
                "pixel_um": np.asarray(reconstruction.get("pixel_um", [np.nan, np.nan]), dtype=float),
                "z_um": _nan_if_none(reconstruction.get("z_um")),
                "propagation_index": _nan_if_none(reconstruction.get("propagation_index")),
                "wavelength_um": _nan_if_none(reconstruction.get("wavelength_um")),
            }
            for name, _ in buffers:
                dataset = products[name]
                _set_attrs(dataset, flat)
                for key, value in (("quality", quality), ("timings", reconstruction.get("timings_s", {})),
                                   ("versions", reconstruction.get("versions", {})),
                                   ("warnings", reconstruction.get("warnings", []))):
                    dataset.attrs[f"{key}_json"] = _json(value)
            frames = reconstruction.get("frames") or []
            if "frames" in group:
                del group["frames"]
            if frames:
                table = group.create_dataset("frames", data=_frames_table(frames))
                table.attrs["acquisition_json"] = _json([frame.get("acquisition") for frame in frames])
            _set_attrs(group, {"job_id": job_id, "job_state": "stored", "error": "",
                               "config_hash": flat["config_hash"], "parameter_set_id": flat["parameter_set_id"]})
            if raw_ref is None:
                raw_ref = header.get("raw_ref")
            if raw_ref is not None:
                group.attrs["raw_ref_json"] = _json(raw_ref)
            if recovered is not None:
                group.attrs["recovered"] = True
                group.attrs["recovered_json"] = _json({"time": utc_timestamp(), **recovered})
        return True

    def read_dhm_result(self, capture_id: str) -> tuple[dict, dict[str, np.ndarray]]:
        """ Return the ``ProductSet`` header and buffers of a capture (written by :meth:`add_dhm_result`).

        Raises
        ------
        KeyError
            If the capture holds no service result.
        """

        with self._read() as f:
            products = f[_attr(f["capture_index"], capture_id)]["products"]
            if "header_json" not in products.attrs:
                raise KeyError(f"Capture {capture_id} holds no DHM service result")
            return _read_product(products)

    def read_capture_job(self, capture_id: str) -> dict:
        """ Return the service attributes of a capture (§15.1) with the defaults for legacy captures.

        Returns
        -------
        dict
            ``adapter``, ``job_id``, ``job_state``, ``error``, ``group_id``,
            ``config_hash``, ``parameter_set_id``, ``recipe``, ``context``,
            ``raw_ref``, ``recovered`` and, if stored, ``frames`` (``FrameRecord`` dicts).
        """

        with self._read() as f:
            group = f[_attr(f["capture_index"], capture_id)]
            job = {"adapter": _attr(group, "adapter", "legacy"), "job_id": _attr(group, "job_id", ""),
                   "job_state": _attr(group, "job_state", "stored"), "error": _attr(group, "error", ""),
                   "group_id": _attr(group, "group_id", ""), "config_hash": _attr(group, "config_hash", ""),
                   "parameter_set_id": _attr(group, "parameter_set_id", ""),
                   "recipe": json.loads(_attr(group, "recipe_json", "{}")),
                   "context": json.loads(_attr(group, "context_json", "{}")),
                   "raw_ref": json.loads(_attr(group, "raw_ref_json", "{}")),
                   "recovered": bool(_attr(group, "recovered", False))}
            if "frames" in group:
                table = group["frames"]
                job["frames"] = _frames_from_table(table[()], json.loads(_attr(table, "acquisition_json", "[]")))
            return job

    def capture_jobs(self) -> dict[str, dict]:
        """ Return ``job_id``, ``job_state`` and the product names of every capture (one file open).

        Legacy captures report ``job_state = "stored"`` and an empty job id;
        camera captures are included with empty values.
        """

        jobs = {}
        with self._read() as f:
            if "capture_index" not in f:
                return jobs
            for capture_id, path in sorted(f["capture_index"].attrs.items()):
                group = f[_text(path)]
                dhm = _attr(group, "kind") == "dhm"
                products = sorted(group["products"]) if "products" in group else []
                jobs[capture_id] = {"job_id": _attr(group, "job_id", ""),
                                    "job_state": _attr(group, "job_state", "stored" if dhm else ""),
                                    "products": products}
        return jobs

    def open_captures(self, states=("reserved", "sent", "acquired")) -> list[dict]:
        """ Return id, structure, job id and state of every capture whose job is in one of ``states``.

        Used after a restart (``sync``) and at the end of a session (``missing``).
        """

        result = []
        with self._read() as f:
            if "capture_index" not in f:
                return result
            for capture_id, path in sorted(f["capture_index"].attrs.items()):
                group = f[_text(path)]
                state = _attr(group, "job_state")
                if state in states:
                    result.append({"capture_id": capture_id, "structure": _attr(group, "structure"),
                                   "job_id": _attr(group, "job_id", ""), "job_state": state})
        return result

    def add_layer_product(self, group_id: str, header: dict, buffers, *, kind: str, structure: str, phase: str,
                          layer_id: int, members: list[str], job_id: str = "", job_state: str = "stored",
                          group_spec: Optional[dict] = None, recipe: Optional[dict] = None,
                          recovered: Optional[dict] = None) -> None:
        """ Store a group and its ``LayerProduct`` under ``/dhm_groups/<group_id>`` (§15.3).

        Parameters
        ----------
        group_id : str
            Group id of the service.
        header : dict
            ``LayerProduct`` 1.0 header as delivered.
        buffers : iterable of (str, ndarray)
            ``phase_rad``, ``intensity_rel``, ``valid``, optional ``field``.
        kind : {"layer", "speckle", "background"}
        structure, phase : str
        layer_id : int
        members : list of str
            Capture ids of the member captures in position order.
        job_id, job_state : str
            Job of the group.
        group_spec, recipe : dict, optional
            ``GroupSpec`` as sent and the effective recipe.
        recovered : dict, optional
            ``reason``, ``original_session`` when fetched after a restart (SI4).
        """

        if kind not in schema.DHM_GROUP_KINDS:
            raise ValueError(f"Unknown group kind {kind!r}; expected one of {schema.DHM_GROUP_KINDS}")
        with self._write() as f:
            parent = _group(f, "dhm_groups")
            if group_id in parent:
                del parent[group_id]
            group = parent.create_group(group_id)
            _set_attrs(group, {"kind": kind, "structure": structure, "phase": phase, "layer_id": int(layer_id),
                               "job_id": job_id, "job_state": job_state, "recovered": recovered is not None})
            group.attrs["group_spec_json"] = _json(group_spec or {})
            group.attrs["recipe_json"] = _json(recipe or {})
            if recovered is not None:
                group.attrs["recovered_json"] = _json({"time": utc_timestamp(), **recovered})
            group.create_dataset("members", data=np.asarray(members, dtype=object), dtype=TEXT)
            _write_product(group.create_group("product"), header, buffers)

    def read_layer_product(self, group_id: str) -> tuple[dict, dict[str, np.ndarray], dict]:
        """ Return header, buffers and group attributes (incl. ``members``) of a stored group. """

        with self._read() as f:
            group = f[f"dhm_groups/{group_id}"]
            header, buffers = _read_product(group["product"])
            info = _get_json_attrs(group)
            info["members"] = [_text(m) for m in group["members"][()]]
            return header, buffers, info

    def dhm_groups(self) -> list[str]:
        """ Return the ids of the stored DHM groups. """

        with self._read() as f:
            return sorted(f["dhm_groups"]) if "dhm_groups" in f else []

    def add_dhm_orphan(self, job_id: str, reference: dict) -> None:
        """ Record a result of an unknown capture as reference only (``/dhm_orphans/<job_id>``, SI4).

        Parameters
        ----------
        job_id : str
        reference : dict
            ``result_id``, ``message_type``, ``structure``, ``layer_id``, ``time``,
            ``host``, ``path``, ``sha256``, ``size_bytes``, ``reason``.
        """

        with self._write() as f:
            parent = _group(f, "dhm_orphans")
            group = parent.require_group(job_id)
            _set_attrs(group, {k: ("" if v is None else v) for k, v in reference.items()})

    def read_dhm_orphans(self) -> dict[str, dict]:
        """ Return the orphan references by job id. """

        with self._read() as f:
            return {job: _get_json_attrs(g) for job, g in sorted(f["dhm_orphans"].items())} if "dhm_orphans" in f \
                else {}

    def write_dhm_calibration(self, kind: str, calibration_id: str, *, parameters: dict, result: dict,
                              job_id: str = "") -> None:
        """ Store a calibration of the DHM service under ``/calibration/dhm/<kind>/<id>`` (§15.5).

        Parameters
        ----------
        kind : {"exposure", "opl_scan", "background"}
        calibration_id : str
        parameters, result : dict
        job_id : str
        """

        if kind not in schema.DHM_CALIBRATION_KINDS:
            raise ValueError(f"Unknown calibration kind {kind!r}; expected one of {schema.DHM_CALIBRATION_KINDS}")
        with self._write() as f:
            group = _group(f, f"calibration/dhm/{kind}").require_group(calibration_id)
            _set_attrs(group, {"time": utc_timestamp(), "session": self._session or "", "job_id": job_id})
            group.attrs["parameters_json"] = _json(parameters)
            group.attrs["result_json"] = _json(result)

    def read_dhm_calibrations(self, kind: str) -> dict[str, dict]:
        """ Return the stored calibrations of one kind by id. """

        with self._read() as f:
            path = f"calibration/dhm/{kind}"
            return {cid: _get_json_attrs(g) for cid, g in sorted(f[path].items())} if path in f else {}

    # ---------------------------------------------------------------- reading

    def read_uuid(self) -> str:
        """ Return the experiment UUID without reading the whole file. """

        return self.read_identification()["experiment_uuid"]

    def read_identification(self) -> dict[str, str]:
        """ Return UUID and label of the experiment and of its substrate. """

        with self._read() as f:
            return {name: _attr(f, name, "") for name in ("experiment_uuid", "experiment_label",
                                                          "substrate_uuid", "substrate_label")}

    def read_status(self) -> str:
        """ Return the experiment status. """

        with self._read() as f:
            return _attr(f, "status", "")

    def has_structure(self, name: str) -> bool:
        """ Return True if a structure of that name is stored. """

        with self._read() as f:
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

        with self._read() as f:
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
            record.materials = self._read_materials(f)
            if "spec/spec_json" in f:
                record.spec = json.loads(_text(f["spec/spec_json"][()]))
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

        with self._read() as f:
            group = f[_attr(f["capture_index"], capture_id)]
            name = "image" if _attr(group, "kind") == "camera" else "holograms"
            return self._read_capture(group), group[name][()], json.loads(_attr(group, "device_json"))

    def read_dhm_product(self, capture_id: str, name: str) -> tuple[np.ndarray, dict]:
        """ Return data and metadata of a DHM product. """

        with self._read() as f:
            dataset = f[_attr(f["capture_index"], capture_id)]["products"][name]
            return dataset[()], json.loads(_attr(dataset, "metadata_json"))

    def read_structure_program(self, structure: str) -> Optional[str]:
        """ Return the whole-structure program, or None if only a reference is stored (T124).

        Reads the compressed form and the text scalar of files before T124.
        """

        with self._read() as f:
            group = f[f"structures/{structure}"]
            if "program" not in group:
                return None
            dataset = group["program"]
            storage = _attr(dataset, "storage")
            if storage == "reference":
                return None
            if storage == "compressed":
                return dataset[()].tobytes().decode("utf-8")
            return _text(dataset[()])

    def read_program(self, structure: str, layer_id: int) -> str:
        """ Return the text of a stored layer program. """

        with self._read() as f:
            return _text(f[f"structures/{structure}/programs/layer_{layer_id:03d}"][()])

    def plane_fit_container(self, name: str) -> bytes:
        """ Return a stored plane-fit container file (e.g. ``"plane.zdc"``) as bytes. """

        with self._read() as f:
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
        with self._read() as f:
            group = f[_attr(f["capture_index"], capture_id)]
            return group["capture_times_s"][()].tolist() if "capture_times_s" in group else [0.0]
