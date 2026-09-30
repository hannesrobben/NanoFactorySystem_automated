##########################################################################
# Copyright (c) 2022-2024 Reinhard Caspary                               #
# <reinhard.caspary@phoenixd.uni-hannover.de>                            #
# This program is free software under the terms of the MIT license.      #
##########################################################################
import datetime
import json
import logging
import os.path
import time
import uuid
from logging import Logger
from pathlib import Path
from typing import Iterator, Optional, Literal
from enum import Enum

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse, Rectangle
from scidatacontainer import Container

from nanofactorysystem import System, ImageContainer, Plane, mkdir, getLogger
from nanofactorysystem.aerobasic import SingleAxis, AxisStatusDataItem
from nanofactorysystem.aerobasic.ascii import AerotechError
from nanofactorysystem.aerobasic.programs import AeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings import DrawableObject, DrawableAeroBasicProgram
from nanofactorysystem.aerobasic.programs.drawings.lines import Corner
from nanofactorysystem.aerobasic.programs.drawings.qr_code import QRCode, QrErrorCorrection
from nanofactorysystem.aerobasic.programs.setups import DefaultSetup, SetupIFOV
from nanofactorysystem.backends import BackendLike
from nanofactorysystem.devices.coordinate_system import CoordinateSystem, PlaneFit, DropDirection, Unit, \
    Point2D, Point3D, Coordinate, ZFunction
from nanofactorysystem.devices.power_calibration import PowerCalibration, power_calibration
from nanofactorysystem.storage import (CaptureRecord, CornerRecord, ExperimentRecord, ExperimentStore,
                                       LayoutRecord, PlaneFitRecord, StructureRecord, export_json,
                                       software_info, utc_timestamp, z_function_to_json)
from nanofactorysystem.storage.json_copies import export_progress, structures_list, write_json
from nanofactorysystem.storage.legacy import LegacyExperiment, is_legacy_folder, read_legacy
from nanofactorysystem.storage.summary import SUMMARY_NAME, format_table, summary
from nanofactorysystem.storage.substrate_store import (SubstrateRecord, SubstrateStore, check_not_synced,
                                                       default_root)
from nanofactorysystem.storage import schema
from nanofactorysystem.dhm.optimage import optImageMedian
from nanofactorysystem.utils.visualization import read_file, plot_movements


class CornerPosition(Enum):
    TL = 0
    TR = 1
    BR = 2
    BL = 3


# test for merge

class StructureType(Enum):
    DUMMY = 0
    NORMAL = 1
    CORNER = 2
    QRCODE = 3
    STITCHING = 4
    IFOV = 5
    REPEAT = 6


class Experiment(object):
    def __init__(self,
                 path: Optional[Path],
                 user: str,
                 objective: str,
                 logger: Logger,
                 sys_args: dict,
                 default_power: float,
                 low_speed_um: float,
                 high_speed_um: float,
                 resin_corner_tr: Point2D,
                 resin_corner_bl: Point2D,
                 structure_size: float,
                 margin: float,
                 padding: float,
                 absolute_grid_center: Point2D,
                 grid: tuple[int, int],
                 n_mid_points: int,
                 drop_direction: DropDirection,
                 corner_z: float,
                 corner_width: float,
                 corner_length: float,
                 corner_height: float,
                 corner_hatch: float,
                 corner_slice: float,
                 fov_dim: tuple[float, float],
                 *,
                 skip_corner: bool = False,
                 plane_fit_mode: int = 0,
                 setup: Literal["IFOV_off", "IFOV_on"] = "IFOV_off",
                 substrate_information: dict=None,
                 backend: BackendLike = None,
                 resume: bool = False,
                 substrate: Optional[str] = None,
                 data_root: Optional[Path] = None,
                 allow_synced_root: bool = False):
        """ Experiment on one substrate.

        Only the newer parameters are documented here; see the class
        attributes for the others. All data is written through an
        :class:`ExperimentStore` into ``<path>/experiment.h5``; the JSON
        files in ``path`` are copies.

        Parameters
        ----------
        path : Path or None
            Experiment folder. None: a new folder
            ``<data root>/<substrate>/<experiment label>_<YYYYMMDD-HHMM>``
            below the default location (requires ``substrate``); the log
            file ``console.log`` is added in that folder.
        substrate_information : dict, optional
            Free information about the substrate (older scripts); stored in
            the experiment file. Use ``substrate`` for substrate records.
        substrate : str, optional
            Label or UUID of a substrate created with
            :class:`SubstrateStore`. The experiment gets the next experiment
            label of the substrate and is entered into its index.
        data_root : Path, optional
            Data root with the substrates; default: :func:`default_root` of
            the user (``dataRoot`` in the config or
            ``~/Documents/Femtika_Experiment/<user>``).
        allow_synced_root : bool
            Accept a data root inside a synchronised folder (Seafile, …).
        backend : {"real", "dummy"}, Backend or None
            Hardware backend passed to :class:`System`. None or ``"real"``
            (default) uses the lab hardware, ``"dummy"`` or a
            ``DummyBackend`` object simulated devices.
        resume : bool
            Continue the experiment stored in ``path`` (restart): its
            experiment file is opened and its UUID is kept. Without
            ``resume``, a folder that already contains an experiment file is
            refused, so that no earlier experiment is overwritten.

        Raises
        ------
        FileExistsError
            If ``path`` contains an experiment file and ``resume`` is False.
        ValueError
            If neither ``path`` nor ``substrate`` is given.
        SyncedFolderError
            If the data root lies in a synchronised folder.
        """

        self.user = str(user)
        self.objective = str(objective)
        self.log = logger

        # Substrate record and experiment folder
        self.substrate: Optional[SubstrateRecord] = None
        self.substrates: Optional[SubstrateStore] = None
        self.experiment_label = ""
        if substrate is not None:
            if data_root is None:
                root = default_root(self.user, allow_synced_root=allow_synced_root)
            else:
                root = Path(data_root)
                if not allow_synced_root:
                    check_not_synced(root)
            self.substrates = SubstrateStore(root)
            self.substrate = self.substrates.get(substrate)
        if path is None:
            if self.substrate is None:
                raise ValueError("Either an experiment folder (path) or a substrate is needed.")
            if resume:
                raise ValueError("resume=True needs the folder of the stored experiment as path.")
            self.experiment_label = self.substrates.next_experiment_label(self.substrate.label)
            path = self.substrates.experiment_folder(self.substrate.label, self.experiment_label,
                                                     datetime.datetime.now())
            Path(path).mkdir(parents=True)
            self.log = getLogger(logfile=Path(path) / "console.log")
        self.path = Path(path)
        self.substrate_information = substrate_information
        log_file = self._log_file()
        self._log_offset = Path(log_file).stat().st_size if log_file and Path(log_file).exists() else 0
        self.sys_args = sys_args
        self.default_power = float(default_power)
        self.low_speed_um = float(low_speed_um)
        self.high_speed_um = float(high_speed_um)

        self.resin_corner_tr = np.array(resin_corner_tr.as_tuple(), dtype=float)
        self.resin_corner_bl = np.array(resin_corner_bl.as_tuple(), dtype=float)
        self.structure_size = float(structure_size)
        self.margin = float(margin)
        self.padding = float(padding)
        self.absolute_grid_center = np.array(absolute_grid_center.as_tuple(), dtype=float)
        self.fov_dimensions = fov_dim

        self.grid = np.array(grid, dtype=int)
        assert self.grid.shape == (2,)
        assert self.grid[0] > 0 and self.grid[1] > 0

        self.n_mid_points = int(n_mid_points)
        assert self.n_mid_points >= 0

        self.drop_direction = drop_direction
        self.plane_fit_mode = plane_fit_mode

        # Corner dimensions
        self.corner_z = float(corner_z)
        self.corner_width = float(corner_width)
        self.corner_length = float(corner_length)
        self.corner_height = float(corner_height)
        self.corner_hatch = float(corner_hatch)
        self.corner_slice = float(corner_slice)

        # UUID for this experiment; a resumed experiment keeps the UUID of its file
        stored = ExperimentStore.exists(self.path)
        if stored and not resume:
            raise FileExistsError(f"{self.path} contains an experiment already. Use a new folder, "
                                  f"or resume=True to continue that experiment.")
        legacy = None
        if stored:
            identification = ExperimentStore.open(self.path, self.log).read_identification()
            self.qr_text = identification["experiment_uuid"]
            self.experiment_label = identification["experiment_label"]
        elif resume and is_legacy_folder(self.path):
            # Folder written before the experiment file existed: imported, keeping its UUID if known
            legacy = read_legacy(self.path, 1 if drop_direction == DropDirection.UP else -1, setup)
            self.qr_text = legacy.uuid or str(uuid.uuid4())
            if legacy.uuid is None:
                self.log.warning("The UUID of the old experiment could not be recovered; a new one is used.")
        else:
            self.qr_text = str(uuid.uuid4())
        self.log.info(f"Experiment {self.qr_text}")

        # No plane fitting data yet
        self.plane_fit_function = None
        self.coordinate_system_grid_to_absolute = None

        # Init system object
        self.log.info("Initialize system object...")
        self.system = System(user, objective, logger, backend=backend, **sys_args)
        self.system.log_dir = self.path  # A3200.log belongs to the experiment

        # Set default laser power
        self.system.controller.power(default_power)

        # AeroTech A3200 API
        self.a3200 = self.system.a3200_new
        if setup == "IFOV_off":
            self.a3200.api(DefaultSetup())
        elif setup == "IFOV_on":
            self.a3200.api(SetupIFOV(objective=self.objective))
            # raise NotImplementedError(
            #     "The IFOV setup has to be adjusted again")
        else:
            raise NotImplementedError("Please use an existing setup!")

        # Acceleration rates of stages and galvanometer
        self.accel_x_mm = float(
            self.a3200.api.AXISSTATUS(SingleAxis.X, AxisStatusDataItem.AccelerationRate).replace(",", "."))
        # note 07.05.2026 - change acceleration to x accel in ifov because of an error
        self.accel_a_mm = float(
            self.a3200.api.AXISSTATUS(SingleAxis.A, AxisStatusDataItem.AccelerationRate).replace(",", ".")) if setup == "IFOV_off" else self.accel_x_mm/2
        self.accel_z_mm = float(
            self.a3200.api.AXISSTATUS(SingleAxis.Z, AxisStatusDataItem.AccelerationRate).replace(",", "."))
        self.accel_x_um = self.accel_x_mm / Unit.um.value
        self.accel_a_um = self.accel_a_mm / Unit.um.value
        self.accel_z_um = self.accel_z_mm / Unit.um.value

        # Initialize structures list with corners
        self.structures = []
        if not skip_corner:  # Skipping printing process of Corner+QR-Code
            self.add_corner_structures()
            if self.qr_text:
                self.add_qrcode_structure()

        # No programs yet
        self.structure_programs = None
        self.structure_configs = None
        self.skip_corner = bool(skip_corner)
        self.setup = setup

        # Experiment file: new, resumed, or created for a resumed folder without one
        self._stored_structures = set()  # names known to be in the experiment file
        self.store = self._open_store(stored, legacy)
        try:
            self._register_experiment()
            self._save_exp_dict()
        except BaseException:
            self.store.end_session("exception")
            raise

    def __enter__(self):
        return self

    def __exit__(self, errtype, value, traceback):
        try:
            self.system.close()
        finally:
            self._end_session(errtype)

    def _end_session(self, errtype) -> None:
        """ Store the logs of this session, set the status after an exception and end the session. """

        if errtype is None:
            reason = "finished"
        else:
            reason = "aborted" if issubclass(errtype, KeyboardInterrupt) else "exception"
        try:
            self.store.write_log("a3200", self.a3200.command_log())
            log_file = self._log_file()
            if log_file and Path(log_file).exists():
                with open(log_file, "rb") as fp:
                    fp.seek(self._log_offset)
                    self.store.write_log("console", fp.read().decode("utf-8", errors="replace"))
            if reason != "finished":
                self.store.set_status(schema.STATUS_ABORTED if reason == "aborted" else schema.STATUS_FAILED)
        finally:
            self.store.end_session(reason)
            self._save_exp_dict()
            self._update_substrate_index()

    def _open_store(self, stored: bool, legacy: Optional[LegacyExperiment] = None) -> ExperimentStore:
        """ Open or create the experiment file and start a session.

        An old folder (``legacy``) is imported into a new experiment file
        (design decision D7); its files are left unchanged.
        """

        if stored:
            store = ExperimentStore.open(self.path, self.log)
            store.begin_session("restart")
            return store

        store = ExperimentStore.create(self.path, self._experiment_record(), self.log)
        store.begin_session("new" if legacy is None else "imported")
        try:
            attenuator = self.system.controller.attenuator
            store.write_calibration(attenuator.data, attenuator["fitKind"], attenuator["calibrationFile"])
            store.write_layout(self._layout())
            if legacy is not None:
                self._import_legacy(store, legacy)
        except BaseException:
            store.end_session("exception")
            raise
        return store

    def _import_legacy(self, store: ExperimentStore, legacy: LegacyExperiment) -> None:
        """ Write the structures, programs and progress of an old folder into the new experiment file. """

        for structure in legacy.structures:
            attempted = sorted(legacy.attempted.get(structure.name, set()))
            if structure.name in legacy.finished:
                structure.status = "printed"
            elif attempted:
                structure.status = "printing"
            store.add_structure(structure)
            self._stored_structures.add(structure.name)
            for file in structure.layer_files:
                if self._absolute(file).exists():
                    store.write_layer_program(structure.name, self._layer_id(file),
                                              self._absolute(file).read_text(), file)
            for layer_id in attempted:
                store.update_progress(structure.name, layer_id, "ok", error="imported from print_progress.json")
        self.log.info(f"Imported {len(legacy.structures)} structures of the old experiment folder {self.path}")

    def _experiment_record(self) -> ExperimentRecord:
        """ Return identification and metadata of this experiment for a new experiment file. """

        values = {
            "default_power": self.default_power, "low_speed_um": self.low_speed_um,
            "high_speed_um": self.high_speed_um, "resin_corner_tr": self.resin_corner_tr,
            "resin_corner_bl": self.resin_corner_bl, "structure_size": self.structure_size,
            "margin": self.margin, "padding": self.padding, "absolute_grid_center": self.absolute_grid_center,
            "grid": self.grid, "n_mid_points": self.n_mid_points, "drop_direction": self.drop_direction.name,
            "corner_z": self.corner_z, "corner_width": self.corner_width, "corner_length": self.corner_length,
            "corner_height": self.corner_height, "corner_hatch": self.corner_hatch,
            "corner_slice": self.corner_slice, "fov_dim": self.fov_dimensions, "skip_corner": self.skip_corner,
            "plane_fit_mode": self.plane_fit_mode, "setup": self.setup,
        }
        converters = {"float": float, "int": int, "bool": bool, "str": str, "enum": str,
                      "vector": lambda v: np.asarray(v, dtype=float), "ivector": lambda v: np.asarray(v, dtype=int)}
        parameters = {name: converters[kind](values[argument]) for argument, _, name, kind in schema.PARAMETERS}
        parameters["log_file"] = self._relative(self._log_file()) if self._log_file() else ""
        parameters["dhm_usage"] = self.system.dhm is not None

        devices = {key: value for key, value in self.system.items().items() if key != "data/objective.json"}
        substrate = {"information": self.substrate_information or {}}
        if self.substrate is not None:
            substrate |= {k: v for k, v in self.substrate.to_dict().items() if k != "experiments"}
        return ExperimentRecord(
            uuid=self.qr_text,
            label=self.experiment_label,
            substrate_uuid=self.substrate.uuid if self.substrate is not None else "",
            substrate_label=self.substrate.label if self.substrate is not None else "",
            substrate=substrate,
            parameters=parameters,
            user={"key": self.user, **self.system.user},
            objective={"key": self.objective, **self.system.objective},
            system={"sys_args": self.sys_args, "devices": devices,
                    "acceleration_x_mm_s2": self.accel_x_mm, "acceleration_a_mm_s2": self.accel_a_mm,
                    "acceleration_z_mm_s2": self.accel_z_mm,
                    "acceleration_a_rule": "controller" if self.setup == "IFOV_off" else "x/2 (IFOV workaround)",
                    "backend": self.system.backend.name},
            software=software_info(),
        )

    def _layout(self) -> LayoutRecord:
        """ Return the geometry of the experiment: rectangle, grid, corners and QR code. """

        corners = []
        qrcode = None
        for s in self.structures:
            if s["structure_type"] == StructureType.CORNER:
                reference = self.corner_location(s["corner"]).as_tuple()
                offset = s["structure"].center_point
                corners.append(CornerRecord(
                    name=s["name"], position=s["corner"].name, reference_um=reference,
                    center_um=(reference[0] + offset.X, reference[1] + offset.Y),
                    rotation_deg=float(getattr(s["structure"], "rotation_degree", 0.0)),
                    double=bool(getattr(s["structure"], "mark", False))))
            elif s["structure_type"] == StructureType.QRCODE:
                qrcode = self.qrcode_location().as_tuple()
        return LayoutRecord(
            rectangle_um=np.array([self.rectangle_tl, self.rectangle_tr, self.rectangle_br, self.rectangle_bl]),
            grid_positions_um=np.array(list(self.iter_experiment_locations()), dtype=float),
            corners=corners, qrcode_um=qrcode, qrcode_text=self.qr_text if qrcode is not None else "")

    def _write_summary(self) -> dict:
        """ Write the experiment summary into the file and as ``experiment_summary.json``; return it. """

        data = summary(self.store.read(include_captures=False))
        self.store.write_summary(data)
        write_json(self.path / SUMMARY_NAME, data)
        return data

    def log_summary(self) -> None:
        """ Write the experiment summary as table to the log. """

        self.log.info("Experiment summary:\n" + format_table(summary(self.store.read())))

    def _save_exp_dict(self):
        """ Write the JSON copies (experiment dictionary, structures) from the experiment file. """

        export_json(self.store.read(include_captures=False), self.path)

    def _register_experiment(self) -> None:
        """ Enter the experiment into the index of its substrate (not again on a restart). """

        if self.substrate is None:
            return
        uuid_text = self.qr_text
        if any(e["uuid"] == uuid_text for e in self.substrates.get(self.substrate.label).experiments):
            return
        layout = self._layout()
        double = layout.double_corner
        folder = self.substrates.folder(self.substrate.label)
        try:
            path = self.path.resolve().relative_to(folder.resolve()).as_posix()
        except ValueError:
            path = str(self.path.resolve())
        self.substrates.register_experiment(self.substrate.label, {
            "uuid": uuid_text, "label": self.experiment_label, "path": path,
            "started": utc_timestamp(), "objective": self.objective, "status": schema.STATUS_CREATED,
            "center_um": [float(v) for v in self.absolute_grid_center],
            "double_corner_um": list(double.center_um) if double is not None else None,
            "double_corner_rotation_deg": double.rotation_deg if double is not None else None,
        })

    def _update_substrate_index(self) -> None:
        """ Copy the experiment status into the index of its substrate. """

        if self.substrate is not None:
            self.substrates.update_experiment(self.substrate.label, self.qr_text, status=self.store.read_status())

    def _relative(self, file) -> str:
        """ Return ``file`` relative to the experiment folder (POSIX form), or unchanged if outside it. """

        try:
            return Path(file).resolve().relative_to(self.path.resolve()).as_posix()
        except ValueError:
            return str(file)

    def _absolute(self, file) -> Path:
        """ Return a stored path as absolute path; relative paths are relative to the experiment folder. """

        file = Path(file)
        return file if file.is_absolute() else self.path / file

    def _log_file(self) -> Optional[str]:
        """ Return the file of the most recently added file handler of the logger, or None. """

        files = [h.baseFilename for h in self.log.handlers if isinstance(h, logging.FileHandler)]
        return files[-1] if files else None

    @staticmethod
    def _parameters_from_file(path: Path) -> dict:
        """ Constructor arguments from the experiment file in ``path``. """

        record = ExperimentStore.open(path).read()
        values = record.parameters
        arguments = {}
        for argument, _, name, kind in schema.PARAMETERS:
            value = values[name]
            if argument in ("resin_corner_tr", "resin_corner_bl", "absolute_grid_center"):
                value = Point2D(*[float(v) for v in value])
            elif kind == "vector":
                value = tuple(float(v) for v in value)
            elif kind == "ivector":
                value = tuple(int(v) for v in value)
            elif kind == "enum":
                value = DropDirection[value]
            arguments[argument] = value
        return {
            "path": path,
            "user": record.user["key"],
            "objective": record.objective["key"],
            "logger": getLogger(logfile=path / Path(values.get("log_file") or "console.log").name),
            "sys_args": record.system["sys_args"],
            **arguments,
            "resume": True,
        }

    @staticmethod
    def parameters_from_dictionary(path) -> dict:
        """ Rebuild the constructor arguments of a stored experiment.

        Reads the experiment file ``experiment.h5`` or, in folders written
        before it existed, ``experiment_dictionary.json``, e.g. to restart an
        aborted print with
        ``Experiment(**Experiment.parameters_from_dictionary(path))``. Vectors
        may be stored as numbers or, in older files, as strings. The
        experiment folder is ``path`` itself, not the folder stored in the
        file, so that a moved or copied experiment can be restarted.

        Parameters
        ----------
        path : str or Path
            Experiment folder.

        Returns
        -------
        dict
            Keyword arguments for :class:`Experiment`. ``logger`` writes to the
            stored log file (or ``console.log`` in the folder); ``resume`` is
            True, so that the stored experiment is continued.
        """

        path = Path(path)
        if ExperimentStore.exists(path):
            arguments = Experiment._parameters_from_file(path)
            identification = ExperimentStore.open(path).read_identification()
            if identification["substrate_label"] and (path.parent / "substrate.json").exists():
                arguments |= {"substrate": identification["substrate_label"], "data_root": path.parent.parent,
                              "allow_synced_root": True}
            return arguments
        data = json.loads((path / "experiment_dictionary.json").read_text())

        def vector(text) -> list[float]:
            # Numbers ([5720.0, 27190.0]) or, in older files, str(): "[5720. 27190.]" or "(500, 500)"
            if isinstance(text, (list, tuple)):
                return [float(v) for v in text]
            return [float(v) for v in str(text).strip("[]() ").replace(",", " ").split()]

        # An experiment in a substrate folder is continued with its substrate record
        substrate = {}
        if data.get("substrate_label") and (path.parent / "substrate.json").exists():
            substrate = {"substrate": data["substrate_label"], "data_root": path.parent.parent,
                         "allow_synced_root": True}

        # The log file is looked up in the given folder (older files store absolute paths)
        logfile = path / Path(data.get("logger") or "console.log").name
        return {
            "path": path,
            "user": data["user"],
            "objective": data["objective"],
            "logger": getLogger(logfile=logfile),
            "sys_args": data["sys_args"],
            "default_power": data["default_power"],
            "low_speed_um": data["low_speed_um"],
            "high_speed_um": data["high_speed_um"],
            "resin_corner_tr": Point2D(*vector(data["resin_corner_tr"])),
            "resin_corner_bl": Point2D(*vector(data["resin_corner_bl"])),
            "structure_size": data["structure_size"],
            "margin": data["margin"],
            "padding": data["padding"],
            "absolute_grid_center": Point2D(*vector(data["absolute_grid_center"])),
            "grid": tuple(int(v) for v in vector(data["grid_size"])),
            "n_mid_points": data["n_mid_points"],
            "drop_direction": DropDirection(data["drop_direction"]),
            "corner_z": data["corner_z"],
            "corner_width": data["corner_width"],
            "corner_length": data["corner_length"],
            "corner_height": data["corner_height"],
            "corner_hatch": data["corner_hatch"],
            "corner_slice": data["corner_slice"],
            "fov_dim": tuple(vector(data["fov_dim"])),
            "skip_corner": bool(data["skip_corner"]),
            "plane_fit_mode": data["plane_fit_mode"],
            "setup": data["setup"] or "IFOV_off",
            "resume": True,
            **substrate,
        }

    def iter_experiment_locations(self) -> Iterator[tuple[float, float]]:
        """ Return experiment locations in um """
        for i in range(self.grid[0]):
            for j in range(self.grid[1]):
                rect_x = self.rectangle_tl[0] + self.margin + j * (self.structure_size + self.padding)
                rect_y = self.rectangle_tl[1] + self.margin + i * (self.structure_size + self.padding)
                yield rect_x + self.structure_size / 2, rect_y + self.structure_size / 2

    def structure_location(self, index) -> Point2D:
        i, j = divmod(index, self.grid[1])
        rect_x = self.rectangle_tl[0] + self.margin + j * (self.structure_size + self.padding)
        rect_y = self.rectangle_tl[1] + self.margin + i * (self.structure_size + self.padding)
        return Point2D(rect_x + self.structure_size / 2, rect_y + self.structure_size / 2)

    def corner_location(self, position: CornerPosition) -> Point2D:
        if position == CornerPosition.TL:
            point = self.rectangle_tl
        elif position == CornerPosition.TR:
            point = self.rectangle_tr
        elif position == CornerPosition.BL:
            point = self.rectangle_bl
        elif position == CornerPosition.BR:
            point = self.rectangle_br
        else:
            raise ValueError(f'Unknown position string "{position}"')
        return Point2D(*point)

    def qrcode_location(self) -> Point2D:
        point = (self.rectangle_tl + self.rectangle_tr) / 2
        return Point2D(*point)

    @property
    def center_point(self) -> np.ndarray:
        return (self.resin_corner_bl + self.resin_corner_tr) / 2

    @property
    def resin_size(self) -> np.ndarray:
        return self.resin_corner_tr - self.resin_corner_bl

    @property
    def grid_center(self) -> np.ndarray:
        return np.asarray([
            self.absolute_grid_center[0] - self.center_point[0],
            self.absolute_grid_center[1] - self.center_point[1]
        ]
        )

    @property
    def grid_width(self) -> float:
        return self.grid[1] * (self.structure_size + self.padding) - self.padding + 2 * self.margin

    @property
    def grid_height(self) -> float:
        return self.grid[0] * (self.structure_size + self.padding) - self.padding + 2 * self.margin

    @property
    def rectangle_tl(self) -> np.ndarray:
        return self.center_point + self.grid_center - [self.grid_width / 2, self.grid_height / 2]

    @property
    def rectangle_br(self) -> np.ndarray:
        return self.center_point + self.grid_center + [self.grid_width / 2, self.grid_height / 2]

    @property
    def rectangle_tr(self) -> np.ndarray:
        return self.center_point + self.grid_center + [self.grid_width / 2, -self.grid_height / 2]

    @property
    def rectangle_bl(self) -> np.ndarray:
        return self.center_point + self.grid_center + [-self.grid_width / 2, self.grid_height / 2]

    def sample_points_for_plane_fitting(self) -> list[tuple[float, float]]:
        n_rows = self.grid[0]  # + 1
        n_cols = self.grid[1]
        points = []
        if self.plane_fit_mode == 0:  # plane fitting points also in between structures
            for i in range(n_rows + 1):
                for j in range(n_cols + 1):
                    x = float(self.rectangle_tl[0]) + self.margin - 0.5 * self.padding + j * (
                            self.structure_size + self.padding)
                    y = float(self.rectangle_tl[1]) + self.margin - 0.5 * self.padding + i * (
                            self.structure_size + self.padding)
                    points.append((x, y))
        elif self.plane_fit_mode == 1:
            x0 = float(self.rectangle_tl[0]) + self.margin - 0.5 * self.padding
            x1 = float(self.rectangle_tl[0]) + self.margin - 0.5 * self.padding + n_cols * (
                    self.structure_size + self.padding)
            y0 = float(self.rectangle_tl[1]) + self.margin - 0.5 * self.padding
            y1 = float(self.rectangle_tl[1]) + self.margin - 0.5 * self.padding + n_rows * (
                    self.structure_size + self.padding)
            points.append((x0, y0))
            points.append((x0, y1))
            points.append((x1, y0))
            points.append((x1, y1))
        else:
            raise NotImplementedError(f"Plane fit mode {self.plane_fit_mode} is not implemented!")
        return points

    # def sample_points_for_plane_fitting_old(self) -> list[tuple[float, float]]:
    #     tl = self.rectangle_tl + self.margin / 2
    #     br = self.rectangle_br - self.margin / 2
    #     points = set()
    #     for x in np.linspace(tl[0], br[0], self.n_mid_points + 2):
    #         points.add((x, tl[1]))
    #         points.add((x, br[1]))
    #
    #     for y in np.linspace(tl[1], br[1], self.n_mid_points + 2):
    #         points.add((tl[0], y))
    #         points.add((br[0], y))
    #
    #     return list(points)

    def plot_experiment(self, show: bool = True):
        # Visualize experiment
        fig, ax = plt.subplots()
        assert isinstance(ax, plt.Axes)

        # Draw the ellipse
        ellipse = Ellipse(self.center_point, self.resin_size[0], self.resin_size[1], edgecolor='lightblue',
                          facecolor='none', lw=2, label="Resin Drop")
        ax.add_patch(ellipse)

        # Draw the outer rectangle
        outer_rectangle = Rectangle(self.rectangle_tl, self.grid_width, self.grid_height, edgecolor='blue',
                                    facecolor='none', lw=2, label="Experiment Field")
        ax.add_patch(outer_rectangle)

        # Draw the grid of rectangles
        center_xs = []
        center_ys = []
        for i, (x, y) in enumerate(self.iter_experiment_locations()):
            x_tl = x - self.structure_size / 2
            y_tl = y - self.structure_size / 2
            rect = Rectangle(
                (x_tl, y_tl),
                width=self.structure_size,
                height=self.structure_size,
                edgecolor='green',
                facecolor='none',
                lw=1
            )
            ax.text(x_tl, y_tl, f"{i}", color="green")
            ax.add_patch(rect)
            center_xs.append(x)
            center_ys.append(y)

        ax.scatter(center_xs, center_ys, s=3, marker="x", color="green", label="Structures")

        plane_fit_points = self.sample_points_for_plane_fitting()
        ax.scatter(*zip(*plane_fit_points), s=3, marker=".", color="red", label="Plane Fitting Probe Points")

        # Set limits and aspect ratio
        ax.set_xlim(self.resin_corner_bl[0], self.resin_corner_tr[0])
        ax.set_ylim(self.resin_corner_bl[1], self.resin_corner_tr[1])
        ax.set_xlabel("X [um]")
        ax.set_ylabel("Y [um]")
        ax.set_aspect('equal')
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.path / "experiment.png")
        self.store.write_layout(self._layout(), (self.path / "experiment.png").read_bytes())
        if show:
            plt.show()

    def plane_fit(self, force: bool = False, *, plane: Optional[ZFunction] = None):
        """ Determine the substrate surface and the global coordinate system.

        Parameters
        ----------
        force : bool
            Measure again even if stored plane detection results exist.
        plane : ZFunction, optional
            Known substrate surface (z in µm as function of x, y in µm). If
            given, no measurement is done and this plane is used directly,
            e.g. for dry runs with the dummy backend.
        """
        if plane is not None:
            self.plane_fit_function = plane
            self.log.info(f"Using given substrate plane {plane!r} (no plane detection)")
            self._store_plane_fit(plane, source="given", interface="", points=np.empty((0, 3)))
            self._init_coordinate_system(plane)
            return

        path = self.path / "planefit"
        mkdir(path, clean=False)
        plane_dc_path = path / "plane.zdc"

        if not force and plane_dc_path.exists():
            self.log.info("Load plane detection results...")
            dc = Container(file=str(plane_dc_path))
            source = "loaded"

        else:
            source = "measured"
            # Plane needs micrometer coordinates
            if self.system.objective['magnification'] == 63.0:
                zlo = self.system.z0
                zup = None
            else:
                zlo = zup = self.system.z0

            plane = Plane(zlo, zup, self.system, self.log, **self.sys_args)

            self.log.info("Store background image...")
            plane.layer.focus.imgBack.write(str(path / "back.zdc"))

            self.log.info("Run plane detection...")
            for x, y in self.sample_points_for_plane_fitting():
                plane.run(x, y, path=path)

            self.log.info("Store plane detection results...")
            dc = plane.container()
            dc.write(str(plane_dc_path))

        interface = "low" if self.drop_direction == DropDirection.DOWN else "high"
        plane_points = dc["meas/result.json"][interface]["points"]
        plane_fit_function = PlaneFit.from_points(np.asarray(plane_points))  # in um
        self.plane_fit_function = plane_fit_function
        self.log.info(str(plane_fit_function))
        containers = {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*.zdc"))}
        self._store_plane_fit(plane_fit_function, source=source, interface=interface,
                              points=np.asarray(plane_points, dtype=float), containers=containers)
        self._init_coordinate_system(plane_fit_function)

    def _store_plane_fit(self, z_function: ZFunction, *, source: str, interface: str, points: np.ndarray,
                         containers: Optional[dict[str, bytes]] = None) -> None:
        """ Store the substrate plane used for this experiment. """

        name, parameters = z_function_to_json(z_function)
        self.store.write_plane_fit(PlaneFitRecord(
            mode=str(self.plane_fit_mode), source=source, function=name, function_json=parameters,
            interface=interface, sample_points_um=np.asarray(self.sample_points_for_plane_fitting(), dtype=float),
            interface_points_um=points), containers)
        self._save_exp_dict()

    def _init_coordinate_system(self, z_function: ZFunction):
        """ Create the global coordinate system from the substrate surface. """

        self.coordinate_system_grid_to_absolute = CoordinateSystem(
            offset_x=self.absolute_grid_center[0],
            offset_y=self.absolute_grid_center[1],
            z_function=z_function,
            drop_direction=self.drop_direction,
            unit=Unit.um
        )

        self.log.info("Done.")

    def opl_scan(self, m0: float = None, force: bool = False) -> float:
        if self.system.dhm is None:
            return 0
        path = self.path / "oplscan"
        mkdir(path, clean=False)

        opl_dc_path = path / "opl.txt"
        if not force and opl_dc_path.exists():
            with open(opl_dc_path, "r") as fp:
                m0 = float(fp.readline())
            self.log.info(f"Retrieved OPL motor pos {m0:.1f} µm")
            source = "loaded"
        else:
            source = "measured"
            image_center = self.coordinate_system_grid_to_absolute.convert({"X": 0, "Y": 0, "Z": 0})
            self.a3200.api.LINEAR(**image_center, F=2)  # Slower, as we also move in z direction and it is scary

            # Dummy call to avoid low intensity images on motorscan.
            optImageMedian(dhm=self.system.dhm, vmedian=127, logger=self.log)

            m0 = self.system.dhm.motorscan(m0)
            self.log.info(
                f"OPL motor pos at {image_center}: {self.system.dhm.device.MotorPos:.1f} µm (set: {m0:.1f} µm)")
            with open(opl_dc_path, "w") as fp:
                fp.write(str(m0))

        self.system.dhm.device.MotorPos = m0
        self.store.write_opl_scan(m0, source)
        return m0

    def add_corner_structures(self):

        # Reference point (Note: reference <> center for corners)
        reference_point = Point3D(0, 0, self.corner_z)

        # Top-right corner
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=90,
            F=self.high_speed_um,
            mark=False)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_tr",
            structure=corner,
            corner=CornerPosition.TR)

        # Top-left corner (marked)
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=0,
            F=self.high_speed_um,
            mark=True)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_tl",
            structure=corner,
            corner=CornerPosition.TL)

        # Bottom-left corner
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=270,
            F=self.high_speed_um,
            mark=False)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_bl",
            structure=corner,
            corner=CornerPosition.BL)

        # Bottom-right corner
        corner = Corner(
            reference_point,
            length=self.corner_length,
            width=self.corner_width,
            height=self.corner_height,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            rotation_degree=180,
            F=self.high_speed_um,
            mark=False)
        self.add_structure(
            structure_type=StructureType.CORNER,
            name="corner_br",
            structure=corner,
            corner=CornerPosition.BR)

    def add_qrcode_structure(self):

        # Reference point (center of QR code)
        reference_point = Point3D(0, 0, self.corner_z)
        qrcode = QRCode(
            reference_point,
            text=self.qr_text,
            version=None,
            error_correction=QrErrorCorrection.Q,
            pixel_pitch=4.0,
            base_height=7.0,
            anchor_height=2.0,
            pixel_height=5.0,
            slice_size=self.corner_slice,
            hatch_size=self.corner_hatch,
            horizontal_velocity=self.high_speed_um,
            horizontal_acceleration=self.accel_a_um,
            vertical_velocity=300,
            vertical_acceleration=self.accel_z_um)
        qrcode.get_image().save(os.path.join(self.path, "qr_code_image.png"))
        self.add_structure(
            structure_type=StructureType.QRCODE,
            name="qrcode",
            structure=qrcode)

    def skip_structure(self):
        return self.add_structure(StructureType.DUMMY, "dummy")

    def add_structure(self,
                      structure_type: StructureType,
                      name: str,
                      structure: Optional[DrawableObject] = None,
                      corner: Optional[CornerPosition] = None,
                      axes: str = None,
                      power: float = None):
        """ Add a structure to the experiment.

        Parameters
        ----------
        structure_type : StructureType
            ``REPEAT`` prints the most recent grid structure (or, for a
            repeat, its original) again in the next grid cell; ``structure``,
            ``axes`` and ``power`` are taken from that structure and the name
            becomes ``<original>_rep<n>``.
        name : str
            Structure name; ``_(<i>)`` is appended if the name is used already.
        structure : DrawableObject, optional
        corner : CornerPosition, optional
            Position of a corner structure.
        axes : str, optional
            Printing axes, default ``"ABZ"``.
        power : float, optional
            Laser power in mW, default ``default_power``.

        Returns
        -------
        str
            The name the structure got.
        """

        repeat_of = ""

        # Sanity checks for normal structure
        if structure_type == StructureType.DUMMY:
            pass

        # Sanity checks for normal structure
        elif structure_type == StructureType.NORMAL:
            assert structure is not None
            n_structures = sum(
                [s["structure_type"] in (
                    StructureType.NORMAL, StructureType.DUMMY, StructureType.REPEAT, StructureType.STITCHING,
                    StructureType.IFOV) for s in
                 self.structures])
            if n_structures >= self.grid[0] * self.grid[1]:
                raise ValueError(f"Too many structures for structure {name}!")

        # Sanity checks for corner structure
        elif structure_type == StructureType.CORNER:
            assert structure is not None
            assert isinstance(corner, CornerPosition)
            corners = [s["corner"] for s in self.structures if s["structure_type"] == StructureType.CORNER]
            if corner in corners:
                raise ValueError(f"Corner position {corner} added twice for corner {name}!")

        # Sanity checks for QR code
        elif structure_type == StructureType.QRCODE:
            assert structure is not None
            n_qrcodes = sum([s["structure_type"] == StructureType.QRCODE for s in self.structures])
            if n_qrcodes != 0:
                raise ValueError(f"More than one QR code given!")

        elif structure_type == StructureType.STITCHING:
            # process should be like serveral different strucutres printed after another?
            # strategy is then only tile wise
            pass

        elif structure_type == StructureType.IFOV:
            assert structure is not None
            n_structures = sum(
                [s["structure_type"] in (
                    StructureType.NORMAL, StructureType.DUMMY, StructureType.REPEAT, StructureType.STITCHING,
                    StructureType.IFOV) for s in
                 self.structures])
            if n_structures >= self.grid[0] * self.grid[1]:
                raise ValueError(f"Too many structures for structure {name}!")

        elif structure_type == StructureType.REPEAT:
            grid_types = (StructureType.NORMAL, StructureType.DUMMY, StructureType.REPEAT, StructureType.STITCHING,
                          StructureType.IFOV)
            grid_structures = [s for s in self.structures if s["structure_type"] in grid_types]
            if len(grid_structures) >= self.grid[0] * self.grid[1]:
                raise ValueError(f"Too many structures for a repetition of {name}!")
            printable = [s for s in grid_structures if s["structure_type"] != StructureType.DUMMY]
            if not printable:
                raise ValueError("A structure has to be added before it can be repeated.")
            original_name = printable[-1].get("repeat_of") or printable[-1]["name"]
            original = next(s for s in self.structures if s["name"] == original_name)
            repeat_of = original_name
            number = 1 + sum(s.get("repeat_of") == original_name for s in self.structures)
            name = f"{original_name}_rep{number}"
            structure = original["structure"]
            axes = original["axes"]
            power = original["power"]

        # Unknown structure type
        else:
            raise ValueError(f"Unknown structure type {structure_type}!")

        # Make sure that each structure has an individual name
        names = [s["name"] for s in self.structures]
        if name in names:
            i = 1
            while f"{name}_({i})" in names:
                i += 1
            name = f"{name}_({i})"

        # Power and axes have default values
        if power is None:
            power = self.default_power
        if axes is None:
            axes = "ABZ"

        # Add structure to list
        self.structures.append({
            "structure_type": structure_type,
            "name": name,
            "structure": structure,
            "axes": axes,
            "power": power,
            "corner": corner,
            "repeat_of": repeat_of,
        })

        # Aware: name may have changed
        return name

    def structure_program(self,
                          x: float,
                          y: float,
                          structure: DrawableObject,
                          name: str,
                          printing_axes: str,
                          power: float,
                          path: Path,
                          n_dhm_img: int = 0,
                          stitching: bool = False):
        plotting_structure = False
        # if not stitching:
        #     plotting_structure = True
        self.log.info(f"Creating layer programs for {name}: {structure}")
        assert isinstance(structure, DrawableObject)

        path = path / name
        mkdir(path, clean=False)
        pgm_path = path / "programs"
        mkdir(pgm_path, clean=False)

        # Make sure that power is not None
        power = float(power)

        # Absolute center coordinates
        offset_x = structure.center_point.X
        offset_y = structure.center_point.Y
        z = self.plane_fit_function(x, y)
        structure_center_absolute_um = {
            "X": x + offset_x,
            "Y": y + offset_y,
            "Z": z,
        }
        structure_center_absolute_mm = {k: v * Unit.um.value for k, v in structure_center_absolute_um.items()}

        # Coordinate systems of stages and galvo scanner
        coordinate_system_stage = CoordinateSystem(
            offset_x=structure_center_absolute_um["X"],
            offset_y=structure_center_absolute_um["Y"],
            z_function=structure_center_absolute_um["Z"],
            drop_direction=self.drop_direction,
            unit=Unit.um
        )
        coordinate_system_galvo = CoordinateSystem(
            offset_x=-offset_x,
            offset_y=-offset_y,
            z_function=structure_center_absolute_um["Z"],
            drop_direction=self.drop_direction,
            unit=Unit.um
        )
        coordinate_system_galvo.axis_mapping = {"X": "A", "Y": "B"}

        # Generate structure and layer programs
        if printing_axes == "ABZ":
            coordinate_system = coordinate_system_galvo
        else:
            coordinate_system = coordinate_system_stage
        structure_pgm = DrawableAeroBasicProgram(coordinate_system)
        layer_pgm_paths = []
        # NOTE What to do with tiles
        x_structure_center = structure_center_absolute_mm["X"]
        y_structure_center = structure_center_absolute_mm["Y"]

        if stitching:
            for _ in structure.iterate_layers(coordinate_system):
                pass

        #     layer_pgm.add_programm(layer)
        #     # ... rest
        #
        #
        # for layer_id, layer in enumerate(structure.iterate_layers(coordinate_system)):
        #     # AeroBasic program for given layer
        #     layer_pgm = AeroBasicProgram()
        #
        #
        #     layer_pgm.LINEAR(X=x_center, Y=y_center)  # move to reference point for galvo scanner

        for layer_id, layer in enumerate(structure.iterate_layers(coordinate_system)):
            layer_pgm = AeroBasicProgram()

            if stitching:  # apparently works!
                x_offset, y_offset = structure.get_tile_center_for_layer(layer_id)
                x_value = x_structure_center + x_offset / 1000
                y_value = y_structure_center + y_offset / 1000
            else:
                x_value = x_structure_center
                y_value = y_structure_center

            layer_pgm.LINEAR(X=x_value, Y=y_value)

            layer_pgm.add_programm(layer)

            # Store layer program file
            layer_pgm_path = pgm_path / f"program_{name}.{layer_id:03d}.txt"
            layer_pgm.write(layer_pgm_path)
            layer_pgm_paths.append(str(layer_pgm_path))

            # Add layer program to structure program
            structure_pgm.add_programm(layer_pgm)

        # Store structure program file
        structure_pgm_path = path / f"program_{name}.txt"
        structure_pgm.write(structure_pgm_path)

        # Structure configuration
        structure_config = {
            "name": name,
            "axes": printing_axes,
            "power": power,
            "center_x": structure_center_absolute_um["X"],
            "center_y": structure_center_absolute_um["Y"],
            "center_z": structure_center_absolute_um["Z"],
            "structure": structure.to_json(),
            "program_file": str(structure_pgm_path),
            "layer_files": layer_pgm_paths,
            "number of dhm images": n_dhm_img,
        }

        if plotting_structure:
            # Plot structure to image file
            self.log.info(f"Plotting {name}")
            movements = read_file(structure_pgm_path)
            plot_movements(movements)
            plt.savefig(path / f"plot_{name}.png")
            plt.close()

        # Done
        return layer_pgm_paths, structure_config

    def build_programs(self):
        # Structures that set the laser power (IFOV) use the calibration of this system's attenuator
        with power_calibration(PowerCalibration(self.system.controller.attenuator.data)):
            self._build_programs()

    def _build_programs(self):

        path = self.path / "structures"
        mkdir(path, clean=False)

        self.structure_programs = []
        self.structure_configs = []
        structure_id = 0
        for structure_dict in self.structures:
            self.log.info(f'Creating program for {structure_dict["name"]}: {structure_dict["structure"]}')

            # Skip dummy structure
            if structure_dict["structure_type"] == StructureType.DUMMY:
                structure_id += 1
                n_dhm_img = 0
                continue

            # Reference point of normal structure
            elif structure_dict["structure_type"] == StructureType.NORMAL:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = False

            elif structure_dict["structure_type"] == StructureType.STITCHING:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = True

            elif structure_dict["structure_type"] == StructureType.IFOV:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = False

            elif structure_dict["structure_type"] == StructureType.REPEAT:
                x, y = self.structure_location(structure_id).as_tuple()
                n_dhm_img = 10
                structure_id += 1
                stitching = False

            # Reference point of corner structure
            elif structure_dict["structure_type"] == StructureType.CORNER:
                corner_pos = structure_dict["corner"]
                x, y = self.corner_location(corner_pos).as_tuple()
                n_dhm_img = 1
                stitching = False
                dhm_stitching = True  # to be done in the future

            # Reference point of qrcode
            elif structure_dict["structure_type"] == StructureType.QRCODE:
                x, y = self.qrcode_location().as_tuple()
                n_dhm_img = 1
                stitching = False

            # Unknown structure type
            else:
                raise ValueError(f"Unknown structure type {structure_dict['structure_type']}!")

            # Store all layer programs and get path list and list of configuration dictionaries
            paths, config = self.structure_program(
                x=x,
                y=y,
                structure=structure_dict["structure"],
                name=structure_dict["name"],
                printing_axes=structure_dict["axes"],
                power=structure_dict["power"],
                path=path,
                n_dhm_img=n_dhm_img,
                stitching=stitching)
            self.structure_programs.append(paths)
            grid_types = (StructureType.NORMAL, StructureType.STITCHING, StructureType.IFOV, StructureType.REPEAT)
            grid_index = structure_id - 1 if structure_dict["structure_type"] in grid_types else -1
            self._store_structure(structure_dict, config, index=len(self.structure_programs) - 1,
                                  grid_index=grid_index, reference=(x, y))

        # structures.json is a copy of the structures in the experiment file
        self.store.set_status(schema.STATUS_BUILT)
        self._save_exp_dict()
        self.log.info("Experiment summary:\n" + format_table(self._write_summary()))
        self.structure_configs = self._with_absolute_paths(structures_list(self.store.read()))

    def _layer_order(self) -> int:
        """ +1 if layers are printed with ascending ids (drop direction UP), -1 otherwise. """

        return 1 if self.drop_direction == DropDirection.UP else -1

    def _store_structure(self, structure_dict: dict, config: dict, *, index: int, grid_index: int,
                         reference: tuple[float, float]) -> None:
        """ Write a built structure and its programs into the experiment file. """

        structure = structure_dict["structure"]
        name = config["name"]
        self._stored_structures.add(name)
        self.store.add_structure(StructureRecord(
            index=index, name=name, type=structure_dict["structure_type"].name, grid_index=grid_index,
            corner_position=structure_dict["corner"].name if structure_dict["corner"] is not None else "",
            axes=config["axes"], setup=self.setup,
            center_um=(config["center_x"], config["center_y"], float(config["center_z"])),
            reference_um=tuple(float(v) for v in reference), power_mw=config["power"],
            structure_class=f"{type(structure).__module__}.{type(structure).__qualname__}",
            config=config["structure"], layer_files=[self._relative(f) for f in config["layer_files"]],
            program_file=self._relative(config["program_file"]),
            layer_order=self._layer_order(), dhm_image_count=config["number of dhm images"],
            repeat_of=structure_dict.get("repeat_of", "")))
        for file in config["layer_files"]:
            self.store.write_layer_program(name, self._layer_id(file), Path(file).read_text(),
                                           self._relative(file))
        self.store.write_structure_program(name, Path(config["program_file"]).read_text())

    @staticmethod
    def _layer_id(file) -> int:
        """ Layer id from a layer program file name ``program_<name>.<iii>.txt``. """

        return int(str(file).split('.')[-2])

    def _ensure_structure(self, name: str, layer_files: list[Path], x: float, y: float, power: float,
                          dhm_image_count: int) -> None:
        """ Register a structure printed without build_programs() (e.g. a direct print_structure call). """

        if name in self._stored_structures:
            return
        self._stored_structures.add(name)
        if self.store.has_structure(name):
            return
        self.store.add_structure(StructureRecord(
            index=-1, name=name, type="DIRECT", grid_index=-1, corner_position="", axes="", setup=self.setup,
            center_um=(float(x), float(y), float("nan")), reference_um=(float(x), float(y)),
            power_mw=float(power), structure_class="", config={}, layer_files=[self._relative(f) for f in layer_files],
            program_file="", layer_order=self._layer_order(), dhm_image_count=int(dhm_image_count)))

    def retrieve_programs(self):
        """ Load the structure configurations from ``structures.json`` (paths made absolute). """

        structure_configs_path = self.path / "structures.json"
        self.structure_configs = self._with_absolute_paths(json.loads(structure_configs_path.read_text()))

    def _with_absolute_paths(self, configs: list[dict]) -> list[dict]:
        """ Return structure configurations with absolute program paths.

        The stored copies hold paths relative to the experiment folder; in
        memory the configurations use absolute paths, as before.
        """

        for config in configs:
            config["layer_files"] = [str(self._absolute(f)) for f in config["layer_files"]]
            if config.get("program_file"):
                config["program_file"] = str(self._absolute(config["program_file"]))
        return configs

    def print_structure(self,
                        pgm_files_list: list[Path],
                        x: float,  # um
                        y: float,  # um
                        name: str,
                        power: float,
                        dhm_image_count: int = 0,
                        restart: bool = False):

        self._ensure_structure(name, pgm_files_list, x, y, power, dhm_image_count)
        self.store.set_status(schema.STATUS_PRINTING)
        self.store.set_structure_status(name, "printing")

        self.log.info(f"Printing {name}")
        # program files angucken
        # allgmein power

        # Set laser power
        self.system.controller.power(power)

        # Absolute coordinates of structure center
        structure_center_absolute_mm = {"X": x / 1000, "Y": y / 1000}

        # Images before structure writing
        if not restart:
            self.measure(structure_center_absolute_mm, structure=name, phase="before",
                         dhm_image_count=dhm_image_count)

        # Prepare order of layer writing
        order = self._layer_order()

        # Write all layers of the structure
        failed = False
        t1 = time.time()
        for index in range(len(pgm_files_list))[::order]:
            layer_pgm_path = pgm_files_list[index]
            layer_id = self._layer_id(layer_pgm_path)
            started = utc_timestamp()
            # Details about the program: if a program exceeds a certain size, consider splitting it
            try:
                task = self.a3200.run_program_as_task(layer_pgm_path, task_id=1)
                task.wait_to_finish()
                task.finish()
                self.store.update_progress(name, layer_id, "ok", started=started)
                self.measure(structure_center_absolute_mm, structure=name, phase="layer", layer_id=layer_id,
                             dhm_image_count=dhm_image_count)
            except AerotechError as e:
                self.log.error(f"Program failed for {name}: {e}")
                failed = True
                self.store.update_progress(name, layer_id, "failed", started=started, error=str(e))
                self._stop_failed_task(task_id=1)
            export_progress(self.store.read(include_captures=False), self.path)
        t2 = time.time()
        self.log.info(f"Making {name} took {t2 - t1:.2f}s")

        # Images after structure writing
        self.measure(structure_center_absolute_mm, structure=name, phase="after",
                     dhm_image_count=dhm_image_count + 10)
        self.store.set_structure_status(name, "failed" if failed else "printed")
        self._save_exp_dict()
        self._write_summary()

    def _stop_failed_task(self, task_id: int) -> None:
        """ Stop a task after a failed program, so that the next program can be loaded. """

        try:
            self.a3200.api.PROGRAM_STOP(task_id)
        except AerotechError as error:
            self.log.error(f"Could not stop task {task_id}: {error}")

    def print_experiment(self):
        if self.structure_configs is None:
            raise ValueError("No programs!")

        for structure_config in self.structure_configs:
            self.print_structure(
                [self._absolute(p) for p in structure_config["layer_files"]],
                x=structure_config["center_x"],
                y=structure_config["center_y"],
                name=structure_config["name"],
                power=structure_config["power"],
                dhm_image_count=structure_config["number of dhm images"]
            )
        self.store.set_status(schema.STATUS_FINISHED)
        self._save_exp_dict()
        self.log.info("Experiment summary:\n" + format_table(self._write_summary()))

    def restart_experiment(self):
        """ Print what an aborted run of this experiment left over.

        The resume point comes from the experiment file: structures that
        were printed (or failed) completely are skipped, and of the other
        structures every layer that was already printed or attempted in an
        earlier session is skipped. This works after any number of aborts.
        Structures that were never started get their "before" capture.

        Raises
        ------
        ValueError
            If the experiment has no built structures.
        """

        record = self.store.read()
        configs = {c["name"]: c for c in self._with_absolute_paths(structures_list(record))}
        structures = [s for s in record.structures if s.type != "DIRECT" and s.name in configs]
        if not structures:
            raise ValueError("No programs: the experiment has no built structures to restart.")
        self.structure_configs = [configs[s.name] for s in structures]

        for structure in structures:
            if structure.status in ("printed", "failed"):
                continue
            config = configs[structure.name]
            attempted = {event["layer_id"] for event in record.progress.get(structure.name, [])}
            layer_files = sorted((Path(f) for f in config["layer_files"]
                                  if self._layer_id(f) not in attempted), key=self._layer_id)
            started = bool(attempted) or structure.status == "printing"
            self.log.info(f"Resuming structure '{structure.name}': {len(layer_files)} of {structure.n_layers} "
                          f"layers left")
            self.print_structure(
                layer_files,
                x=config["center_x"],
                y=config["center_y"],
                name=structure.name,
                power=config["power"],
                dhm_image_count=config["number of dhm images"],
                restart=started
            )
        self.store.set_status(schema.STATUS_FINISHED)
        self._save_exp_dict()
        self.log.info("Experiment summary:\n" + format_table(self._write_summary()))

    def measure(self,
                coordinate: Coordinate,
                *,
                structure: str,
                phase: Literal["before", "layer", "after"] = "layer",
                layer_id: int = -1,
                dhm_image_count: int = 0,
                offsets_um: Optional[list[tuple[float, float]]] = None,
                ) -> list[tuple[Optional[Container], ImageContainer]]:
        """ Take DHM and camera captures at one or more positions.

        Every capture is stored in the experiment file with a
        :class:`CaptureRecord` that holds the commanded and the actual stage
        position. The returned containers carry the same record as
        ``data/capture.json``; they are not written to files
        (``ExperimentStore.export_capture`` writes a ``.zdc`` on request).

        Parameters
        ----------
        coordinate : dict
            Absolute X and Y of the structure center in mm.
        structure : str
            Structure the captures belong to.
        phase : {"before", "layer", "after"}
            When the capture is taken.
        layer_id : int
            Layer after which the capture is taken; -1 for before/after.
        dhm_image_count : int
            Number of holograms per DHM capture.
        offsets_um : list of (float, float), optional
            Capture positions as (x, y) offsets in µm from ``coordinate``.
            Default: one capture at ``coordinate``.

        Returns
        -------
        list of tuple
            ``(dhm_container, camera_container)`` per position;
            ``dhm_container`` is None without DHM.
        """

        offsets = [(0.0, 0.0)] if offsets_um is None else [(float(x), float(y)) for x, y in offsets_um]
        self._ensure_structure(structure, [], 1000 * coordinate["X"], 1000 * coordinate["Y"], 0.0, dhm_image_count)
        results = []
        for index, (dx, dy) in enumerate(offsets):
            target = dict(coordinate)
            target["X"] += dx / 1000
            target["Y"] += dy / 1000
            commanded = tuple(1000 * target[axis] if axis in target else None for axis in "XYZ")

            # Move to given absolute coordinate and read back where the stages are
            self.a3200.api.LINEAR(**target, F=20)
            actual = self.system.current_pos()

            def record(kind, image_count):
                return CaptureRecord(
                    kind=kind, structure=structure, phase=phase, layer_id=int(layer_id),
                    image_index=index, image_count=int(image_count), offset_um=(dx, dy),
                    commanded_um=commanded, actual_um=actual)

            # Take DHM image
            if self.system.dhm is not None:
                capture = record("dhm", dhm_image_count)
                dhm_container = self.system.dhm.container(opt=False, loc=actual, image_count=dhm_image_count)
                holograms, times = self._holograms(dhm_container)
                self.store.add_capture(capture, holograms, device=dhm_container["data/hologram.json"],
                                       capture_times_s=times)
                dhm_container["data/capture.json"] = capture.to_dict()
                self.log.info(f"DHM image: capture {capture.capture_id} of {structure} ({phase} {layer_id})")
            else:
                self.log.info(f"DHM images was not captured!")
                dhm_container = None

            # Take camera image
            capture = record("camera", 1)
            camera_container = self.system.camera.container(loc=actual)
            self.store.add_capture(capture, camera_container["meas/image.png"],
                                   device=camera_container["data/camera.json"])
            camera_container["data/capture.json"] = capture.to_dict()
            self.log.info(f"Camera image: capture {capture.capture_id} of {structure} ({phase} {layer_id})")

            results.append((dhm_container, camera_container))

        return results

    @staticmethod
    def _holograms(container) -> tuple[np.ndarray, list[float]]:
        """ Return the holograms (n×H×W) and capture durations of a DHM container. """

        n = 1 + sum(1 for key in container.keys() if key.startswith("meas/image_") and key.endswith(".png"))
        images = [container["meas/image.png"]] + [container[f"meas/image_{i}.png"] for i in range(1, n)]
        if "meas/image_capture_times.json" in container.keys():
            times = container["meas/image_capture_times.json"]
            durations = [times[f"Image_{i}_capture_time"] for i in range(n)]
        else:
            durations = [container["meas/image_capture_time.json"]]
        return np.stack(images), [float(t) for t in durations]


    # def measurement_factory(self,
    #         #system: System,
    #         coordinate: Coordinate,
    #         name: str,
    #         #*,
    #         #save_folder: Path
    # ) -> Callable[[int], None]:
    #     """
    #     Coordinate in mm in absolute coordinates
    #     """
    #
    #     def do_measurement(layer_id: int):
    #         # Move to given absolute coordinate
    #         self.a3200.api.LINEAR(**coordinate, F=20)
    #
    #         # Take DHM image
    #         dhm_container = self.system.dhm.container(opt=True)
    #         fn = self.path / "dhm" / f"hologram_{name}.{layer_id}.zdc"
    #         dhm_container.write(fn)
    #         self.log.info(f"Hologram image: '{fn}'")
    #
    #         # Take camera image
    #         camera_container = self.system.getimage()
    #         fn = self.path / "camera" / f"camera_{name}.{layer_id}.zdc"
    #         camera_container.write(fn)
    #         self.log.info(f"Camera image: '{fn}'")
    #
    #         return None
    #
    #     return do_measurement
