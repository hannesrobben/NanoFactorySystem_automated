##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""SQLite database of measured voxel sizes (docs/design/VOXEL_DATABASE.md)."""
import csv
import datetime
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .interpolation import interpolate
from .migrations import migrate

SETUPS = ("IFOV_off", "IFOV_on")
METHODS = ("SEM", "AFM", "DHM", "optical", "ascending-scan", "other")
CSV_COLUMNS = ("material", "objective", "setup", "power_mW", "velocity_um_s", "width_um", "height_um",
               "width_std_um", "height_std_um", "n_lines", "method", "experiment_uuid", "date", "notes")
MEASUREMENT_COLUMNS = ("id", "material", "objective", "setup", "power_mW", "velocity_um_s", "width_um",
                       "height_um", "width_std_um", "height_std_um", "n_lines", "method", "experiment_uuid",
                       "date", "notes", "source")


@dataclass(frozen=True)
class VoxelSize:
    """ Voxel width and height for one set of printing parameters.

    Parameters
    ----------
    width_um, height_um : float or None
        Interpolated values; None if the quantity cannot be determined.
    width_method, height_method : str
        ``"exact"``, ``"interpolated-2d"``, ``"interpolated-dose"``, or ``""``
        if the value is None.
    n_points : int
        Largest number of distinct measured points used for one of the values.
    """

    width_um: Optional[float]
    height_um: Optional[float]
    width_method: str
    height_method: str
    n_points: int


def default_path() -> Path:
    """ Path of the voxel database: ``system.voxelDatabase`` of the configuration, else
    ``~/Documents/Femtika_Experiment/voxels.sqlite``.

    Raises
    ------
    SyncedFolderError
        If the path lies in a synchronised folder.
    """

    from ..config import sysConfig
    from ..storage.substrate_store import check_not_synced

    configured = sysConfig.section("system").get("voxelDatabase")
    path = Path(configured).expanduser() if configured else \
        Path.home() / "Documents" / "Femtika_Experiment" / "voxels.sqlite"
    check_not_synced(path.parent)
    return path


def _optional_float(text: str) -> Optional[float]:
    return float(text) if str(text).strip() != "" else None


class VoxelDatabase:
    """ Measured voxel sizes and their interpolation.

    Opening a database runs the pending schema migrations.

    Parameters
    ----------
    path : Path
        Database file; it is created if it does not exist.
    min_points : int
        Minimum number of distinct points for the 2-D interpolation.
    min_points_1d : int
        Minimum number of distinct doses for the 1-D dose fallback.
    """

    def __init__(self, path: Path, *, min_points: int = 3, min_points_1d: int = 2):
        self.path = Path(path)
        self.min_points = int(min_points)
        self.min_points_1d = int(min_points_1d)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys = ON")
        try:
            migrate(self.connection)
        except BaseException:
            self.connection.close()
            raise

    @classmethod
    def create(cls, path: Path, seed: Optional[Path] = None, **kwargs) -> "VoxelDatabase":
        """ Create a new database, optionally filled from a seed CSV file.

        Raises
        ------
        FileExistsError
            If the file exists already.
        """

        if Path(path).exists():
            raise FileExistsError(f"Voxel database exists already: {path}")
        database = cls(path, **kwargs)
        if seed is not None:
            database.import_csv(seed)
        return database

    @classmethod
    def default(cls, **kwargs) -> "VoxelDatabase":
        """ Open (or create) the database at :func:`default_path`. """

        return cls(default_path(), **kwargs)

    def close(self) -> None:
        """ Close the database connection. """

        self.connection.close()

    def __enter__(self) -> "VoxelDatabase":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def schema_version(self) -> int:
        """ ``PRAGMA user_version`` of the database. """

        return self.connection.execute("PRAGMA user_version").fetchone()[0]

    # ---------------------------------------------------------------- writing

    def add_material(self, name: str, supplier: str = "", notes: str = "") -> int:
        """ Add a material and return its id; an existing material keeps its data. """

        row = self.connection.execute("SELECT id FROM material WHERE name = ?", (name,)).fetchone()
        if row is not None:
            return row[0]
        return self.connection.execute("INSERT INTO material (name, supplier, notes) VALUES (?, ?, ?)",
                                       (name, supplier, notes)).lastrowid

    def materials(self) -> list[str]:
        """ Names of all materials. """

        return [row[0] for row in self.connection.execute("SELECT name FROM material ORDER BY name")]

    def add_measurement(self, material: str, objective: str, setup: str, power_mW: float, velocity_um_s: float,
                        *, width_um: Optional[float] = None, height_um: Optional[float] = None,
                        width_std_um: Optional[float] = None, height_std_um: Optional[float] = None,
                        n_lines: int = 1, method: str, experiment_uuid: str = "", date: Optional[str] = None,
                        notes: str = "", source: str = "") -> int:
        """ Add a measurement; an unknown material is created.

        Parameters
        ----------
        material, objective, setup : str
            Conditions (``setup``: ``"IFOV_off"`` or ``"IFOV_on"``).
        power_mW, velocity_um_s : float
            Laser power as set in the software, writing velocity.
        width_um, height_um : float, optional
            Measured size; at least one is required.
        width_std_um, height_std_um : float, optional
            Standard deviations over ``n_lines`` measured lines.
        n_lines : int
            Number of lines the values are averaged over (weight in the lookup).
        method : str
            One of ``METHODS``.
        experiment_uuid, date, notes, source : str
            Where the lines were printed, the measurement date (ISO; default
            today), free text and the origin (e.g. an imported file).

        Returns
        -------
        int
            Id of the measurement.

        Raises
        ------
        ValueError
            For an unknown method or setup, or if neither width nor height is given.
        """

        if method not in METHODS:
            raise ValueError(f"Unknown method {method!r}; use one of {METHODS}")
        if setup not in SETUPS:
            raise ValueError(f"Unknown setup {setup!r}; use one of {SETUPS}")
        if width_um is None and height_um is None:
            raise ValueError("A measurement needs a width or a height.")
        material_id = self.add_material(material)
        return self.connection.execute(
            "INSERT INTO voxel_measurement (material_id, objective, setup, power_mW, velocity_um_s, width_um, "
            "height_um, width_std_um, height_std_um, n_lines, method, experiment_uuid, date, notes, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (material_id, objective, setup, float(power_mW), float(velocity_um_s), width_um, height_um,
             width_std_um, height_std_um, int(n_lines), method, experiment_uuid,
             date or datetime.date.today().isoformat(), notes, source)).lastrowid

    def import_csv(self, path: Path) -> int:
        """ Import measurements from a CSV file with the columns ``CSV_COLUMNS``.

        The import runs in one transaction: an invalid row imports nothing.

        Returns
        -------
        int
            Number of imported rows.
        """

        path = Path(path)
        with open(path, newline="", encoding="utf-8") as fp:
            rows = list(csv.DictReader(fp))
        self.connection.execute("BEGIN")
        try:
            for row in rows:
                self.add_measurement(
                    row["material"], row["objective"], row["setup"], float(row["power_mW"]),
                    float(row["velocity_um_s"]), width_um=_optional_float(row.get("width_um", "")),
                    height_um=_optional_float(row.get("height_um", "")),
                    width_std_um=_optional_float(row.get("width_std_um", "")),
                    height_std_um=_optional_float(row.get("height_std_um", "")),
                    n_lines=int(row.get("n_lines") or 1), method=row["method"],
                    experiment_uuid=row.get("experiment_uuid", "") or "", date=row.get("date") or None,
                    notes=row.get("notes", "") or "", source=path.name)
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        return len(rows)

    def export_csv(self, path: Path) -> None:
        """ Write all measurements in the import format. """

        with open(path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in self.measurements():
                writer.writerow({column: "" if row[column] is None else row[column] for column in CSV_COLUMNS})

    # ---------------------------------------------------------------- reading

    def measurements(self, material: Optional[str] = None, objective: Optional[str] = None,
                     setup: Optional[str] = None) -> list[dict]:
        """ Measurements, optionally filtered, as dictionaries with the keys ``MEASUREMENT_COLUMNS``. """

        query = ("SELECT m.id, t.name, m.objective, m.setup, m.power_mW, m.velocity_um_s, m.width_um, m.height_um, "
                 "m.width_std_um, m.height_std_um, m.n_lines, m.method, m.experiment_uuid, m.date, m.notes, "
                 "m.source FROM voxel_measurement m JOIN material t ON t.id = m.material_id")
        conditions, values = [], []
        for column, value in (("t.name", material), ("m.objective", objective), ("m.setup", setup)):
            if value is not None:
                conditions.append(f"{column} = ?")
                values.append(value)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        return [dict(zip(MEASUREMENT_COLUMNS, row)) for row in self.connection.execute(query + " ORDER BY m.id",
                                                                                       values)]

    def voxel_size(self, material: str, objective: str, setup: str, power_mW: float,
                   velocity_um_s: float) -> Optional[VoxelSize]:
        """ Voxel width and height for a set of printing parameters (design §4).

        Returns
        -------
        VoxelSize or None
            None if neither width nor height can be determined (unknown
            material, no or too few measurements, outside the measured range).
        """

        rows = self.measurements(material, objective, setup)
        results = {}
        for quantity in ("width_um", "height_um"):
            points = [r for r in rows if r[quantity] is not None]
            results[quantity] = interpolate(
                [r["power_mW"] for r in points], [r["velocity_um_s"] for r in points],
                [r[quantity] for r in points], [r["n_lines"] for r in points], float(power_mW),
                float(velocity_um_s), min_points=self.min_points, min_points_1d=self.min_points_1d)
        (width, width_method, n_width), (height, height_method, n_height) = results["width_um"], results["height_um"]
        if width is None and height is None:
            return None
        return VoxelSize(width_um=width, height_um=height, width_method=width_method, height_method=height_method,
                         n_points=max(n_width, n_height))
