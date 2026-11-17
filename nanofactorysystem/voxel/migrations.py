##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Schema migrations of the voxel database (docs/design/VOXEL_DATABASE.md §3).

``MIGRATIONS[n]`` migrates a database from version ``n`` to ``n + 1``. The
version is kept in ``PRAGMA user_version``.
"""
import sqlite3


def migrate_0_to_1(connection: sqlite3.Connection) -> None:
    """ Create the tables ``material`` and ``voxel_measurement`` (schema version 1). """

    # Single statements: executescript() would commit the surrounding transaction
    _execute_all(connection, """
        CREATE TABLE material (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE,
            supplier    TEXT NOT NULL DEFAULT '',
            notes       TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE voxel_measurement (
            id              INTEGER PRIMARY KEY,
            material_id     INTEGER NOT NULL REFERENCES material(id),
            objective       TEXT NOT NULL,
            setup           TEXT NOT NULL CHECK (setup IN ('IFOV_off', 'IFOV_on')),
            power_mW        REAL NOT NULL CHECK (power_mW > 0),
            velocity_um_s   REAL NOT NULL CHECK (velocity_um_s > 0),
            width_um        REAL CHECK (width_um > 0),
            height_um       REAL CHECK (height_um > 0),
            width_std_um    REAL,
            height_std_um   REAL,
            n_lines         INTEGER NOT NULL DEFAULT 1 CHECK (n_lines > 0),
            method          TEXT NOT NULL,
            experiment_uuid TEXT NOT NULL DEFAULT '',
            date            TEXT NOT NULL,
            notes           TEXT NOT NULL DEFAULT '',
            source          TEXT NOT NULL DEFAULT '',
            CHECK (width_um IS NOT NULL OR height_um IS NOT NULL)
        );

        CREATE INDEX voxel_lookup ON voxel_measurement (material_id, objective, setup);
    """)


def migrate_1_to_2(connection: sqlite3.Connection) -> None:
    """ Add the material registry (schema version 2, docs/design/INFORMATION_MODEL.md §8).

    ``material`` gets ``kind`` (existing rows become resins) and ``created``;
    the new table ``material_property`` holds extensible properties with unit,
    wavelength, state and source.
    """

    _execute_all(connection, """
        ALTER TABLE material ADD COLUMN kind TEXT NOT NULL DEFAULT 'resin'
            CHECK (kind IN ('resin', 'substrate', 'medium'));

        ALTER TABLE material ADD COLUMN created TEXT NOT NULL DEFAULT '';

        CREATE TABLE material_property (
            id              INTEGER PRIMARY KEY,
            material_id     INTEGER NOT NULL REFERENCES material(id),
            key             TEXT NOT NULL CHECK (key <> ''),
            value_real      REAL,
            value_text      TEXT,
            unit            TEXT NOT NULL DEFAULT '',
            wavelength_nm   REAL CHECK (wavelength_nm IS NULL OR wavelength_nm > 0),
            state           TEXT NOT NULL DEFAULT 'any' CHECK (state IN ('uncured', 'cured', 'any')),
            temperature_c   REAL,
            uncertainty     REAL CHECK (uncertainty IS NULL OR uncertainty >= 0),
            source          TEXT NOT NULL DEFAULT '',
            date            TEXT NOT NULL,
            notes           TEXT NOT NULL DEFAULT '',
            CHECK (value_real IS NOT NULL OR value_text IS NOT NULL),
            CHECK (value_real IS NULL OR unit <> '')
        );

        CREATE INDEX material_property_lookup ON material_property (material_id, key);
    """)


def _execute_all(connection: sqlite3.Connection, script: str) -> None:
    for statement in script.split(";"):
        if statement.strip():
            connection.execute(statement)


MIGRATIONS = [migrate_0_to_1, migrate_1_to_2]
SCHEMA_VERSION = len(MIGRATIONS)


def migrate(connection: sqlite3.Connection) -> int:
    """ Bring a database to :data:`SCHEMA_VERSION` inside one transaction.

    Parameters
    ----------
    connection : sqlite3.Connection
        Connection in autocommit mode (``isolation_level=None``), so that
        the transaction is controlled here.

    Returns
    -------
    int
        The version the database had before.

    Raises
    ------
    RuntimeError
        If the database is newer than this code.
    """

    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"Voxel database has schema version {version}; this code knows up to {SCHEMA_VERSION}.")
    if version == SCHEMA_VERSION:
        return version
    try:
        connection.execute("BEGIN")
        for step in MIGRATIONS[version:]:
            step(connection)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    return version
