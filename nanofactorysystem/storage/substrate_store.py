##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Substrates, default data location and experiment index (docs/design/EXPERIMENT_STORAGE.md §3, §4, §8).

Layout below the data root of a user::

    <root>/<substrate label>/substrate.json
    <root>/<substrate label>/<experiment label>_<YYYYMMDD-HHMM>/experiment.h5
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
SUBSTRATE_SCHEMA_VERSION = "1.0"
DEFAULT_SYNC_FOLDER_NAMES = ("Seafile", "OneDrive", "Dropbox")


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
        Substrate and resin, e.g. ``{"substrate": "boro-silicate glass",
        "thickness_um": 700.0, "resin": "SZ2080", "resin_thickness_um": 75.0}``.
    resin_drops : list of dict
        Resin drops, each with ``edges_um`` (list of (x, y)) and ``added``.
    notes : str
        Free text.
    experiments : list of dict
        Index of the experiments on this substrate (see
        :meth:`SubstrateStore.register_experiment`).
    extra : dict
        Further information without a fixed field (e.g. keys of an old
        ``substrate_information.json``).
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

    def to_dict(self) -> dict:
        """ Return the content of ``substrate.json``. """

        return {"schema_version": SUBSTRATE_SCHEMA_VERSION, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "SubstrateRecord":
        """ Build a record from the content of ``substrate.json``. """

        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**fields)


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
               extra: Optional[dict] = None) -> SubstrateRecord:
        """ Create a substrate record.

        Parameters
        ----------
        user : str
            User key.
        user_initials : str
            Initials for the label (see :func:`initials`).
        label : str, optional
            Label; default: :meth:`next_label`.
        material, resin_drops, notes, extra
            See :class:`SubstrateRecord`.

        Returns
        -------
        SubstrateRecord

        Raises
        ------
        FileExistsError
            If a substrate with that label exists.
        """

        label = label or self.next_label(user_initials)
        if self._file(label).exists():
            raise FileExistsError(f"Substrate {label} exists already in {self.root}")
        record = SubstrateRecord(label=label, uuid=str(uuid_module.uuid4()), created=utc_timestamp(), user=user,
                                 material=dict(material or {}), resin_drops=list(resin_drops or []), notes=notes,
                                 extra=dict(extra or {}))
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

    def add_resin_drop(self, label: str, edges_um: list) -> SubstrateRecord:
        """ Record a resin drop with its edges (list of (x, y) in µm). """

        return self._update(label, lambda r: r.resin_drops.append(
            {"edges_um": [list(map(float, e)) for e in edges_um], "added": utc_timestamp()}))

    def next_experiment_label(self, label: str) -> str:
        """ Return the next free experiment label ``<substrate>-A``, ``-B``, … """

        used = {e["label"] for e in self.get(label).experiments}
        index = 0
        while f"{label}-{experiment_letters(index)}" in used:
            index += 1
        return f"{label}-{experiment_letters(index)}"

    def experiment_folder(self, label: str, experiment_label: str, started: datetime.datetime) -> Path:
        """ Folder of a new experiment: ``<substrate>/<experiment label>_<YYYYMMDD-HHMM>``. """

        return self.folder(label) / f"{experiment_label}_{started:%Y%m%d-%H%M}"

    def register_experiment(self, label: str, entry: dict) -> SubstrateRecord:
        """ Add an experiment to the index of a substrate.

        Parameters
        ----------
        label : str
            Substrate label.
        entry : dict
            ``uuid``, ``label``, ``path`` (relative to the substrate folder,
            or absolute if outside it), ``started``, ``objective``,
            ``status``, ``center_um``, ``double_corner_um``,
            ``double_corner_rotation_deg``.

        Raises
        ------
        ValueError
            If the experiment label is used already.
        """

        def add(record):
            if any(e["label"] == entry["label"] for e in record.experiments):
                raise ValueError(f"Experiment label {entry['label']} is used already on {label}")
            record.experiments.append(dict(entry))

        return self._update(label, add)

    def update_experiment(self, label: str, uuid: str, **fields) -> SubstrateRecord:
        """ Update fields (e.g. ``status``) of an experiment in the index. """

        def change(record):
            for entry in record.experiments:
                if entry["uuid"] == uuid:
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
        absolute ``folder`` added, sorted by start time.
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
            folder = Path(entry["path"])
            folder = folder if folder.is_absolute() else store.folder(label) / folder
            found.append({**entry, "substrate_label": record.label, "substrate_uuid": record.uuid,
                          "folder": str(folder)})
    return sorted(found, key=lambda e: e.get("started", ""))
