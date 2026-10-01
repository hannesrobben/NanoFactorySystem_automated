# Design: Voxel database

Status: approved 2026-09-30

Approved by the maintainer on 2026-09-30 in the Claude Code session, with every proposal in §9
accepted as written.
Date: 2026-09-30. Todo: T53. Used by: T54 (voxel-aware slicing), later F7 (printing strategies).

## 1. Goals and non-goals

**Goals**
- Store measured voxel sizes (width and height of a written line) together with the conditions they were
  measured under: material, objective, setup (IFOV on/off), laser power and writing velocity, plus how and
  where they were measured.
- Answer "which voxel width and height do I get for this material, objective, setup, power and velocity?"
  with interpolation between measured points, but never outside the measured range.
- Keep the database file outside git; keep a small seed file (CSV) in git from which a database can be built.
- Evolve the schema with numbered migrations that run when the database is opened.

**Non-goals**
- Physical models of the voxel shape (threshold models, proximity effects). The interpolation is purely
  empirical.
- Automatic measurement of voxels (e.g. from DHM data). Measurements are entered by hand or imported from CSV.
- Using the data in the slicer. That is T54, which gets the query interface defined here (§6).

## 2. Terms and units

| Term | Meaning | Unit |
|---|---|---|
| width | Lateral line width of a single written line (full width, as measured) | µm |
| height | Axial extent of a single written line | µm |
| power | Laser power as set in the software, i.e. the value converted by the attenuator calibration (the same number as in `Experiment.add_structure(power=...)` and in `IFOV_Lines`) | mW |
| velocity | Writing velocity of the line | µm/s |
| dose | Two-photon dose variable `P² / v` (power squared over velocity); the interpolation works with `ln(dose)` | mW²·s/µm |
| setup | `"IFOV_off"` or `"IFOV_on"` (the setups of `aerobasic/programs/setups.py`) | – |
| objective | Objective key of the configuration, e.g. `"Zeiss 63x"` | – |

A measurement can have a width without a height (e.g. SEM top view); both are optional, but at least one is
required.

## 3. Schema (version 1)

SQLite, schema version in `PRAGMA user_version`.

```sql
CREATE TABLE material (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,          -- e.g. "SZ2080"
    supplier    TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE voxel_measurement (
    id              INTEGER PRIMARY KEY,
    material_id     INTEGER NOT NULL REFERENCES material(id),
    objective       TEXT NOT NULL,             -- objective key, e.g. "Zeiss 63x"
    setup           TEXT NOT NULL CHECK (setup IN ('IFOV_off', 'IFOV_on')),
    power_mW        REAL NOT NULL CHECK (power_mW > 0),
    velocity_um_s   REAL NOT NULL CHECK (velocity_um_s > 0),
    width_um        REAL CHECK (width_um > 0),
    height_um       REAL CHECK (height_um > 0),
    width_std_um    REAL,                      -- standard deviation, if several lines were measured
    height_std_um   REAL,
    n_lines         INTEGER NOT NULL DEFAULT 1,
    method          TEXT NOT NULL,             -- 'SEM', 'AFM', 'DHM', 'optical', 'ascending-scan', 'other'
    experiment_uuid TEXT NOT NULL DEFAULT '',  -- experiment the lines were printed in (T47)
    date            TEXT NOT NULL,             -- ISO date of the measurement
    notes           TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT '',  -- e.g. the imported CSV file
    CHECK (width_um IS NOT NULL OR height_um IS NOT NULL)
);

CREATE INDEX voxel_lookup ON voxel_measurement (material_id, objective, setup);
```

The columns required by T53 are all present; `width_std_um`, `height_std_um`, `n_lines` and `source` are
additions that cost nothing and let averaged measurements keep their spread.

**Migrations.** `voxel/migrations.py` holds an ordered list `MIGRATIONS = [migrate_0_to_1, …]`. Opening a
database runs, inside one transaction, every migration from `PRAGMA user_version` up to the newest and then
sets `user_version`. A database with a newer version than the code knows is refused.

## 4. Lookup and interpolation

A query `voxel_size(material, objective, setup, power_mW, velocity_um_s)` uses only the measurements with the
same material, objective and setup. Width and height are interpolated independently, each only from the
measurements that have that quantity.

1. **Exact hit.** If measurements exist at the same power and velocity (relative tolerance 1e-6), the result
   is their mean (weighted by `n_lines`), `method = "exact"`.
2. **2-D interpolation** (proposal, §9 V1). Points in the plane `(ln P, ln v)`. If there are at least
   `min_points` (default 3) points that are not collinear, and the query lies inside their convex hull, the
   value is interpolated linearly on the Delaunay triangulation (`scipy.interpolate.LinearNDInterpolator`),
   `method = "interpolated-2d"`.
3. **1-D fallback over the dose.** If the points are collinear in that plane (e.g. a pure power series at one
   velocity, or a line of constant dose), the value is interpolated linearly over `ln(P²/v)` between the two
   neighbouring measured doses. This needs at least `min_points_1d` (default 2) distinct doses, and the query
   dose must lie within the measured dose range; `method = "interpolated-dose"`.
   It is only used if the query lies on the measured line (distance to the fitted line in `(ln P, ln v)` below
   a tolerance), because otherwise the dose would be used to extrapolate across power or velocity.
4. **Otherwise `None`** (unknown material, no measurements for the combination, too few points, or outside
   the measured range). There is no extrapolation.

Duplicates (same P and v) are averaged before interpolating. The result carries the number of points used and
the method, so that the slicer (T54) and the metadata (T54: "the values used are stored") can record where a
value came from.

## 5. Seed file, CSV import and location

- **CSV format** (header row, comma-separated, UTF-8):
  `material,objective,setup,power_mW,velocity_um_s,width_um,height_um,width_std_um,height_std_um,n_lines,method,experiment_uuid,date,notes`.
  Empty cells are NULL; unknown materials are created on import.
- **Seed file:** `config/voxel_seed.csv` in git (initially only the header, see §9 V3). `VoxelDatabase.create(path,
  seed=...)` builds a new database from it.
- **Database file:** not in git (`*.sqlite` in `.gitignore`). Its path is configured in `nanofactory.json` as
  `system.voxelDatabase`; without it, `~/Documents/Femtika_Experiment/voxels.sqlite` is used (next to the user
  data roots of T48, not in a synchronised folder, same check as `storage.substrate_store.check_not_synced`).
- **Export:** `export_csv()` writes all measurements in the import format, e.g. for backups or for sharing.

## 6. API sketch

New package `nanofactorysystem/voxel/`:

```python
@dataclass(frozen=True)
class VoxelSize:
    width_um: float | None
    height_um: float | None
    width_method: str          # "exact", "interpolated-2d", "interpolated-dose" or "" if None
    height_method: str
    n_points: int              # measurements used

class VoxelDatabase:
    def __init__(self, path: Path, *, min_points: int = 3, min_points_1d: int = 2): ...  # opens, migrates
    @classmethod
    def create(cls, path: Path, seed: Path | None = None) -> "VoxelDatabase": ...
    @classmethod
    def default(cls) -> "VoxelDatabase": ...                                   # configured path
    def close(self) -> None: ...                                               # also context manager

    def add_material(self, name: str, supplier: str = "", notes: str = "") -> int: ...
    def materials(self) -> list[str]: ...
    def add_measurement(self, material: str, objective: str, setup: str, power_mW: float,
                        velocity_um_s: float, *, width_um=None, height_um=None, width_std_um=None,
                        height_std_um=None, n_lines=1, method: str, experiment_uuid="", date=None,
                        notes="", source="") -> int: ...
    def import_csv(self, path: Path) -> int: ...                               # returns rows imported
    def export_csv(self, path: Path) -> None: ...
    def measurements(self, material=None, objective=None, setup=None) -> list[dict]: ...
    def voxel_size(self, material: str, objective: str, setup: str, power_mW: float,
                   velocity_um_s: float) -> VoxelSize | None: ...
```

`voxel_size` returns `None` when neither width nor height can be determined; a `VoxelSize` may still have one
of them as `None`. T54 builds its `VoxelModel` interface on top of this (a database-backed model and a
"no data" model).

## 7. Tests (synthetic data)

- Schema: a new database has `user_version = 1`; a migration from version 0 runs; a newer version is refused;
  constraints reject a measurement without width and height, and non-positive values.
- Exact hit, including averaging of duplicates weighted by `n_lines`.
- 2-D interpolation inside the hull reproduces a linear function of `(ln P, ln v)` exactly.
- Outside the convex hull → `None`; unknown material → `None`; too few points → `None`.
- 1-D dose fallback for a pure power series; a query off the measured line → `None`.
- CSV import and export round trip; unknown materials are created on import.
- Width and height with different point sets (e.g. heights only at some points).

## 8. Relation to the slicer (T54)

- `JobParameters.voxel_size_um` and `SlicingParameters.contour_offset_um` already exist in
  `aerobasic/slicer/parameters.py`. T54 fills them from a `VoxelSize` (offset = half the width, first and last
  slice shifted by half the height) and stores the values and their `method` in the experiment metadata.
- Without data (`None`) the slicer keeps today's behaviour exactly (golden files unchanged).

## 9. Decisions

All proposals below were accepted by the maintainer on 2026-09-30 (V2: the calibration file is not
recorded; V3: the seed file starts with the header only).


- **V1 – Interpolation variable.** Proposal: 2-D linear interpolation in `(ln P, ln v)` inside the convex hull,
  with a 1-D fallback over `ln(P²/v)` only for collinear data (§4). Alternative: always 1-D over the dose
  (simpler, assumes that only `P²/v` matters).
- **V2 – Power reference.** Proposal: the power as set in the software (attenuator-calibrated mW, the value in
  the programs). Should the database also record which calibration file was active?
- **V3 – Seed data.** Proposal: the seed CSV starts with the header only. Do you have existing voxel
  measurements (e.g. from the DHM paper or SEM) that should go into it?
- **V4 – Location.** Proposal: one database per lab PC at `system.voxelDatabase` (default
  `~/Documents/Femtika_Experiment/voxels.sqlite`). Alternative: per user, or a network share (SQLite on a
  network share is risky with concurrent writers).
- **V5 – Minimum points.** Proposal: `min_points = 3` for 2-D and `min_points_1d = 2` for the dose fallback,
  configurable per call. Are these sensible for your data density?

## 10. Approval

Approved by the maintainer on 2026-09-30 (all proposals in §9 accepted); recorded in the status line
at the top.
