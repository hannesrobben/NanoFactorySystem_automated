##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Substrates, default data location and experiment index (docs/design/EXPERIMENT_STORAGE.md §3, §4, §8).

Layout below the data root of a user::

    <root>/<substrate label>/substrate.json
    <root>/<substrate label>/<experiment label>_<YYYYMMDD-HHMM>/experiment.h5

Record version 2 (T76, docs/design/INFORMATION_MODEL.md §3.2) adds the
substrate material, type and dimensions and, per resin drop, its material,
batch, thickness and application. A version-1 file is read as version 2 and
written as version 2 only when the record changes. Index entries may be
``planned`` (written by a substrate main before the run) and carry the area
the experiment occupies and the index of its resin drop;
:func:`substrate_overview` lists them with the status of the experiment file.
"""
import datetime
import json
import re
import string
import uuid as uuid_module
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .json_copies import write_json
from .locking import ExperimentLock
from .records import utc_timestamp

SUBSTRATE_FILE = "substrate.json"
SUBSTRATE_LOCK = "substrate.lock"
SUBSTRATE_SCHEMA_VERSION = "2.0"
DEFAULT_SYNC_FOLDER_NAMES = ("Seafile", "OneDrive", "Dropbox")
SUBSTRATE_TYPES = ("cover_slip", "slide", "wafer", "other")
DIMENSION_FIELDS = {"rectangle": ("width_mm", "length_mm", "thickness_um"),
                    "round": ("diameter_mm", "thickness_um")}
APPLICATIONS = ("drop", "dip_in")
STATUS_PLANNED = "planned"
# Status of the experiment file (or "planned") -> state shown in overviews
STATES = {"planned": "planned", "created": "running", "built": "running", "printing": "running",
          "finished": "done", "aborted": "aborted", "failed": "aborted"}


def check_substrate_fields(substrate_type: str = "", dimensions: Optional[dict] = None,
                           application: Optional[str] = None) -> None:
    """ Validate the version-2 fields of a substrate record.

    Raises
    ------
    ValueError
        For an unknown substrate type, shape, dimension field or resin
        application.
    """

    if substrate_type and substrate_type not in SUBSTRATE_TYPES:
        raise ValueError(f"Unknown substrate type {substrate_type!r}; known: {SUBSTRATE_TYPES}")
    dimensions = dimensions or {}
    shape = dimensions.get("shape")
    if shape is not None and shape not in DIMENSION_FIELDS:
        raise ValueError(f"Unknown substrate shape {shape!r}; known: {sorted(DIMENSION_FIELDS)}")
    allowed = set(DIMENSION_FIELDS.get(shape, ("thickness_um",))) | {"shape"}
    unknown = sorted(set(dimensions) - allowed)
    if unknown:
        raise ValueError(f"Dimensions {unknown} do not belong to shape {shape!r}; allowed: {sorted(allowed)}")
    if application is not None and application not in APPLICATIONS:
        raise ValueError(f"Unknown resin application {application!r}; known: {APPLICATIONS}")


def _upgrade_v1(data: dict) -> dict:
    """ Read a version-1 ``substrate.json`` as version 2 (INFORMATION_MODEL.md §6.4); the material dict is kept. """

    data = dict(data)
    material = data.get("material") or {}
    data.setdefault("substrate_material", str(material.get("substrate", "") or ""))
    if "dimensions" not in data:
        data["dimensions"] = {"thickness_um": float(material["thickness_um"])} \
            if material.get("thickness_um") is not None else {}
    drops = []
    for drop in data.get("resin_drops", []):
        drop = dict(drop)
        drop.setdefault("material", str(material.get("resin", "") or ""))
        drop.setdefault("batch", str(material.get("batch", "") or ""))
        thickness = material.get("resin_thickness_um")
        drop.setdefault("thickness_um", None if thickness is None else float(thickness))
        drop.setdefault("application", "drop")
        drops.append(drop)
    data["resin_drops"] = drops
    return data


class SyncedFolderError(ValueError):
    """ The data root lies inside a folder that is synchronised to a server. """


@dataclass
class SubstrateRecord:
    """ One physical substrate and the experiments printed on it.

    Parameters
    ----------
    label : str
        Hand-written label, e.g. ``"HR-26-001"``.
    uuid : str
        Internal substrate UUID.
    created : str
        Creation time (ISO 8601, UTC).
    user : str
        User key.
    material : dict
        Free dict of older mains (record version 1), kept unchanged, e.g.
        ``{"substrate": "boro-silicate glass", "thickness_um": 700.0,
        "resin": "SZ2080", "resin_thickness_um": 75.0}``.
    resin_drops : list of dict
        Resin drops, each with ``edges_um`` (list of (x, y)), ``added`` and
        (version 2) ``material`` (registry name of the resin), ``batch``,
        ``thickness_um`` and ``application`` (``"drop"`` or ``"dip_in"``).
    notes : str
        Free text.
    experiments : list of dict
        Index of the experiments on this substrate (see
        :meth:`SubstrateStore.register_experiment`).
    extra : dict
        Further information without a fixed field (e.g. keys of an old
        ``substrate_information.json``).
    substrate_material : str
        Registry name of the substrate material (kind ``substrate``), or free
        text.
    substrate_type : str
        ``"cover_slip"``, ``"slide"``, ``"wafer"``, ``"other"`` or ``""``
        (unknown).
    dimensions : dict
        ``shape`` (``"rectangle"`` / ``"round"``) and the fields of that
        shape (``width_mm``, ``length_mm`` / ``diameter_mm``) plus
        ``thickness_um``.
    """

    label: str
    uuid: str
    created: str
    user: str
    material: dict[str, Any] = field(default_factory=dict)
    resin_drops: list[dict] = field(default_factory=list)
    notes: str = ""
    experiments: list[dict] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    substrate_material: str = ""
    substrate_type: str = ""
    dimensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """ Return the content of ``substrate.json`` (record version 2). """

        return {"schema_version": SUBSTRATE_SCHEMA_VERSION, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "SubstrateRecord":
        """ Build a record from the content of ``substrate.json`` (version 1 is read as version 2). """

        if str(data.get("schema_version", "1.0")).split(".")[0] == "1":
            data = _upgrade_v1(data)
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**fields)

    def drop_index(self, edges_um) -> Optional[int]:
        """ Index of the resin drop with these edges, or None. """

        if edges_um is None:
            return None
        edges = [[float(v) for v in edge] for edge in edges_um]
        for index, drop in enumerate(self.resin_drops):
            if drop.get("edges_um") == edges:
                return index
        return None

    def material_names(self, drop: Optional[int] = None) -> dict:
        """ Material names for the material snapshots of an experiment on a drop (T75, T76).

        Parameters
        ----------
        drop : int, optional
            Index of the experiment's resin drop; default: the most recent
            drop.

        Returns
        -------
        dict
            The version-1 ``material`` dict, overridden by the substrate
            material and the drop's resin and batch where they are set (the
            form ``voxel.materials.material_names`` reads).
        """

        names = dict(self.material)
        if self.substrate_material:
            names["substrate"] = self.substrate_material
        drops = self.resin_drops if drop is None else self.resin_drops[drop:drop + 1]
        if drops:
            if drops[-1].get("material"):
                names["resin"] = drops[-1]["material"]
            if drops[-1].get("batch"):
                names["batch"] = drops[-1]["batch"]
        return names


def initials(user: dict) -> str:
    """ Return the initials of a user for substrate labels.

    Parameters
    ----------
    user : dict
        User section of the configuration (``initials``, ``name``, ``key``).

    Returns
    -------
    str
        The ``initials`` key if set, else the upper-case first letters of
        the words of ``name`` (``"Hannes Robben"`` → ``"HR"``), else the
        first two letters of the user key.
    """

    if user.get("initials"):
        return str(user["initials"]).upper()
    words = [w for w in re.split(r"[\s\-_.]+", str(user.get("name") or "")) if w]
    if words:
        return "".join(w[0] for w in words).upper()
    return str(user.get("key", "XX"))[:2].upper()


def check_not_synced(path: Path, names=DEFAULT_SYNC_FOLDER_NAMES) -> None:
    """ Refuse a data root inside a synchronised folder (design decision D1).

    Parameters
    ----------
    path : Path
        Data root.
    names : sequence of str
        Folder names of sync clients (case-insensitive).

    Raises
    ------
    SyncedFolderError
        If a component of the resolved path has one of the names.
    """

    lowered = {name.lower() for name in names}
    for part in Path(path).resolve().parts:
        if part.lower() in lowered:
            raise SyncedFolderError(
                f"The experiment data root {path} lies in a synchronised folder ({part}). A sync client may lock or "
                f"upload a half-written experiment file. Use another folder, set 'dataRoot' for the user in "
                f"nanofactory.json, or pass allow_synced_root=True.")


def default_root(user: str, *, allow_synced_root: bool = False) -> Path:
    """ Return the data root of a user.

    Parameters
    ----------
    user : str
        User key in the configuration.
    allow_synced_root : bool
        Accept a root inside a synchronised folder.

    Returns
    -------
    Path
        ``dataRoot`` of the user section if set, else
        ``~/Documents/Femtika_Experiment/<user>``.

    Raises
    ------
    SyncedFolderError
        If the root lies in a synchronised folder (see :func:`check_not_synced`).
    """

    from ..config import sysConfig

    section = sysConfig.user(user)
    root = Path(section["dataRoot"]).expanduser() if section.get("dataRoot") \
        else Path.home() / "Documents" / "Femtika_Experiment" / user
    if not allow_synced_root:
        names = sysConfig.section("system").get("syncFolderNames", DEFAULT_SYNC_FOLDER_NAMES)
        check_not_synced(root, names)
    return root


def experiment_letters(index: int) -> str:
    """ Return the experiment letter for an index: 0 → A, 25 → Z, 26 → AA, 27 → AB, … """

    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = string.ascii_uppercase[remainder] + letters
    return letters


class SubstrateStore:
    """ The substrates below one data root.

    Parameters
    ----------
    root : Path
        Data root of a user.
    """

    def __init__(self, root: Path):
        self.root = Path(root)

    def folder(self, label: str) -> Path:
        """ Folder of a substrate. """

        return self.root / label

    def _file(self, label: str) -> Path:
        return self.folder(label) / SUBSTRATE_FILE

    def labels(self) -> list[str]:
        """ Labels of all substrates below the root. """

        if not self.root.is_dir():
            return []
        return sorted(p.parent.name for p in self.root.glob(f"*/{SUBSTRATE_FILE}"))

    def next_label(self, user_initials: str, year: Optional[int] = None) -> str:
        """ Propose the next free substrate label ``<initials>-<yy>-<nnn>`` (counter restarts every year). """

        yy = (year if year is not None else datetime.date.today().year) % 100
        prefix = f"{user_initials}-{yy:02d}-"
        numbers = [int(label[len(prefix):]) for label in self.labels()
                   if label.startswith(prefix) and label[len(prefix):].isdigit()]
        return f"{prefix}{max(numbers, default=0) + 1:03d}"

    def create(self, user: str, user_initials: str, *, label: Optional[str] = None,
               material: Optional[dict] = None, resin_drops: Optional[list[dict]] = None, notes: str = "",
               extra: Optional[dict] = None, substrate_material: str = "", substrate_type: str = "",
               dimensions: Optional[dict] = None) -> SubstrateRecord:
        """ Create a substrate record.

        Parameters
        ----------
        user : str
            User key.
        user_initials : str
            Initials for the label (see :func:`initials`).
        label : str, optional
            Label; default: :meth:`next_label`.
        material, resin_drops, notes, extra, substrate_material, substrate_type, dimensions
            See :class:`SubstrateRecord`.

        Returns
        -------
        SubstrateRecord

        Raises
        ------
        FileExistsError
            If a substrate with that label exists.
        ValueError
            For an unknown substrate type, shape or dimension field.
        """

        check_substrate_fields(substrate_type, dimensions)
        label = label or self.next_label(user_initials)
        if self._file(label).exists():
            raise FileExistsError(f"Substrate {label} exists already in {self.root}")
        record = SubstrateRecord(label=label, uuid=str(uuid_module.uuid4()), created=utc_timestamp(), user=user,
                                 material=dict(material or {}), resin_drops=list(resin_drops or []), notes=notes,
                                 extra=dict(extra or {}), substrate_material=substrate_material,
                                 substrate_type=substrate_type, dimensions=dict(dimensions or {}))
        self.folder(label).mkdir(parents=True, exist_ok=True)
        write_json(self._file(label), record.to_dict())
        return record

    def get(self, label_or_uuid: str) -> SubstrateRecord:
        """ Return the substrate with the given label or UUID.

        Raises
        ------
        KeyError
            If there is no such substrate.
        """

        if self._file(label_or_uuid).exists():
            return SubstrateRecord.from_dict(json.loads(self._file(label_or_uuid).read_text()))
        for label in self.labels():
            record = self.get(label)
            if record.uuid == label_or_uuid:
                return record
        raise KeyError(f"No substrate {label_or_uuid!r} in {self.root}")

    def _update(self, label: str, change) -> SubstrateRecord:
        lock = ExperimentLock(self.folder(label) / SUBSTRATE_LOCK)
        lock.acquire()
        try:
            record = self.get(label)
            change(record)
            write_json(self._file(label), record.to_dict())
            return record
        finally:
            lock.release()

    def add_resin_drop(self, label: str, edges_um: list, *, material: str = "", batch: str = "",
                       thickness_um: Optional[float] = None, application: str = "drop") -> SubstrateRecord:
        """ Record a resin drop.

        Parameters
        ----------
        label : str
            Substrate label.
        edges_um : list of (x, y)
            Edges of the drop in µm.
        material, batch : str
            Registry name and batch of the resin (decision M3: material per drop).
        thickness_um : float, optional
            Resin thickness.
        application : {"drop", "dip_in"}
        """

        check_substrate_fields(application=application)
        return self._update(label, lambda r: r.resin_drops.append(
            {"edges_um": [list(map(float, e)) for e in edges_um], "added": utc_timestamp(),
             "material": material, "batch": batch,
             "thickness_um": None if thickness_um is None else float(thickness_um), "application": application}))

    def update_substrate(self, label: str, **fields) -> SubstrateRecord:
        """ Change fields of a substrate record (e.g. ``substrate_type``, ``dimensions``, ``notes``).

        Raises
        ------
        ValueError
            For fields that do not exist or cannot be changed (``label``,
            ``uuid``, ``created``, ``experiments``), or invalid values.
        """

        fixed = {"label", "uuid", "created", "experiments"}
        unknown = sorted(set(fields) - (set(SubstrateRecord.__dataclass_fields__) - fixed))
        if unknown:
            raise ValueError(f"Fields {unknown} cannot be changed")
        current = self.get(label)
        check_substrate_fields(fields.get("substrate_type", current.substrate_type),
                               fields.get("dimensions", current.dimensions))

        def change(record):
            for name, value in fields.items():
                setattr(record, name, value)

        return self._update(label, change)

    def next_experiment_label(self, label: str) -> str:
        """ Return the next free experiment label ``<substrate>-A``, ``-B``, … """

        used = {e["label"] for e in self.get(label).experiments if e.get("label")}
        index = 0
        while f"{label}-{experiment_letters(index)}" in used:
            index += 1
        return f"{label}-{experiment_letters(index)}"

    def experiment_folder(self, label: str, experiment_label: str, started: datetime.datetime) -> Path:
        """ Folder of a new experiment: ``<substrate>/<experiment label>_<YYYYMMDD-HHMM>``. """

        return self.folder(label) / f"{experiment_label}_{started:%Y%m%d-%H%M}"

    def register_experiment(self, label: str, entry: dict, *, replaces: Optional[str] = None) -> SubstrateRecord:
        """ Add an experiment to the index of a substrate.

        Parameters
        ----------
        label : str
            Substrate label.
        entry : dict
            ``uuid``, ``label``, ``path`` (relative to the substrate folder,
            or absolute if outside it), ``started``, ``objective``,
            ``status``, ``center_um``, ``double_corner_um``,
            ``double_corner_rotation_deg``, ``area_um`` (``[[x0, y0], [x1, y1]]``,
            the rectangle incl. corner markers and QR code) and
            ``resin_drop`` (index or None).
        replaces : str, optional
            ``plan_id`` of a planned entry (:meth:`plan_experiment`) that this
            entry takes the place of.

        Raises
        ------
        ValueError
            If the experiment label is used already.
        """

        def add(record):
            if any(e.get("label") == entry["label"] for e in record.experiments):
                raise ValueError(f"Experiment label {entry['label']} is used already on {label}")
            for index, existing in enumerate(record.experiments):
                if replaces is not None and existing.get("status") == STATUS_PLANNED \
                        and existing.get("plan_id") == replaces:
                    record.experiments[index] = {**dict(entry), "plan_id": replaces}
                    return
            record.experiments.append(dict(entry))

        return self._update(label, add)

    def plan_experiment(self, label: str, name: str, *, objective: str, area_um, resin_drop: Optional[int] = None,
                        center_um=None) -> str:
        """ Enter a planned experiment (no experiment file yet) into the index.

        A planned entry of the same name is replaced, so running a substrate
        main again does not add duplicates.

        Parameters
        ----------
        label : str
            Substrate label.
        name : str
            Experiment name in the substrate main (``ExperimentSpec.name``).
        objective : str
        area_um : ((x0, y0), (x1, y1))
            Rectangle the experiment will occupy, incl. markers.
        resin_drop : int, optional
            Index of its resin drop.
        center_um : (x, y), optional

        Returns
        -------
        str
            The ``plan_id`` to pass to :meth:`register_experiment` (``replaces``).
        """

        plan_id = f"planned:{name}"
        entry = {"uuid": "", "label": "", "name": name, "plan_id": plan_id, "status": STATUS_PLANNED,
                 "planned": utc_timestamp(), "objective": objective,
                 "area_um": [[float(v) for v in corner] for corner in area_um], "resin_drop": resin_drop,
                 "center_um": None if center_um is None else [float(v) for v in center_um]}

        def add(record):
            for index, existing in enumerate(record.experiments):
                if existing.get("status") == STATUS_PLANNED and existing.get("plan_id") == plan_id:
                    record.experiments[index] = entry
                    return
            record.experiments.append(entry)

        self._update(label, add)
        return plan_id

    def update_experiment(self, label: str, uuid: str, **fields) -> SubstrateRecord:
        """ Update fields (e.g. ``status``) of an experiment in the index. """

        def change(record):
            for entry in record.experiments:
                if entry.get("uuid") == uuid:
                    entry.update(fields)
                    return
            raise KeyError(f"Experiment {uuid} is not registered on substrate {label}")

        return self._update(label, change)

    def import_legacy(self, file: Path, user: str, user_initials: str, *, label: Optional[str] = None,
                      ) -> SubstrateRecord:
        """ Create a substrate from an old ``substrate_information.json`` (free dictionary).

        Known keys are not interpreted; the whole dictionary is kept in
        ``extra``, a ``name``/``Name`` key becomes the note.
        """

        data = json.loads(Path(file).read_text())
        name = data.get("name") or data.get("Name") or ""
        return self.create(user, user_initials, label=label, notes=str(name), extra=data)


def find_experiments(root: Path, *, substrate: Optional[str] = None, objective: Optional[str] = None,
                     since: Optional[str] = None, until: Optional[str] = None,
                     status: Optional[str] = None) -> list[dict]:
    """ Find experiments below a data root.

    Parameters
    ----------
    root : Path
        Data root.
    substrate : str, optional
        Substrate label or UUID.
    objective : str, optional
        Objective key, e.g. ``"Zeiss 63x"``.
    since, until : str, optional
        ISO dates or times; compared with the experiment start (inclusive).
    status : str, optional
        Experiment status, e.g. ``"finished"``.

    Returns
    -------
    list of dict
        Index entries with ``substrate_label``, ``substrate_uuid`` and the
        absolute ``folder`` added, sorted by start time. Planned entries
        (no experiment file yet) are only returned with ``status="planned"``.
    """

    store = SubstrateStore(root)
    found = []
    for label in store.labels():
        record = store.get(label)
        if substrate is not None and substrate not in (record.label, record.uuid):
            continue
        for entry in record.experiments:
            started = entry.get("started", "")
            if objective is not None and entry.get("objective") != objective:
                continue
            if since is not None and started < since:
                continue
            if until is not None and started[:len(until)] > until:
                continue
            if status is not None and entry.get("status") != status:
                continue
            if entry.get("status") == STATUS_PLANNED and status != STATUS_PLANNED:
                continue
            if "path" not in entry:
                found.append({**entry, "substrate_label": record.label, "substrate_uuid": record.uuid,
                              "folder": None})
                continue
            folder = Path(entry["path"])
            folder = folder if folder.is_absolute() else store.folder(label) / folder
            found.append({**entry, "substrate_label": record.label, "substrate_uuid": record.uuid,
                          "folder": str(folder)})
    return sorted(found, key=lambda e: e.get("started", ""))


def layout_area_um(layout, clearance_um: float) -> list[list[float]]:
    """ Area of an experiment from its stored layout: the rectangle, widened by ``clearance_um`` if it has markers.

    Parameters
    ----------
    layout : LayoutRecord
    clearance_um : float
        How far corner markers and QR code reach beyond the rectangle.

    Returns
    -------
    list
        ``[[x0, y0], [x1, y1]]`` in µm.
    """

    import numpy as np

    rectangle = np.asarray(layout.rectangle_um, dtype=float)
    clearance = clearance_um if layout.corners or layout.qrcode_um is not None else 0.0
    return [[float(v) for v in rectangle.min(axis=0) - clearance],
            [float(v) for v in rectangle.max(axis=0) + clearance]]


@dataclass
class ExperimentOverview:
    """ One experiment of a substrate as shown in an overview (T76).

    Parameters
    ----------
    name : str
        Experiment label (``HR-26-001-A``), or the planned name.
    status : str
        ``"planned"`` or the status of the experiment file (``created``,
        ``built``, ``printing``, ``finished``, ``aborted``, ``failed``).
    state : str
        ``"planned"``, ``"running"`` (created, built, printing), ``"done"``
        (finished) or ``"aborted"`` (aborted, failed).
    area_um : list, optional
        ``[[x0, y0], [x1, y1]]`` incl. markers, or None if unknown.
    resin_drop : int, optional
    uuid, objective, started : str
    folder : Path, optional
        Experiment folder, None for planned experiments.
    error : str
        Why the experiment file could not be read (status and area then come
        from the index), else ``""``.
    """

    name: str
    status: str
    state: str
    area_um: Optional[list] = None
    resin_drop: Optional[int] = None
    uuid: str = ""
    objective: str = ""
    started: str = ""
    folder: Optional[Path] = None
    error: str = ""


def substrate_overview(root: Path, substrate: str, *, refresh: bool = True,
                       qr_clearance_um: Optional[float] = None) -> list[ExperimentOverview]:
    """ All experiments of a substrate with status and area, in index order (T76).

    Parameters
    ----------
    root : Path
        Data root.
    substrate : str
        Substrate label or UUID.
    refresh : bool
        Read status and (if missing in the index) area from each experiment
        file, which is the truth; the index is only a cache. Unreadable
        files keep the index values and report ``error``.
    qr_clearance_um : float, optional
        Marker clearance for areas computed from a layout; default: half the
        QR code width of :mod:`nanofactorysystem.experiment`.

    Returns
    -------
    list of ExperimentOverview
        Planned experiments included, in the order of the index.
    """

    store = SubstrateStore(root)
    record = store.get(substrate)
    if qr_clearance_um is None:
        from ..experiment import QR_CODE_WIDTH_UM
        qr_clearance_um = QR_CODE_WIDTH_UM / 2
    overview = []
    for entry in record.experiments:
        status = entry.get("status", "")
        item = ExperimentOverview(name=entry.get("label") or entry.get("name", ""), status=status,
                                  state=STATES.get(status, "running"), area_um=entry.get("area_um"),
                                  resin_drop=entry.get("resin_drop"), uuid=entry.get("uuid", ""),
                                  objective=entry.get("objective", ""), started=entry.get("started", ""))
        if status != STATUS_PLANNED and "path" in entry:
            folder = Path(entry["path"])
            item.folder = folder if folder.is_absolute() else store.folder(record.label) / folder
            if refresh:
                from .experiment_store import ExperimentStore
                try:
                    stored = ExperimentStore.open(item.folder).read(include_captures=False)
                except (OSError, KeyError, ValueError) as error:
                    item.error = str(error)
                else:
                    item.status = stored.status
                    item.state = STATES.get(stored.status, "running")
                    if item.area_um is None and stored.layout is not None:
                        item.area_um = layout_area_um(stored.layout, qr_clearance_um)
        overview.append(item)
    return overview
