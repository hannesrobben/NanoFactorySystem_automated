##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Voxel models for voxel-aware slicing (T54).

A voxel model returns the voxel width and height for laser parameters; it
implements the protocol ``aerobasic.slicer.voxel.VoxelModel``.
"""
from pathlib import Path
from typing import Any, Optional

from .database import VoxelDatabase, VoxelSize


class NoVoxelData:
    """ Model without data: the slicer keeps its behaviour without voxel compensation. """

    def voxel_size(self, power_mw: float, velocity_um_s: float) -> Optional[VoxelSize]:
        """ Always None. """

        return None

    def describe(self) -> dict[str, Any]:
        """ Description for the metadata. """

        return {"type": "none"}


class FixedVoxelModel:
    """ One voxel size for all laser parameters (a manual estimate, or tests).

    Parameters
    ----------
    width_um, height_um : float or None
        Voxel width and height in µm.
    """

    def __init__(self, width_um: Optional[float], height_um: Optional[float]):
        if width_um is None and height_um is None:
            raise ValueError("A fixed voxel model needs a width or a height.")
        self.width_um = width_um
        self.height_um = height_um

    def voxel_size(self, power_mw: float, velocity_um_s: float) -> VoxelSize:
        """ The fixed size, independent of the laser parameters. """

        return VoxelSize(self.width_um, self.height_um, "fixed" if self.width_um is not None else "",
                         "fixed" if self.height_um is not None else "", 0)

    def describe(self) -> dict[str, Any]:
        """ Description for the metadata. """

        return {"type": "fixed", "width_um": self.width_um, "height_um": self.height_um}


class DatabaseVoxelModel:
    """ Measured voxel sizes of one material, objective and setup from the voxel database (T53).

    Parameters
    ----------
    material, objective, setup : str
        Conditions of the print (``setup``: ``"IFOV_off"`` or ``"IFOV_on"``).
    database : VoxelDatabase or Path, optional
        The database; default: :meth:`VoxelDatabase.default`. A path is
        opened for each query and closed again.
    """

    def __init__(self, material: str, objective: str, setup: str, database: VoxelDatabase | Path | None = None):
        self.material = material
        self.objective = objective
        self.setup = setup
        self.database = database

    def voxel_size(self, power_mw: float, velocity_um_s: float) -> Optional[VoxelSize]:
        """ Interpolated voxel size (see :meth:`VoxelDatabase.voxel_size`), or None without data. """

        if isinstance(self.database, VoxelDatabase):
            return self.database.voxel_size(self.material, self.objective, self.setup, power_mw, velocity_um_s)
        with (VoxelDatabase(self.database) if self.database is not None else VoxelDatabase.default()) as database:
            return database.voxel_size(self.material, self.objective, self.setup, power_mw, velocity_um_s)

    def describe(self) -> dict[str, Any]:
        """ Description for the metadata (the database path, not its content). """

        path = self.database.path if isinstance(self.database, VoxelDatabase) else self.database
        return {"type": "database", "material": self.material, "objective": self.objective, "setup": self.setup,
                "database": str(path) if path is not None else "default"}
