##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Material registry: photoresists, substrate materials and media with extensible properties.

The registry lives in the voxel database (schema version 2, decision M1 of
docs/design/INFORMATION_MODEL.md): the table ``material`` is shared with the
voxel measurements, ``material_property`` holds one row per property value.
New property keys need no code change; :data:`KNOWN_PROPERTY_KEYS` only
warns when a common key is entered with an unexpected unit.

An experiment stores a :class:`MaterialSnapshot` of every material it uses,
so later changes in the registry never change a stored experiment (G7).
"""
import csv
import datetime
import math
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from .database import VoxelDatabase, default_path

KINDS = ("resin", "substrate", "medium")
STATES = ("uncured", "cured", "any")
ROLES = ("resin", "substrate", "medium")
SNAPSHOT_SCHEMA = "nanofactory.material_snapshot/1"

# Expected units of common property keys; a different unit only gives a warning
KNOWN_PROPERTY_KEYS = {
    "refractive_index": "1",
    "density": "g/cm3",
    "shrinkage": "%",
    "viscosity": "mPa s",
    "abbe_number": "1",
}

PROPERTY_CSV_COLUMNS = ("material", "kind", "supplier", "key", "value", "unit", "wavelength_nm", "state",
                        "temperature_c", "uncertainty", "source", "date", "notes")


class UnitWarning(UserWarning):
    """ A known property key was entered with an unexpected unit. """


@dataclass(frozen=True)
class MaterialProperty:
    """ One property value of a material.

    Parameters
    ----------
    key : str
        Property name, e.g. ``"refractive_index"``; any non-empty text.
    value : float or str
        Number in ``unit``, or text for non-numeric facts.
    unit : str
        Unit of a numeric value (``"1"`` for dimensionless); may be empty
        for text values.
    wavelength_nm : float, optional
        Wavelength of an optical property.
    state : {"uncured", "cured", "any"}
        Liquid resin, polymerised resin, or independent of it.
    temperature_c, uncertainty : float, optional
        Temperature and uncertainty (same unit as the value).
    source : str
        Data sheet, publication (DOI) or own measurement (experiment UUID).
    date : str
        When the value was determined or entered (ISO 8601).
    notes : str
        Free text.
    """

    key: str
    value: Union[float, str]
    unit: str = ""
    wavelength_nm: Optional[float] = None
    state: str = "any"
    temperature_c: Optional[float] = None
    uncertainty: Optional[float] = None
    source: str = ""
    date: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        """ Return the property as JSON-compatible dictionary. """

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialProperty":
        """ Build a property from :meth:`to_dict` output. """

        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass(frozen=True)
class Material:
    """ A material of the registry with its properties.

    Parameters
    ----------
    name : str
        Unique registry name, e.g. ``"SZ2080"``.
    kind : {"resin", "substrate", "medium"}
        What the material is used as.
    supplier, notes, created : str
        Free information; ``created`` is the time the entry was made.
    properties : tuple of MaterialProperty
        All property values, oldest first.
    """

    name: str
    kind: str = "resin"
    supplier: str = ""
    notes: str = ""
    created: str = ""
    properties: tuple[MaterialProperty, ...] = ()

    def property(self, key: str, *, wavelength_nm: Optional[float] = None,
                 state: Optional[str] = None) -> Optional[MaterialProperty]:
        """ Return the matching property value, or None.

        Parameters
        ----------
        key : str
            Property name.
        wavelength_nm : float, optional
            Required wavelength; it must match exactly (no interpolation).
        state : {"uncured", "cured", "any"}, optional
            Required state; values stored with state ``"any"`` match every
            state, an exact match is preferred.

        Returns
        -------
        MaterialProperty or None
            Among several matches the most recent ``date`` wins (then the
            most recently entered).
        """

        candidates = []
        for order, item in enumerate(self.properties):
            if item.key != key:
                continue
            if wavelength_nm is not None and (item.wavelength_nm is None
                                              or not math.isclose(item.wavelength_nm, wavelength_nm)):
                continue
            if state is not None and item.state not in (state, "any"):
                continue
            exact_state = state is None or item.state == state
            candidates.append((exact_state, item.date, order, item))
        if not candidates:
            return None
        return max(candidates, key=lambda c: c[:3])[3]

    def refractive_index(self, wavelength_nm: Optional[float] = None,
                         state: Optional[str] = None) -> Optional[float]:
        """ Refractive index for a wavelength and state, or None (see :meth:`property`). """

        item = self.property("refractive_index", wavelength_nm=wavelength_nm, state=state)
        return None if item is None or isinstance(item.value, str) else float(item.value)

    def to_dict(self) -> dict:
        """ Return the material as JSON-compatible dictionary. """

        data = asdict(self)
        data["properties"] = [p.to_dict() for p in self.properties]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        """ Build a material from :meth:`to_dict` output. """

        values = {k: data[k] for k in ("name", "kind", "supplier", "notes", "created") if k in data}
        return cls(**values, properties=tuple(MaterialProperty.from_dict(p) for p in data.get("properties", [])))


@dataclass
class MaterialSnapshot:
    """ Copy of a material as used by one experiment.

    Parameters
    ----------
    role : {"resin", "substrate", "medium"}
        What the material is used as in the experiment.
    name : str
        Material name as given (registry name or free text).
    known : bool
        True if the registry had an entry; then ``material`` holds it.
    material : Material, optional
        The registry entry at the time of the snapshot.
    batch : str
        Batch / lot of the material (it belongs to the use, not the material).
    name_source : str
        Where the name came from (``"argument"``, ``"substrate"``, ``"sys_args"``).
    registry_file : str
        Database file the snapshot was taken from (empty without registry).
    registry_schema_version : int
        Schema version of that database (0 without registry).
    taken : str
        Time of the snapshot (ISO 8601, UTC).
    schema : str
        :data:`SNAPSHOT_SCHEMA`.
    """

    role: str
    name: str
    known: bool = False
    material: Optional[Material] = None
    batch: str = ""
    name_source: str = ""
    registry_file: str = ""
    registry_schema_version: int = 0
    taken: str = field(default_factory=lambda: _utc_now())
    schema: str = SNAPSHOT_SCHEMA

    def refractive_index(self, wavelength_nm: Optional[float] = None,
                         state: Optional[str] = None) -> Optional[float]:
        """ Refractive index from the snapshot, or None if unknown.

        Which index is the ``n_medium`` of a DHM result (liquid resin, cured
        resin, developed structure) is decision G4; the snapshot carries all
        stored values so that the decision does not change stored data.
        """

        return None if self.material is None else self.material.refractive_index(wavelength_nm, state)

    def to_dict(self) -> dict:
        """ Return the snapshot as JSON-compatible dictionary. """

        data = asdict(self)
        data["material"] = None if self.material is None else self.material.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialSnapshot":
        """ Build a snapshot from :meth:`to_dict` output. """

        values = {k: data[k] for k in cls.__dataclass_fields__ if k in data and k != "material"}
        material = data.get("material")
        return cls(**values, material=None if material is None else Material.from_dict(material))


def _utc_now() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _optional_float(text) -> Optional[float]:
    return None if text is None or str(text).strip() == "" else float(text)


class MaterialRegistry:
    """ Materials and their properties in the voxel database.

    Parameters
    ----------
    database : VoxelDatabase or Path
        Open database, or a file that is opened (and created if missing).
    """

    def __init__(self, database: Union[VoxelDatabase, Path, str]):
        self._owns_database = not isinstance(database, VoxelDatabase)
        self.database = VoxelDatabase(Path(database)) if self._owns_database else database
        self.connection = self.database.connection

    @classmethod
    def open_existing(cls, path: Optional[Path] = None) -> Optional["MaterialRegistry"]:
        """ Open the registry only if its file exists (never create one).

        Parameters
        ----------
        path : Path, optional
            Database file; default: :func:`~nanofactorysystem.voxel.default_path`.

        Returns
        -------
        MaterialRegistry or None
            None if the file does not exist.
        """

        path = Path(path) if path is not None else default_path()
        return cls(path) if path.exists() else None

    def close(self) -> None:
        """ Close the database if the registry opened it. """

        if self._owns_database:
            self.database.close()

    def __enter__(self) -> "MaterialRegistry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------------------------------------------------------------- writing

    def add_material(self, name: str, kind: str = "resin", supplier: str = "", notes: str = "") -> Material:
        """ Add a material; an existing material keeps its data.

        Raises
        ------
        ValueError
            For an unknown kind, or if the material exists with another kind.
        """

        if kind not in KINDS:
            raise ValueError(f"Unknown material kind {kind!r}; use one of {KINDS}")
        row = self.connection.execute("SELECT kind FROM material WHERE name = ?", (name,)).fetchone()
        if row is None:
            self.connection.execute("INSERT INTO material (name, supplier, notes, kind, created) VALUES (?, ?, ?, ?, ?)",
                                    (name, supplier, notes, kind, _utc_now()))
        elif row[0] != kind:
            raise ValueError(f"Material {name!r} exists as {row[0]!r}, not as {kind!r}")
        return self.material(name)

    def add_property(self, material: str, key: str, value: Union[float, str], unit: str = "", *,
                     wavelength_nm: Optional[float] = None, state: str = "any",
                     temperature_c: Optional[float] = None, uncertainty: Optional[float] = None,
                     source: str = "", date: Optional[str] = None, notes: str = "") -> int:
        """ Add a property value to a material and return its id.

        Parameters
        ----------
        material : str
            Registry name.
        key : str
            Property name; new keys are accepted without code change.
        value : float or str
            Numeric value (needs ``unit``) or text.
        unit : str
            Unit of a numeric value; ``"1"`` for dimensionless values.
        wavelength_nm, state, temperature_c, uncertainty, source, date, notes
            See :class:`MaterialProperty`; ``date`` defaults to today.

        Raises
        ------
        KeyError
            If the material is not in the registry.
        ValueError
            For an empty key, an unknown state, or a number without unit.
        """

        if not key:
            raise ValueError("A property needs a key.")
        if state not in STATES:
            raise ValueError(f"Unknown state {state!r}; use one of {STATES}")
        numeric = not isinstance(value, str)
        if numeric and not unit:
            raise ValueError(f"Property {key!r} of {material!r}: a numeric value needs a unit ('1' if dimensionless).")
        expected = KNOWN_PROPERTY_KEYS.get(key)
        if expected is not None and unit and unit != expected:
            warnings.warn(f"Property {key!r} of {material!r} entered in {unit!r}; usually {expected!r}.",
                          UnitWarning, stacklevel=2)
        material_id = self._material_id(material)
        return self.connection.execute(
            "INSERT INTO material_property (material_id, key, value_real, value_text, unit, wavelength_nm, state, "
            "temperature_c, uncertainty, source, date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (material_id, key, float(value) if numeric else None, None if numeric else str(value), unit,
             _optional_float(wavelength_nm), state, _optional_float(temperature_c), _optional_float(uncertainty),
             source, date or datetime.date.today().isoformat(), notes)).lastrowid

    def import_csv(self, path: Path) -> int:
        """ Import materials and property values from a CSV file (:data:`PROPERTY_CSV_COLUMNS`).

        A row with an empty ``key`` only adds the material. ``source`` is
        kept as written (it names the origin of the value, not the file).
        The import runs in one transaction: an invalid row imports nothing.

        Returns
        -------
        int
            Number of imported property values.
        """

        path = Path(path)
        with open(path, newline="", encoding="utf-8") as fp:
            rows = list(csv.DictReader(fp))
        count = 0
        self.connection.execute("BEGIN")
        try:
            for row in rows:
                self.add_material(row["material"], row.get("kind") or "resin", row.get("supplier", "") or "")
                if not row.get("key"):
                    continue
                text = row.get("value", "")
                try:
                    value: Union[float, str] = float(text)
                except ValueError:
                    value = text
                self.add_property(row["material"], row["key"], value, row.get("unit", "") or "",
                                  wavelength_nm=_optional_float(row.get("wavelength_nm")),
                                  state=row.get("state") or "any",
                                  temperature_c=_optional_float(row.get("temperature_c")),
                                  uncertainty=_optional_float(row.get("uncertainty")),
                                  source=row.get("source", "") or "", date=row.get("date") or None,
                                  notes=row.get("notes", "") or "")
                count += 1
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        return count

    def export_csv(self, path: Path) -> None:
        """ Write all materials and property values in the import format. """

        with open(path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=PROPERTY_CSV_COLUMNS)
            writer.writeheader()
            for name in self.materials():
                material = self.material(name)
                base = {"material": material.name, "kind": material.kind, "supplier": material.supplier}
                if not material.properties:
                    writer.writerow(base)
                for item in material.properties:
                    row = dict(base, **{k: v for k, v in item.to_dict().items()})
                    writer.writerow({k: "" if row.get(k) is None else row.get(k, "") for k in PROPERTY_CSV_COLUMNS})

    # ---------------------------------------------------------------- reading

    def _material_id(self, name: str) -> int:
        row = self.connection.execute("SELECT id FROM material WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(f"Material {name!r} is not in the registry")
        return row[0]

    def materials(self, kind: Optional[str] = None) -> list[str]:
        """ Names of all materials, optionally of one kind. """

        if kind is None:
            rows = self.connection.execute("SELECT name FROM material ORDER BY name")
        else:
            rows = self.connection.execute("SELECT name FROM material WHERE kind = ? ORDER BY name", (kind,))
        return [row[0] for row in rows]

    def material(self, name: str) -> Material:
        """ Return a material with all its properties.

        Raises
        ------
        KeyError
            If the material is not in the registry.
        """

        row = self.connection.execute("SELECT id, name, kind, supplier, notes, created FROM material WHERE name = ?",
                                      (name,)).fetchone()
        if row is None:
            raise KeyError(f"Material {name!r} is not in the registry")
        material_id, name, kind, supplier, notes, created = row
        properties = tuple(
            MaterialProperty(key=key, value=value_real if value_real is not None else value_text, unit=unit,
                             wavelength_nm=wavelength_nm, state=state, temperature_c=temperature_c,
                             uncertainty=uncertainty, source=source, date=date, notes=notes)
            for key, value_real, value_text, unit, wavelength_nm, state, temperature_c, uncertainty, source, date, notes
            in self.connection.execute(
                "SELECT key, value_real, value_text, unit, wavelength_nm, state, temperature_c, uncertainty, source, "
                "date, notes FROM material_property WHERE material_id = ? ORDER BY id", (material_id,)))
        return Material(name=name, kind=kind, supplier=supplier, notes=notes, created=created, properties=properties)

    def get(self, name: str) -> Optional[Material]:
        """ Return a material, or None if it is not in the registry. """

        try:
            return self.material(name)
        except KeyError:
            return None

    def snapshot(self, name: str, role: str, *, batch: str = "", name_source: str = "") -> MaterialSnapshot:
        """ Copy a material for an experiment (unknown names give ``known = False``).

        Raises
        ------
        ValueError
            For an unknown role.
        """

        if role not in ROLES:
            raise ValueError(f"Unknown material role {role!r}; use one of {ROLES}")
        material = self.get(name)
        return MaterialSnapshot(role=role, name=name, known=material is not None, material=material, batch=batch,
                                name_source=name_source, registry_file=str(self.database.path),
                                registry_schema_version=self.database.schema_version)


def unregistered_snapshot(name: str, role: str, *, batch: str = "", name_source: str = "") -> MaterialSnapshot:
    """ Snapshot of a material name when no registry is available. """

    if role not in ROLES:
        raise ValueError(f"Unknown material role {role!r}; use one of {ROLES}")
    return MaterialSnapshot(role=role, name=name, batch=batch, name_source=name_source)


def material_names(*, materials: Optional[dict] = None, substrate_material: Optional[dict] = None,
                   sample: Optional[dict] = None) -> dict[str, tuple[str, str, str]]:
    """ Material name, batch and source per role, from the strongest source that names it.

    Order (weakest first): ``sys_args["sample"]`` (``material`` → resin,
    ``substrate`` → substrate), the substrate record's material dictionary
    (``resin``, ``substrate``, ``medium``, ``batch`` for the resin), the
    experiment's ``materials`` argument.

    Returns
    -------
    dict
        ``{role: (name, batch, source)}`` for every role that has a name.
    """

    result: dict[str, tuple[str, str, str]] = {}
    sample = sample or {}
    for role, key in (("resin", "material"), ("substrate", "substrate")):
        if sample.get(key):
            result[role] = (str(sample[key]), "", "sys_args")
    substrate_material = substrate_material or {}
    for role in ROLES:
        if substrate_material.get(role):
            batch = str(substrate_material.get("batch", "")) if role == "resin" else ""
            result[role] = (str(substrate_material[role]), batch, "substrate")
    for role, value in (materials or {}).items():
        if role not in ROLES:
            raise ValueError(f"Unknown material role {role!r}; use one of {ROLES}")
        if value:
            batch = result.get(role, ("", "", ""))[1]
            result[role] = (str(value), batch, "argument")
    return result


def as_material_dict(material: Any) -> dict:
    """ Normalise ``SubstrateSpec.material``: a registry name means the resin.

    Parameters
    ----------
    material : str, dict or None
        A registry name of the resin, or the free dictionary of older mains.

    Returns
    -------
    dict
        ``{"resin": name}`` for a name, a copy of a dictionary, ``{}`` for None.
    """

    if material is None:
        return {}
    if isinstance(material, str):
        return {"resin": material}
    if isinstance(material, dict):
        return dict(material)
    raise TypeError(f"material must be a registry name or a dictionary, not {type(material).__name__}")
