##########################################################################
# Copyright (c) 2026 Hannes Robben                                       #
# <hannes.robben@phoenixd.uni-hannover.de>                               #
# This program is free software under the terms of the MIT license.      #
##########################################################################
"""Material and voxel database: measured voxel sizes and their lookup (docs/design/VOXEL_DATABASE.md),
and the material registry (docs/design/INFORMATION_MODEL.md §3.1, §8)."""

from .database import CSV_COLUMNS, METHODS, SETUPS, VoxelDatabase, VoxelSize, default_path
from .materials import (KINDS, KNOWN_PROPERTY_KEYS, LEGACY_STATES, PHYSICAL_STATES, PROPERTY_CSV_COLUMNS,
                        REGISTRY_EXPORT_SCHEMA, ROLES, STATES, Material, MaterialProperty, MaterialRegistry,
                        MaterialSnapshot, MissingPropertyError, UnitWarning, as_material_dict, material_names,
                        normalize_state, unregistered_snapshot)
from .migrations import SCHEMA_VERSION
from .model import DatabaseVoxelModel, FixedVoxelModel, NoVoxelData
